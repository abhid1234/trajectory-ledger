"""Deterministic Phase 1c diagnostic view over already-projected records."""

from __future__ import annotations

from typing import Any

from .core import canonical_bytes, digest, resolve_unique_source_record, strictest_classification
from .report import BANNED


PROPOSAL_BY_INVARIANT = {
    "parent_referent_present": ("workflow", "require_present_parent_reference"),
    "parent_edge_nonconflicting": ("workflow", "require_single_asserted_parent_target"),
    "memory_read_not_stale": ("policy", "require_current_memory_version_on_read"),
    "tainted_memory_not_reused_unquarantined": ("memory", "quarantine_exact_memory_version"),
}


def _proposal(finding: dict[str, Any], evidence_records: list[dict[str, Any]],
              base_projection_digest: str) -> dict[str, Any]:
    proposal_type, operation = PROPOSAL_BY_INVARIANT[finding["invariant"]]
    target = finding["intervention_ref"]
    proposal = {
        "proposal_version": "phase1c-declarative-2",
        "proposal_type": proposal_type,
        "operation": operation,
        "target_ref": target,
        "evidence_record_ids": [record["record_id"] for record in evidence_records],
        "base_projection_digest": base_projection_digest,
        "expiry": "end_of_saved_task_replay",
        "reversible": True,
        "reverse": {"operation": "restore_saved_task_baseline", "target_ref": target},
        "disposition": "eligible_for_saved_task_comparison" if proposal_type == "memory"
            else "declarative_review_only",
        "execution_authority": "none",
    }
    proposal["proposal_id"] = "proposal-" + digest(proposal)[:24]
    return proposal


