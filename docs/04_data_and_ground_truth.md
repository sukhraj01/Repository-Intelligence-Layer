# Ground truth and datasets

> **Derived copy** of the team's Master Project Document (rev 16, dated 2026-10-11).
> The master doc is the source of truth. If this file and the master disagree, the master wins; record the drift as an Open question in `PROJECT_STATE.md` instead of silently editing here.

*Master-doc section(s): Ground truth and datasets.*

Ground truth is not missing. It is a dataset-selection and disjointness problem, and the only piece that must genuinely be built is the training pool.

## The constraint that breaks the obvious plan

**CORE-Bench releases evaluation data only.** The HuggingFace release is Level-2, Level-3 and rewritten-query benchmark data, laid out as `LEVEL-2/<dataset>/<repository>/` with `corpus.jsonl`, `queries.jsonl`, `qrels.jsonl`. There is no train split. The 53,301-PR SFT set used in the paper was not released.

So "train on CORE-Bench supervision" has no referent. CORE-Bench is evaluation, full stop.

## The mining recipe

All three published training sets used the same mechanical procedure, and it requires no human annotation:

- Mine merged PRs that close an issue.
- Issue text becomes the query.
- Functions touched by the patch become positives.
- Other functions in the same repository become negatives; mine hard ones by similarity.
This is what SweLoc, CoRNStack and CORE-Bench's SFT set all did. Replicating it on repositories post-dating model cutoffs is the honest answer to "establish your ground truth".

## Dataset assignment by stage

| Stage | Dataset | Role | Note |
|---|---|---|---|
| A — train | **SweLoc** (SweRank) | Primary pool | Purpose-built for issue localization; not published under that name: the available candidate, `gangiswag/train_data` python, is the Python part of SweLocMulti (SweRank+) and holds benchmark repositories (corrected, see DEV-001 and DEV-004) |
| A — train | **Own PR-mined set** | Contamination-safe replication | The piece we actually build |
| A — train | CodeSearchNet | Transfer-gap arm | Not a substitute for repo-level data |
| C — retrieval eval | **CORE-Bench L2** | Primary metric | Issue-to-edit localization |
| C — retrieval eval | **CORE-Bench L3** | Structural / graph question | Tests, docs, configuration |
| C — retrieval eval | CORE-Bench L2/L3 REWRITE | Free query-rewriting ablation | Paper reports rewriting can hurt |
| C — retrieval eval | Loc-Bench | Contamination check, category balance | 560 examples in V1, 660 in V0.2; not every row post-dates Oct 2024 (corrected, see DEV-001) |
| C — retrieval eval | CoIR | Generalization | Cut first if behind |
| D — agent eval | **SWE-bench Verified** | Resolved rate | Overlaps L2 — see below |

Dropped: Nokia / Stack Overflow code-search data. It adds a third distribution with its own relevance biases, serves none of the three RQs, and is scope creep.

## The overlap: a trap and an opportunity

CORE-Bench Level-2 is registered over SWE-bench Pro, Verified, Live, SWE-Bench++, SWE-bench+, Multi-SWE-bench and SWE-bench Multilingual; Level-3 over Pro, Verified, Multi-SWE-bench and Multilingual. **SWE-bench Verified sits inside both.**

*The trap.* If the training pool contains any repository appearing in L2, L3 or Verified, there is leakage. Instance-level disjointness is insufficient — a model that saw `django` functions in training has an advantage on every `django` instance. Enforce **repository-level disjointness**: build the held-out repo list first, filter the training pool against it, report the counts.

*The opportunity.* Because the same instances carry both retrieval qrels and executable tests, retrieval quality and resolved rate can be computed **on the same instance and paired**. RQ3 then becomes "for instances where retrieval improved, did resolution improve" — a paired per-instance analysis with far more power than comparing aggregate rates at n=30–50. This is the strongest single design choice available and it exists only because of the overlap.

## Label quality caveat to state out loud

LocAgent is explicit that patch-derived locations are approximate: a bug can be fixed somewhere other than where it was fixed historically, so gold locations are approximate targets. They also exclude edited documentation, import statements and comments from the localization target. The RQ2 false-negative discussion is literally about this.
