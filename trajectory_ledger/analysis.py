"""The four frozen deterministic Phase 1a invariants."""

from __future__ import annotations

from typing import Any

from .core import build_lineage

INVARIANTS = (
    "parent_referent_present",
    "parent_edge_nonconflicting",
    "memory_read_not_stale",
    "tainted_memory_not_reused_unquarantined",
)


def _finding(name: str, status: str, refs: list[str], alternative: str, evidence_limitations: list[str]) -> dict[str, Any]:
    return {
        "invariant": name,
        "result": "hypothesis" if status == "violated" else "abstention",
        "confidence": "unknown",
        "intervention_ref": refs[0] if refs else "none",
        "evidence_for": refs[:8],
        "evidence_against": [],
        "assumptions": ["fixture_assertions_untrusted", "deterministic_projection_only"],
        "alternatives": [alternative],
        "bounds": ["single_fixture", "phase1a_mechanism_only"],
        "replay_result": "not_run",
        "evidence_limitations": evidence_limitations,
    }


def evaluate(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lineage = build_lineage(records)
    evidence_limitations = ["lineage_truncated"] if any(item.get("truncated") for item in lineage) else []
    missing = [e["from_ref"] for e in lineage if not e.get("truncated") and e["edge_kind"] == "parent" and "missing" in e["states"]]
    conflicts = [e["from_ref"] for e in lineage if not e.get("truncated") and e["edge_kind"] == "parent" and "conflicting" in e["states"]]
    memory = [(r["sequence"], r["payload"]) for r in records if r["record_type"] == "memory_op"]
    stale = [m["source_id"] for _, m in memory if m["action"] == "read" and m["state"] == "stale"]
    tainted_seen: set[tuple[str, str, str]] = set()
    quarantined: set[tuple[str, str, str]] = set()
    reused: list[str] = []
    for _, item in sorted(memory):
        key = (item["namespace"], item["item"], item["version"])
        if item["action"] == "quarantine":
            quarantined.add(key)
            continue
        if item["action"] == "read" and key in tainted_seen and key not in quarantined:
            reused.append(item["source_id"])
        if item["state"] == "tainted":
            tainted_seen.add(key)
    checks = (
        (INVARIANTS[0], missing, "source_reference_may_be_incomplete"),
        (INVARIANTS[1], conflicts, "multiple_source_assertions_may_coexist"),
        (INVARIANTS[2], stale, "fixture_state_label_may_be_inaccurate"),
        (INVARIANTS[3], reused, "taint_label_or_quarantine_history_may_be_incomplete"),
    )
    return [_finding(name, "violated" if refs else "unknown", refs, alternative, evidence_limitations) for name, refs, alternative in checks]
