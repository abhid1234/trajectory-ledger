# Trajectory Ledger — Product Brief

Status: implemented Phase 1c local diagnostic mechanism; not release ready

## Product in one sentence

Trajectory Ledger helps an engineer inspect one stored, synthetic or redacted
agent trace and produce a reviewable record of where a narrow intervention may
be worth investigating—without claiming a root cause or changing a live system.

## Audience and problem

The first user is an engineer who owns or debugs an agent workflow and can
prepare a trace in the project's bounded JSON format. After a failed run, that
engineer can often see the events but cannot readily answer three narrower
questions:

1. Which recorded event is supported as a useful investigation point?
2. What is the smallest reversible change suggested by that evidence?
3. Did the local mechanism apply, compare, and reverse that change as specified?

This is an auditability problem, not a promise to diagnose arbitrary agents.
Ordinary trace inspection can obscure lineage, provenance, and the boundary
between an observation and an explanation. A final score also cannot establish
which earlier event mattered. Trajectory Ledger makes those boundaries explicit
and defaults to abstention when the available projected evidence is incomplete
or ambiguous.

The intended operator is comfortable running a local Python CLI and reviewing
JSON artifacts. Teams needing live ingestion, a hosted interface, broad trace
format support, or automatic remediation are not the audience for this phase.

## Phase 1c user outcome

For one accepted fixture, the CLI writes a local evidence packet containing a
hash-linked ledger, rebuilt lineage, deterministic invariant findings, bounded
hypotheses or abstentions, and `diagnostic.json`. A supported finding may also
produce a single-change declarative proposal. Only the memory-quarantine
proposal can enter the saved-task document comparison; policy and workflow
proposals remain inspectable data.

The useful outcome is a narrower human review question with traceable evidence.
The tool may return `human_may_consider_promotion` only when every mechanical
comparison criterion passes. That phrase means “inspect this candidate,” not
“the change works,” “ship it,” or “apply it.” Every other path returns
`abstain_no_promotion_recommendation`.

## How the local journey works

1. **Ingest:** validate one inert local fixture against strict size, shape, path,
   and identifier bounds; never import or execute target code.
2. **Project:** retain enumerated typed fields. Reduce unknown fields to
   classification, byte length, and content hash; do not render those hashes.
3. **Rebuild:** append canonical records to a hash-linked ledger and reconstruct
   asserted, present, missing, or conflicting lineage without inventing links.
4. **Inspect:** evaluate four deterministic invariants and cite projected ledger
   record IDs for every supported likely failure point.
5. **Bound:** attach unknown confidence, alternatives, assumptions, and
   single-fixture/mechanism-only limits, or abstain when support is insufficient.
6. **Propose:** emit at most a narrow, evidence-bound, expiring declarative
   change with an exact reverse operation. No proposal targets production.
7. **Compare:** for the supported memory case only, use a separate jailed process
   to compare exact saved-task documents and verify document-level reversal.
8. **Review:** present deterministic local artifacts for a human decision. The
   software has no deployment, promotion, or external-write authority.

## Honest claims

Local tests and fixtures can demonstrate that the implementation parses its
bounded format, preserves the tested ledger relationships, evaluates its fixed
invariants, creates allowed proposal data, fails closed when replay isolation is
not proven, and compares and reverses exact documents when replay completes.

They do not demonstrate that a hypothesis identifies a true or unique cause,
that a proposal improves a real task, that replay transfers to production, or
that the product is useful to its intended audience. The accepted corpus is
synthetic/redacted mechanism evidence, not efficacy, localization, calibration,
prevalence, usability, or market evidence. Those claims remain unverified until
separately designed human research or a preregistered evaluation is completed.

## Non-goals

- Proving root cause, ranking explanations, or claiming causal certainty.
- Measuring real-task efficacy or localization accuracy in the current corpus.
- Applying changes, promoting candidates, or making release decisions.
- Online learning, model or weight updates, self-modifying agents, or automatic
  remediation.
- Live or network ingestion, production traces, external model/tool calls,
  account access, deployment, or production writes.
- A general trace viewer, hosted service, control plane, or observability
  platform replacement.
- Supporting arbitrary schemas, executable plugins, target repositories, or all
  agent frameworks.
- Guaranteeing source truth, complete tamper detection, secret discovery, or
  semantic rollback.
- Marketing, customer commitments, or claims of reliable multi-agent operation.

## Product hypothesis and next evidence gap

The hypothesis is that evidence-linked lineage, bounded hypotheses, reversible
proposal data, and explicit abstention can help an engineer make a narrower and
more auditable investigation decision than ordinary trace inspection alone.
That value proposition has not been validated with target users.

The next product-clarity gate is human review of whether the artifact packet is
understandable and decision-useful. The separate efficacy/localization study
remains blocked pending preregistration and independent review. Neither gate is
cleared by the current unit suite or demo.
