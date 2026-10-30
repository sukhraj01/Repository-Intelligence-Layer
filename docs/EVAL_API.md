# Retrieval evaluation contract

The shared entry point implements D13 (Rewrite wording with original labels) and D17
(query-weighted mean with a repository-clustered interval). L2 and L3 stay separate. This
entry point scores **released chunks**; existing unit-level experiments retain their D18 gold
readings. Converting unit scores to chunk scores or changing gold readings is outside this API.

Run from the repository root:

```sh
make eval CONFIG=configs/experiments/c_eval_smoke.yaml
# Active CPU environment without Poetry:
make eval RUN= CONFIG=configs/experiments/c_eval_smoke.yaml
```

The example is synthetic and labelled `role: fixture`. It verifies plumbing and an intentionally
removed error/API anchor; its scores are not benchmark results. Actual original/Rewrite corpora
and pinned encoder scores must be acquired on the compute cluster before the scientific ablation.
A configured test split is a single stated setting; this command never sweeps parameters.

## Loader and scorer

```python
read_folder(path: str, *, rewrite_path: str | None = None) -> CoreBenchFolder
read_split(root: str, level: str, dataset: str, folder: str,
           *, rewrite: bool = False) -> CoreBenchFolder
evaluate_scores(folder: CoreBenchFolder, scorer: Callable[[CoreBenchQuery], Float],
                *, prefilter_k: int = 10000) -> list[dict[str, Any]]
evaluate_folder(folder: CoreBenchFolder, params: BM25Params | None = None,
                *, prefilter_k: int = 10000) -> list[dict[str, Any]]
```

`read_split` resolves `root/data/LEVEL-2/<dataset>/<folder>` or `LEVEL-3`; rewritten
queries come from `root/data/Rewrite-LEVEL-2/...` or `Rewrite-LEVEL-3/...`. Corpus, order,
positive labels, and candidate lists always come from the original folder. Missing/defective
Rewrite qrels are ignored. Query ids must match exactly before qrel filtering; duplicates or a
missing Rewrite query fail. Queries without positive original qrels are dropped and counted.
Original positives absent from the corpus remain in the metric denominator.

The scorer returns a finite float64 vector in original corpus order. Ranking first truncates the
whole-folder list at `prefilter_k`, then restricts to the query candidates. Ties break by corpus
order. `evaluate_scores` returns query id, candidate/positive counts, token count, and ranks of each
positive under both the protocol and filter-first readings. Reported metrics use protocol ranks,
binary-gain nDCG@10 and Recall@100, on the same original query identities for each condition.

## Cached dense adapter

```python
folder_hashes(original: CoreBenchFolder, rewrite: CoreBenchFolder) -> dict[str, str]
CachedScores(path: str, original: CoreBenchFolder, rewrite: CoreBenchFolder)
CachedScores.score(query: CoreBenchQuery, condition: str) -> Float
```

This adapter imports no model runtime. Generate actual scores on the compute cluster with one
pinned encoder, same revision/tokenization/sequence limit in both conditions. Store NPZ with
`allow_pickle=False` compatible arrays:

| Field | Shape / content |
|---|---|
| `corpus_ids` | string vector, original corpus order |
| `query_ids` | string vector, original retained query order |
| `original_scores`, `rewrite_scores` | finite float matrices, queries × corpus |
| `metadata` | JSON string scalar, including nonempty `encoder`, `revision`, `max_tokens`, `query_template`, and all `folder_hashes` fields |

Include encoder settings and upstream artifact provenance in metadata. The adapter checks content
hashes, wording, ids, orders, dimensions and configured encoder/revision/sequence limit before scoring. Cache files
live at `<cache_root>/<L2|L3>/<dataset>/<folder>.npz`. The two matrices are loaded into memory;
measure per-unit memory and size them on the cluster before a real corpus run. Synthetic test
matrices use a fixture encoder identifier and cannot support a dense-model performance claim.

## Statistics

`ril.evaluation.stats` owns the power calculations formerly in `power.py` and bootstrap helpers
formerly in `metrics.py`; those modules retain compatible exports. Exact McNemar and the 2026-10-18
minimum detectable effect cells retain their recorded precision. Effects are fractions, not points.

```python
clustered_mean_ci(values, repositories, *, draws=2000, seed=0, level=.95)
clustered_paired_diff_ci(a, b, repositories, *, draws=2000, seed=0, level=.95)
exact_mcnemar_p(b: int, c: int) -> float
mde_mcnemar(n: int, d: float, alpha=.05, target=.80, step=.0025) -> float | None
```

