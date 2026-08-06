"""One base-bound, declarative memory-quarantine patch."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .core import ValidationError, digest, is_identifier

PATCH_KEYS = {"patch_version", "base_hash", "operation", "namespace", "item", "version", "expiry", "hypothesis_ref", "reverse"}


def build_patch(manifest: dict[str, Any], namespace: str, item: str, version: str, hypothesis_ref: str) -> dict[str, Any]:
    for value in (namespace, item, version, hypothesis_ref):
        if not is_identifier(value):
            raise ValidationError("invalid_patch_identifier")
    return {
        "patch_version": "memory-quarantine-1",
        "base_hash": digest(manifest),
        "operation": "quarantine",
        "namespace": namespace,
        "item": item,
        "version": version,
        "expiry": "end-of-replay",
        "hypothesis_ref": hypothesis_ref,
        "reverse": {"operation": "remove_quarantine", "namespace": namespace, "item": item, "version": version},
    }


def validate_patch(patch: dict[str, Any], manifest: dict[str, Any]) -> None:
    if set(patch) != PATCH_KEYS or patch.get("patch_version") != "memory-quarantine-1" or patch.get("operation") != "quarantine":
        raise ValidationError("invalid_or_executable_patch_fields")
    if patch.get("base_hash") != digest(manifest) or patch.get("expiry") != "end-of-replay":
        raise ValidationError("patch_base_or_expiry_mismatch")
    reverse = patch.get("reverse")
    if not isinstance(reverse, dict) or set(reverse) != {"operation", "namespace", "item", "version"} or reverse.get("operation") != "remove_quarantine":
        raise ValidationError("invalid_reverse_delta")
    for key in ("namespace", "item", "version", "hypothesis_ref"):
        if not is_identifier(patch.get(key)):
            raise ValidationError("invalid_patch_identifier")
    if any(reverse[k] != patch[k] for k in ("namespace", "item", "version")):
        raise ValidationError("reverse_delta_mismatch")


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if set(manifest) != {"items", "quarantine"}:
        raise ValidationError("invalid_memory_manifest")
    if not isinstance(manifest["items"], list) or not isinstance(manifest["quarantine"], list):
        raise ValidationError("invalid_memory_manifest")
    for collection in (manifest["items"], manifest["quarantine"]):
        for entry in collection:
            if not isinstance(entry, dict) or set(entry) != {"namespace", "item", "version"}:
                raise ValidationError("invalid_memory_manifest")
            if not all(is_identifier(entry[key]) for key in ("namespace", "item", "version")):
                raise ValidationError("invalid_memory_manifest")


def apply_patch(manifest: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    validate_patch(patch, manifest)
    _validate_manifest(manifest)
    candidate = deepcopy(manifest)
    entry = {k: patch[k] for k in ("namespace", "item", "version")}
    if candidate["items"].count(entry) != 1:
        raise ValidationError("patch_target_missing_or_ambiguous")
    if entry in candidate["quarantine"]:
        raise ValidationError("patch_target_already_quarantined")
    candidate["quarantine"].append(entry)
    candidate["quarantine"].sort(key=lambda value: (value["namespace"], value["item"], value["version"]))
    return candidate


def reverse_patch(candidate: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    _validate_manifest(candidate)
    restored = deepcopy(candidate)
    entry = {k: patch[k] for k in ("namespace", "item", "version")}
    if restored.get("quarantine", []).count(entry) != 1:
        raise ValidationError("reverse_target_mismatch")
    restored["quarantine"].remove(entry)
    return restored
