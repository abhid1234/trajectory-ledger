# Trajectory Ledger — Roadmap

Status: proposed sequence; documentation only. Phase 1a is a **walking skeleton**, not launch-ready.

## Phase 0 — Gate packet (this commit)

Deliver the product brief, architecture, preregistered evaluation, threat model, roadmap, decision log, and checkpoint. Exit when Mason accepts the problem boundary and Claude’s later independent review questions are resolved. No code or launch material.

## Phase 1a — Local walking skeleton

Target: demonstrate the complete ingest → redact → inspect → hypothesize → propose → replay → compare → review journey with inert files, without efficacy or promotion claims.

Measurable milestones:

1. **Schema and boundary:** eight record types, typed allowlist, no raw retention, about 40 valid/invalid/adversarial fixtures across three fault families.
2. **Ledger and lineage:** append-only writer and rebuildable projection; expected internal references reconstructed; no silent invented parents; integrity claim bounded to what a local hash chain can observe.
3. **Bounded analysis:** four deterministic invariants and structured hypothesis envelopes with evidence for/against, assumptions, alternatives, confidence/bounds, and abstention.
4. **Patch contract:** one memory-quarantine example, base-bound with a reverse delta; privilege-broadening and executable fields rejected.
5. **Inert replay:** out-of-process mechanism comparison with OS-enforced filesystem/network isolation and positive-control violations.
6. **Review report:** deterministic escaped text, no threshold verdict, no efficacy claim, no promotion output.

Phase exit requires every mechanism and security check in `EVALUATION.md`, plus a bounded re-review. Failure invokes stop/narrow rather than relaxed checks.

## Phase 1b — Preregistered evidence-quality gate

Only after Phase 1a is green and a new independent review accepts the seven preregistration conditions in `EVALUATION.md`: freeze exact strata, denominators, a strong baseline, ordered authorship, a surprise fault family, statistical decision rules, and a falsifiable lineage-ablation stop gate. Phase 1b is still local and inert. It may produce a go/narrow/stop recommendation, never automatic promotion or production authority.

## Phase 2 — Evidence-quality validation

Only after Phase 1 review: expand fault families, label organic local traces that contain no sensitive production data, measure inter-rater agreement, compare against ordinary logs and deterministic-invariants-only, and run a blinded crossover time-to-diagnosis study. Exit hypothesis: the ledger improves decision quality or time without hiding uncertainty. If not, narrow to an integrity/invariants tool.

## Phase 3 — Adapter feasibility, still read-only

Only after a separate authorization: add one version-pinned OpenTelemetry JSON adapter and one framework adapter, both offline. Measure fidelity and schema churn. No live collector, no network, no production data, and no patch application.

## Explicitly deferred

Hosted service, live ingestion, production connectors, external model calls, online learning, weight updates, automatic patching/promotion, broad framework support, organization/tenant features, marketing, and launch are not roadmap commitments. Each requires a new threat model and explicit authorization.

## Resourcing and review gates

One writer/implementer owns Phase 1 to keep authority clear. Mason owns product/design/build decisions; Codex is the sole implementation writer. Vera's cited brief remains research evidence, not authority. Claude performs bounded read-only review, never concurrent writing. Each phase gets a frozen scope, clean commit set, evaluation manifest, and explicit go/narrow/stop record.
