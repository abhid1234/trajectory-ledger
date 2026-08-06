# Trajectory Ledger — Decision Log

## 2026-08-01 — Freeze the hardened local diagnostic build

Decision: close the approved build phase at the existing local-only diagnostic
boundary. Provide an operator demo, developer verification, evidence mapping,
limitations, and a release checklist whose disposition remains `NOT RELEASE
READY` until every required human/review item is satisfied. Tests, replay, or a
`human_may_consider_promotion` recommendation cannot promote the build or change
release state automatically. The later efficacy/localization study remains
separate and unstarted.

Reason: the implementation and deterministic mechanism evidence are sufficient
for a local handoff, but do not supply causal, efficacy, localization, privacy,
security-release, operational-support, or production evidence.

## 2026-08-01 — Preserve inspectable proposals on replay failure

Decision: after successful bounded ingest and proposal validation, a failed or unavailable jailed saved-task comparison produces a sanitized `saved_task_replay_failed_closed` status, no replay ledger record, and an abstention recommendation. The declarative proposal remains inspectable and reversible. This preserves the smallest useful diagnostic flow without treating an unavailable comparison as evidence and without adding an in-process fallback.

The proposal identifier is bound to the validated projected evidence before any
replay result or operator attestation is available. In-process code may construct
the inert declarative baseline/candidate documents needed by the jailed child;
it never treats that construction as replay evidence. A validation, OS,
subprocess, or timeout failure discards the comparison result, emits no replay
record, and exposes only the fixed sanitized failure label. Unknown-content
classification remains an internal typed-projection policy and is not evidence
that arbitrary future secret shapes will be recognized.

Status: decisions for the first documentation gate. Rankings concern the bounded first slice, not universal product quality.

## D-001 — Build a local vertical prototype of Trajectory Ledger

Decision: recommend a framework-neutral, local, read-only evidence and replay layer whose output is a human-gated candidate manifest. Confidence: medium; this is a falsifiable product hypothesis, not validation.

Why: the source brief identifies the bridge from trace lineage to reversible evaluation as a plausible cross-topic bottleneck, while explicitly warning that localization may be non-identifiable and replay may not transfer. The first slice therefore tests the bridge without granting production authority.

## Ranked alternatives

| Rank | Alternative | Decision and rationale | Revisit trigger |
|---:|---|---|---|
| 1 | Extend an existing observability platform | Best commercialization/integration alternative; incumbents already own ingestion and UI. Not first because this gate must test the causal/replay layer without platform coupling. | A platform exposes stable local plugin APIs or prototype users reject a standalone journey. |
| 2 | Deterministic-invariants-only | Safest fallback and strongest baseline. It avoids evaluator capture and causal overclaiming but cannot test bounded hypothesis/replay value alone. | Localization misses baseline, labels are unreliable, or replay is inconclusive. |
| 3 | Memory Governor | Narrow, practical read/write/quarantine/forget policy with clearer scope. It tests only the memory branch, not delegation/artifact lineage. | Most diagnosed failures are memory-policy failures or users cannot supply orchestration traces. |
| 4 | ArtifactBus | Immediately useful typed, immutable coordination substrate; risks turning this documentation-only read layer into workflow infrastructure and production state. | Handoff loss dominates and teams request deterministic coordination over diagnosis. |
| 5 | Benchmark-only | Maximizes scientific clarity and could publish negative results, but offers less direct workflow utility. | Product workflow adds no diagnosis value, or neutral datasets become the scarce asset. |
| 6 | Automatic remediation | Rejected for this horizon. Evaluator capture, poisoning, privilege expansion, side effects, and rollback gaps make autonomy incompatible with the evidence. | Not before independent production-grade safety evidence and a separately authorized gate. |

The ranking intentionally puts extending an incumbent above a standalone product as the strongest alternative. The prototype earns continuation only by demonstrating differentiated causal/replay value.

## D-002 — Deterministic core; optional heuristics second

Decision: ingestion, redaction, lineage, invariants, replay, comparison, and gating require no model call. Optional model-backed analysis is outside Phase 1 unless separately approved and must emit the same bounded hypothesis schema.

Reason: core reproducibility and offline operation are necessary controls. The source brief treats LLM failure localization results as promising preprint evidence, not universal accuracy.

## D-003 — Append-only redacted evidence with no raw retention in Phase 1

Decision: use immutable redacted event envelopes and rebuildable projections. Phase 1 retains no raw bytes, admits only enumerated typed fields, and permits no free-text passthrough.

Reason: inert synthetic fixtures do not require a vault. Removing it is the largest available safety and scope improvement. Any later raw-retention feature requires its own threat-model gate.

## D-004 — Hypotheses, not causal verdicts

Decision: forbid “root cause proved” semantics. Require evidence for/against, uncertainty, bounds, alternatives, assumptions, and abstention for every causal output.

Reason: multiple events may be jointly causal and counterfactuals may be unknowable. Agreement among evaluators does not create truth.

## D-005 — One declarative, reversible patch

Decision: a candidate contains one primary intervention, exact base hash, allowlisted data fields, expiry, and reverse delta. It is never applied to target or production state.

Reason: one-change replay improves attribution and limits privilege/rollback risk. Interactions between patches are explicitly deferred.

## D-006 — Separate mechanism verification from efficacy evaluation

Decision: Phase 1a verifies only the walking-skeleton mechanism and emits no threshold or promotion outcome. A later Phase 1b may freeze decision rules before tuning and output go/narrow/stop after a new review. No automatic promotion.

Reason: recorded-tool replay cannot measure patch efficacy unless fixture authors script the result. Mechanism proof and product evidence must not be conflated.

## D-007 — No launch framing

Decision: call Phase 1 a vertical prototype and exclude hosted, live, production, and marketing work.

Reason: the evidence and threat model support a controlled experiment, not launch readiness.

## D-008 — Accept the independent review's Phase 1a cut

Decision: accept the no-raw, eight-record, four-invariant, one-patch, three-family, approximately forty-fixture scope. Accept process isolation, controlled language, honest hash-chain limits, and a required re-verification before code. Defer efficacy thresholds, calibration, signing, keyed digests, cost proxies, and statistical gates.

Reason: Claude's bounded review at commit `24155c0` found the original Phase 1 to be the entire product rather than a safe first slice and identified unmeasurable or gameable evaluation claims. The review is recorded in `REVIEW-CLAUDE-DESIGN.md`.
