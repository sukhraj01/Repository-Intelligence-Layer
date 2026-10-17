read: full — 16 pages incl. appendices, PDF v1, pdftotext -layout (poppler), 2026-10-17

# CodeGrep — Chen et al. (arXiv 2608.05886v1, 6 Aug 2026), "CodeGrep: An RL-Trained Retrieval Agent for LLM Coding Agents"

Source file: arXiv PDF v1, 16 pages (body 8 pages, references pp.8-9, appendices A-F pp.10-16: infrastructure, reward details, training diagnostics, retriever baselines, a case study). arXiv holds only v1. The extracted text has 16 pages and no blank page. Every page was read, including Tables 1-8. Literature-scan source (topics: training-data quality for retrievers; and the closest published test of whether a trained retriever changes resolved rate with the agent held fixed).

## What it established

- A 14B retrieval agent (grep, glob and read tools, up to four turns) trained with reinforcement learning against file labels that combine the SWE-bench gold-patch files with files mined from 67,074 open-source agent trajectories ("CATM"; Sec. 3.4, pp.3-4). The trajectory miner keeps each file an earlier agent opened and reasoned about, has a judge model label the post-read reasoning relevant or not, and weights files by a saturating function of reasoning length (weight at least 0.15 to keep); 31,977 samples (47.7%) survive (Sec. 3.4, p.4; Appendix A, p.12).
- Downstream test with the agent held fixed: the retriever's output is injected into a frozen OpenHands agent with a 30B open model on all 500 SWE-bench Verified instances (Sec. 4.1, p.5; Table 3, p.7). Baseline (no retrieval) resolves 25.8%, BM25 top-2 25.2%, a dense code embedding model (Jina 1.5B) top-2 25.8%, CodeGrep 27.0% (+1.2 points); resolved-issue rounds fall from 23.0 to 19.6 and tokens from 631K to 514K for CodeGrep, while BM25 raises tokens to 763K (Table 3, p.7).
- The authors read this as a precision threshold: file-level precision 0.375 (BM25) hurts, 0.445 (dense) is neutral, 0.677 (CodeGrep) buys efficiency (Sec. 5.1, pp.6-7; Table 2, p.6). They also report that moving an efficiency term from the reward to the advantage estimator cut policy drift (KL 0.31 to 0.09) and that dropping a line-range reward term improved both training stability and downstream efficiency (Sec. 3.5 and 5.2, pp.4-8).
- Within the 94 instances that the baseline and BM25 both resolve, BM25 uses 6.6% more rounds and 38.6% more tokens (p.7); within the 96 that the baseline and CodeGrep both resolve, rounds fall 20.1 to 18.3 and tokens 525K to 448K (Sec. 5.3, p.8).

## What it did not establish

- The resolved-rate gain is 1.2 points, which is six instances out of 500; there is one run per configuration and no seed, interval or paired test anywhere in the paper (searched for), although the abstract says "reproducibly positive". The authors' own words for the main result are "small but reproducibly positive" (abstract, p.1) and "contribution is concentrated on rollout cost, not resolve rate" (Limitations, p.8). The comparison of the baseline (25.8%) with the publicly reported figure for the same configuration (25.2 ± 0.7%) is the only variance reference (p.5).
- The precision threshold rests on three retrievers and is not tested elsewhere; the authors say transfer to other agents is open (p.7).
- No leakage statement for the downstream test: the training trajectories come from a public set whose reference title names SWE-bench Verified (reference list, p.9), the paper states that its retrieval-quality evaluation uses held-out instances of another dataset (Sec. 4.2, p.6), and nothing says whether the Verified instances or their repositories overlap training trajectories (not found). This is the repository-disjointness question the project's leakage tests exist for.
- Not a supervision-quality comparison: the three trained versions differ in reward design, not in training data; there is no unfiltered-data arm, so the 47.7% retention filter is not ablated.
- The dense baseline is a pretrained embedding model used zero-shot; BM25 and the dense model are given the same top-2 budget; a trained embedding retriever is not tested.

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

