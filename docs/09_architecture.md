# Architecture and implementation

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): Architecture and implementation.*

## The CodeUnit — freeze this in week 1

The interface between the parser, all three retrieval signals, the training-data builder and the evaluation harness. Every component reads it.

```
@dataclass
class CodeUnit:
    # identity
    id: str                 # "auth.py::TokenManager.verify_jwt"
    repo_id: str
    language: str

    # location
    file: str
    start_line: int
    end_line: int

    # structure -> feeds the dense encoder
    unit_type: str          # function | method | class
    name: str
    qualified_name: str
    signature: str
    docstring: str | None

    # content
    source: str

    # relationships -> feeds the structural signal
    calls: list[str]
    called_by: list[str]
    tests: list[str]
    configs: list[str]

    # metadata
    is_test: bool
    loc: int
    last_modified: str
```

## Offline indexing, once per repository

- Parse with `ast` (or tree-sitter if multi-language later). Skip `__pycache__`, `.git`, vendored and generated files.
- Build call, import, inherit graphs. **Record edge-recovery coverage.**
- Build the lexical index: split identifiers (camelCase, snake_case), index name / signature / docstring / body as separately weighted fields. BM25 with k₁=1.2, b=0.75 — tune b, since code unit lengths vary enormously.
- Encode units and store in a flat exact index. **This is the only box that changes between experimental arms.**

## Online retrieval

```
def retrieve(location, task, max_results=20, max_tokens=4096):
    q = interpret(location, task)

    cand_lex    = bm25.search(q, k=1000)
    cand_dense  = ann.search(encoder(q), k=1000)
    cand_struct = graph.neighbours(location, max_hops=2)

    fused = rrf([cand_lex, cand_dense, cand_struct], k=60)
    top   = cross_encoder.rerank(q, fused[:100])[:max_results]

    return assemble(top, budget=max_tokens)
```

Use RRF, not a weighted score sum: BM25 returns unbounded scores whose scale shifts with corpus statistics while cosine sits in a narrow band, so a weighted sum needs per-corpus retuning. RRF uses rank only and needs none — worth more than the last fraction of a point when the stack must stay identical across four arms.

Use a **flat exact** index, not ANN. At 10³–10⁵ units per repository it costs milliseconds, and it removes ANN recall as a confound — an apparent difference between arms must not be an artifact of approximate search.

The `assemble` step is easy to overlook: deduplicate overlapping units, order so the most relevant survives truncation, attach signatures of called functions, fit a hard token budget. **Keep it byte-identical across arms.**

## Defaults to start from

| Parameter | Value |
|---|---|
| Pooling | mean over tokens, masked |
| Temperature tau | 0.05 (range 0.03–0.07) |
| Batch size | as large as memory allows — it is the in-batch negative count |
| Learning rate | 2e-5, linear decay, 10% warmup |
| Optimizer updates | 20,000, fixed across arms |
| Max sequence length | 512 |
| Fusion | RRF, k=60 |
| Seeds | 3 minimum per arm |

## Repository layout

```
ril/
  parsing/      repository_parser.py, code_unit.py, call_graph.py
  retrieval/    bm25_index.py, dense_encoder.py, hybrid_retriever.py, ranking.py
  training/     contrastive_loss.py, training.py, data_loader.py, supervision.py
  evaluation/   metrics.py, core_bench.py, agent_integration.py
  bench/        latency_harness.py, profile_stages.py
  analysis/     error_analysis.py, visualization.py
  config/       parameters.py, paths.py
```
