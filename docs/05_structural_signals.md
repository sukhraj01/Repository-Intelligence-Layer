# Structural signals and knowledge graphs

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): Structural signals and knowledge graphs.*

The professor's suggestion is correct and the schema already exists in published form. The gap we can fill is at the two ends of his chain: the issue at one end, tests and configuration at the other.

## The chain he described

`issue → implementation → caller → dependency → test → configuration`

No published schema covers all of it. LocAgent covers implementation through dependency. KGCompass adds the issue. No ablation shows the value of test and configuration links (corrected, see DEV-006: LARGER builds such links but reports no ablation of them) — and they are part of what CORE-Bench Level-3 scores.

## LocAgent schema (adopt this)

Directed heterogeneous graph, built with Python `ast`, indexing in seconds per repository.

- Node types: `directory`, `file`, `class`, `function`
- Edge types: `contain`, `import`, `invoke`, `inherit`
- Function is the smallest node; its source is the retrieval document
- Entity id is the fully qualified name, e.g. `src/utils.py:MathUtils.calculate_sum`

## LocAgent's ablation — already an RQ1

| Setting | File Acc@5 | Module Acc@10 | Function Acc@10 |
|---|---|---|---|
| Full | 88.32 | 82.85 | 71.53 |
| w/o graph traversal | 86.13 | 78.47 | 66.06 |
| `contain` edges only | 86.50 | 79.56 | 66.42 |
| 1 hop only | 86.86 | 80.29 | 66.79 |
| w/o BM25 index | 75.18 | 68.98 | 60.22 |

Three readings that change our design. Directory structure is nearly worthless — `contain`-only barely beats removing the graph, so `invoke`/`import`/`inherit` carry the signal. Multi-hop matters more at function level than file level. And removing BM25 costs more than removing the graph entirely, which is a warning against over-investing in structure.

## KGCompass extension

Unifies code entities with repository artifacts — issues and pull requests become nodes. Scores functions by combining semantic similarity with shortest path length from the issue node. Reports that 89.7% of 146 ground-truth functions lie two or more hops from the issue node (corrected, see DEV-005; 69.7% was the superseded first version). Language-agnostic and incrementally updatable.

## Our addition

Add `test` and `config` node types with `tests`/`configures` edges, and evaluate on CORE-Bench L3 rather than L2. This is where the remaining structural novelty concentrates.

## Design fork to decide

LocAgent uses the graph as an **agent tool** (the agent calls `TraverseGraph`). Our RIL design uses it as a **retrieval signal** (hop-decay score fused with BM25 and dense). These are different systems with different latency profiles. Pick deliberately; do not drift between them.

Baseline scoring if signal: `struct(u) = γ^dist(ℓ,u)` with γ≈0.5. Personalized PageRank seeded at the query location is the more principled version, worth trying second.

## Known limitation to quantify

Static call-graph extraction in Python is incomplete — dynamic dispatch, `getattr`, decorators, monkey-patching and duck typing all produce unresolvable edges. No published figure supports an expected recovery range for arbitrary repositories (corrected, see DEV-007); edge recovery is reported as the dynamic-oracle recall beside the call-site breakdown (ADR-012). Measure and report it; if RQ1 finds structural signals weak, incomplete extraction is a candidate explanation and the coverage figure is what makes that credible.
