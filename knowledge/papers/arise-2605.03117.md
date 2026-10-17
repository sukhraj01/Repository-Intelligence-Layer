read: full — 13 pages incl. appendices, PDF v2, pdftotext -layout (poppler) plus a page raster of the patch-type and trajectory figures (p.10, looked at, no number quoted from them), 2026-10-17

# ARISE — Seddik, Seddik, Esmaeili, Sadatbenis, Fard (arXiv 2605.03117v2, 3 Jul 2026)

Source file: arXiv PDF v2, 13 pages (body 11 pages, references pp.12-13; the paper has no appendix). The extracted
text has 13 pages and no blank page (`scripts/check_paper_note.py`). Every page was read. The paper is a preprint;
the first-pass notes and `knowledge/papers/README.md` list it as an ARISE graph with data-flow edges and a
call-resolution policy.

## What it established

- A multi-granularity Python program graph (directory, module, class, function, method and statement nodes;
  contains, imports, calls, inherits and intra-procedural definition-use edges) exposed to a tool-using agent through
  three tiers: structural navigation, a data-flow slice query, and a token-budgeted context bundle (Sec. 3,
  pp.4-5).
- With an open 32B backbone and SWE-agent as the host, adding the toolset raises resolved instances on SWE-bench Lite
  from 52 to 66 of 300, and raises function-level Recall@1 from 0.43 to 0.60 (Table 2, p.7; Table 3, p.8).
- A control that exposes the slice tool but builds the graph without statement nodes or data-flow edges stays within
  0.01 of the structural-only condition, which attributes the slicing gain to the graph and not to the extra
  tool (Table 3, p.8; Sec. 4.4, p.8).
- The same toolset mounted on a second host with a larger open backbone helps on one host and hurts on the other
  (Table 4, p.9).
- Remaining failures are mostly "wrong file" because the slice does not cross call edges (Table 5, p.9).

## What it did not establish

- No per-edge-type ablation of the structural edges. The ablation adds tiers of tools (Structural, Slicing, Full) and
  one control (Coarse); import, call and inherit edges are never removed individually, and the call-resolution policy
  is not compared with a more permissive one.
- No measurement of how accurate the resolved call edges are or how many are dropped.
- One attempt per instance and per condition, no seeds, no confidence intervals (Sec. 6.1, p.11). The 4.7-point gain is
  14 instances (Sec. 4.2, p.6).
- The localization-repair link is correlational: localization and repair run in separate sessions and the Spearman
  coefficients are across conditions of one instance set (Sec. 4.3, p.7; Sec. 6.3, p.11).
- No per-query latency; graph-build time and tokens only (Sec. 5.3, p.10; Table 6, p.9).
- "Structural" is the authors' re-implementation of capabilities of earlier systems, not those systems run as
  published (Sec. 3.3, p.5); the published RepoGraph and the other baseline rows are partly adopted from the
  literature (Table 2, p.7).
- No held-out or contamination analysis beyond using the base-commit snapshot and holding the backbone fixed
  (Sec. 6.1, p.11).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages. Backbone is an
open 32B coder model unless stated.

| Claim | Value | Where |
|---|---|---|
| Resolved on SWE-bench Lite (of 300): bare host / host with structural graph (re-implementation) / full toolset | 52 (17.3%); 57 (19.0%); 66 (22.0%) | Table 2, p.7 |
| Resolved: slicing tier / structural graph with the slice tool but no data-flow graph | 63 (21.0%); 59 (19.5%) | Table 2, p.7 |
| Resolved: host plus the published RepoGraph / Agentless / KGCompass (same backbone) | 58 (19.3%); 40 (13.3%); 46 (15.3%) | Table 2, p.7 |
| Lexical lower bound (BM25, no agent) | 8 (2.67%) | Table 2, p.7 |
| Tokens per instance (thousands): host / structural / slicing / full | 510 / 531 / 550 / 560 | Table 2, p.7 |
| Function Recall@1: host / structural / control / slicing / full | 0.43 / 0.50 / 0.51 / 0.57 / 0.60 | Table 3, p.8 |
| Function Recall@1 of a dedicated localization agent | 0.35 | Table 3, p.8 |
| File Recall@1: host / full | 0.57 / 0.67 | Table 3, p.8 |
| Line Recall@1: host / full | 0.26 / 0.41 | Table 3, p.8 |
| Spearman correlation of Function R@1 and Pass@1: host / structural / slicing / full | 0.38 / 0.42 / 0.51 / 0.53 | Table 2, p.7 |
| Newly localized instances that turn resolved vs unchanged-localization instances | 28% vs 3% | Sec. 4.3, p.8 |
| Failure categories for the full toolset (234 failures): wrong file / right file wrong function | 99 (42%) / 58 (25%) | Table 5, p.9 |
| Portability, larger open backbone: host alone / host with toolset | 100 / 102 of 300 | Table 4, p.9 |
| Second host alone / with toolset (after adapting its tool layer) | 109 / 96 of 300 | Table 4, p.9 |
| Second host with the toolset before adapting its tool layer | 3.6% | Sec. 4.5, p.9 |
| Graph size per repository, median nodes / edges / statement nodes | 134,000 / 313,000 / 94,000 | Sec. 5.3, p.10 |
| First-build time: smallest / median / largest repository | 1.7 s / 2.2 min / 33 min | Sec. 5.3, p.10 |
| Share of build time in the data-flow pass | 96% to 99% | Sec. 5.3, p.10 |
| Maximum agent turns (the bundle budget is 8 000 tokens, written with a space in the paper) | 40 | Sec. 4.1, p.6 |
| Bundle scoring weights | 1.0, 0.5, 1.5 | Sec. 3.3, p.5 |

