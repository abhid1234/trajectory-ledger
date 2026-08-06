"""Adversarial state, identity, and ingestion boundary regressions."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trajectory_ledger.analysis import evaluate
from trajectory_ledger.core import Limits, ValidationError, ingest_fixture
from trajectory_ledger.diagnostic import build_diagnostic


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


def hypotheses(fixture: str) -> dict[str, dict]:
    records = ingest_fixture(fixture, FIXTURES)
    return {
        finding["invariant"]: finding
        for finding in evaluate(records)
        if finding["result"] == "hypothesis"
    }


class AdversarialFlowTests(unittest.TestCase):
    def test_invalid_fields_fail_closed_without_coercion(self):
        cases = (
            ("clean.json", "boolean-seed", lambda value: value["manifest"].update(seed=True), "invalid_seed"),
            ("stale_memory_read.json", "unknown-state", lambda value: value["records"][1].update(state="fresh"), "invalid_enum:memory_state"),
            ("conflicting_parent.json", "nonboolean-assertion", lambda value: value["records"][-1].update(source_asserted=1), "invalid_boolean:source_asserted"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for fixture, name, mutate, expected in cases:
                with self.subTest(name=name):
                    candidate = json.loads((FIXTURES / fixture).read_text(encoding="ascii"))
                    mutate(candidate)
                    path = root / f"{name}.json"
                    path.write_text(json.dumps(candidate), encoding="ascii")
                    with self.assertRaisesRegex(ValidationError, expected):
                        ingest_fixture(path.name, root)

    def test_stale_detection_is_exact_version_scoped_and_sticky(self):
        boundary = hypotheses("stale_version_boundary.json")
        finding = boundary["memory_read_not_stale"]
        self.assertEqual(finding["evidence_for"], ["memory-op-2"])
        self.assertNotIn("memory-op-1", finding["evidence_for"])

        # A later expire operation cannot rewrite the earlier observed read.
        expired = hypotheses("stale_then_expire.json")["memory_read_not_stale"]
        self.assertEqual(expired["evidence_for"], ["memory-op-1"])

    def test_duplicate_source_identity_abstains_instead_of_selecting_a_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = json.loads((FIXTURES / "stale_memory_read.json").read_text(encoding="ascii"))
            duplicate = json.loads(json.dumps(source["records"][1]))
            source["records"].append(duplicate)
            path = root / "duplicate.json"
            path.write_text(json.dumps(source), encoding="ascii")
            records = ingest_fixture(path.name, root)

        diagnostic = build_diagnostic(records, evaluate(records), {})
        point = diagnostic["likely_failure_points"][0]
        self.assertEqual(point["status"], "abstention_unsupported_evidence")
        self.assertEqual(point["evidence_record_ids"], [])
        self.assertEqual(diagnostic["proposals"], [])

    def test_tied_conflict_sources_are_all_reported_in_stable_order(self):
        first = hypotheses("conflict_two_sources.json")["parent_edge_nonconflicting"]
        second = hypotheses("conflict_two_sources.json")["parent_edge_nonconflicting"]
        self.assertEqual(first["evidence_for"], ["event-1", "event-1", "event-2", "event-2"])
        self.assertEqual(second["evidence_for"], first["evidence_for"])
        self.assertEqual(first["intervention_ref"], "event-1")

    def test_quarantine_reset_is_key_scoped_across_versions(self):
        # Quarantining v1 must not suppress a later tainted reuse of v2.
        self.assertNotIn(
            "tainted_memory_not_reused_unquarantined",
            hypotheses("tainted_different_version.json"),
        )

        # A quarantine that precedes the taint is still a reset for that exact key.
        self.assertNotIn(
            "tainted_memory_not_reused_unquarantined",
            hypotheses("tainted_quarantine_before_read.json"),
        )

    def test_record_count_boundary_accepts_limit_and_rejects_limit_plus_one(self):
        source = json.loads((FIXTURES / "clean.json").read_text(encoding="ascii"))
        template = source["records"][0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for count, accepted in ((3, True), (4, False)):
                with self.subTest(count=count):
                    candidate = json.loads(json.dumps(source))
                    candidate["records"] = []
                    for index in range(count):
                        record = json.loads(json.dumps(template))
                        record["id"] = f"event-{index}"
                        candidate["records"].append(record)
                    path = root / f"records-{count}.json"
                    path.write_text(json.dumps(candidate), encoding="ascii")
                    if accepted:
                        self.assertEqual(len(ingest_fixture(path.name, root, Limits(max_records=3))), 4)
                    else:
                        with self.assertRaisesRegex(ValidationError, "invalid_fixture_collections"):
                            ingest_fixture(path.name, root, Limits(max_records=3))


if __name__ == "__main__":
    unittest.main()
