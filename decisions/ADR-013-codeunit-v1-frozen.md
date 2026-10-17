# ADR-013: CodeUnit v1 frozen

- **Status:** Proposed — schema frozen as v1 on the engineer's decisions of 2026-10-17; one question
  that does not change the schema (Q28, class unit `source`) is still open, so the ADR is not Accepted
- **Date:** 2026-10-17
- **Decided by:** engineer (decisions D4 to D11); D4, D6 and D11 are defaults he may still edit
- **Related:** `specs/code_unit.md` (the decision log is there), ADR-003, ADR-004, ADR-011 (graph,
  planned), `docs/09_architecture.md`, `docs/ARCHITECTURE.md`

## Context
The CodeUnit is the only type shared across component boundaries. The draft left eight questions
open (what the relation lists hold, the `repo_id` form, which definitions are units, the link to
benchmark chunks, `last_modified`, `is_test`, who fills `tests`, the `id` format). The parser, the
graph, the index and the evaluation loaders cannot start on a moving type, and a change after the
first index costs a re-index and a re-run of everything downstream.

## Alternatives considered
Per question, the options and their trade-offs were written up before the decision (the options are
in the decision log in `specs/code_unit.md`, and each decision states the alternative it replaced):
unit ids / qualified names / paths for relations; `owner/name` with or without a commit; units with
or without a residual module unit; a chunk-id field against a derived mapping; commit time against
file time; path rule against name or marker rules; `#<line>` against ordinal suffixes for collisions.

## Decision
Freeze the schema as v1: the nineteen fields of `specs/code_unit.md`, `unit_type` extended with
`"module"` (D6), `CODEUNIT_SCHEMA_VERSION = "v1"`, and the meanings fixed by D4 to D11. The id
builder and converter, the `repo_id` normalizer, the `is_test` rule and the enum validation are
implemented and tested; the canonical serialization is unchanged and pinned by a golden test.

## Rationale
Each decision carries its own reason in the spec. Together: relations are projections of a separate
typed edge store keyed by stable ids (D4, D11); identity is repository name plus path plus qualified
name and never the snapshot (D5, D11); every gold position can be reached at unit level through the
module unit (D6); evaluation chunks are mapped, not embedded in the type (D7); fields that depend on
history or on the graph are computed where that information exists (D8, D10); `is_test` is a cheap
path rule validated against pytest (D9).

## Trade-offs
The edge store is a second artifact to version and keep consistent with the units. A module unit adds
one unit per file to every index (latency and index size not yet measured). The path rule labels
helper files under `tests/` as tests. An ordinal id can shift when a conditional duplicate definition
is inserted between two same-name definitions.

## Evidence class and the experiment that could change it
- **Evidence class:** per decision in the spec: D5 (renames), D6 (positions in a sample of 160), D7
  (paper tables and the data audit) and D9 (pytest agreement on three repositories) are measured or
  read in full; D4, D8, D10, D11 (the id rule) are reasoned only; the pool-id converter is measured.
- **Cheapest experiments that could flip it:** the first parse and graph build (resolution coverage
  for D4, collision rate for D11, `tests` edge precision for D10), pilot M and E1 (D6, D7), pilot E5
  (D8). Each is inside a session already planned; none is run here.

## Evidence
`specs/code_unit.md` (per decision); `results/logs/d_is_test_rule_2026-10-17.json`;
`results/logs/d_content_overlap_audit_2026-10-17.json` (pool-id round trip);
`results/logs/s3_codeunit_chunk_mapping_2026-10-17.json`; `knowledge/papers/core-bench-2606.11864.md`.

## Related benchmarks
None; no latency row yet (harness not built). The module unit's effect on index size and retrieval
is the subject of pilots M and E1.

## References
`docs/09_architecture.md`, `docs/05_structural_signals.md`, `knowledge/papers/larger-2605.16352.md`,
`knowledge/papers/locagent-2503.09089.md`.

## Conditions to revisit
- The edge-recovery numbers show the relation lists are mostly empty (D4).
- Pilot M or E1 show the module unit buys nothing (D6), or the match rate is too low for the mapping (D7).
- The collision rate makes ordinal ids unstable (D11).
- A repository whose tests the path rule misses (D9).
- The engineer edits D4, D6 or D11: a version bump and a re-index plan.

## Addenda
_None._
