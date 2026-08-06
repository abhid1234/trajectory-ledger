from __future__ import annotations

import base64
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from trajectory_ledger.analysis import INVARIANTS, evaluate
from trajectory_ledger.cli import run_fixture
from trajectory_ledger.core import RECORD_TYPES, Limits, ValidationError, build_lineage, digest, ingest_fixture, make_envelope, verify_ledger, write_ledger
from trajectory_ledger.patching import apply_patch, build_patch, reverse_patch, validate_patch
from trajectory_ledger.replay import prove_isolation, replay, sandbox_available
from trajectory_ledger.report import BANNED, render_json, render_text, report_document

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


class Phase1aTests(unittest.TestCase):
    def test_fixture_families_and_exact_invariants(self):
        expected = {
            "clean.json": set(),
            "conflicting_parent.json": {"parent_edge_nonconflicting"},
            "mandatory_abstain.json": set(),
            "missing_lineage.json": {"parent_referent_present"},
            "stale_memory_read.json": {"memory_read_not_stale"},
            "tainted_memory_reuse.json": {"tainted_memory_not_reused_unquarantined"},
            "tainted_trailing_quarantine.json": {"tainted_memory_not_reused_unquarantined"},
        }
        for name, violated in expected.items():
            records = ingest_fixture(name, FIXTURES)
            findings = evaluate(records)
            self.assertEqual(tuple(item["invariant"] for item in findings), INVARIANTS)
            self.assertEqual({item["invariant"] for item in findings if item["result"] == "hypothesis"}, violated)
            self.assertTrue(all(set(item) == {"invariant", "result", "confidence", "intervention_ref", "evidence_for", "evidence_against", "assumptions", "alternatives", "bounds", "replay_result", "evidence_limitations"} for item in findings))

    def test_unknown_prose_is_nonrecoverable_shape_only(self):
        records = ingest_fixture("demo.json", FIXTURES)
        source = (FIXTURES / "demo.json").read_text()
        self.assertNotIn("detail", source)  # demo itself carries no source prose
        with tempfile.TemporaryDirectory() as directory:
            data = json.loads(source)
            canary = "TL_SECRET_canary_901"
            data["records"][0]["detail"] = canary
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            projected = ingest_fixture(path.name, path.parent)
            encoded = json.dumps(projected)
            redacted = projected[1]["payload"]["redacted_fields"]["detail"]
            self.assertEqual(redacted["classification"], "unknown")
            self.assertGreater(redacted["byte_length"], 0)
            self.assertEqual(redacted, {
                "classification": "unknown",
                "byte_length": len(json.dumps(canary, separators=(",", ":")).encode("ascii")),
                "redacted": True,
            })
            shapes = [canary, canary.encode().hex(), base64.b64encode(canary.encode()).decode(), canary.replace("_", "%5F")]
            self.assertTrue(all(shape not in encoded for shape in shapes))
            self.assertNotIn(gzip.compress(canary.encode()).hex(), encoded)
            self.assertNotIn(canary.encode("utf-16").hex(), encoded)
            data["records"][0]["detail"] = canary[:10]
            data["records"][0]["note"] = canary[10:]
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertNotIn(canary, json.dumps(ingest_fixture(path.name, path.parent)))

    def test_bounded_invalid_payloads_and_executable_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            oversize = root / "oversize.json"
            oversize.write_bytes(b" " * 129)
            with self.assertRaisesRegex(ValidationError, "payload_too_large"):
                ingest_fixture(oversize.name, root, Limits(max_bytes=128))
            deep: object = "x"
            for _ in range(20):
                deep = [deep]
            (root / "deep.json").write_text(json.dumps(deep), encoding="ascii")
            with self.assertRaisesRegex(ValidationError, "payload_too_deep"):
                ingest_fixture("deep.json", root, Limits(max_depth=8))
        manifest = {"items": [], "quarantine": []}
        patch = build_patch(manifest, "demo", "memory-1", "v1", "hypothesis-1")
        patch["command"] = "run-target"
        with self.assertRaisesRegex(ValidationError, "executable"):
            validate_patch(patch, manifest)

    def test_path_and_symlink_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "allowed"
            root.mkdir()
            (base / "outside.json").write_text("{}", encoding="ascii")
            link = root / "link.json"
            link.symlink_to(FIXTURES / "demo.json")
            with self.assertRaisesRegex(ValidationError, "symlink"):
                ingest_fixture(link.name, root)
            with self.assertRaisesRegex(ValidationError, "outside"):
                ingest_fixture(FIXTURES / "demo.json", root)
            with self.assertRaisesRegex(ValidationError, "outside"):
                ingest_fixture("../outside.json", root)

    def test_ledger_integrity_ids_and_honest_truncation_limit(self):
        records = ingest_fixture("demo.json", FIXTURES)
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.jsonl"
            write_ledger(records, ledger)
            self.assertEqual(verify_ledger(ledger), (True, "observable_chain_valid_unanchored_truncation_not_detectable"))
            original_ids = [r["record_id"] for r in records]
            self.assertEqual(original_ids, [r["record_id"] for r in ingest_fixture("demo.json", FIXTURES)])
            lines = ledger.read_text().splitlines()
            changed = json.loads(lines[1])
            changed["payload"]["actor"] = "attacker"
            lines[1] = json.dumps(changed, sort_keys=True, separators=(",", ":"))
            ledger.write_text("\n".join(lines) + "\n")
            self.assertFalse(verify_ledger(ledger)[0])
        truncated = build_lineage(records, max_depth=0)
        self.assertEqual(truncated[-1]["reason"], "declared_lineage_limit")

    def test_patch_base_binding_and_document_reversal(self):
        baseline = {"items": [{"namespace": "demo", "item": "memory-1", "version": "v1"}], "quarantine": []}
        patch = build_patch(baseline, "demo", "memory-1", "v1", "hypothesis-1")
        candidate = apply_patch(baseline, patch)
        self.assertNotEqual(digest(candidate), digest(baseline))
        self.assertEqual(digest(reverse_patch(candidate, patch)), digest(baseline))
        patch["base_hash"] = "0" * 64
        with self.assertRaisesRegex(ValidationError, "base"):
            apply_patch(baseline, patch)
        absent = {"items": [], "quarantine": []}
        absent_patch = build_patch(absent, "demo", "memory-1", "v1", "hypothesis-1")
        with self.assertRaisesRegex(ValidationError, "target_missing"):
            apply_patch(absent, absent_patch)

    @unittest.skipUnless(sandbox_available(), "genuine macOS sandbox unavailable: fail-closed path tested separately")
    def test_os_isolation_positive_controls_and_replay(self):
        self.assertEqual(prove_isolation(), {"network_probe": True, "parent_write_probe": True, "symlink_output_probe": True})
        baseline = {"items": [{"namespace": "demo", "item": "memory-1", "version": "v1"}], "quarantine": []}
        candidate = {"items": baseline["items"], "quarantine": [baseline["items"][0]]}
        result = replay(baseline, candidate, digest(baseline))
        self.assertFalse(result["documents_equal"])
        self.assertEqual(result["quarantine_added"], baseline["items"])

    def test_replay_fails_closed_without_proven_os_enforcement(self):
        if not sandbox_available():
            with self.assertRaisesRegex(ValidationError, "unavailable_fail_closed"):
                baseline = {"items": [], "quarantine": []}
                replay(baseline, baseline, digest(baseline))

    def test_report_repeatability_language_and_authority(self):
        findings = evaluate(ingest_fixture("demo.json", FIXTURES))
        replay_result = {"mechanism_demonstration": "bounded_declarative_document_comparison", "evidence_label": "scripted_fixture_response", "outcome_label": "not_real_task_outcome", "document_reversal_restored": True}
        outputs = [report_document("run-demo", findings, replay_result, "abstain") for _ in range(3)]
        self.assertEqual(len({item["deterministic_digest"] for item in outputs}), 1)
        rendered = (render_json(outputs[0]) + render_text(outputs[0])).lower()
        self.assertTrue(all(term not in rendered for term in BANNED))
        self.assertNotIn('"promotion"', rendered)
        self.assertIn("no_production_or_promotion_authority", rendered)

    def test_exact_record_type_surface(self):
        self.assertEqual(RECORD_TYPES, {"run", "event", "edge", "memory_op", "hypothesis", "patch", "replay", "gate_decision"})
        with self.assertRaisesRegex(ValidationError, "unknown_record_type"):
            make_envelope("promotion", "run-demo", 0, {}, "GENESIS")

    def test_cli_binds_patch_to_fixture_hypothesis_and_propagates_classification(self):
        if not sandbox_available():
            self.skipTest("genuine macOS sandbox unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = json.loads((FIXTURES / "demo.json").read_text())
            for record in data["records"]:
                record["classification"] = "sensitive"
            fixture = root / "sensitive.json"
            fixture.write_text(json.dumps(data), encoding="utf-8")
            output = root / "out"
            run_fixture(fixture, output)
            rows = [json.loads(line) for line in (output / "ledger.jsonl").read_text().splitlines()]
            derived = [row for row in rows if row["record_type"] in {"hypothesis", "patch", "replay", "gate_decision"}]
            self.assertTrue(derived and all(row["classification"] == "sensitive" for row in derived))
            patch = next(row for row in rows if row["record_type"] == "patch")
            hypothesis_ids = {row["record_id"] for row in rows if row["record_type"] == "hypothesis"}
            self.assertIn(patch["payload"]["hypothesis_ref"], hypothesis_ids)
            self.assertEqual(json.loads((output / "report.json").read_text())["classification"], "sensitive")
            self.assertEqual(json.loads((output / "lineage.json").read_text())["classification"], "sensitive")

    def test_clean_fixture_emits_no_patch_or_replay_and_pipeline_repeats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean_output = root / "clean"
            run_fixture(FIXTURES / "clean.json", clean_output)
            clean_rows = [json.loads(line) for line in (clean_output / "ledger.jsonl").read_text().splitlines()]
            self.assertFalse({"patch", "replay"} & {row["record_type"] for row in clean_rows})
            self.assertFalse((clean_output / "patch.json").exists())
            if not sandbox_available():
                return
            digests = []
            for index in range(3):
                output = root / f"out-{index}"
                run_fixture(FIXTURES / "demo.json", output)
                digests.append(json.loads((output / "report.json").read_text())["deterministic_digest"])
            self.assertEqual(len(set(digests)), 1)

    def test_lineage_truncation_is_visible_in_findings_and_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = [
                {"type": "event", "id": f"event-{index}", "classification": "internal", "kind": "step", "actor": "agent-a", "state_version": f"s{index}", "parents": []}
                for index in range(18)
            ]
            edges = [
                {"type": "edge", "id": f"edge-{index}", "classification": "internal", "kind": "parent", "from": "event-0", "to": f"event-{index + 1}", "source_asserted": True}
                for index in range(17)
            ]
            fixture = {"fixture_version": "phase1a-1", "run_id": "run-truncated", "records": events + edges, "manifest": {"fixture": "truncated-lineage", "environment": "darwin-24.6", "seed": 9}}
            path = root / "truncated.json"
            path.write_text(json.dumps(fixture), encoding="ascii")
            findings = evaluate(ingest_fixture(path.name, root))
            self.assertTrue(all("lineage_truncated" in item["evidence_limitations"] for item in findings))
            document = report_document("run-truncated", findings, {"mechanism_demonstration": "not_run"}, "abstain")
            self.assertIn("lineage_truncated", document["limitations"])

    def test_trailing_quarantine_keeps_hypothesis_without_partial_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out"
            document = run_fixture(FIXTURES / "tainted_trailing_quarantine.json", output)
            rows = [json.loads(line) for line in (output / "ledger.jsonl").read_text().splitlines()]
            self.assertIn("tainted_memory_not_reused_unquarantined", {finding["invariant"] for finding in document["hypotheses"] if finding["result"] == "hypothesis"})
            self.assertFalse({"patch", "replay"} & {row["record_type"] for row in rows})
            self.assertFalse((output / "patch.json").exists())
            self.assertEqual(document["replay"]["reason"], "target_already_quarantined_after_violation")


if __name__ == "__main__":
    unittest.main()
