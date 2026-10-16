# Open decisions

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): Open decisions.*

Every one of these must close by end of week 2. Each has a recommendation; none is settled until the team agrees and it is written down.

| # | Decision | Options | Recommendation |
|---|---|---|---|
| 1 | Training pool | SweLoc / own PR-mined / both | **Both** — SweLoc to avoid being blocked, own set for contamination safety |
| 2 | Quality signal | SweRank K-rank / heuristics / LLM judge | **K-rank**, published and continuous |
| 3 | Graph role | retrieval signal (hop-decay score) vs agent tool (TraverseGraph) | **Signal** — matches RIL architecture and keeps latency predictable |
| 4 | Retrieval granularity | function / CORE-Bench chunks / both | **Both** — chunks for reported metrics, functions internally |
| 5 | Primary benchmark | L2 / L3 / Loc-Bench | **L2 primary, L3 for the graph question**, Loc-Bench as contamination check |
| 6 | Base encoder | CodeBERT / UniXcoder / Qwen3-Embedding-0.6B | **Qwen3-0.6B** — CORE-Bench reports strong post-SFT results at CPU-feasible size |
| 7 | Agent scaffold | SWE-agent / OpenHands / Agentless / custom | **Agentless** — simplest to hold constant; complexity is a liability here |
| 8 | Base LLM for agent | API / local quantized | Decide on budget; if local, quantize identically across all arms |
| 9 | Cross-encoder rerank | include / exclude | Include but measure; it likely dominates latency |
| 10 | Usable by others? | yes / no | Decide now — it changes CLI, config and packaging decisions in week 1, not week 10 |

## Week-1 deliverables, in order

- Freeze the CodeUnit schema and write it down — every component reads it; changing it in week 9 means re-indexing and re-running everything
- Build the held-out repository list from CORE-Bench L2/L3 and SWE-bench Verified
- Filter any candidate training pool against that list; record how many instances survive
- Stand up the per-commit latency harness (fixed query set → p50/p95/p99 per stage → append-only CSV)
- Parse one real repository end to end; print ten CodeUnits and the call-graph edge-recovery percentage
- Decide items 1–10 above and record the decision and reasoning

## Things to say "I don't know" about

Do not bluff on: exact figures from papers not read in full; whether the effect will be significant; which intervention will win; implementation details not yet decided. "That is provisional — I will fix it in week 1 once I have looked at the data" is a complete and respectable answer.
