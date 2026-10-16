# Project identity + System versus experiment

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): Project identity, System versus experiment.*

## Project identity

RIL is a repository-level code retrieval layer for LLM coding agents, plus a controlled study of whether the retriever's training supervision affects whether the agent actually resolves the issue.

| Field | Value |
|---|---|
| Project | Repository Intelligence Layer (RIL) |
| Lead | Sukhraj Singh |
| Team | 3 members |
| Institution | IIIT Hyderabad |
| Course | NLP semester project (also targeting placements) |
| Duration | 16 weeks |
| Status | Research design locked; implementation not started |
| Language scope | Python only |

The professor has approved the direction and raised three requirements: establish the ground truth before anything else, consider knowledge graphs for structural information, and engage seriously with CORE-Bench as the setting. A standing fourth requirement applies to all his projects: latency and throughput analysis, profiled per component, recorded before every commit.

## System versus experiment

Two things are being built, and only one of them is the contribution. Stating this first prevents the single most likely objection — "code search already exists".

**The system (engineering).** A retrieval layer over a repository: function-level indexing, lexical plus dense plus structural signals, rank fusion, context assembly under a token budget. Not novel on its own. It is the apparatus, and for placement purposes it is also the portfolio artifact.

**The experiment (the research).** Several retrievers that differ only in training supervision, one fixed agent, and a measurement of whether the difference survives to task resolution. This is what a reviewer judges.

The two pull against each other and the project must hold both. A good experiment freezes the retrieval stack so only one variable moves; a good product tunes it however it takes. Resolution: build and tune RIL properly first, freeze a configuration before the supervision runs begin, and keep the frozen config separate from the demo config.