## Method details we need

- **Graph (Sec. 3.2, p.4).** Python `ast`. A structural pass emits directory, module, class, function and method
  nodes with contains, imports, imported-by and inherits edges. A second pass resolves calls against the caller's import
  alias map and keeps only unambiguous direct calls and qualified `module.function()` calls; dynamic dispatch through
  attribute access is dropped on the stated ground that spurious call edges are more harmful than missing ones
  (cited, not tested here). A program-graph pass makes one statement node per top-level statement in each function and
  adds intra-procedural definition-use edges by a reaching-definition scan in source order; globals and nonlocals
  are handled.
- **Tools (Sec. 3.3, pp.4-5).** Tier 1: entity search by TF-IDF, bounded traversal along given edge types, enclosing
  scopes, code spans, entity info. Tier 2: a slice query (backward, forward, both; stops at function boundaries). Tier
  3: a context bundle packed greedily under a token budget by a hand-set score of relevance, proximity and slice
  membership, and a suspect ranking that expands through the call subgraph.
- **Protocol (Sec. 3.5, pp.5-6; Sec. 4.1, p.6).** SWE-bench Lite (300 instances, 11 repositories); localization and
  repair are separate sessions; Pass@1 from one patch; recall at file, function and line level.
- **Reproducibility (Sec. 4.1, p.6).** Open-weight backbones served locally with fixed decoding settings; the standard
  SWE-bench Docker harness.

## Graph facts recorded for this project (R2 fields)

| Field | ARISE |
|---|---|
| Graph role | agent tool (queryable navigation and a data-flow slice); the bundle ranker is a hand-set score; not learned |
| Edge types used | contains, imports, imported-by, calls, called-by, inherits, definition-use and use-definition (Sec. 3.2, p.4); nodes include statements; no test or configuration node or edge type |
| Edge types ablated | tool tiers and a data-flow-off control, not individual edge types (Tables 2-3, pp.7-8) |
| Resolution coverage measured | no; only a policy of resolving unambiguous calls and dropping dynamic dispatch |
| Latency | graph build seconds to minutes per repository; token cost per condition; no per-query latency (Sec. 5.3, p.10) |
| Held-out handling | no training; graph built from the base-commit snapshot to avoid retrieval-time leakage; backbone contamination acknowledged and held constant (Sec. 6.1, p.11) |

## Relation to RQ1 / RQ2 / RQ3

- RQ1: it measures a signal (data flow) that the project does not plan to build; its relevance is as a negative and
  as a design note: statement-level edges are intra-procedural and miss root causes in callees. The structural tier
  adds 1.7 resolved points over the host (Sec. 4.4, p.8), which is small next to the data-flow tier (2.0 points)
  and is one run.
- RQ2: nothing on supervision.
- RQ3: it is a retrieval-to-resolution example with the agent held fixed, on one backbone, one attempt per instance;
  the localization-repair correlation is suggestive, not causal, by the authors' own account (Sec. 4.3, p.7).
- Backbone dependence: the same published systems score very differently under the open backbone here (for example a
  published repair system at 15.3% in Table 2, p.7) than in their own papers, so graph benefits and backbone are
  entangled.

## Discrepancies

- **G4 "call resolution drops dynamic dispatch on purpose; no test or configuration nodes" holds** (Sec. 3.2, p.4).
  Test files are parsed as ordinary Python modules (every `.py` file is parsed) and nothing marks them as tests.
- With the abstract's "attribute the improvement to the data-flow graph rather than the tool schema" (p.1): supported
  by one control and a gap of 0.01 in Function R@1 (Table 3, p.8) and 1.5 points in Pass@1 between Slicing and
  the control (Table 2, p.7), one run each.
- Internal: the portability section says the second host dropped to 3.6% before its tool layer was adapted and to
  32.0% after (Sec. 4.5, p.9), so the second-host row of Table 4 is for a modified integration.
- Internal: Table 2 lists the agent, the backbone and the repair stage as fixed, but the token cost of the full toolset
  (560 thousand) is higher than the host's (510 thousand) (Table 6, p.9), so the gain is not free.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| G4 call resolution drops dynamic dispatch on purpose | confirmed | Sec. 3.2, p.4 | "we resolve only unambiguous direct and qualified module.function() calls and drop dynamic dispatch through attribute access"; justified by two cited works (p.4), not by an ablation here. |
| G4 no test or configuration nodes | confirmed | Sec. 3.2, p.4 | Node types are directory, module, class, function, method, statement; edge types listed on p.4 contain no test or configuration relation. |
