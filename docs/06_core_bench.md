# CORE-Bench reference

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): CORE-Bench reference.*

[CORE-Bench](https://arxiv.org/abs/2606.11864) (Zhang et al., Beihang/Peking, arXiv 2606.11864, submitted 10 June 2026, revised 13 July 2026) establishes that repository-level retrieval is a distinct and much harder problem than snippet retrieval. It is our primary evaluation and our framing.

Data: [zhangfw123/CORE-Bench](https://huggingface.co/datasets/zhangfw123/CORE-Bench) · Code: [CORE-Bench-Eval](https://github.com/zhangfw123/CORE-Bench-Eval) · built on MTEB.

## The three levels

| Level | Goal | Scale |
|---|---|---|
| L1 — Code Understanding | Text-to-code, code-to-text, code-to-code, hybrid, competitive programming | 172,961 queries; 2,412,296 corpus items |
| L2 — Issue-to-Edit Localization | Retrieve files or chunks that must be modified | 632 folders (605 distinct repositories; corrected, see DEV-002); 5,061 queries; 9,377,120 chunks |
| L3 — Broader Context Retrieval | Retrieve auxiliary code, tests, documentation, configuration | 97 folders (92 distinct repositories; corrected, see DEV-002); 2,580 queries; 2,609,581 chunks |

L2 and L3 are built from SWE-bench-series instances. Registered groups: `CORE_BENCH_LEVEL1`, `LEVEL2`, `LEVEL3`, `LEVEL2_REWRITE`, `LEVEL3_REWRITE`.

## The performance cliff (nDCG@10)

| Model | L1 | L2 | L3 |
|---|---|---|---|
| Qwen3-8B | 71.7 | 20.3 | 34.4 |
| e5-mistral-7b | 54.7 | 18.3 | 33.9 |

Roughly a 70% collapse from L1 to L2. Code-specific embedding models — CodeRankEmbed, Jina Code, SweRankEmbed-Large — do not meaningfully close the gap.

## Four findings that shape our design

- **Cross-level correlation is weak.** L1 only moderately predicts L2. Snippet benchmarks tell you almost nothing about agent performance — this independently justifies our "metrics are a leaky proxy" argument.
- **Dense repositories punish recall.** Recall@100 drops sharply in large tightly-coupled codebases even when nDCG@10 holds; relevant chunks are pushed past the top-100. This is the recall-ceiling problem, measured.
- **Query rewriting can hurt.** Cleaning issue text removes repository-specific anchors — error strings, API names, URLs — that are critical signals. Either drop query expansion or ablate it against the REWRITE splits.
- **SFT on repository-level data works.** Qwen3-0.6B 17.0→26.5 (+56%), Qwen3-8B 20.3→32.8 (+62%), trained on 53,301 PRs across 628 repositories with multi-positive InfoNCE and repository-local hard negatives. A 0.6B model reaches ~80% of the 8B model's post-SFT performance.
That fourth finding is why RQ2 is a comparison of interventions and not a demonstration that supervision matters.

## What it does not measure

- Token cost of an agent's multi-step exploratory search loops — single-pass retrieval only
- Repository freshness; it uses fixed snapshots, so stale-index behaviour is untested
- Cross-language retrieval; L2 and L3 are segmented by language

## Granularity mismatch to resolve

L2 retrieves files or chunks, averaging roughly 15,000 chunks per repository. Our CodeUnit design is function-level. Recommendation: adopt their chunking for reported metrics so numbers are comparable, keep function-level units internally for the graph.
