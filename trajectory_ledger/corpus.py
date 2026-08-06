"""Machine-checked Phase 1b synthetic/redacted corpus contract."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .analysis import evaluate
from .core import Limits, ValidationError, canonical_bytes, ingest_fixture, read_bounded_regular_file, strictest_classification
from .report import BANNED, EFFICACY_GATE_STATUS

CATEGORY_FLOORS = {
    "clean_controls": 8,
    "missing_lineage": 5,
    "conflicting_lineage": 5,
    "stale_memory_boundaries": 5,
    "tainted_reuse_ordering": 8,
    "compound_multiple_hypotheses": 3,
    "abstention_and_truncation": 3,
    "classification_propagation": 3,
}
NEGATIVE_FLOOR = 16
CASE_KEYS = {
    "fixture", "family", "primary_category", "expected_result", "expected_invariants",
    "expected_patch_disposition", "expected_replay_disposition", "boundary", "classification",
    "claim_boundary",
}
NEGATIVE_KEYS = {"case_id", "category", "expected_error", "disposition", "boundary", "claim_boundary"}


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = read_bounded_regular_file(path.name, path.parent, Limits(max_bytes=64_000))
        value = json.loads(data)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("invalid_corpus_manifest") from exc
    if not isinstance(value, dict) or set(value) != {"schema", "efficacy_gate_status", "accepted", "negative_cases"}:
        raise ValidationError("invalid_corpus_manifest")
    if value["schema"] != "phase1b-evidence-manifest-1" or value["efficacy_gate_status"] != EFFICACY_GATE_STATUS:
        raise ValidationError("efficacy_gate_must_remain_blocked")
    return value


def _normalized_signature(records: list[dict[str, Any]], case: dict[str, Any]) -> bytes:
    identifiers: dict[str, str] = {}

    def token(value: str) -> str:
        if value not in identifiers:
            identifiers[value] = f"id{len(identifiers)}"
        return identifiers[value]

    structure: list[dict[str, Any]] = []
    for record in records:
        if record["record_type"] == "event":
            payload = record["payload"]
            structure.append({
                "type": "event", "kind": payload["event_kind"], "classification": payload["classification"],
                "id": token(payload["source_id"]), "parents": [token(item) for item in payload["parents"]],
            })
        elif record["record_type"] == "edge":
            payload = record["payload"]
            structure.append({
                "type": "edge", "kind": payload["edge_kind"], "classification": payload["classification"],
                "from": token(payload["from_ref"]), "to": token(payload["to_ref"]), "asserted": payload["source_asserted"],
            })
        elif record["record_type"] == "memory_op":
            payload = record["payload"]
            structure.append({
                "type": "memory_op", "action": payload["action"], "state": payload["state"],
                "classification": payload["classification"], "event": token(payload["event_ref"]),
                "namespace": token(payload["namespace"]), "item": token(payload["item"]), "version": token(payload["version"]),
            })
    return canonical_bytes({
        "structure": structure,
        "expected_invariants": sorted(case["expected_invariants"]),
        "patch": case["expected_patch_disposition"],
        "replay": case["expected_replay_disposition"],
    })


def validate_manifest(manifest_path: Path, fixtures_root: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    accepted = manifest["accepted"]
    negatives = manifest["negative_cases"]
    if not isinstance(accepted, list) or len(accepted) < sum(CATEGORY_FLOORS.values()):
        raise ValidationError("accepted_corpus_floor_not_met")
    if not isinstance(negatives, list) or len(negatives) < NEGATIVE_FLOOR:
        raise ValidationError("negative_case_floor_not_met")
    case_ids: set[str] = set()
    signatures: dict[str, set[bytes]] = {category: set() for category in CATEGORY_FLOORS}
    counts: Counter[str] = Counter()
    for case in accepted:
        if not isinstance(case, dict) or set(case) != CASE_KEYS:
            raise ValidationError("invalid_accepted_case")
        fixture = case["fixture"]
        if fixture in case_ids:
            raise ValidationError("duplicate_case_identifier")
        case_ids.add(fixture)
        category = case["primary_category"]
        if category not in CATEGORY_FLOORS:
            raise ValidationError("invalid_primary_category")
        if case["expected_result"] != "accept" or case["claim_boundary"] != "mechanism_only":
            raise ValidationError("invalid_claim_boundary")
        records = ingest_fixture(fixture, fixtures_root)
        observed = sorted(item["invariant"] for item in evaluate(records) if item["result"] == "hypothesis")
        if observed != sorted(case["expected_invariants"]):
            raise ValidationError("manifest_invariant_mismatch:" + fixture)
        if strictest_classification(records) != case["classification"]:
            raise ValidationError("manifest_classification_mismatch:" + fixture)
        tainted = next((item for item in evaluate(records) if item["invariant"] == "tainted_memory_not_reused_unquarantined" and item["result"] == "hypothesis"), None)
        patch_disposition = "not_emitted"
        replay_disposition = "not_run"
        if tainted is not None:
            evidence_ref = tainted["evidence_for"][0]
            target = next(record["payload"] for record in records if record["record_type"] == "memory_op" and record["payload"]["source_id"] == evidence_ref)
            key = tuple(target[name] for name in ("namespace", "item", "version"))
            quarantined = {
                tuple(record["payload"][name] for name in ("namespace", "item", "version"))
                for record in records if record["record_type"] == "memory_op" and record["payload"]["action"] == "quarantine"
            }
            if key in quarantined:
                patch_disposition = "blocked_already_quarantined"
            else:
                patch_disposition = "emitted"
                replay_disposition = "bounded_comparison_completed"
        if case["expected_patch_disposition"] != patch_disposition or case["expected_replay_disposition"] != replay_disposition:
            raise ValidationError("manifest_disposition_mismatch:" + fixture)
        signature = _normalized_signature(records, case)
        if signature in signatures[category]:
            raise ValidationError("duplicate_normalized_behavior_signature:" + category)
        signatures[category].add(signature)
        counts[category] += 1
    for category, floor in CATEGORY_FLOORS.items():
        if counts[category] < floor:
            raise ValidationError("category_floor_not_met:" + category)
    negative_ids: set[str] = set()
    for case in negatives:
        if not isinstance(case, dict) or set(case) != NEGATIVE_KEYS or case["claim_boundary"] != "mechanism_only":
            raise ValidationError("invalid_negative_case")
        if case["case_id"] in negative_ids or case["case_id"] in case_ids:
            raise ValidationError("duplicate_case_identifier")
        negative_ids.add(case["case_id"])
    prose = canonical_bytes(manifest).decode("ascii").lower()
    if any(term in prose for term in BANNED):
        raise ValidationError("banned_manifest_language")
    return {"accepted": len(accepted), "negative_cases": len(negatives), "category_counts": dict(sorted(counts.items())), "efficacy_gate_status": EFFICACY_GATE_STATUS}
