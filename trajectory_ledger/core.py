"""Bounded ingestion, canonical records, ledger integrity, and lineage."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "phase1a-1"
REDACTOR_VERSION = "typed-allowlist-1"
RECORD_TYPES = frozenset(
    {"run", "event", "edge", "memory_op", "hypothesis", "patch", "replay", "gate_decision"}
)
IDENT_MAX = 48
ENUMS = {
    "classification": {"public", "internal", "sensitive", "unknown"},
    "event_kind": {"start", "step", "tool", "memory", "evaluate", "finish", "error"},
    "edge_kind": {"parent", "input", "output", "memory", "evaluation"},
    "memory_action": {"read", "write", "quarantine", "expire"},
    "memory_state": {"clean", "stale", "tainted", "quarantined", "expired"},
}
CLASSIFICATION_RANK = {"public": 0, "internal": 1, "sensitive": 2, "unknown": 3}


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Limits:
    max_bytes: int = 64_000
    max_records: int = 128
    max_depth: int = 12
    max_string_bytes: int = 256
    max_edges: int = 256


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def strictest_classification(records: list[dict[str, Any]]) -> str:
    values = [record.get("classification", "unknown") for record in records]
    if any(value not in CLASSIFICATION_RANK for value in values):
        raise ValidationError("invalid_record_classification")
    return max(values, key=CLASSIFICATION_RANK.__getitem__, default="unknown")


def is_identifier(value: Any) -> bool:
    if not isinstance(value, str) or not (1 <= len(value.encode("utf-8")) <= IDENT_MAX):
        return False
    return all(c.isascii() and (c.isalnum() or c in "_-.:") for c in value)


def _measure(value: Any, depth: int, limits: Limits) -> None:
    if depth > limits.max_depth:
        raise ValidationError("payload_too_deep")
    if isinstance(value, str):
        if len(value.encode("utf-8")) > limits.max_string_bytes:
            raise ValidationError("string_too_large")
        return
    if isinstance(value, list):
        if len(value) > limits.max_records * 4:
            raise ValidationError("collection_too_large")
        for item in value:
            _measure(item, depth + 1, limits)
    elif isinstance(value, dict):
        if len(value) > 32:
            raise ValidationError("object_too_large")
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValidationError("non_string_key")
            _measure(key, depth + 1, limits)
            _measure(item, depth + 1, limits)
    elif value is not None and not isinstance(value, (bool, int)):
        raise ValidationError("unsupported_json_type")


def read_bounded_regular_file(path: Path, allowed_root: Path, limits: Limits = Limits()) -> bytes:
    """Read one bounded regular file without permitting links or root escape."""
    path = Path(path)
    allowed_root = Path(allowed_root)
    root = allowed_root.resolve(strict=True)
    if path.is_absolute():
        candidate = path
    else:
        candidate = root / path
    if candidate.is_symlink():
        raise ValidationError("symlink_input")
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValidationError("path_outside_allowed_root") from exc
    fd = os.open(resolved, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValidationError("input_not_single_regular_file")
        if info.st_size > limits.max_bytes:
            raise ValidationError("payload_too_large")
        data = os.read(fd, limits.max_bytes + 1)
        if len(data) != info.st_size or len(data) > limits.max_bytes:
            raise ValidationError("input_changed_or_too_large")
        return data
    finally:
        os.close(fd)


def _unknown(value: Any) -> dict[str, Any]:
    raw = canonical_bytes(value)
    # Do not persist an unsalted digest of untrusted prose. For low-entropy
    # secrets (tokens, email addresses, flags), such a digest is a practical
    # offline guessing oracle. The bounded shape is sufficient to prove that a
    # field was removed without retaining source-derived content.
    return {"classification": "unknown", "byte_length": len(raw), "redacted": True}


def _ident(value: Any, field: str) -> str:
    if not is_identifier(value):
        raise ValidationError(f"invalid_identifier:{field}")
    return value


def _enum(value: Any, field: str) -> str:
    if value not in ENUMS[field]:
        raise ValidationError(f"invalid_enum:{field}")
    return value


def _ident_list(value: Any, field: str, maximum: int = 16) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValidationError(f"invalid_list:{field}")
    return [_ident(item, field) for item in value]


def _project_record(source: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(source, dict) or source.get("type") not in {"event", "edge", "memory_op"}:
        raise ValidationError("invalid_source_record_type")
    kind = source["type"]
    common = {"type", "id", "classification"}
    payload: dict[str, Any] = {"source_id": _ident(source.get("id"), "id")}
    payload["classification"] = _enum(source.get("classification", "internal"), "classification")
    if kind == "event":
        allowed = common | {"kind", "actor", "state_version", "parents"}
        payload.update(
            event_kind=_enum(source.get("kind"), "event_kind"),
            actor=_ident(source.get("actor"), "actor"),
            state_version=_ident(source.get("state_version"), "state_version"),
            parents=_ident_list(source.get("parents", []), "parents"),
        )
    elif kind == "edge":
        allowed = common | {"kind", "from", "to", "source_asserted"}
        payload.update(
            edge_kind=_enum(source.get("kind"), "edge_kind"),
            from_ref=_ident(source.get("from"), "from"),
            to_ref=_ident(source.get("to"), "to"),
            source_asserted=source.get("source_asserted"),
        )
        if not isinstance(payload["source_asserted"], bool):
            raise ValidationError("invalid_boolean:source_asserted")
    else:
        allowed = common | {"action", "namespace", "item", "version", "state", "event"}
        payload.update(
            action=_enum(source.get("action"), "memory_action"),
            namespace=_ident(source.get("namespace"), "namespace"),
            item=_ident(source.get("item"), "item"),
            version=_ident(source.get("version"), "version"),
            state=_enum(source.get("state"), "memory_state"),
            event_ref=_ident(source.get("event"), "event"),
        )
    unknown = {key: _unknown(source[key]) for key in sorted(source.keys() - allowed)}
    if unknown:
        payload["redacted_fields"] = unknown
    return kind, payload


def make_envelope(record_type: str, run_id: str, sequence: int, payload: dict[str, Any], prev_hash: str) -> dict[str, Any]:
    if record_type not in RECORD_TYPES:
        raise ValidationError("unknown_record_type")
    content_hash = digest(payload)
    identity = {"record_type": record_type, "run_id": run_id, "sequence": sequence, "content_hash": content_hash}
    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": "rec-" + digest(identity)[:32],
        "record_type": record_type,
        "run_id": run_id,
        "sequence": sequence,
        "observed_at": None,
        "ingested_at": "deterministic-fixture-time",
        "producer": "trajectory-ledger-phase1a",
        "source_ref": "local-inert-fixture",
        "classification": payload.get("classification", "internal"),
        "content_hash": content_hash,
        "prev_record_hash": prev_hash,
        "payload": payload,
    }


def ingest_fixture(path: Path, allowed_root: Path, limits: Limits = Limits()) -> list[dict[str, Any]]:
    data = read_bounded_regular_file(path, allowed_root, limits)
    try:
        document = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise ValidationError("invalid_json") from exc
    _measure(document, 0, limits)
    if not isinstance(document, dict) or set(document) != {"fixture_version", "run_id", "records", "manifest"}:
        raise ValidationError("invalid_fixture_shape")
    if document["fixture_version"] != "phase1a-1" or not is_identifier(document["run_id"]):
        raise ValidationError("invalid_fixture_header")
    records = document["records"]
    manifest = document["manifest"]
    if not isinstance(records, list) or len(records) > limits.max_records or not isinstance(manifest, dict):
        raise ValidationError("invalid_fixture_collections")
    if set(manifest) != {"fixture", "environment", "seed"}:
        raise ValidationError("invalid_manifest")
    run_id = document["run_id"]
    source_projected = [_project_record(record) for record in records]
    source_classification = max(
        (payload["classification"] for _, payload in source_projected),
        key=CLASSIFICATION_RANK.__getitem__,
        default="internal",
    )
    run_payload = {
        "classification": source_classification,
        "fixture": _ident(manifest["fixture"], "fixture"),
        "environment": _ident(manifest["environment"], "environment"),
        "seed": manifest["seed"],
        "fixture_version": "phase1a-1",
        "redactor_version": REDACTOR_VERSION,
        "invariant_version": "invariants-1",
        "patch_version": "memory-quarantine-1",
    }
    if not isinstance(run_payload["seed"], int) or isinstance(run_payload["seed"], bool):
        raise ValidationError("invalid_seed")
    projected = [("run", run_payload)] + source_projected
    if sum(1 for kind, _ in projected if kind == "edge") > limits.max_edges:
        raise ValidationError("too_many_edges")
    envelopes: list[dict[str, Any]] = []
    prev = "GENESIS"
    for sequence, (record_type, payload) in enumerate(projected):
        envelope = make_envelope(record_type, run_id, sequence, payload, prev)
        envelopes.append(envelope)
        prev = digest(envelope)
    return envelopes


def write_ledger(records: list[dict[str, Any]], path: Path) -> None:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError as exc:
        raise ValidationError("ledger_already_exists") from exc
    with os.fdopen(fd, "w", encoding="ascii", newline="\n") as handle:
        for record in records:
            handle.write(canonical_bytes(record).decode("ascii") + "\n")


def verify_ledger(path: Path) -> tuple[bool, str]:
    prev = "GENESIS"
    try:
        lines = path.read_text(encoding="ascii").splitlines()
        for sequence, line in enumerate(lines):
            record = json.loads(line)
            if record["sequence"] != sequence or record["prev_record_hash"] != prev:
                return False, "chain_mismatch"
            if digest(record["payload"]) != record["content_hash"]:
                return False, "content_mismatch"
            expected_id = "rec-" + digest({"record_type": record["record_type"], "run_id": record["run_id"], "sequence": sequence, "content_hash": record["content_hash"]})[:32]
            if record["record_id"] != expected_id:
                return False, "record_id_mismatch"
            prev = digest(record)
    except (OSError, UnicodeError, KeyError, ValueError, TypeError):
        return False, "invalid_ledger"
    return True, "observable_chain_valid_unanchored_truncation_not_detectable"


def resolve_unique_source_record(
    records: list[dict[str, Any]], source_id: str
) -> dict[str, Any] | None:
    """Return one projected source record, or abstain when absent or ambiguous."""
    matches = [
        record
        for record in records
        if record["record_type"] in {"event", "edge", "memory_op"}
        and record["payload"].get("source_id") == source_id
    ]
    return matches[0] if len(matches) == 1 else None


def build_lineage(records: list[dict[str, Any]], max_depth: int = 16) -> list[dict[str, Any]]:
    ids = {r["payload"].get("source_id") for r in records if r["record_type"] in {"event", "edge", "memory_op"}}
    edges = [r["payload"] for r in records if r["record_type"] == "edge"]
    pairs: dict[tuple[str, str], set[str]] = {}
    for edge in edges:
        pairs.setdefault((edge["from_ref"], edge["edge_kind"]), set()).add(edge["to_ref"])
    result = []
    for edge in edges[:max_depth]:
        states = []
        if edge["source_asserted"]:
            states.append("source_asserted")
        states.append("referent_present" if edge["from_ref"] in ids and edge["to_ref"] in ids else "missing")
        if len(pairs[(edge["from_ref"], edge["edge_kind"])]) > 1:
            states.append("conflicting")
        result.append({"from_ref": edge["from_ref"], "to_ref": edge["to_ref"], "edge_kind": edge["edge_kind"], "states": states})
    # Parent arrays are represented as derived claims, never silently promoted to source edges.
    for record in records:
        if record["record_type"] == "event":
            for parent in record["payload"]["parents"]:
                result.append({"from_ref": record["payload"]["source_id"], "to_ref": parent, "edge_kind": "parent", "states": ["derived", "referent_present" if parent in ids else "missing"]})
    if len(edges) > max_depth:
        result.append({"truncated": True, "represented": max_depth, "total": len(edges), "reason": "declared_lineage_limit"})
    return result
