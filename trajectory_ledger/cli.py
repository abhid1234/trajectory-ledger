from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .analysis import evaluate
from .core import ValidationError, build_lineage, canonical_bytes, digest, ingest_fixture, make_envelope, resolve_unique_source_record, strictest_classification, verify_ledger, write_ledger
from .diagnostic import build_diagnostic, render_diagnostic
from .patching import apply_patch, build_patch, reverse_patch
from .replay import replay
from .report import render_json, render_text, report_document


def _write_ascii(path: Path, data: str | bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    if isinstance(data, bytes):
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    else:
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(data)


def _verify_staged_packet(root: Path, expected: dict[str, bytes]) -> None:
    """Fail closed unless every staged byte can be read back exactly."""
    try:
        names = {entry.name for entry in root.iterdir()}
        if names != set(expected):
            raise ValidationError("staged_packet_file_set_mismatch")
        for name, contents in expected.items():
            path = root / name
            if path.is_symlink() or not path.is_file() or path.read_bytes() != contents:
                raise ValidationError("staged_packet_readback_mismatch")
        valid, _ = verify_ledger(root / "ledger.jsonl")
        if not valid:
            raise ValidationError("staged_ledger_invalid")
    except OSError as exc:
        raise ValidationError("staged_packet_unreadable") from exc


def _sync_directory_tree(root: Path, names: set[str]) -> None:
    """Request durable storage of staged files and their directory entries."""
    descriptors: list[int] = []
    try:
        for name in sorted(names):
            descriptor = os.open(
                root / name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            )
            descriptors.append(descriptor)
            os.fsync(descriptor)
        directory = os.open(root, os.O_RDONLY)
        descriptors.append(directory)
        os.fsync(directory)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _memory_manifest(records: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, str]] = []
    quarantine: list[dict[str, str]] = []
    for record in records:
        if record["record_type"] != "memory_op":
            continue
        payload = record["payload"]
        entry = {key: payload[key] for key in ("namespace", "item", "version")}
        if entry not in items:
            items.append(entry)
        if payload["action"] == "quarantine" and entry not in quarantine:
            quarantine.append(entry)
    key = lambda entry: (entry["namespace"], entry["item"], entry["version"])
    return {"items": sorted(items, key=key), "quarantine": sorted(quarantine, key=key)}


