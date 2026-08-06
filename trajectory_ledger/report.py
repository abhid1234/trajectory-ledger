"""Controlled-vocabulary deterministic text and JSON reports."""

from __future__ import annotations

import json
from typing import Any

from .core import canonical_bytes, digest

BANNED = ("root cause", "caused by", "because", "responsible for", "the failure was", "proves", "improves outcomes", "ready for promotion")
OUTCOMES = {"go", "narrow", "stop", "abstain"}
EFFICACY_GATE_STATUS = "blocked_separate_preregistration_required"


def report_document(run_id: str, findings: list[dict[str, Any]], replay: dict[str, Any], outcome: str, classification: str = "internal") -> dict[str, Any]:
    if outcome not in OUTCOMES:
        raise ValueError("invalid_human_self_attestation")
    evidence_limits = sorted({limit for finding in findings for limit in finding.get("evidence_limitations", [])})
    hypotheses = [finding for finding in findings if finding.get("result") == "hypothesis"]
    abstentions = [finding for finding in findings if finding.get("result") == "abstention"]
    if replay.get("mechanism_demonstration") == "bounded_declarative_document_comparison":
        replay_disposition = "bounded_comparison_completed"
    elif replay.get("reason") == "target_already_quarantined_after_violation":
        replay_disposition = "patch_blocked_target_already_quarantined"
    else:
        replay_disposition = "no_patch_or_replay"
    document = {
        "schema": "phase1b-evidence-report-1",
        "classification": classification,
        "run_id": run_id,
        "scope": "local_inert_mechanism_demonstration",
        "hypotheses": findings,
        "hypothesis_interpretation": {
            "ordering": "unordered_set",
            "unique_explanation": False,
            "ranking": "none",
        },
        "observed_invariant_results": [
            {"invariant": finding["invariant"], "result": finding["result"]} for finding in findings
        ],
        "patch_replay_disposition": replay_disposition,
        "evidence_completeness": "abstained_or_incomplete" if abstentions or evidence_limits else "bounded_fixture_complete",
        "replay": replay,
        "human_self_attestation": outcome,
        "limitations": ["source_assertions_untrusted", "hash_chain_unanchored", "document_reversal_only", "phase1b_blocked", *evidence_limits],
        "next_safe_human_action": "review_bounded_artifacts_without_external_action",
        "authority": "no_production_or_promotion_authority",
        "efficacy_gate_status": EFFICACY_GATE_STATUS,
    }
    rendered = canonical_bytes(document).decode("ascii").lower()
    if any(term in rendered for term in BANNED):
        raise ValueError("banned_language")
    document["deterministic_digest"] = digest(document)
    return document


def render_json(document: dict[str, Any]) -> str:
    return canonical_bytes(document).decode("ascii") + "\n"


def render_text(document: dict[str, Any]) -> str:
    # Values are fixed-vocabulary identifiers; JSON escaping fences presentation.
    lines = [
        "TRAJECTORY LEDGER PHASE 1B MECHANISM EVIDENCE",
        "observed_invariant_results=" + json.dumps(document["observed_invariant_results"], sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        "patch_replay_disposition=" + json.dumps(document["patch_replay_disposition"], ensure_ascii=True),
        "evidence_completeness=" + json.dumps(document["evidence_completeness"], ensure_ascii=True),
        "hypothesis_interpretation=" + json.dumps(document["hypothesis_interpretation"], sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        "limitations=" + json.dumps(document["limitations"], ensure_ascii=True),
        "next_safe_human_action=" + json.dumps(document["next_safe_human_action"], ensure_ascii=True),
        "scope=" + json.dumps(document["scope"], ensure_ascii=True),
        "run_id=" + json.dumps(document["run_id"], ensure_ascii=True),
        "human_self_attestation=" + json.dumps(document["human_self_attestation"], ensure_ascii=True),
        "authority=" + json.dumps(document["authority"], ensure_ascii=True),
        "efficacy_gate_status=" + json.dumps(document["efficacy_gate_status"], ensure_ascii=True),
    ]
    for finding in document["hypotheses"]:
        lines.append("invariant=" + json.dumps(finding["invariant"], ensure_ascii=True) + " result=" + json.dumps(finding["result"], ensure_ascii=True))
    lines.append("deterministic_digest=" + document["deterministic_digest"])
    output = "\n".join(lines) + "\n"
    if any(term in output.lower() for term in BANNED):
        raise ValueError("banned_language")
    return output