| Claim | Value | Where |
|---|---|---|
| Resolve rate on 500 Verified instances: no retrieval / BM25 / dense embedding / CodeGrep | 25.8% / 25.2% / 25.8% / 27.0% | Table 3, p.7 |
| Resolved-instance rounds and tokens: baseline / CodeGrep | 23.0 and 631K / 19.6 and 514K | Table 3, p.7 |
| BM25 resolved-instance tokens | 763K | Table 3, p.7 |
| Dense embedding resolved-instance tokens | 587K | Table 3, p.7 |
| File precision: BM25 / dense embedding / CodeGrep | 0.375 / 0.445 / 0.677 | Table 2, p.6 |
| Share of issues with F-beta at least 0.8: BM25 and dense / CodeGrep | 7.0% / 43.0% | Table 2, p.6 |
| Publicly reported baseline for the same configuration | 25.2 +- 0.7% | Sec. 4.1, p.5 |
| Trajectories mined / effective training samples | 67,074 / 31,977 (47.7%) | Sec. 3.4, p.4; Table 5, p.12 |
| Policy drift (KL to reference), reward-layer scaling against advantage-layer scaling | about 0.31 against 0.09 | Sec. 5.2, p.6 |
| Instances resolved by both baseline and BM25 / by both baseline and CodeGrep | 94 / 96 | Sec. 5.1, p.6; Sec. 5.3, p.8 |
| Training cost | about 27 hours per run, stopped at step 897 of 2000 | Sec. 3.6, p.5 |
| Number of runs per configuration | not stated (one reported) | Sec. 4, pp.5-7 |

## Method details we need

- **Training data (supervision)**: positives = gold-patch files plus mined files with weight at least 0.15; every kept file is a hard positive in the reward (Sec. 3.4, p.4). The mining judge is an open model (named in Appendix A.2, p.11) run in 16 threads for about five hours; the weighting constants are estimated over the whole data set in two passes.
- **Reward**: precision-biased F-beta (beta 0.5) on files, an efficiency scale applied at the advantage layer, no line-range term in the final version (Sec. 3.5, p.4).
- **Agent and retriever settings**: frozen OpenHands agent, a 30B open model, temperature 0, 100-round maximum; the retriever returns a short file list injected into the instruction text (Sec. 3.1 p.2; Sec. 4.1 p.5). BM25 and the dense model each return their top 2 files (Table 3 caption, p.7).
- **Retrieval-quality evaluation**: an internal held-out set of another public dataset with mined labels, audited by the authors' engineers (Sec. 4.2, p.6).
- **Hardware**: one node with eight accelerators; LoRA rank 32 on a 14B model (Appendix A.4, p.11).

## Relation to RQ1 / RQ2 / RQ3

- RQ1: none directly; it shows retrieval precision at a top-2 budget, not ranking quality over the repository.
- RQ2: its supervision is trajectory-mined, judge-filtered and reweighted positives (47.7% kept), the same kind of intervention as the FILTER and WEIGHT arms, but the paper does not compare against an unfiltered arm.
- RQ3: it is the closest published test of "retriever changes, agent fixed, resolved rate measured": +1.2 points on 500 Verified instances for a retriever that is far better by precision (0.677 against 0.375 and 0.445), and a loss for the weakest one. It reports efficiency effects larger than resolved-rate effects. For the project's power analysis (n = 432 and 302 in the paired set) a 1.2-point difference on 500 instances is far below what the planned tests can resolve; see the power table in the experiments document when it exists.

## Discrepancies

- Abstract against body: "reproducibly positive" resolve-rate lift, where the body reports one run per configuration and the Limitations paragraph says the contribution is concentrated on cost, not resolve rate (pp.1, 8).
- Table 3 reports resolved rounds for the three CodeGrep iterations (22.7, 21.4 and 19.6), while the text for CodeGrep v1 says "−1.3% rounds" relative to 23.0 (p.7); these are consistent (22.7 is 1.3% lower).

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Search lead: a trained retriever evaluated by resolved rate with the agent fixed | confirmed, with small effect | Table 3, p.7 | +1.2 points on 500 instances, one run; efficiency gain 15% rounds and 19% tokens on resolved instances. |
| "Retrieval quality translates through a precision threshold" | stated, three data points | Sec. 5.1, p.6-7 | Not tested on other agents; the authors flag transfer as open. |
