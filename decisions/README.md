# Decisions (ADRs)

Every significant engineering or research decision lives here as `ADR-NNN-<slug>.md`, written from
`_TEMPLATE.md`. ADRs are **append-only in spirit**: when evidence changes a decision, add an
addendum and (if reversed) mark the old ADR superseded — keep the original reasoning.

**ADR-001 … ADR-010 are the ten open decisions from the master doc.** Seven were accepted on 2026-11-03 (001 to 006 and 010); ADR-007, 008 and 009 stay `Proposed`, each with the input it waits for. They were due by **end of week 2**. Evidence is gathered per ADR, and work
that cannot wait proceeds behind `provisional: ADR-0NN` flags; no ADR is filled in before the team decides.

| ADR | Decision | Master doc's recommendation | Status | Decided by |
|---|---|---|---|---|
| [ADR-001](ADR-001-training-pool.md) | Training pool | Both — SweLoc to avoid being blocked, own set for contamination safety. | Accepted (2026-11-03) | lead |
| [ADR-002](ADR-002-quality-signal.md) | Quality signal for FILTER and WEIGHT | K-rank — published, continuous, makes FILTER and WEIGHT the same signal applied as a hard threshold vs a soft weight. | Accepted (2026-11-03) | lead |
| [ADR-003](ADR-003-graph-role.md) | Graph role: retrieval signal vs agent tool | Signal — matches RIL's architecture and keeps latency predictable. | Accepted (2026-11-03) | lead |
| [ADR-004](ADR-004-retrieval-granularity.md) | Retrieval granularity | Both — CORE-Bench chunking for reported metrics so numbers are comparable; function-level units internally for the graph. | Accepted (2026-11-03) | lead |
| [ADR-005](ADR-005-primary-benchmark.md) | Primary benchmark | L2 primary, L3 for the graph question, Loc-Bench as contamination check. | Accepted (2026-11-03) | lead |
| [ADR-006](ADR-006-base-encoder.md) | Base encoder | Qwen3-0.6B — CORE-Bench reports strong post-SFT results at CPU-feasible size. | Accepted (2026-11-03) | lead |
| [ADR-007](ADR-007-agent-scaffold.md) | Agent scaffold | Agentless — simplest to hold constant; complexity is a liability for a controlled study. | Proposed (open, see addendum of 2026-11-03) | _pending_ |
| [ADR-008](ADR-008-base-llm.md) | Base LLM for the agent | Decide on budget; if local, quantize identically across all arms. | Proposed (open, see addendum of 2026-11-03) | _pending_ |
| [ADR-009](ADR-009-cross-encoder-rerank.md) | Cross-encoder rerank | Include but measure — it likely dominates latency. | Proposed (open, see addendum of 2026-11-03) | _pending_ |
| [ADR-010](ADR-010-usable-by-others.md) | Is RIL meant to be usable by others? | Decide now — it changes CLI, config and packaging decisions in week 1, not week 10. | Accepted (2026-11-03) | lead |
| [ADR-011](ADR-011-repo-graph-schema.md) | RepoGraph schema, edge taxonomy, storage | — (options and evidence only) | Proposed | _pending_ |
| [ADR-012](ADR-012-edge-recovery-definitions.md) | Edge-recovery definitions | — (four definitions measured, none chosen) | Proposed | _pending_ |
| [ADR-013](ADR-013-codeunit-v1-frozen.md) | CodeUnit v1 frozen (decisions D4-D11) | — (engineer's decisions, 2026-10-17) | Proposed (schema frozen; Q28 open) | engineer |
| [ADR-014](ADR-014-context-assembly.md) | Context assembly policy (D102) | — (policy stated in the brief of 2026-11-06) | Proposed (`provisional: D102`) | _pending_ |

## Adding a new ADR

1. Copy `_TEMPLATE.md` to `ADR-0NN-<slug>.md` using the next free number (011 onward).
2. Fill every section; use `Proposed` until the engineer/team accepts it.
3. Add a row to the table above and reference the ADR from `docs/ARCHITECTURE.md` (Decision traceability).
4. Commit messages for the work it governs cite the ADR.

## Decisions that are already settled by the master doc (not ADRs)

These are locked in the design and are changed only through `docs/DEVIATIONS.md` with engineer sign-off:

- RQ2 compares supervision strategies at **matched optimization budgets** (optimizer updates fixed).
- Fusion is **RRF (k=60)**; the index is **flat exact**; context assembly is byte-identical across arms.
- Python only; the quality signal is not invented; repository-level disjointness.

## Where the 2026-10-17 engineer decisions (D1-D13) are recorded

| Decision (earlier question) | Owning document |
|---|---|
| D1 held-out matching (Q8), D2 token (Q22) | `specs/held_out_repos.md` (addendum) and ADR-001 (addendum) |
| D3 Loc-Bench tier (Q9), D13 Rewrite qrels (Q23) | `specs/held_out_repos.md` and ADR-005 (addenda) |
| D12 unit-level evaluation on Verified (Q21) | ADR-004 and ADR-005 (addenda) |
| D4-D11 CodeUnit (Q13-Q20) | `specs/code_unit.md` decision log and ADR-013; D4 also noted in ADR-003, D6 and D7 in ADR-004 |

## Where the 2026-10-18 engineer decisions (D14-D24) are recorded

| Decision (earlier question) | Owning document |
|---|---|
| D14 wording and derived-copy corrections (Q24, Q25) | `docs/DEVIATIONS.md` DEV-010 (and DEV-011, reference audit); ADR-003 addendum |
| D15 edge-recovery reporting (Q27) | ADR-012 addendum; `specs/repo_graph.md` Q-G15 |
| D16 graph read structure (Q38), D19 first stored families (Q37), D20 projections (Q32) | ADR-011 addendum; `specs/repo_graph.md` ("Decided on 2026-10-18") |
| D17 averaging (Q40), D23 contamination scan (Q44) | ADR-005 addendum; `docs/EXPERIMENTS.md` (rules; E-CONTAM-PROBE) |
| D18 gold readings (Q39, Q41; provisional) | ADR-004 addendum; ADR-003 addendum; `docs/EXPERIMENTS.md` (rules) |
| D20 module unit and timestamp readings (Q29), stage taxonomy (Q34) | `specs/code_unit.md` and ADR-013 addenda; `specs/latency_harness.md` addendum |
| D21 GPU budget (Q42) | ADR-006 addendum; `docs/COMPUTE.md` ("GPU budget") |
| D22 provisional pool until the filter-state experiment (Q43) | ADR-001 addendum |
| D24 not decided in advance: Q28 (ADR-013), Q35/Q36 (ADR-011), Q30 (ADR-003), encoder (ADR-006), pool (ADR-001, after the filter-state experiment); Q45 waits for ADR-007 | the addenda named, each stating that measurement settles it |
| D25 class unit source (Q28) | ADR-013 addendum of 2026-10-29 |
| D26 ambiguous sites, D27 external boundary (Q35, Q36) | ADR-011 addendum of 2026-10-29 |
| D28 negative policy, D30 teacher cells, D31 batch shape (Q51, Q52, Q53) | ADR-002 addendum of 2026-10-29 |
| D29 pool accepted with its limitation (Q50) | ADR-001 addendum of 2026-10-29 |
| D32 third dev L3 repository (Q47) | ADR-005 addendum of 2026-10-29 |
| D33 no encoder-instruction variants unless needed (Q48) | ADR-006 addendum of 2026-10-29 (second) |

ADR-011 (RepoGraph schema, edge taxonomy, storage) is opened as Proposed with options and no choice (`specs/repo_graph.md`, `docs/GRAPH_DESIGN.md`). ADR-012 (edge-recovery definitions) is reserved for the first parse and graph build.

## Where the 2026-11-03 decisions are recorded

| Decision | Owning document |
|---|---|
| ADR-001 to ADR-006 and ADR-010 accepted as recommended in the brief (D67); ADR-007 to ADR-009 open | each ADR, addendum of 2026-11-03 |
| O1 to O15 on the RQ2 final-experiment protocol (D68 to D82) | `docs/RQ2_PROTOCOL.md` section 11 |
| Departures from the master document that follow (encoder, update count, FILTER level and teachers, RQ3 fallback, label sheet) | `docs/DEVIATIONS.md` DEV-019 to DEV-023 |
| Cap for the final RQ2 stage | `docs/COMPUTE.md` ("Block 3") |
