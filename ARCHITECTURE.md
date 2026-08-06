# Trajectory Ledger — Architecture

Status: implemented local vertical diagnostic prototype; frozen at the local
mechanism boundary and not release ready.

## Design constraints

The core is deterministic and model-free. All inputs are untrusted. It uses local files, performs no network access, imports no target modules, invokes no target commands, performs no production writes, and never applies a candidate automatically. Limits are configured before ingestion and fail closed: allowed roots, maximum files/bytes/events/edge depth, replay cases/repetitions/duration, and output size.

The internal schema is pinned and versioned. Phase 1a has one canonical fixture format and no open attribute bag or external adapter. Framework and OpenTelemetry adapters are deferred.

## Minimal components

```text
local inert fixture
  -> bounded parser + schema validator
  -> typed-allowlist deterministic redactor (no raw retention)
  -> append-only redacted event log
  -> rebuildable lineage projection
  -> invariants + bounded hypothesis engine
  -> candidate patch manifest (never auto-applied)
  -> jailed out-of-process fixture replay (baseline/candidate)
  -> mechanism comparison + human review record
```

- **Ingress:** resolves a user-selected path beneath an allowlisted root, rejects links/special files and oversize input, reads bytes without executing or dynamically importing content, validates a non-recursive JSON subset, and records adapter/schema versions.
- **Redactor:** a versioned typed allowlist admits only enumerated fields and values. Every field declares one of: boolean/numeric type; a closed enumeration; or a bounded, non-regex identifier grammar plus maximum byte length. Phase 1a stores no source-derived prose. Any value outside its declared constraint, plus every unknown field, becomes classification, byte length, and content hash only. A record pins its redactor version. A ruleset upgrade does not retroactively protect old records: affected records are quarantined or re-ingested from their source fixture.
- **Ledger:** append-only, hash-linked envelopes. Corrections and deletions are new tombstone/supersession events. A projection can be discarded and rebuilt.
- **Analyzer:** four deterministic invariants consume redacted projections only. Every finding is a hypothesis envelope, including `unknown`; heuristic plugins are deferred.
- **Patch builder:** Phase 1a creates one declarative memory-quarantine delta against a fixture-owned manifest and a reverse delta. Other patch classes are deferred.
- **Replay runner:** a separate process interprets a small declarative fixture DSL inside a fresh filesystem jail with no network capability. It does not deserialize language-native objects or execute target code. Baseline and candidate have identical inputs. Positive-control fixtures must attempt and trip each safety boundary. If isolation or comparison fails after a valid proposal is built, the proposal may remain available for inspection, but no replay record is emitted and the diagnostic must recommend abstention; there is no in-process fallback.
- **Review writer:** records a human `go`, `narrow`, `stop`, or `abstain` decision as operator self-attestation. It has no promotion or write authority.

The CLI has an explicit compute/render boundary before artifact persistence. It
ingests, analyzes, performs any bounded replay, and renders diagnostic and report artifacts in
memory before creating the requested output directory. A failure in those
stages therefore cannot leave a destination that resembles a completed packet.
Individual filesystem write failures can still leave a partial directory; the
exclusive-create policy prevents it from being silently reused or overwritten.

## Canonical data model

Every object is an immutable envelope with `schema_version`, `record_id`, `record_type`, `run_id`, `sequence`, `observed_at` (optional source time), `ingested_at`, `producer`, `source_ref`, `classification`, `content_hash`, `prev_record_hash`, and `payload`. IDs are generated locally; source-supplied IDs are data, not authority.

Phase 1a record types:

| Type | Required relationships / purpose |
|---|---|
| `run` | fixture, configuration, versions, seeds, declared limits |
| `event` | parent event(s), actor, kind, state version, input/output refs |
| `edge` | typed relationship, source assertion, referent state, provenance |
| `memory_op` | read/write/quarantine/expire, namespace, item/version and provenance refs |
| `hypothesis` | intervention point, evidence for/against, assumptions, alternatives, confidence/bounds |
| `patch` | base manifest hash, allowed delta, reverse delta, rationale/hypothesis refs |
| `replay` | suite/version, baseline or candidate hash, seeds, result refs, limits |
| `gate_decision` | rule version; outcome limited to `go`, `narrow`, `stop`, or `abstain`; operator self-attestation; bounded rationale classification |

Relationships are asserted edges with their own provenance. The projection distinguishes `referent_present`, `source_asserted`, `derived`, `missing`, and `conflicting`; it never silently repairs lineage. `referent_present` means only that an internal reference resolves in the same untrusted input. Generated text must never call a single-input claim "verified."

## Integrity and content hashes

Canonical serialization is defined before hashing. Each envelope includes its payload hash and previous ledger-record hash; run manifests include an ordered ledger digest. Hashes detect in-place or observable tampering but cannot detect truncation or a rewrite from genesis without an external anchor, and they do not authenticate an untrusted producer. Signing and keyed digests are deferred.

## Redaction boundary

Phase 1a is no-raw: source bytes are parsed from the selected fixture and discarded after the typed projection is produced. Analysis, replay, hypothesis generation, and reports accept only redacted handles. Canary tests measure coverage against an explicit finite encoding set; they do not prove recognition of unknown secret shapes. Derived artifacts inherit the strictest input classification.

## Candidate patch contract

A patch is data, not code. Phase 1a permits only quarantine of one referenced memory item. It declares a base content hash, exact allowlisted fields, expected mechanism effect as a hypothesis, scope, expiry, reverse operation, and evidence refs. Any base-hash mismatch, unknown field, broadened capability, new path, network request, executable content, or missing reverse delta rejects the patch. Reversal evidence is document-level only and makes no semantic rollback claim.

## Trust boundaries and failure behavior

The source fixture, embedded trace text, claimed lineage, analyzer output, and evaluator output are untrusted. The parser/redactor boundary, append-only writer, process-isolation launcher, declarative replay interpreter, and report renderer form the small trusted computing base. Redactor/scanner matching must be linear-time with a per-field budget. Validation failures append a sanitized rejection receipt when safe. Ambiguous evidence, incomplete lineage, unavailable controls, or integrity failure produces `ABSTAIN`, never guessed attribution.

## Generated-language contract

Reports use a fixed vocabulary. `root cause`, `caused by`, `because`, `responsible for`, and `the failure was` are banned from generated causal conclusions; templates are linted. Phase 1a renders no source-derived trace prose. All configured labels and operator-authored text are escaped and provenance-fenced. Reports are not safe input to another agent. The approved term is **fixture intervention-point match**, never causal localization. The Phase 1a schema has no promotion value or promotion authority.
