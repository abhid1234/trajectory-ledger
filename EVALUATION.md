# Trajectory Ledger — Evaluation Plan

Status: Phase 1c local diagnostic mechanism implemented over the Phase 1b evidence expansion. Efficacy/localization evaluation remains blocked pending a separate preregistration and review.

## Phase 1c local diagnostic acceptance

Phase 1c consumes only the existing typed projection. It links likely failure points to projected ledger record IDs, retains unknown confidence and explicit alternatives/bounds, and maps supported invariant findings to single-change declarative policy, memory, or workflow proposals. Only the existing memory-quarantine proposal is applied in replay; the other proposal types have no execution authority.

The saved-task comparison is an inert scripted-fixture document comparison, not a real task outcome. A human-review recommendation is allowed only for exactly one supported memory hypothesis/proposal when evidence resolves completely and replay is complete, base-bound, adds exactly the intended quarantine, removes nothing, changes the candidate, and restores the baseline digest after reversal. Multiple likely points and every failed or missing criterion yield `abstain_no_promotion_recommendation`.

The preregistered efficacy/localization study is later validation and is not a prerequisite for this local diagnostic mechanism. No Phase 1c result clears that separate gate.

## Phase 1b mechanism-evidence expansion

Phase 1b-E expands engineering evidence only. `fixtures/manifest.json` declares 41 accepted synthetic/redacted fixtures and 17 rejected cases. The validator enforces the reviewed primary-category floors, exact invariant and patch/replay dispositions, strictest classification, unique case identifiers, and unique normalized structural signatures within each primary category. Manifest labels and boundaries are subject to the same banned-claim lint as reports.

The negative matrix is table-driven and separate from accepted-corpus counts. It covers top-level shape, header, required field, source type, enum, identifier, collection, depth, size, malformed JSON, bounded unknown fields, symlink input, path escape, executable patch fields, patch base mismatch, unavailable sandbox, and malformed replay output.

Replay compares exact bounded declarative memory documents. It rejects unknown document fields and reports baseline/candidate digests, base binding, quarantine additions/removals/unchanged entries, complete-document equality, and document-level reversal. The fixed labels are `scripted_fixture_response` and `not_real_task_outcome`.

Reports lead with invariant observations, patch/replay disposition, evidence completeness, unordered hypothesis interpretation, limitations, and the next safe human action. Hypotheses are an unordered set with `unique_explanation=false` and `ranking=none`, including when several findings coexist.

Both the manifest and generated reports machine-check the exact field:

`efficacy_gate_status=blocked_separate_preregistration_required`

There is no efficacy, localization, causal, prevalence, calibration, promotion, or gate-clearing result in this phase.

## Phase 1a claims under test

1. A bounded inert fixture can be parsed and projected without retaining raw source bytes or inventing lineage.
2. Four deterministic invariants can emit bounded hypothesis envelopes or abstain.
3. One declarative memory-quarantine patch can be applied to an inert manifest, compared against an identical baseline input, and reversed at the document level.
4. The jailed replay process rejects side-effect attempts and produces a deterministic escaped report.

Phase 1a does **not** test real task efficacy, live transfer, causal proof, model behavior, automatic remediation, or promotion readiness.

## Frozen Phase 1a assets

- About 40 deterministic inert fixtures across three fault families—`missing_lineage`, `stale_memory_read`, and `tainted_memory_reuse`—plus clean controls, mandatory-abstain cases, and safety positive controls.
- Eight record types: `run`, `event`, `edge`, `memory_op`, `hypothesis`, `patch`, `replay`, and `gate_decision`.
- Four deterministic invariants: `parent_referent_present`, `parent_edge_nonconflicting`, `memory_read_not_stale`, and `tainted_memory_not_reused_unquarantined`; plus one memory-quarantine patch class.
- A content-hashed manifest that identifies fixture version, redactor version, invariant version, patch version, environment, and the deterministic digest field subset.
- Recorded reference environment: Apple M4 Mac mini, 16 GiB RAM, Darwin 24.6.0. Timing results are descriptive only.

## Phase 1a mandatory checks

| Area | Check | Required result |
|---|---|---|
| Parsing | valid/invalid bounded fixtures | exact declared accept/reject result |
| Privacy | canaries outside the typed projection | zero matches for the enumerated scanner shapes |
| Lineage | expected internal references | all represented; zero silently invented parents |
| Invariants | four deterministic checks | exact expected envelope or abstention |
| Patch | one quarantine delta + reverse delta | base-bound; document-level reversal restores baseline digest |
| Replay isolation | network, parent-write, symlink-output, oversize/deep input, executable-field positive controls | every control trips and the run fails closed |
| Integrity | in-place record modification | detected; truncation/rewrite-from-genesis reported as unanchored and not guaranteed |
| Language | generated report templates | escaped; provenance-fenced; banned causal terms absent |
| Repeatability | deterministic result digest | identical across three clean reruns |
| Authority | any promotion/production action | impossible; no promotion outcome exists |

The repeatability digest excludes wall-clock fields and local presentation identifiers. Record identifiers must be pure functions of canonical content plus sequence and are tested separately. The canary scanner is bounded to UTF-8, UTF-16, base64, hex, percent-encoding, gzip, and values split across adjacent fields; other encodings and unknown secret shapes are explicitly outside its detection claim.

## Mechanism-only replay

Baseline and candidate receive identical inert inputs. A fixture may encode a scripted outcome response to quarantine solely to prove that the harness applies, observes, and reverses a declarative change. No success-rate threshold or efficacy claim is permitted. The report labels this a mechanism demonstration authored into the fixture.

The out-of-process runner must have a filesystem jail rooted at its fresh run directory and no network capability. Safety tests are positive controls: if an attempted violation does not trigger the expected control, the test fails.

## Separate efficacy/localization gate remains blocked

Before any efficacy/localization suite is frozen or run, a new review must verify all of the following:

1. Exact preregistered stratum counts and disjoint splits, with separate decidable and mandatory-abstain denominators.
2. An all-cases fixture intervention-point match denominator where abstention counts as non-match; conditional answered-case accuracy is secondary.
3. A named strong baseline (initially the earliest-error heuristic), content-hashed and measured before invariants are tuned.
4. Ordered authorship: freeze the fault-injection spec before invariants, then hold one surprise family until invariants are frozen and prohibit tuning against it.
5. A stated multiplicity policy, exact paired tests, minimum detectable effect, and per-family sample-size rules; underpowered rows are reporting-only.
6. No patch-outcome efficacy gate unless an independently authored deterministic responsive policy makes such a claim measurable.
7. A preregistered lineage ablation stop gate. If removing cross-run lineage does not degrade fixture intervention-point matching by the declared margin, the standalone thesis fails and the project narrows.

The current fixtures and invariants are engineering controls, not an efficacy/localization measurement suite. Any such suite requires a new content-hashed fault specification and ordered authorship; it may reuse only generic parser/safety controls, never these mechanism cases as held-out evidence.

Calibration, signing, keyed digests, cost-proxy thresholds, automatic promotion, and production claims are outside Phase 1a. Stop/narrow decisions in Phase 1b must bind to named rows and default to deterministic-invariants-only or benchmark-only rather than discretionary continuation.
