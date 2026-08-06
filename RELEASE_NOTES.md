# Trajectory Ledger — Release Notes (local release candidate)

**Artifact:** Phase 1c local diagnostic slice
**Commit at these notes:** `596d716d` (branch `factory/trajectory-ledger-local-diagnostic`)
**Approved evidence pin:** `800d05bb` (Task 29 APPROVED — see below)
**Release disposition: NOT RELEASE READY.** This is a *local* release candidate.
Public release remains blocked on human gates that software cannot clear (see
"Open release gates"). Passing tests or a replay recommendation do not change
this disposition automatically.

---

## What this is

Trajectory Ledger is a local, standard-library-only Python 3.11 CLI that takes
**one** bounded, inert, synthetic-or-redacted agent-trace fixture and produces a
reviewable evidence packet answering three narrow questions for a human:

1. Which recorded event does the projected evidence *support* investigating?
2. What is the smallest reversible change that evidence suggests?
3. Did the local mechanism compare and reverse that change exactly as specified?

The output is an evidence packet for human review — **not** an automated
diagnosis, fix, or promotion.

## What changed since the approved evidence pin (`800d05bb`)

The pin recorded Task 29's APPROVED evidence: 25 focused adversarial tests + 42
full tests, no skips, plus compile and diff hygiene. Since then, four quality
passes landed on this branch:

| Pass | Category | Factory job | Commit | Terminal result |
|---|---|---|---|---|
| 6 | keyboard_focus | 61 | `3d725997` | completed |
| 7 | touch_responsiveness | 63 | `fb3beb93` | completed |
| 8 | zoom_reflow | 64 | `312c427e` | completed |
| 9 | assistive_semantics | 66 | `9e9dbaaa` | completed |

Pass 9 (this release) restructured the CLI completion receipt into uniquely
named, linearly ordered `STATUS` / `DECISION` / `EVIDENCE SUMMARY` /
`NEXT ACTION` / `ARTIFACT LOCATION` sections, and routed the fail-closed
validation path to standard error with an explicit `status=abstained`
announcement (exit 2). Human screen-reader compatibility remains **explicitly
unverified** — see `ASSISTIVE-SEMANTICS-PASS-09.md`.

Post-pass-9 hardening (`1715d999`), from the automated security first-pass
finding **F1**: an existing or unusable output directory used to raise an
uncaught `OSError` traceback (leaking absolute paths + stack) instead of the
uniform fail-closed receipt. It now maps to
`ValidationError(output_directory_unavailable)` → `status=abstained` (exit 2),
with two added regressions. See `REVIEW-SECURITY-PRIVACY-FIRSTPASS.md`.

> Note on Factory state: pass 10 (`contrast_motion`, job 67) is recorded as
> `blocked` and the project row is `failed`; that block was a worktree-clean /
> durable-job recovery condition (Codex Factory Cockpit lane), not a product
> defect. It is out of scope for these product release notes.

## Test evidence (this HEAD, `596d716d`)

Run under the pinned interpreter `Python 3.11.15` (`python3.11`):

```
PYTHONPATH=. python3.11 -m unittest -v
Ran 51 tests in ~1.6s — OK
```

- **Full suite: 51/51 pass, no skips** — 14 (`test_phase1a`) + 6 (`test_phase1b`) + 31 (`test_phase1c`).
- **Focused adversarial slice: 31/31 pass** (`tests.test_phase1c`, ~0.2s).
- **Safe local demo:** `scripts/local_demo.sh` exits 0 and prints
  `recommendation=human_may_consider_promotion`, `replay_criteria_passed=true`,
  `authority=human_review_only_no_external_action`.

Local observation, this HEAD only (host-specific, not a pinned digest):
`diagnostic.json` for `fixtures/demo_redacted_tainted.json` hashed
`4952e2995fe7453cb276e376ada4a9de708223700e0ecb6f79d6c67cc31373e8`. The
retained direct-Mini evidence in `README.md`/`CHECKPOINT.md` is for earlier
committed candidates and version-1 contracts and is not superseded by this
observation.

> Caveat: under Python 3.14 (not the target), 3 checks diverge (a stricter
> sandbox positive control and a 42-vs-40 reflow-width bound). The supported
> interpreter is **3.11**; run it there.

## Safety boundaries (unchanged, enforced)

Does **not**: execute or import target code, call a model or network service,
retain raw source bytes, read live Factory state, write production state, emit a
promotion action, measure efficacy/localization, or establish causation. Replay
runs out-of-process under `/usr/bin/sandbox-exec`; if genuine enforcement cannot
be proven, replay **fails closed** and the tool abstains. No in-process
substitute is used.

## Limitations (stated plainly)

- Synthetic/redacted fixtures do not establish causation, efficacy, localization
  accuracy, calibration, prevalence, or real-task improvement.
- Hash chaining detects tested in-place mutations but cannot authenticate inputs
  or guarantee detection of unanchored truncation / rewrite from genesis.
- Redaction canaries cover enumerated shapes only; retained byte-length and
  SHA-256 metadata intentionally reveal size/equality information.
- Replay compares exact declarative documents; it is not semantic rollback or a
  real-task outcome, and `sandbox-exec` evidence is host-specific.
- `human_may_consider_promotion` means "inspect this candidate," not "it works,"
  "ship it," or "apply it." It grants no authority.

## Open release gates (human-only; NOT cleared)

From `LOCAL-BUILD-HANDOFF.md`, all mandatory and unchecked:

- [ ] Canonical owner/human accepts the final artifacts and limitations.
- [ ] Independent security reviewer accepts host-specific jail evidence and residual risks.
- [ ] Privacy/data reviewer accepts typed-projection metadata leakage and input policy.
- [ ] Release authority approves a scoped release plan, packaging, support, rollback.
- [ ] Efficacy/localization claims supported by a separate, preregistered, reviewed study.

## How to run

```sh
cd factory/projects/trajectory-ledger
PYTHON_BIN=python3.11 ./scripts/local_demo.sh   # safe synthetic demo
# your own approved synthetic/redacted fixture:
PYTHONPATH=. python3.11 -m trajectory_ledger.cli INPUT.json NEW_OUTPUT_DIR --attest abstain
```

See `README.md`, `PRODUCT-BRIEF.md`, `THREAT-MODEL.md`, and
`LOCAL-BUILD-HANDOFF.md` for full detail.
