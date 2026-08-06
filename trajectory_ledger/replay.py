"""Fail-closed macOS sandbox-exec launcher and denial proof."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .core import ValidationError, canonical_bytes, digest, is_identifier

DOCUMENT_KEYS = {"items", "quarantine"}
ENTRY_KEYS = {"namespace", "item", "version"}
RESULT_KEYS = {
    "mechanism_demonstration", "evidence_label", "outcome_label",
    "baseline_digest", "candidate_digest", "candidate_base_bound",
    "quarantine_added", "quarantine_removed", "quarantine_unchanged",
    "documents_equal",
}


def validate_document(document: Any) -> None:
    if not isinstance(document, dict) or set(document) != DOCUMENT_KEYS:
        raise ValidationError("invalid_replay_document")
    item_keys: set[tuple[str, str, str]] = set()
    for key in ("items", "quarantine"):
        collection = document[key]
        if not isinstance(collection, list) or len(collection) > 128:
            raise ValidationError("invalid_replay_document")
        seen: set[tuple[str, str, str]] = set()
        for entry in collection:
            if not isinstance(entry, dict) or set(entry) != ENTRY_KEYS:
                raise ValidationError("invalid_replay_document")
            values = tuple(entry[name] for name in ("namespace", "item", "version"))
            if not all(is_identifier(value) for value in values) or values in seen:
                raise ValidationError("invalid_replay_document")
            seen.add(values)
        source_keys = [tuple(entry[name] for name in ("namespace", "item", "version")) for entry in collection]
        if source_keys != sorted(source_keys):
            raise ValidationError("noncanonical_replay_document")
        if key == "items":
            item_keys = seen
        elif not seen <= item_keys:
            raise ValidationError("invalid_replay_document")


def validate_transition(baseline: dict[str, Any], candidate: dict[str, Any]) -> None:
    """Allow only an unchanged state or one additive quarantine transition."""
    validate_document(baseline)
    validate_document(candidate)
    if candidate["items"] != baseline["items"]:
        raise ValidationError("replay_items_changed")
    entry_key = lambda entry: tuple(entry[name] for name in ("namespace", "item", "version"))
    baseline_quarantine = {entry_key(entry) for entry in baseline["quarantine"]}
    candidate_quarantine = {entry_key(entry) for entry in candidate["quarantine"]}
    if not baseline_quarantine <= candidate_quarantine:
        raise ValidationError("replay_quarantine_removed")
    if len(candidate_quarantine - baseline_quarantine) > 1:
        raise ValidationError("replay_transition_unbounded")


def validate_replay_result(result: Any, baseline: dict[str, Any] | None = None, candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        raise ValidationError("invalid_replay_result")
    if result["mechanism_demonstration"] != "bounded_declarative_document_comparison":
        raise ValidationError("invalid_replay_result")
    if result["evidence_label"] != "scripted_fixture_response" or result["outcome_label"] != "not_real_task_outcome":
        raise ValidationError("invalid_replay_result")
    if not all(isinstance(result[key], bool) for key in ("candidate_base_bound", "documents_equal")):
        raise ValidationError("invalid_replay_result")
    for key in ("baseline_digest", "candidate_digest"):
        value = result[key]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValidationError("invalid_replay_result")
    for key in ("quarantine_added", "quarantine_removed", "quarantine_unchanged"):
        validate_document({"items": result[key], "quarantine": []})
    if (baseline is None) != (candidate is None):
        raise ValidationError("invalid_replay_result")
    if baseline is not None and candidate is not None:
        entry_key = lambda entry: tuple(entry[name] for name in ("namespace", "item", "version"))
        baseline_quarantine = {entry_key(entry): entry for entry in baseline["quarantine"]}
        candidate_quarantine = {entry_key(entry): entry for entry in candidate["quarantine"]}
        expected = {
            "baseline_digest": digest(baseline),
            "candidate_digest": digest(candidate),
            "candidate_base_bound": True,
            "quarantine_added": [candidate_quarantine[key] for key in sorted(candidate_quarantine.keys() - baseline_quarantine.keys())],
            "quarantine_removed": [baseline_quarantine[key] for key in sorted(baseline_quarantine.keys() - candidate_quarantine.keys())],
            "quarantine_unchanged": [baseline_quarantine[key] for key in sorted(baseline_quarantine.keys() & candidate_quarantine.keys())],
            "documents_equal": baseline == candidate,
        }
        if any(result[key] != value for key, value in expected.items()):
            raise ValidationError("replay_result_state_mismatch")
    return result


def _quoted(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace('"', '\\"')


def _profile(run_root: Path) -> str:
    package_root = Path(__file__).resolve().parent.parent
    python_root = Path(sys.base_prefix).resolve()
    rules = [
        "(version 1)",
        "(deny default)",
        "(allow process-exec (literal \"%s\"))" % _quoted(Path(sys.executable).resolve()),
        "(allow process-fork)",
        "(allow sysctl-read)",
        # CPython resolves absolute paths from the filesystem root during
        # startup. This grants only the root directory entry, not its subtree.
        "(allow file-read* (literal \"/\"))",
        "(allow file-read* (subpath \"/System\"))",
        "(allow file-read* (subpath \"/usr/lib\"))",
        "(allow file-read* (subpath \"%s\"))" % _quoted(python_root),
        "(allow file-read* (subpath \"%s\"))" % _quoted(package_root),
        "(allow file-read* (subpath \"%s\"))" % _quoted(run_root),
        "(allow file-write* (subpath \"%s\"))" % _quoted(run_root),
        "(deny network*)",
    ]
    return "\n".join(rules)


def sandbox_available() -> bool:
    if sys.platform != "darwin" or shutil.which("sandbox-exec") != "/usr/bin/sandbox-exec":
        return False
    probe = subprocess.run(
        ["/usr/bin/sandbox-exec", "-p", "(version 1) (allow default)", "/usr/bin/true"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=2,
        check=False,
    )
    return probe.returncode == 0


def _invoke(root: Path) -> subprocess.CompletedProcess[bytes]:
    root = root.resolve(strict=True)
    profile = root / "profile.sb"
    profile.write_text(_profile(root), encoding="ascii")
    executable = str(Path(sys.executable).resolve())
    child = str(Path(__file__).resolve().with_name("replay_child.py"))
    command = [
        "/usr/bin/sandbox-exec", "-f", str(profile), executable, "-I", "-B",
        child, str(root),
    ]
    env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, check=False)


def _write_request(root: Path, operation: str, baseline: dict[str, Any] | None = None, candidate: dict[str, Any] | None = None, expected_base_digest: str = "", network_port: int = 9) -> None:
    request = {"operation": operation, "baseline": baseline or {"items": [], "quarantine": []}, "candidate": candidate or {"items": [], "quarantine": []}, "expected_base_digest": expected_base_digest, "network_port": network_port}
    (root / "request.json").write_bytes(canonical_bytes(request))


def prove_isolation() -> dict[str, bool]:
    if not sandbox_available():
        raise ValidationError("os_sandbox_unavailable_fail_closed")
    results: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="tl-proof-") as outer:
        outer_path = Path(outer)
        for operation in ("network_probe", "parent_write_probe"):
            root = outer_path / operation
            root.mkdir()
            listener = None
            port = 9
            if operation == "network_probe":
                listener = socket.socket()
                listener.bind(("127.0.0.1", 0))
                listener.listen(1)
                listener.settimeout(0.05)
                port = listener.getsockname()[1]
            _write_request(root, operation, network_port=port)
            try:
                process = _invoke(root)
                connected = False
                if listener is not None:
                    try:
                        connection, _ = listener.accept()
                    except TimeoutError:
                        pass
                    else:
                        connected = True
                        connection.close()
                results[operation] = process.returncode == 77 and not connected
            finally:
                if listener is not None:
                    listener.close()
            if operation == "parent_write_probe" and (outer_path / "forbidden.txt").exists():
                results[operation] = False
        root = outer_path / "symlink_output_probe"
        root.mkdir()
        target = outer_path / "symlink-target.json"
        (root / "result.json").symlink_to(target)
        _write_request(root, "symlink_output_probe")
        process = _invoke(root)
        results["symlink_output_probe"] = process.returncode == 77 and not target.exists()
    if not all(results.values()):
        raise ValidationError("os_sandbox_positive_control_failed")
    return results


def replay(baseline: dict[str, Any], candidate: dict[str, Any], expected_base_digest: str) -> dict[str, Any]:
    validate_transition(baseline, candidate)
    if not isinstance(expected_base_digest, str) or expected_base_digest != digest(baseline):
        raise ValidationError("replay_base_mismatch")
    prove_isolation()
    with tempfile.TemporaryDirectory(prefix="tl-replay-") as directory:
        root = Path(directory)
        _write_request(root, "compare_documents", baseline, candidate, expected_base_digest)
        process = _invoke(root)
        if process.returncode != 0:
            raise ValidationError("sandboxed_replay_failed_closed")
        output = root / "result.json"
        if output.is_symlink() or output.stat().st_size > 4096:
            raise ValidationError("invalid_replay_output")
        try:
            result = json.loads(output.read_text(encoding="ascii"))
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise ValidationError("invalid_replay_output") from exc
        return validate_replay_result(result, baseline, candidate)
