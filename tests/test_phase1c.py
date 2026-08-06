from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from trajectory_ledger.analysis import evaluate
from trajectory_ledger.cli import entrypoint, render_completion_summary, run_fixture
from trajectory_ledger.core import ValidationError, ingest_fixture
from trajectory_ledger.diagnostic import build_diagnostic, render_diagnostic


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
LAUNCH_PREVIEWS = sorted((ROOT / "launch").glob("*.html"))


def passing_replay() -> dict:
    entry = {"namespace": "demo", "item": "memory-1", "version": "v1"}
    return {
        "mechanism_demonstration": "bounded_declarative_document_comparison",
        "evidence_label": "scripted_fixture_response",
        "outcome_label": "not_real_task_outcome",
        "baseline_digest": "a" * 64,
        "candidate_digest": "b" * 64,
        "candidate_base_bound": True,
        "quarantine_added": [entry],
        "quarantine_removed": [],
        "documents_equal": False,
        "document_reversal_restored": True,
    }


class Phase1cTests(unittest.TestCase):


    def test_cli_help_is_keyboard_operable_without_stdin_and_orders_arguments(self):
        result = subprocess.run(
            [sys.executable, "-m", "trajectory_ledger.cli", "--help"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("fixture output", result.stdout)
        self.assertLess(result.stdout.index("fixture"), result.stdout.index("output"))
        self.assertIn("--attest MODE", result.stdout)
        self.assertIn("go, narrow, stop, or abstain", result.stdout)
        self.assertIn("--full-report", result.stdout)

    def test_cli_help_reflows_for_a_narrow_terminal(self):
        result = subprocess.run(
            [sys.executable, "-m", "trajectory_ledger.cli", "--help"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "COLUMNS": "40",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith("\n"))
        self.assertLessEqual(max(map(len, result.stdout.splitlines())), 40)
        self.assertIn("--attest MODE", result.stdout)
        self.assertIn("--full-report", result.stdout)

    def test_cli_help_preserves_controls_at_200_percent_zoom_equivalent(self):
        # A 40-column terminal is the text-layout equivalent of doubling text
        # size in the default 80-column viewport. Argparse owns the reflow.
        outputs = {}
        for columns in (80, 40):
            result = subprocess.run(
                [sys.executable, "-m", "trajectory_ledger.cli", "--help"],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "COLUMNS": str(columns),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs[columns] = " ".join(result.stdout.split())

        self.assertEqual(outputs[40], outputs[80])
        for control in ("-h, --help", "--attest MODE", "--full-report"):
            self.assertIn(control, outputs[40])

    def test_cli_help_keeps_every_control_on_a_small_screen(self):
        result = subprocess.run(
            [sys.executable, "-m", "trajectory_ledger.cli", "--help"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "COLUMNS": "20",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith("\n"))
        for control in ("-h, --help", "--attest MODE", "--full-report"):
            self.assertIn(control, result.stdout)
        for value in ("go", "narrow", "stop", "abstain"):
            self.assertIn(value, result.stdout)

    def test_keyboard_interrupt_recovers_to_shell_without_traceback(self):
        stderr = StringIO()
        with mock.patch(
            "trajectory_ledger.cli.main", side_effect=KeyboardInterrupt
        ), redirect_stderr(stderr):
            status = entrypoint()
        self.assertEqual(status, 130)
        self.assertEqual(stderr.getvalue(), "\nCANCELLED operator_keyboard_interrupt\n")
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_precommit_failure_does_not_leave_output_directory(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "trajectory_ledger.cli.build_diagnostic",
            side_effect=ValueError("render_contract_rejected"),
        ):
            output = Path(directory) / "artifacts"
            with self.assertRaisesRegex(ValueError, "render_contract_rejected"):
                run_fixture(FIXTURES / "clean.json", output)
            self.assertFalse(output.exists())

    def test_persistence_failure_never_commits_partial_packet_and_retry_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "artifacts"
            from trajectory_ledger.cli import _write_ascii as real_write

            def corrupt_diagnostic(path, data):
                if path.name == "diagnostic.json":
                    return real_write(path, b"corrupt")
                return real_write(path, data)

            with mock.patch(
                "trajectory_ledger.cli._write_ascii", side_effect=corrupt_diagnostic
            ):
                with self.assertRaisesRegex(
                    ValidationError, "staged_packet_readback_mismatch"
                ):
                    run_fixture(FIXTURES / "clean.json", output)

            self.assertFalse(output.exists())
            incomplete = list(root.glob(".trajectory-ledger-incomplete-*"))
            self.assertEqual(len(incomplete), 1)
            self.assertFalse((incomplete[0] / "COMMITTED").exists())

            retry = root / "artifacts-retry"
            run_fixture(FIXTURES / "clean.json", retry)
            self.assertTrue((retry / "diagnostic.json").is_file())
            self.assertEqual(list(retry.glob(".trajectory-ledger-incomplete-*")), [])

    def test_committed_packet_detects_ledger_corruption(self):
        from trajectory_ledger.core import verify_ledger

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "artifacts"
            run_fixture(FIXTURES / "clean.json", output)
            ledger = output / "ledger.jsonl"
            damaged = ledger.read_text(encoding="ascii").replace(
                '"sequence":1', '"sequence":9', 1
            )
            ledger.write_text(damaged, encoding="ascii")
            self.assertEqual(verify_ledger(ledger), (False, "chain_mismatch"))

    def test_storage_error_fails_closed_without_committing_destination(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "trajectory_ledger.cli.os.fsync", side_effect=OSError("offline volume")
        ):
            root = Path(directory)
            output = root / "artifacts"
            with self.assertRaisesRegex(
                ValidationError, "output_persistence_failed"
            ):
                run_fixture(FIXTURES / "clean.json", output)
            self.assertFalse(output.exists())
            self.assertEqual(
                len(list(root.glob(".trajectory-ledger-incomplete-*"))), 1
            )

    def test_parent_sync_failure_reports_uncertain_but_complete_commit(self):
        # A clean packet has five files plus one staging-directory fsync before
        # the seventh fsync attempts to persist the parent rename.
        effects = [None] * 6 + [OSError("parent sync failed")]
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "trajectory_ledger.cli.os.fsync", side_effect=effects
        ):
            output = Path(directory) / "artifacts"
            with self.assertRaisesRegex(
                ValidationError, "output_commit_durability_uncertain"
            ):
                run_fixture(FIXTURES / "clean.json", output)
            self.assertTrue((output / "diagnostic.json").is_file())
            self.assertEqual(len(list(output.iterdir())), 5)

    def test_clean_run_succeeds_with_network_calls_denied(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "socket.socket.connect", side_effect=AssertionError("network attempted")
        ):
            output = Path(directory) / "artifacts"
            run_fixture(FIXTURES / "clean.json", output)
            self.assertTrue((output / "diagnostic.json").exists())

    def test_completion_summary_directs_first_use_without_claiming_action(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "trajectory_ledger.cli.replay", return_value=passing_replay()
        ):
            output = Path(directory) / "artifacts"
            run_fixture(FIXTURES / "demo_redacted_tainted.json", output)
            summary = render_completion_summary(output)
        self.assertIn("STATUS\nstatus=complete\nDECISION\n", summary)
        self.assertIn("EVIDENCE SUMMARY\n", summary)
        self.assertIn("NEXT ACTION\n", summary)
        self.assertIn("ARTIFACT LOCATION\n", summary)
        self.assertIn("recommendation=human_may_consider_promotion", summary)
        self.assertIn("authority=human_review_only_no_external_action", summary)
        self.assertIn("supported_failure_points=1", summary)
        self.assertIn("evidence_limited_failure_points=0", summary)
        self.assertIn("unsupported_failure_points=0", summary)
        self.assertIn("proposals=1", summary)
        self.assertIn("proposal_dispositions=eligible_for_saved_task_comparison", summary)
        self.assertIn("replay_criteria_passed=true", summary)
        self.assertIn("blocking_reasons=none", summary)
        self.assertIn("review_first=" + str(output / "diagnostic.json"), summary)
        self.assertIn("next_step=human_review_memory_candidate_and_evidence", summary)
        self.assertNotIn("ready for promotion", summary.lower())

    def test_completion_summary_has_linear_unique_section_structure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "artifacts"
            run_fixture(FIXTURES / "clean.json", output)
            summary = render_completion_summary(output)

        sections = ["STATUS", "DECISION", "EVIDENCE SUMMARY", "NEXT ACTION", "ARTIFACT LOCATION"]
        positions = [summary.index(section + "\n") for section in sections]
        self.assertEqual(positions, sorted(positions))
        for section in sections:
            self.assertEqual(summary.count(section + "\n"), 1)

    def test_validation_failure_announces_abstained_state_on_stderr(self):
        stderr = StringIO()
        stdout = StringIO()
        with mock.patch(
            "trajectory_ledger.cli.main",
            side_effect=ValidationError("invalid_fixture"),
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            status = entrypoint()

        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(
            stderr.getvalue(),
            "TRAJECTORY LEDGER LOCAL DIAGNOSTIC FAILED\n"
            "STATUS\n"
            "status=abstained\n"
            "ERROR\n"
            "phase1c_diagnostic_failed_closed=invalid_fixture\n",
        )

    def test_run_fixture_fails_closed_on_existing_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "artifacts"
            output.mkdir()
            with self.assertRaises(ValidationError) as caught:
                run_fixture(FIXTURES / "clean.json", output)
        self.assertEqual(str(caught.exception), "output_directory_unavailable")

    def test_entrypoint_abstains_without_traceback_on_existing_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "artifacts"
            output.mkdir()
            argv = ["trajectory-ledger", str(FIXTURES / "clean.json"), str(output), "--attest", "abstain"]
            stderr = StringIO()
            stdout = StringIO()
            with mock.patch.object(sys, "argv", argv), redirect_stdout(stdout), redirect_stderr(stderr):
                status = entrypoint()
        self.assertEqual(status, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("status=abstained", stderr.getvalue())
        self.assertIn("output_directory_unavailable", stderr.getvalue())
        # No traceback and no absolute-path leak in the operator-facing failure.
        self.assertNotIn("Traceback", stderr.getvalue())
        self.assertNotIn(str(output), stderr.getvalue())

    def test_completion_summary_exposes_fail_closed_blocker_and_tailored_next_step(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "trajectory_ledger.cli.replay",
            side_effect=ValidationError("sandbox_unavailable"),
        ):
            output = Path(directory) / "artifacts"
            run_fixture(FIXTURES / "demo_redacted_tainted.json", output)
            summary = render_completion_summary(output)
        self.assertIn("recommendation=abstain_no_promotion_recommendation", summary)
        self.assertIn("proposal_dispositions=eligible_for_saved_task_comparison", summary)
        self.assertIn("replay_criteria_passed=false", summary)
        self.assertIn(
            "blocking_reasons=saved_task_comparison_incomplete_or_failed", summary
        )
        self.assertIn(
            "next_step=review_saved_task_comparison_fail_closed_checks", summary
        )

    def test_completion_summary_separates_evidence_limited_points(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "artifacts"
            run_fixture(FIXTURES / "lineage_truncated.json", output)
            summary = render_completion_summary(output)
        self.assertIn("recommendation=abstain_no_promotion_recommendation", summary)
        self.assertIn("supported_failure_points=0", summary)
        self.assertIn("evidence_limited_failure_points=1", summary)
        self.assertIn("unsupported_failure_points=0", summary)
        self.assertIn(
            "blocking_reasons=evidence_support_incomplete_or_ambiguous,"
            "proposal_not_eligible_for_saved_task_comparison", summary
        )

    def test_supported_failure_point_proposal_and_passing_saved_task_replay(self):
        records = ingest_fixture("demo.json", FIXTURES)
        document = build_diagnostic(records, evaluate(records), passing_replay())
        point = next(item for item in document["likely_failure_points"] if item["invariant"] == "tainted_memory_not_reused_unquarantined")
        self.assertEqual(point["status"], "bounded_hypothesis")
        self.assertTrue(point["evidence_record_ids"])
        self.assertEqual(point["confidence"], "unknown")
        self.assertIn("no_causal_or_localization_claim", point["bounds"])
        proposal = next(item for item in document["proposals"] if item["proposal_type"] == "memory")
        self.assertTrue(proposal["reversible"])
        self.assertEqual(proposal["execution_authority"], "none")
        self.assertTrue(document["saved_task_replay_comparison"]["criteria_passed"])
        self.assertEqual(document["recommendation"], "human_may_consider_promotion")
        self.assertEqual(len({build_diagnostic(records, evaluate(records), passing_replay())["deterministic_digest"] for _ in range(3)}), 1)

    def test_unsupported_evidence_abstains_and_emits_no_proposal(self):
        records = ingest_fixture("clean.json", FIXTURES)
        finding = {
            "invariant": "memory_read_not_stale", "result": "hypothesis",
            "intervention_ref": "missing-source", "evidence_for": ["missing-source"],
            "alternatives": ["fixture_state_label_may_be_inaccurate"], "evidence_limitations": [],
        }
        document = build_diagnostic(records, [finding], passing_replay())
        self.assertEqual(document["likely_failure_points"][0]["status"], "abstention_unsupported_evidence")
        self.assertEqual(document["proposals"], [])
        self.assertEqual(document["recommendation"], "abstain_no_promotion_recommendation")

    def test_no_promotion_recommendation_when_any_replay_criterion_fails(self):
        records = ingest_fixture("demo.json", FIXTURES)
        for key, value in {
            "mechanism_demonstration": "not_run",
            "evidence_label": "untrusted",
            "outcome_label": "real_task_outcome",
            "baseline_digest": "invalid",
            "candidate_digest": "a" * 64,
            "candidate_base_bound": False,
            "quarantine_added": [],
            "quarantine_removed": [{"namespace": "demo", "item": "other", "version": "v1"}],
            "documents_equal": True,
            "document_reversal_restored": False,
        }.items():
            with self.subTest(key=key):
                replay = passing_replay()
                replay[key] = value
                document = build_diagnostic(records, evaluate(records), replay)
                self.assertFalse(document["saved_task_replay_comparison"]["criteria_passed"])
                self.assertEqual(document["recommendation"], "abstain_no_promotion_recommendation")

    def test_duplicate_source_id_is_ambiguous_and_abstains(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = json.loads((FIXTURES / "demo.json").read_text(encoding="ascii"))
            source["records"][-2]["id"] = source["records"][-1]["id"]
            (root / "duplicate.json").write_text(json.dumps(source), encoding="utf-8")
            records = ingest_fixture("duplicate.json", root)
            with mock.patch("trajectory_ledger.cli.replay", return_value=passing_replay()):
                run_fixture(root / "duplicate.json", root / "out")
            cli_document = json.loads((root / "out" / "diagnostic.json").read_text(encoding="ascii"))
            rows = [
                json.loads(line)
                for line in (root / "out" / "ledger.jsonl").read_text(encoding="ascii").splitlines()
            ]
            self.assertFalse((root / "out" / "patch.json").exists())
            self.assertFalse({"patch", "replay"} & {row["record_type"] for row in rows})
            self.assertEqual(cli_document["proposals"], [])
            self.assertEqual(cli_document["recommendation"], "abstain_no_promotion_recommendation")
        document = build_diagnostic(records, evaluate(records), passing_replay())
        point = next(item for item in document["likely_failure_points"] if item["invariant"] == "tainted_memory_not_reused_unquarantined")
        self.assertEqual(point["status"], "abstention_unsupported_evidence")
        self.assertEqual(point["evidence_record_ids"], [])
        self.assertEqual(document["proposals"], [])
        self.assertEqual(document["recommendation"], "abstain_no_promotion_recommendation")

    def test_expanded_diagnostic_and_proposal_contracts_are_versioned(self):
        records = ingest_fixture("demo.json", FIXTURES)
        document = build_diagnostic(records, evaluate(records), passing_replay())
        self.assertEqual(document["schema"], "phase1c-local-diagnostic-2")
        self.assertEqual(document["proposals"][0]["proposal_version"], "phase1c-declarative-2")
        self.assertIn("disposition", document["proposals"][0])
        self.assertIn("review_decision", document)

    def test_later_ambiguous_evidence_ref_emits_no_patch_or_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = json.loads(
                (FIXTURES / "tainted_repeated_reads.json").read_text(encoding="ascii")
            )
            source["records"][0]["id"] = "memory-op-3"
            fixture = root / "later-duplicate.json"
            fixture.write_text(json.dumps(source), encoding="ascii")
            with mock.patch("trajectory_ledger.cli.replay", return_value=passing_replay()):
                run_fixture(fixture, root / "out")

            diagnostic = json.loads(
                (root / "out" / "diagnostic.json").read_text(encoding="ascii")
            )
            rows = [
                json.loads(line)
                for line in (root / "out" / "ledger.jsonl").read_text(encoding="ascii").splitlines()
            ]
            self.assertFalse((root / "out" / "patch.json").exists())
            self.assertFalse({"patch", "replay"} & {row["record_type"] for row in rows})
            self.assertEqual(diagnostic["proposals"], [])
            self.assertEqual(diagnostic["recommendation"], "abstain_no_promotion_recommendation")

    def test_unknown_secret_is_absent_from_diagnostic_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = json.loads((FIXTURES / "demo.json").read_text(encoding="ascii"))
            canary = "TL_SECRET_phase1c_901"
            source["records"][0]["private_note"] = canary
            fixture = root / "stored.json"
            fixture.write_text(json.dumps(source), encoding="utf-8")
            records = ingest_fixture(fixture.name, root)
            encoded = render_diagnostic(build_diagnostic(records, evaluate(records), passing_replay()))
            self.assertNotIn(canary, encoded)
            self.assertNotIn(canary.encode().hex(), encoded)

    def test_clean_trace_abstains_without_failure_point_or_proposal(self):
        records = ingest_fixture("clean.json", FIXTURES)
        document = build_diagnostic(records, evaluate(records), {"mechanism_demonstration": "not_run"})
        self.assertEqual(document["likely_failure_points"], [])
        self.assertEqual(document["proposals"], [])
        self.assertEqual(document["recommendation"], "abstain_no_promotion_recommendation")

    def test_policy_and_workflow_proposals_are_declarative_only(self):
        cases = {
            "missing_lineage.json": ("workflow", "require_present_parent_reference"),
            "stale_memory_read.json": ("policy", "require_current_memory_version_on_read"),
        }
        for fixture, expected in cases.items():
            with self.subTest(fixture=fixture):
                records = ingest_fixture(fixture, FIXTURES)
                document = build_diagnostic(records, evaluate(records), {"mechanism_demonstration": "not_run"})
                self.assertEqual((document["proposals"][0]["proposal_type"], document["proposals"][0]["operation"]), expected)
                self.assertEqual(document["proposals"][0]["execution_authority"], "none")
                self.assertEqual(document["proposals"][0]["disposition"], "declarative_review_only")
                self.assertEqual(
                    document["review_decision"],
                    {
                        "outcome": "abstain_no_promotion_recommendation",
                        "blocking_reasons": ["proposal_not_eligible_for_saved_task_comparison"],
                        "next_step": "human_review_declarative_proposal_without_execution",
                    },
                )
                self.assertEqual(document["recommendation"], "abstain_no_promotion_recommendation")

    def test_multiple_likely_points_abstain_despite_memory_replay(self):
        records = ingest_fixture("compound_three_findings.json", FIXTURES)
        document = build_diagnostic(records, evaluate(records), passing_replay())
        self.assertGreater(len(document["likely_failure_points"]), 1)
        self.assertIn(
            "multiple_supported_failure_points_require_disambiguation",
            document["review_decision"]["blocking_reasons"],
        )
        self.assertEqual(
            document["review_decision"]["next_step"],
            "collect_discriminating_evidence_before_selecting_a_proposal",
        )
        self.assertEqual(document["recommendation"], "abstain_no_promotion_recommendation")

    def test_incomplete_lineage_blocks_supported_memory_recommendation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = json.loads((FIXTURES / "demo.json").read_text(encoding="ascii"))
            source["records"] = [
                record for record in source["records"] if record["type"] != "edge"
            ]
            for index in range(17):
                source["records"].extend([
                    {
                        "type": "event", "id": f"benign-child-{index}",
                        "classification": "internal", "kind": "step", "actor": "agent-a",
                        "state_version": f"child-{index}", "parents": [],
                    },
                    {
                        "type": "event", "id": f"benign-parent-{index}",
                        "classification": "internal", "kind": "step", "actor": "agent-a",
                        "state_version": f"parent-{index}", "parents": [],
                    },
                    {
                        "type": "edge", "id": f"benign-edge-{index}",
                        "classification": "internal", "kind": "parent",
                        "from": f"benign-child-{index}", "to": f"benign-parent-{index}",
                        "source_asserted": True,
                    },
                ])
            (root / "incomplete.json").write_text(json.dumps(source), encoding="ascii")
            records = ingest_fixture("incomplete.json", root)

        document = build_diagnostic(records, evaluate(records), passing_replay())
        memory_point = next(
            point for point in document["likely_failure_points"]
            if point["invariant"] == "tainted_memory_not_reused_unquarantined"
        )
        self.assertEqual(memory_point["status"], "bounded_hypothesis")
        self.assertEqual(memory_point["uncertainty"]["evidence_limitations"], ["lineage_truncated"])
        self.assertIn(
            "evidence_support_incomplete_or_ambiguous",
            document["review_decision"]["blocking_reasons"],
        )
        self.assertEqual(
            document["review_decision"]["next_step"], "repair_or_extend_trace_evidence"
        )
        self.assertEqual(document["recommendation"], "abstain_no_promotion_recommendation")

    def test_review_decision_distinguishes_clean_unsupported_replay_and_passing_paths(self):
        clean_records = ingest_fixture("clean.json", FIXTURES)
        clean = build_diagnostic(clean_records, evaluate(clean_records), {})
        self.assertEqual(clean["review_decision"]["blocking_reasons"], ["no_invariant_violation_observed"])

        unsupported_finding = {
            "invariant": "memory_read_not_stale", "result": "hypothesis",
            "intervention_ref": "missing-source", "evidence_for": ["missing-source"],
            "alternatives": [], "evidence_limitations": [],
        }
        unsupported = build_diagnostic(clean_records, [unsupported_finding], {})
        self.assertEqual(
            unsupported["review_decision"]["next_step"], "repair_or_extend_trace_evidence"
        )

        memory_records = ingest_fixture("demo.json", FIXTURES)
        failed = build_diagnostic(memory_records, evaluate(memory_records), {})
        self.assertEqual(
            failed["review_decision"]["blocking_reasons"],
            ["saved_task_comparison_incomplete_or_failed"],
        )
        passed = build_diagnostic(memory_records, evaluate(memory_records), passing_replay())
        self.assertEqual(passed["review_decision"]["blocking_reasons"], [])
        self.assertEqual(passed["proposals"][0]["disposition"], "eligible_for_saved_task_comparison")
        self.assertEqual(
            passed["review_decision"]["next_step"], "human_review_memory_candidate_and_evidence"
        )

    def test_primary_diagnostic_rejects_banned_causal_language(self):
        records = ingest_fixture("clean.json", FIXTURES)
        finding = {
            "invariant": "memory_read_not_stale",
            "result": "hypothesis",
            "intervention_ref": "missing-source",
            "evidence_for": ["missing-source"],
            "alternatives": ["the failure was externally determined"],
            "evidence_limitations": [],
        }
        with self.assertRaisesRegex(ValueError, "banned_language"):
            build_diagnostic(records, [finding], passing_replay())

    def test_redacted_demo_artifacts_are_deterministic_and_canary_free(self):
        fixture = FIXTURES / "demo_redacted_tainted.json"
        canary = "TL_REDACTION_CANARY_31"
        digests = []
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "trajectory_ledger.cli.replay", return_value=passing_replay()
        ):
            root = Path(directory)
            for index in range(3):
                output = root / f"out-{index}"
                run_fixture(fixture, output)
                diagnostic = json.loads((output / "diagnostic.json").read_text(encoding="ascii"))
                digests.append(diagnostic["deterministic_digest"])
                artifacts = b"".join(path.read_bytes() for path in sorted(output.iterdir()))
                self.assertNotIn(canary.encode(), artifacts)
                self.assertNotIn(canary.encode().hex().encode(), artifacts)
                self.assertEqual(diagnostic["recommendation"], "human_may_consider_promotion")
                self.assertTrue(diagnostic["saved_task_replay_comparison"]["criteria_passed"])
        self.assertEqual(len(set(digests)), 1)

    def test_replay_failure_emits_proposal_and_abstaining_diagnostic(self):
        diagnostic_digests = []
        proposal_ids = []
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "trajectory_ledger.cli.replay",
            side_effect=ValidationError("environment_specific_detail"),
        ):
            for index in range(3):
                output = Path(directory) / f"out-{index}"
                run_fixture(FIXTURES / "demo_redacted_tainted.json", output)
                diagnostic = json.loads(
                    (output / "diagnostic.json").read_text(encoding="ascii")
                )
                report = json.loads(
                    (output / "report.json").read_text(encoding="ascii")
                )
                ledger = (output / "ledger.jsonl").read_text(encoding="ascii")
                diagnostic_digests.append(diagnostic["deterministic_digest"])
                proposal_ids.append(diagnostic["proposals"][0]["proposal_id"])
                self.assertEqual(
                    diagnostic["recommendation"],
                    "abstain_no_promotion_recommendation",
                )
                self.assertFalse(
                    diagnostic["saved_task_replay_comparison"]["criteria_passed"]
                )
                self.assertEqual(len(diagnostic["proposals"]), 1)
                self.assertTrue((output / "patch.json").exists())
                self.assertEqual(
                    report["replay"]["reason"],
                    "saved_task_replay_failed_closed",
                )
                self.assertNotIn(
                    "environment_specific_detail",
                    ledger + json.dumps(diagnostic) + json.dumps(report),
                )
                rows = [json.loads(line) for line in ledger.splitlines()]
                self.assertNotIn("replay", {row["record_type"] for row in rows})
        self.assertEqual(len(set(diagnostic_digests)), 1)
        self.assertEqual(len(set(proposal_ids)), 1)

    def test_replay_timeout_is_sanitized_and_proposal_identity_is_stable(self):
        fixture = FIXTURES / "demo_redacted_tainted.json"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch(
                "trajectory_ledger.cli.replay", return_value=passing_replay()
            ):
                run_fixture(fixture, root / "passing", attest="go")
            with mock.patch(
                "trajectory_ledger.cli.replay",
                side_effect=subprocess.TimeoutExpired(
                    cmd=["secret-token-7f31", "/sensitive/replay-bin", "--credential"],
                    timeout=5,
                ),
            ):
                run_fixture(fixture, root / "timeout", attest="abstain")
            passing = json.loads(
                (root / "passing" / "diagnostic.json").read_text(encoding="ascii")
            )
            timeout = json.loads(
                (root / "timeout" / "diagnostic.json").read_text(encoding="ascii")
            )
            timeout_artifacts = b"".join(
                path.read_bytes() for path in sorted((root / "timeout").iterdir())
            )
            self.assertEqual(
                passing["proposals"][0]["proposal_id"],
                timeout["proposals"][0]["proposal_id"],
            )
            self.assertEqual(
                timeout["recommendation"], "abstain_no_promotion_recommendation"
            )
            self.assertNotIn(b"secret-token-7f31", timeout_artifacts)
            self.assertNotIn(b"/sensitive/replay-bin", timeout_artifacts)
            self.assertNotIn(b"--credential", timeout_artifacts)

    def test_redacted_abstention_demo_emits_no_proposal_or_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out"
            run_fixture(FIXTURES / "demo_redacted_abstain.json", output)
            diagnostic = json.loads((output / "diagnostic.json").read_text(encoding="ascii"))
            artifacts = b"".join(path.read_bytes() for path in sorted(output.iterdir()))
            self.assertEqual(diagnostic["likely_failure_points"], [])
            self.assertEqual(diagnostic["proposals"], [])
            self.assertEqual(diagnostic["recommendation"], "abstain_no_promotion_recommendation")
            self.assertFalse((output / "patch.json").exists())
            self.assertNotIn(b"TL_REDACTION_CANARY_32", artifacts)

    def test_failed_document_reversal_forces_abstention(self):
        records = ingest_fixture("demo_redacted_tainted.json", FIXTURES)
        replay = passing_replay()
        document = build_diagnostic(records, evaluate(records), replay)
        self.assertTrue(document["saved_task_replay_comparison"]["checks"]["document_reversal_restored"])
        replay["document_reversal_restored"] = False
        reversed_failure = build_diagnostic(records, evaluate(records), replay)
        self.assertFalse(reversed_failure["saved_task_replay_comparison"]["criteria_passed"])
        self.assertEqual(reversed_failure["recommendation"], "abstain_no_promotion_recommendation")


if __name__ == "__main__":
    unittest.main()