Intervals return `(mean, low, high)`. Paired differences mean `a - b`. Callers must align identities;
the runner checks `(level, dataset, folder, query_id)` and groups clusters by canonical `repo` across
folders. Each bootstrap draws R whole repositories with replacement from R names, keeps all queries
of each drawn occurrence, then recomputes the query-weighted ratio. The point is the query mean,
never the mean of repository means. One cluster produces a degenerate interval and provides no
between-repository uncertainty. Missing pairs fail instead of silently shrinking the sample.

`Boot(repos, seed, draws=2000)` retains the existing table builder's micro, macro and cluster
weight behavior, including seeded draws, for migration. Analysis table builders remain on their
existing implementation pending owner consolidation; equivalence is tested. The legacy query-only
`mean_ci`/`paired_diff_ci` exports remain for compatibility; new primary reports use clustered helpers.
MDE checks all feasible grid effects plus the observed-discordance endpoint, including off-grid rates;
`None` means the specified target is unattainable, not zero effect.

## Configuration and output

The example lists all common YAML fields. `retriever.kind` accepts `bm25` (`k1`, `b`) or
`cached_dense` (`cache_root`, `encoder`, `revision`, `max_tokens`). Dense requires `rewrite: true`. `role` is
`dev`, `test` or `fixture`; tuning belongs on dev repositories only. Split/folder membership is
explicit; dev membership is checked against the six registered repositories, and fixture role
requires the synthetic fixture dataset and example repositories. One folder/level may appear once. `warmup_n` is discarded score calls, `repeats` is the
number of measured calls per query; batch size is one. Unknown top-level/retriever keys fail.

The configured output directory contains `config.yaml`, `hardware.json`, `results.json`,
`latency_log.csv`, and `throughput_log.csv`; optional `log_path` gets the same result JSON. Repeated
runs overwrite JSON/config and append timing rows. Use a fresh output/log path per registered run.
The SHA-256 config hash covers the supplied configuration and runner version; it includes output
paths. Results also carry the full git hash, dirty flag, seed, input text hashes, labels/candidate
hash, role, split and encoder configuration. Dense runs also record the score-file SHA-256 and
complete encoder metadata. Hashes identify inputs; they do not prove a dataset's
upstream provenance. Preserve the acquisition manifest beside real data.

| Result field | Meaning |
|---|---|
| `metrics` | level, condition, metric, n, repository count, mean/low/high in [0,1]; signed differences may be negative |
| `query_rows` | level/dataset/folder/repo/query id, condition, metric values, original/lost exact anchor counts; no issue or corpus text |
| `input_hashes` | corpus, both wording, labels/candidates hashes, dropped-unlabelled count |
| `latency_rows` | standard `LATENCY_COLUMNS`: environment, query-set id, discarded warmup count, warm state, stage, p50/p95/p99 ms, measured n |
| `throughput_rows` | standard `THROUGHPUT_COLUMNS`: environment, workload id, offline stage, units, seconds, units/s |

BM25 latency covers tokenization and scoring. Cached dense latency is explicitly named
`cached_scores_lookup`: score-row access only, excludes encoding/search and is not comparable to
BM25 latency. Offline `bm25_index` or `cached_scores_load` throughput counts corpus documents,
with the measured load/build seconds. These stage names are confined to this evaluator's per-run
CSV; additions to the central harness taxonomy require its owner's change. No retrieval timing is
presented as full interactive latency. Anchor counts are an exploratory exact-string heuristic
(backticks, URLs, dotted names, Error/Exception names), not proof that lost anchors caused a drop.

The published BM25 artifact regression pins Verified L2/L3 and all-L2 rows to recorded precision.
Verified uses folder means; all-L2 uses a mean of per-dataset folder means, which differs from the
plain 632-folder mean. Passing this artifact check does not reproduce retrieval from unavailable
raw corpora. A new corpus reproduction is a separate, currently blocked gate.

For the actual dev ablation, the two ready configurations include Pro openlibrary, qutebrowser,
ansible and Live conan, haystack, streamlink; L3 is available for the three Pro repositories.
Acquire all original and Rewrite query files first, then run on the verified account:

```sh
make eval RUN= CONFIG=configs/experiments/c_rewrite_bm25_dev.yaml
# GPU allocation only, after quota/card checks and cached model acquisition:
RIL_CLUSTER=1 python -m ril.evaluation.rewrite_cache --config configs/experiments/c_rewrite_dense_dev.yaml
make eval RUN= CONFIG=configs/experiments/c_rewrite_dense_dev.yaml
```

The cache preparer calls the existing DenseEncoder, gates CUDA with a real matrix product and
uses the pinned cached model (no download while holding the GPU). It rejects score matrices above
its configurable memory ceiling and writes each completed file atomically. This does not replace
measured full-process memory sizing before a new scale. Current account access/data absence blocks
these actual-data commands; no completed ablation or GPU cost is claimed.
