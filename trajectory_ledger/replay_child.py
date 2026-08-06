"""Declarative replay interpreter. Invoked only through the OS sandbox launcher."""

from __future__ import annotations

import json
import errno
import os
import socket
import sys
import hashlib
from pathlib import Path


def main() -> int:
    # The trusted launcher passes a canonical absolute root and the OS profile
    # binds this process to it. Re-resolving here would require directory reads
    # above that root and unnecessarily broaden the sandbox.
    root = Path(sys.argv[1])
    if not root.is_absolute():
        return 19
    request_path = root / "request.json"
    output_path = root / "result.json"
    request = json.loads(request_path.read_text(encoding="ascii"))
    if set(request) != {"operation", "baseline", "candidate", "expected_base_digest", "network_port"}:
        return 20
    operation = request["operation"]
    try:
        if operation == "network_probe":
            socket.socket().connect(("127.0.0.1", request["network_port"]))
            return 21
        if operation == "parent_write_probe":
            (root.parent / "forbidden.txt").write_text("probe", encoding="ascii")
            return 22
        if operation == "symlink_output_probe":
            output_path.write_text("probe", encoding="ascii")
            return 24
        if operation != "compare_documents":
            return 25
        baseline = request["baseline"]
        candidate = request["candidate"]
        if not isinstance(baseline, dict) or not isinstance(candidate, dict):
            return 27
        canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        baseline_digest = hashlib.sha256(canonical(baseline)).hexdigest()
        candidate_digest = hashlib.sha256(canonical(candidate)).hexdigest()
        entry_key = lambda entry: (entry["namespace"], entry["item"], entry["version"])
        baseline_quarantine = {entry_key(entry): entry for entry in baseline["quarantine"]}
        candidate_quarantine = {entry_key(entry): entry for entry in candidate["quarantine"]}
        ordered = lambda keys, source: [source[key] for key in sorted(keys)]
        result = {
            "mechanism_demonstration": "bounded_declarative_document_comparison",
            "evidence_label": "scripted_fixture_response",
            "outcome_label": "not_real_task_outcome",
            "baseline_digest": baseline_digest,
            "candidate_digest": candidate_digest,
            "candidate_base_bound": request["expected_base_digest"] == baseline_digest,
            "quarantine_added": ordered(candidate_quarantine.keys() - baseline_quarantine.keys(), candidate_quarantine),
            "quarantine_removed": ordered(baseline_quarantine.keys() - candidate_quarantine.keys(), baseline_quarantine),
            "quarantine_unchanged": ordered(baseline_quarantine.keys() & candidate_quarantine.keys(), baseline_quarantine),
            "documents_equal": baseline_digest == candidate_digest,
        }
        fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            json.dump(result, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return 0
    except OSError as exc:
        # Only access-denial errno values prove the sandbox caused the failure.
        if exc.errno in {errno.EPERM, errno.EACCES}:
            return 77
        return 26


if __name__ == "__main__":
    raise SystemExit(main())