def run_fixture(fixture: Path, output: Path, attest: str = "abstain") -> dict[str, Any]:
    # Build and validate the complete packet before reserving its destination.
    # This keeps ingestion, analysis, replay, and rendering failures from leaving
    # an output directory that could be mistaken for a completed diagnostic.
    records = ingest_fixture(fixture.name, fixture.parent)
    lineage = build_lineage(records)
    findings = evaluate(records)
    classification = strictest_classification(records)
    prev = digest(records[-1])
    hypothesis_records: list[dict[str, Any]] = []
    for finding in findings:
        envelope = make_envelope("hypothesis", records[0]["run_id"], len(records), {"classification": classification, **finding}, prev)
        records.append(envelope)
        hypothesis_records.append(envelope)
        prev = digest(envelope)
    proposal_base_digest = digest(records)

    replay_result: dict[str, Any] = {"mechanism_demonstration": "not_run", "reason": "no_memory_quarantine_hypothesis"}
    eligible = next((index for index, finding in enumerate(findings) if finding["result"] == "hypothesis" and finding["invariant"] == "tainted_memory_not_reused_unquarantined"), None)
    if eligible is not None:
        evidence = findings[eligible].get("evidence_for")
        if not isinstance(evidence, list) or not evidence:
            raise ValidationError("hypothesis_evidence_unbound")
        evidence_records = (
            [resolve_unique_source_record(records, evidence_ref) for evidence_ref in evidence]
            if all(isinstance(evidence_ref, str) for evidence_ref in evidence)
            else []
        )
        if (
            len(evidence_records) != len(evidence)
            or any(record is None for record in evidence_records)
            or any(record["record_type"] != "memory_op" for record in evidence_records if record)
        ):
            replay_result = {
                "mechanism_demonstration": "not_run",
                "reason": "hypothesis_evidence_incomplete_or_ambiguous",
            }
        else:
            memory = evidence_records[0]["payload"]
            baseline = _memory_manifest(records)
            target = {key: memory[key] for key in ("namespace", "item", "version")}
            if target in baseline["quarantine"]:
                replay_result = {"mechanism_demonstration": "not_run", "reason": "target_already_quarantined_after_violation"}
            else:
                patch = build_patch(baseline, memory["namespace"], memory["item"], memory["version"], hypothesis_records[eligible]["record_id"])
                candidate = apply_patch(baseline, patch)
                restored = reverse_patch(candidate, patch)
                try:
                    replay_result = replay(baseline, candidate, patch["base_hash"])
                except (ValidationError, OSError, subprocess.SubprocessError):
                    # Ingestion and the declarative proposal remain useful evidence when
                    # the OS jail cannot prove a comparison. Do not substitute an
                    # in-process replay or expose environment-specific exception text.
                    replay_result = {
                        "mechanism_demonstration": "not_run",
                        "reason": "saved_task_replay_failed_closed",
                        "document_reversal_restored": False,
                    }
                else:
                    replay_result["document_reversal_restored"] = digest(restored) == digest(baseline)
                derived = [("patch", patch)]
                if replay_result["mechanism_demonstration"] != "not_run":
                    derived.append(("replay", replay_result))
                for record_type, payload in derived:
                    envelope = make_envelope(record_type, records[0]["run_id"], len(records), {"classification": classification, **payload}, prev)
                    records.append(envelope)
                    prev = digest(envelope)

    gate = {"classification": classification, "rule_version": "human-attestation-1", "outcome": attest, "operator_self_attestation": True}
    envelope = make_envelope("gate_decision", records[0]["run_id"], len(records), gate, prev)
    records.append(envelope)
    document = report_document(records[0]["run_id"], findings, replay_result, attest, classification)
    diagnostic = build_diagnostic(
        records,
        findings,
        replay_result,
        proposal_base_digest=proposal_base_digest,
    )
    patch_payload = next((record["payload"] for record in records if record["record_type"] == "patch"), None)

    artifacts = {
        "lineage.json": json.dumps(
            {"classification": classification, "edges": lineage},
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n",
        "report.json": render_json(document),
        "report.txt": render_text(document),
        "diagnostic.json": render_diagnostic(diagnostic),
    }
    if patch_payload is not None:
        artifacts["patch.json"] = json.dumps(
            patch_payload, sort_keys=True, separators=(",", ":")
        ) + "\n"

    # The ledger's on-disk bytes must be known up front so the staged packet can
    # be read back and compared exactly before it is committed.
    ledger_bytes = b"".join(canonical_bytes(record) + b"\n" for record in records)
    expected: dict[str, bytes] = {
        name: contents.encode("ascii") if isinstance(contents, str) else contents
        for name, contents in artifacts.items()
    }
    expected["ledger.jsonl"] = ledger_bytes

    # Never overwrite operator data: refuse an occupied destination up front.
    if output.exists() or output.is_symlink():
        raise ValidationError("output_directory_unavailable")
    try:
        staging = Path(
            tempfile.mkdtemp(prefix=".trajectory-ledger-incomplete-", dir=output.parent)
        )
    except OSError as exc:
        raise ValidationError("output_directory_unavailable") from exc

    # Stage the whole packet beside the destination, prove every byte reads back
    # and the ledger chain verifies, fsync the files and their directory, then
    # commit with one atomic rename. A failed attempt leaves the dot-prefixed
    # incomplete directory as inspectable evidence and never a partial packet.
    try:
        write_ledger(records, staging / "ledger.jsonl")
        for name, contents in artifacts.items():
            _write_ascii(staging / name, contents)
        _verify_staged_packet(staging, expected)
        _sync_directory_tree(staging, set(expected))
        os.replace(staging, output)
    except ValidationError:
        raise
    except OSError as exc:
        raise ValidationError("output_persistence_failed") from exc

    # The packet is committed. Persist the parent directory entry so the rename
    # survives a crash. If only this final sync fails, the packet is present but
    # not provably durable -- a distinct, explicit status rather than a claim of
    # either absence or safe persistence.
    try:
        parent_fd = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except OSError as exc:
        raise ValidationError("output_commit_durability_uncertain") from exc
    return document


def render_completion_summary(output: Path) -> str:
    """Render the small operator receipt; detailed evidence stays in artifacts."""
    diagnostic = json.loads((output / "diagnostic.json").read_text(encoding="ascii"))
    replay = diagnostic["saved_task_replay_comparison"]
    decision = diagnostic["review_decision"]
    supported = sum(
        point["status"] == "bounded_hypothesis"
        and not point["uncertainty"]["evidence_limitations"]
        for point in diagnostic["likely_failure_points"]
    )
    evidence_limited = sum(
        point["status"] == "bounded_hypothesis"
        and bool(point["uncertainty"]["evidence_limitations"])
        for point in diagnostic["likely_failure_points"]
    )
    unsupported = sum(
        point["status"] == "abstention_unsupported_evidence"
        for point in diagnostic["likely_failure_points"]
    )
    dispositions = sorted({proposal["disposition"] for proposal in diagnostic["proposals"]})
    lines = [
        "TRAJECTORY LEDGER LOCAL DIAGNOSTIC COMPLETE",
        "STATUS",
        "status=complete",
        "DECISION",
        "recommendation=" + diagnostic["recommendation"],
        "authority=" + diagnostic["authority"],
        "EVIDENCE SUMMARY",
        "supported_failure_points=" + str(supported),
        "evidence_limited_failure_points=" + str(evidence_limited),
        "unsupported_failure_points=" + str(unsupported),
        "proposals=" + str(len(diagnostic["proposals"])),
        "proposal_dispositions=" + (",".join(dispositions) if dispositions else "none"),
        "replay_criteria_passed=" + ("true" if replay["criteria_passed"] else "false"),
        "blocking_reasons=" + (
            ",".join(decision["blocking_reasons"])
            if decision["blocking_reasons"] else "none"
        ),
        "NEXT ACTION",
        "next_step=" + decision["next_step"],
        "review_first=" + str(output / "diagnostic.json"),
        "ARTIFACT LOCATION",
        "artifacts=" + str(output),
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a local, review-only diagnostic evidence packet from one inert fixture.",
        epilog="Start safely: ./scripts/local_demo.sh",
    )
    parser.add_argument("fixture", type=Path, help="canonical synthetic or redacted JSON fixture")
    parser.add_argument("output", type=Path, help="new directory for the evidence packet")
    parser.add_argument(
        "--attest",
        choices=("go", "narrow", "stop", "abstain"),
        default="abstain",
        metavar="MODE",
        help="operator attestation: go, narrow, stop, or abstain (default: abstain)",
    )
    parser.add_argument(
        "--full-report",
        action="store_true",
        help="print the detailed text report instead of the concise completion receipt",
    )
    args = parser.parse_args()
    document = run_fixture(args.fixture, args.output, args.attest)
    print(render_text(document) if args.full_report else render_completion_summary(args.output), end="")
    return 0


def entrypoint() -> int:
    """Translate expected command failures and keyboard cancellation to exit codes."""
    try:
        return main()
    except ValidationError as exc:
        print(
            "TRAJECTORY LEDGER LOCAL DIAGNOSTIC FAILED\n"
            "STATUS\n"
            "status=abstained\n"
            "ERROR\n"
            "phase1c_diagnostic_failed_closed=" + str(exc),
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        # Ctrl-C is an operator cancellation, not an application failure.  Keep
        # the terminal usable, avoid a traceback, and use the conventional
        # shell status for SIGINT so scripts can distinguish the interruption.
        print("\nCANCELLED operator_keyboard_interrupt", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(entrypoint())
