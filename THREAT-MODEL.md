# Trajectory Ledger — Threat Model

Status: first-gate model for local, inert-fixture operation. It does not authorize implementation or production use.

## Assets, actors, and trust assumptions

Protected assets are raw trace contents, local secrets, lineage integrity, evaluator independence, patch and replay integrity, filesystem boundaries, operator authority, and rollback evidence. Attackers may control any trace string, claimed path/ID/edge, fixture metadata, artifact, memory entry, or evaluator-targeting text. Honest inputs may also be malformed.

The local operator and minimal runtime are trusted only within their declared roles. Source traces, adapters, analyzers, evaluators, and candidate patches are not trusted merely because they are local. No ambient credentials are required. Network is denied. The prototype has no production identity or write capability.

## Threats and required controls

| Threat | Failure path | Prevent / detect / recover controls |
|---|---|---|
| Trace injection | Trace text instructs an analyzer, evaluator, renderer, or operator to act | Phase 1a stores no source-derived prose; schema/value constraints; escape configured labels and operator text; deterministic core; no tool authority for analyzers; injection canaries; show provenance; abstain on instruction/data ambiguity |
| PII or secrets | Raw values leak through logs, hashes, reports, derived hypotheses, or fixtures | No raw retention; typed allowlist; unknown/free-text values become classification, length, and a redaction marker only; no source-derived digest; derived-label propagation; bounded canary scans |
| Path traversal | Claimed paths, links, archives, or artifact names escape allowed roots | Resolve and compare canonical paths; descriptor-relative access where available; reject absolute/parent traversal, symlinks, hard-link surprises, devices, sockets, archives, and filename-derived output paths |
| Unsafe deserialization | Crafted input triggers object construction or code execution | Strict bounded JSON subset; no pickle/YAML object tags/eval/dynamic imports; depth/string/count limits; schema validation before projection; no target-code execution |
| Forged lineage | Source invents parents, identities, ordering, or hashes | Separate source assertions from internally present referents; locally assigned IDs/sequences; hash chain; missing/conflicting edge state; never repair silently; integrity failure forces abstention |
| Evaluator capture (Phase 1b) | Patch optimizes judge quirks or injects evaluator instructions | Deferred: frozen evaluator cards; clean holdout and placebo; independent rubric/source; analyzer/evaluator separation; subgroup reporting; rotate only via new preregistration |
| Replay side effects | Replay calls network/tools, writes broadly, or mutates source fixtures | Separate process; OS-enforced no-network and filesystem jail; declarative interpreter only; read-only inputs; fresh per-run directory; allowlisted outputs and quotas; positive-control violations |
| Privilege escalation | Patch broadens capabilities, paths, delegation, or approvals | Patch schema allowlists narrow fields; monotonic authority rule; no credentials; base-hash binding; reject executable content/new paths/network; human gate has only next-local-gate authority |
| Poisoning | Untrusted episode becomes trusted memory/policy or biases suite | Provenance/taint retained through derivation; quarantine by default; no automatic memory write; contradiction evidence; clean controls; held-out suite; one-change rule; expiry and reversible manifests |
| Reversal failure | Candidate document cannot be reversed or evidence/config disappears | Append-only patch/review records; base and candidate hashes; mandatory reverse delta; immutable fixture/environment manifests; document-level reversal rehearsal; Phase 1a records `stop` on mismatch |

## Abuse and reliability cases

- **Resource exhaustion:** cap files, bytes, nesting, events, fan-out, graph depth, repetitions, runtime, and outputs; terminate cleanly and append a bounded receipt.
- **Hash disclosure:** unknown/free-text fields are never hashed into retained artifacts because low-entropy hashes are guessing oracles. Structural envelope and document hashes cover only the redacted projection.
- **TOCTOU/file replacement:** open validated regular files without following links, then verify identity/size; copy permitted fixture bytes to the isolated run before parsing.
- **CSV/formula/HTML/terminal injection:** the first report format is escaped plain text or strict data; prefix dangerous spreadsheet cells if export is later added; never render trace HTML.
- **Rollback as attack:** only an authorized human may select a known base-bound version; document-level reversal cannot expand authority and makes no semantic rollback claim.
- **Algorithmic denial:** redactor and canary matching are linear-time with per-field budgets; backtracking regular expressions are forbidden.
- **Downstream prompt injection:** Phase 1a reports contain no source-derived trace prose and are explicitly not safe agent input. If a later phase permits quoted trace data, it must provenance-fence that data behind a separate review.
- **Denial through abstention (Phase 1b):** deferred coverage/abstention denominators must be preregistered; safety-critical ambiguity results in `abstain`, never promotion.

## Security acceptance tests

The prototype cannot pass unless positive controls prove that the OS isolation rejects an outbound connection, parent-directory write, symlinked output, oversize/deep payload, and executable patch field. Tests must also show zero planted-canary matches outside the typed projection for the enumerated encodings, rejection of traversal/link/special-file cases, detection of in-place record modification, honest non-detection of unanchored truncation/rewrite-from-genesis, safe escaped rendering, and document-level reversal to the baseline digest.

## Residual risk

Local isolation can be misconfigured; redaction cannot recognize every secret; ruleset upgrades cannot retroactively protect no-raw records, so affected records must be quarantined or re-ingested; hashes prove limited consistency rather than truth; a local chain cannot detect rewrite-from-genesis without an external anchor; evaluators may share hidden biases; replay cannot reproduce external state; and a reversible manifest does not guarantee semantic rollback. These risks keep the first slice local, inert, human-gated, and non-production.
