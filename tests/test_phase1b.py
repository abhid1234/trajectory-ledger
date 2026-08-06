from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

from trajectory_ledger.analysis import evaluate
from trajectory_ledger.core import Limits, ValidationError, digest, ingest_fixture
from trajectory_ledger.corpus import CATEGORY_FLOORS, load_manifest, validate_manifest
from trajectory_ledger.patching import build_patch, validate_patch
from trajectory_ledger.replay import replay, sandbox_available, validate_document, validate_replay_result, validate_transition
from trajectory_ledger.report import EFFICACY_GATE_STATUS, render_text, report_document

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
MANIFEST = FIXTURES / "manifest.json"


class Phase1bTests(unittest.TestCase):
    def test_manifest_corpus_floors_signatures_expectations_and_blocked_gate(self):
        summary = validate_manifest(MANIFEST, FIXTURES)
        self.assertGreaterEqual(summary["accepted"], 40)
        self.assertGreaterEqual(summary["negative_cases"], 16)
        self.assertEqual(summary["efficacy_gate_status"], EFFICACY_GATE_STATUS)
        for category, floor in CATEGORY_FLOORS.items():
            self.assertGreaterEqual(summary["category_counts"][category], floor)

    def test_duplicate_normalized_signature_is_rejected(self):
        manifest = load_manifest(MANIFEST)
        duplicate = dict(manifest["accepted"][0])
        duplicate["fixture"] = "clean-copy.json"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for source in FIXTURES.glob("*.json"):
                if source.name != "manifest.json":
                    (root / source.name).write_bytes(source.read_bytes())
            (root / "clean-copy.json").write_bytes((FIXTURES / manifest["accepted"][0]["fixture"]).read_bytes())
            manifest["accepted"].append(duplicate)
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="ascii")
            with self.assertRaisesRegex(ValidationError, "duplicate_normalized_behavior_signature"):
                validate_manifest(path, root)

    def test_manifest_reader_rejects_symlinks_and_oversize_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest-link.json").symlink_to(MANIFEST)
            with self.assertRaisesRegex(ValidationError, "symlink_input"):
                load_manifest(root / "manifest-link.json")
            oversized = root / "oversized.json"
            oversized.write_bytes(b" " * 64_001)
            with self.assertRaisesRegex(ValidationError, "payload_too_large"):
                load_manifest(oversized)

    def test_table_driven_negative_matrix(self):
        base = json.loads((FIXTURES / "clean.json").read_text())

        def ingest_document(document, *, limits=Limits()):
            root = Path(self.tempdir_name)
            path = root / "case.json"
            path.write_text(json.dumps(document), encoding="ascii")
            ingest_fixture(path.name, root, limits)

        def malformed_json():
            root = Path(self.tempdir_name)
            (root / "case.json").write_text("{", encoding="ascii")
            ingest_fixture("case.json", root)

        def oversize():
            root = Path(self.tempdir_name)
            (root / "case.json").write_bytes(b" " * 129)
            ingest_fixture("case.json", root, Limits(max_bytes=128))

        def symlink():
            root = Path(self.tempdir_name)
            (root / "link.json").symlink_to(FIXTURES / "clean.json")
            ingest_fixture("link.json", root)

        def escape():
            root = Path(self.tempdir_name)
            ingest_fixture(FIXTURES / "clean.json", root)

        def executable_patch():
            memory = {"items": [], "quarantine": []}
            patch = build_patch(memory, "demo", "memory-1", "v1", "hypothesis-1")
            patch["command"] = "target"
            validate_patch(patch, memory)

        def base_mismatch():
            memory = {"items": [], "quarantine": []}
            patch = build_patch(memory, "demo", "memory-1", "v1", "hypothesis-1")
            patch["base_hash"] = "0" * 64
            validate_patch(patch, memory)

        valid_replay = {
            "mechanism_demonstration": "bounded_declarative_document_comparison",
            "evidence_label": "scripted_fixture_response", "outcome_label": "not_real_task_outcome",
            "baseline_digest": "0" * 64, "candidate_digest": "0" * 64,
            "candidate_base_bound": True, "quarantine_added": [], "quarantine_removed": [],
            "quarantine_unchanged": [], "documents_equal": True,
        }
        cases = {}
        changed = dict(base); changed["extra"] = True
        cases["top-level-shape"] = lambda changed=changed: ingest_document(changed)
        changed = dict(base); changed["fixture_version"] = "other"
        cases["header-version"] = lambda changed=changed: ingest_document(changed)
        changed = json.loads(json.dumps(base)); del changed["records"][0]["id"]
        cases["required-record-field"] = lambda changed=changed: ingest_document(changed)
        changed = json.loads(json.dumps(base)); changed["records"][0]["type"] = "run"
        cases["source-record-type"] = lambda changed=changed: ingest_document(changed)
        changed = json.loads(json.dumps(base)); changed["records"][0]["kind"] = "unknown"
        cases["closed-enum"] = lambda changed=changed: ingest_document(changed)
        changed = json.loads(json.dumps(base)); changed["records"][0]["id"] = "bad/id"
        cases["identifier-characters"] = lambda changed=changed: ingest_document(changed)
        changed = json.loads(json.dumps(base)); changed["records"][0]["parents"] = [f"event-{i}" for i in range(17)]
        cases["collection-limit"] = lambda changed=changed: ingest_document(changed)
        deep: object = "x"
        for _ in range(20): deep = [deep]
        cases["depth-limit"] = lambda deep=deep: ingest_document(deep, limits=Limits(max_depth=8))
        cases["byte-size-limit"] = oversize
        cases["malformed-json"] = malformed_json
        changed = json.loads(json.dumps(base)); changed["records"][0]["detail"] = "x" * 257
        cases["unknown-field-bound"] = lambda changed=changed: ingest_document(changed)
        cases["symlink-input"] = symlink
        cases["path-escape"] = escape
        cases["executable-patch-field"] = executable_patch
        cases["patch-base-mismatch"] = base_mismatch
        cases["sandbox-unavailable"] = lambda: replay({"items": [], "quarantine": []}, {"items": [], "quarantine": []}, digest({"items": [], "quarantine": []}))
        malformed = dict(valid_replay); malformed["ignored"] = True
        cases["malformed-replay-output"] = lambda: validate_replay_result(malformed)

        manifest_cases = load_manifest(MANIFEST)["negative_cases"]
        self.assertGreaterEqual(len(manifest_cases), 16)
        for declared in manifest_cases:
            with self.subTest(case_id=declared["case_id"]), tempfile.TemporaryDirectory() as directory:
                self.tempdir_name = directory
                context = mock.patch("trajectory_ledger.replay.sandbox_available", return_value=False) if declared["case_id"] == "sandbox-unavailable" else nullcontext()
                with context, self.assertRaisesRegex(ValidationError, declared["expected_error"]):
                    cases[declared["case_id"]]()

    def test_replay_document_schema_wrong_base_and_malformed_result(self):
        baseline = {"items": [], "quarantine": []}
        with self.assertRaisesRegex(ValidationError, "base_mismatch"):
            replay(baseline, baseline, "0" * 64)
        with self.assertRaisesRegex(ValidationError, "invalid_replay_document"):
            validate_document({"items": [], "quarantine": [], "ignored": []})
        with self.assertRaisesRegex(ValidationError, "invalid_replay_result"):
            validate_replay_result({})

    def test_replay_state_is_canonical_and_transition_is_single_addition(self):
        first = {"namespace": "demo", "item": "memory-1", "version": "v1"}
        second = {"namespace": "demo", "item": "memory-2", "version": "v1"}
        baseline = {"items": [first, second], "quarantine": []}
        validate_transition(baseline, {"items": [first, second], "quarantine": [first]})
        with self.assertRaisesRegex(ValidationError, "noncanonical"):
            validate_document({"items": [second, first], "quarantine": []})
        with self.assertRaisesRegex(ValidationError, "items_changed"):
            validate_transition(baseline, {"items": [first], "quarantine": []})
        with self.assertRaisesRegex(ValidationError, "transition_unbounded"):
            validate_transition(baseline, {"items": [first, second], "quarantine": [first, second]})
        with self.assertRaisesRegex(ValidationError, "quarantine_removed"):
            validate_transition({"items": [first], "quarantine": [first]}, {"items": [first], "quarantine": []})

    def test_replay_result_is_bound_to_exact_state(self):
        entry = {"namespace": "demo", "item": "memory-1", "version": "v1"}
        baseline = {"items": [entry], "quarantine": []}
        candidate = {"items": [entry], "quarantine": [entry]}
        result = {
            "mechanism_demonstration": "bounded_declarative_document_comparison",
            "evidence_label": "scripted_fixture_response", "outcome_label": "not_real_task_outcome",
            "baseline_digest": digest(baseline), "candidate_digest": digest(candidate),
            "candidate_base_bound": True, "quarantine_added": [entry], "quarantine_removed": [],
            "quarantine_unchanged": [], "documents_equal": False,
        }
        self.assertIs(validate_replay_result(result, baseline, candidate), result)
        result["candidate_digest"] = "0" * 64
        with self.assertRaisesRegex(ValidationError, "state_mismatch"):
            validate_replay_result(result, baseline, candidate)

    @unittest.skipUnless(sandbox_available(), "genuine macOS sandbox unavailable")
    def test_replay_changed_unchanged_and_reversal_summary(self):
        entry = {"namespace": "demo", "item": "memory-1", "version": "v1"}
        baseline = {"items": [entry], "quarantine": []}
        unchanged = replay(baseline, baseline, digest(baseline))
        self.assertTrue(unchanged["documents_equal"])
        self.assertEqual(unchanged["quarantine_added"], [])
        candidate = {"items": [entry], "quarantine": [entry]}
        changed = replay(baseline, candidate, digest(baseline))
        self.assertFalse(changed["documents_equal"])
        self.assertTrue(changed["candidate_base_bound"])
        self.assertEqual(changed["quarantine_added"], [entry])
        self.assertEqual(changed["outcome_label"], "not_real_task_outcome")

    def test_multiple_hypotheses_are_unordered_and_gate_is_blocked(self):
        findings = evaluate(ingest_fixture("compound_three_findings.json", FIXTURES))
        document = report_document("run-compound", findings, {"mechanism_demonstration": "not_run"}, "abstain")
        self.assertEqual(document["hypothesis_interpretation"], {"ordering": "unordered_set", "unique_explanation": False, "ranking": "none"})
        self.assertEqual(document["efficacy_gate_status"], EFFICACY_GATE_STATUS)
        text = render_text(document)
        self.assertLess(text.index("observed_invariant_results="), text.index("scope="))


if __name__ == "__main__":
    unittest.main()