def _replay_assessment(replay: dict[str, Any], expected_entry: dict[str, str] | None) -> dict[str, Any]:
    baseline_digest = replay.get("baseline_digest")
    candidate_digest = replay.get("candidate_digest")
    valid_digest = lambda value: (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
    checks = {
        "comparison_completed": replay.get("mechanism_demonstration") == "bounded_declarative_document_comparison",
        "saved_task_input_label": replay.get("evidence_label") == "scripted_fixture_response",
        "not_real_task_outcome": replay.get("outcome_label") == "not_real_task_outcome",
        "comparison_digests_present": valid_digest(baseline_digest) and valid_digest(candidate_digest),
        "candidate_base_bound": replay.get("candidate_base_bound") is True,
        "only_expected_change": expected_entry is not None and replay.get("quarantine_added") == [expected_entry]
            and replay.get("quarantine_removed") == [],
        "candidate_differs": replay.get("documents_equal") is False and baseline_digest != candidate_digest,
        "document_reversal_restored": replay.get("document_reversal_restored") is True,
    }
    return {
        "label": "saved_task_scripted_fixture_comparison",
        "checks": checks,
        "criteria_passed": all(checks.values()),
        "limits": ["inert_stored_trace_only", "scripted_fixture_response", "not_real_task_outcome", "document_comparison_only"],
    }


def _review_decision(points: list[dict[str, Any]], proposals: list[dict[str, Any]],
                     assessment: dict[str, Any]) -> dict[str, Any]:
    unsupported = any(point["status"] == "abstention_unsupported_evidence" for point in points)
    incomplete = any(
        point["status"] == "bounded_hypothesis"
        and point["uncertainty"]["evidence_limitations"]
        for point in points
    )
    supported = [point for point in points if point["status"] == "bounded_hypothesis"]
    memory = [proposal for proposal in proposals if proposal["proposal_type"] == "memory"]
    blockers: list[str] = []
    if not points:
        blockers.append("no_invariant_violation_observed")
    if unsupported or incomplete:
        blockers.append("evidence_support_incomplete_or_ambiguous")
    if len(supported) > 1:
        blockers.append("multiple_supported_failure_points_require_disambiguation")
    if len(supported) == 1 and not memory:
        blockers.append("proposal_not_eligible_for_saved_task_comparison")
    if len(supported) == 1 and len(memory) == 1 and not assessment["criteria_passed"]:
        blockers.append("saved_task_comparison_incomplete_or_failed")

    may_consider = not blockers and len(supported) == 1 and len(proposals) == 1 and len(memory) == 1
    if may_consider:
        next_step = "human_review_memory_candidate_and_evidence"
    elif "multiple_supported_failure_points_require_disambiguation" in blockers:
        next_step = "collect_discriminating_evidence_before_selecting_a_proposal"
    elif "evidence_support_incomplete_or_ambiguous" in blockers:
        next_step = "repair_or_extend_trace_evidence"
    elif "proposal_not_eligible_for_saved_task_comparison" in blockers:
        next_step = "human_review_declarative_proposal_without_execution"
    elif "saved_task_comparison_incomplete_or_failed" in blockers:
        next_step = "review_saved_task_comparison_fail_closed_checks"
    else:
        next_step = "review_trace_for_evidence_outside_frozen_invariants"
    return {
        "outcome": "human_may_consider_promotion" if may_consider else "abstain_no_promotion_recommendation",
        "blocking_reasons": blockers,
        "next_step": next_step,
    }


def build_diagnostic(records: list[dict[str, Any]], findings: list[dict[str, Any]],
                     replay: dict[str, Any], *,
                     proposal_base_digest: str | None = None) -> dict[str, Any]:
    """Build a report that cannot recommend review without supported evidence and replay."""
    points: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    expected_entry = None
    for finding in findings:
        if finding.get("result") != "hypothesis":
            continue
        refs = finding.get("evidence_for", [])
        resolved_records = (
            [resolve_unique_source_record(records, ref) for ref in refs]
            if isinstance(refs, list) and all(isinstance(ref, str) for ref in refs)
            else []
        )
        unambiguous_refs = len(resolved_records) == len(refs) and all(
            record is not None for record in resolved_records
        )
        evidence_records = (
            [record for record in resolved_records if record is not None]
            if refs and unambiguous_refs
            else []
        )
        supported = bool(refs) and unambiguous_refs
        point = {
            "invariant": finding["invariant"],
            "status": "bounded_hypothesis" if supported else "abstention_unsupported_evidence",
            "likely_failure_point_ref": finding["intervention_ref"] if supported else "none",
            "evidence_record_ids": [record["record_id"] for record in evidence_records],
            "confidence": "unknown",
            "bounds": ["single_stored_fixture", "deterministic_invariant_only", "no_causal_or_localization_claim"],
            "uncertainty": {
                "source_assertions_trusted": False,
                "unique_explanation": False,
                "alternatives": finding.get("alternatives", []),
                "evidence_limitations": finding.get("evidence_limitations", []),
            },
        }
        points.append(point)
        if supported:
            proposal = _proposal(
                finding,
                evidence_records,
                proposal_base_digest or digest(records),
            )
            proposals.append(proposal)
            if proposal["proposal_type"] == "memory":
                payload = evidence_records[0]["payload"]
                expected_entry = {key: payload[key] for key in ("namespace", "item", "version")}

    assessment = _replay_assessment(replay, expected_entry)
    review_decision = _review_decision(points, proposals, assessment)
    document = {
        "schema": "phase1c-local-diagnostic-2",
        "classification": strictest_classification(records),
        "scope": "local_synthetic_or_redacted_stored_trace",
        "likely_failure_points": points,
        "proposals": proposals,
        "saved_task_replay_comparison": assessment,
        "recommendation": review_decision["outcome"],
        "review_decision": review_decision,
        "authority": "human_review_only_no_external_action",
        "nonclaims": ["causal_proof", "efficacy", "localization_accuracy", "production_readiness"],
        "efficacy_gate_status": "blocked_separate_preregistration_required",
    }
    rendered = canonical_bytes(document).decode("ascii").lower()
    if any(term in rendered for term in BANNED):
        raise ValueError("banned_language")
    document["deterministic_digest"] = digest(document)
    return document


def render_diagnostic(document: dict[str, Any]) -> str:
    return canonical_bytes(document).decode("ascii") + "\n"
