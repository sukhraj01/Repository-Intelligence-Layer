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

## Addendum 2026-10-23 — engineer decisions D20 and D24 of 2026-10-18

- **D20 (closes Q29).** The readings made in code for the module unit (D6) and the timestamp form (D8) are accepted as
  written (`specs/code_unit.md`, addendum). Schema unchanged, v1. Evidence class: reasoned, pinned by the golden test.
- **D24 (Q28 not decided in advance).** The class unit's `source` (full class text, header only, header plus method
  signatures) is settled by measurement: unit-level BM25 and the containment expansion on the dev repositories, with
  repository-clustered intervals, index size and build time. The parser offers the forms as a config option behind
  `provisional: ADR-013` until the engineer decides; the CodeUnit schema is not affected by any of the three.


## Addendum 2026-10-23 — Q28 measured: class-unit source forms (evidence only; Q28 stays open, `provisional: ADR-013` stays)

- **What was measured** (`docs/EXPERIMENTS.md` E-CLASS-SOURCE; rows `x1-class-source-dev`, `x1-extras`). Three forms of a class
  unit's `source`, offered by the parser as `ParseOptions.class_source` (`full`, the default of every build so far; `header`, the
  class span without its methods; `header_sigs`, `header` plus each method's decorators and `def` lines). Only the text differs:
  ids, spans and every other field are identical, so the schema is untouched (v1, golden test unchanged) and the gold mapping is the
  same in every form. Unit-level BM25 and the pilot-E3 expansion on the five dev repositories (351 L2, 155 L3 queries).
- **Result.** Under the readings that count every overlapped unit as gold (decision D18), `full` is ahead by 2 to 3 points at L2
  nDCG@10 and L3 Recall@100, for BM25 alone (`header` -2.3 [-3.4, -1.3] and -2.9 [-3.6, -2.1] under `units_all_nomod`) and after the
  `core` expansion (-2.0 [-3.1, -0.8] and -1.7 [-3.1, -0.5]); `header_sigs` is not better than `header`. The rule stated before the
  run therefore keeps `full`. Under pilot M's mapping (a class is gold only when a chunk touches none of its methods) the three
  forms are not distinguishable for BM25 or the `core` expansion. The advantage of `full` comes mostly from the gold reading: a class
  whose method is gold is itself gold under D18 part 1, and only `full` repeats the method's text. The cost of `full`: about 55% more
  indexed tokens and 26% more postings per snapshot (median 517,550 against 332,714 tokens), build time p50 2.83 s against 2.45 s.
- **Evidence class.** Measured (exploratory, dev only, one seed of a deterministic pipeline; Verified not scored for the forms).
- **Experiment that could flip it.** The same comparison for the dense encoder of ADR-006 (long class units are truncated, so `full`
  may lose there), and under a gold reading that does not make a class gold through its methods; both are minutes on the existing
  extras once dense scores exist (X2's unit texts would have to be encoded per form).
- **What it does not settle.** Which gold reading is right for classes (ADR-004, D18 part 1) — the form question and that one are now
  the same question.
