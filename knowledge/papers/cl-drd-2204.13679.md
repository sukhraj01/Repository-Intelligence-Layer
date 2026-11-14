read: full — 5 pages incl. appendices, PDF v1, pdftotext -layout (poppler), page counts equal (pdfinfo 5, extracted 5, none blank); Table 1 and Figure 2 (page 4) rendered and looked at; there is no appendix; re-read in full from the stored PDF (SHA-256 2217eb3c81c596876582075a873bea892c37041d797c87348eb6444788da12cc), first read 2026-10-29, 2026-11-14

# CL-DRD — Zeng, Zamani and Vinay (arXiv 2204.13679v1, SIGIR 2022 short paper), "Curriculum Learning for Dense Retrieval Distillation"

Re-read 2026-11-14 from the stored PDF: body and appendices read page by page; the reference list (pp. 5 (reference list)) was checked for the entries the text cites rather than read entry by entry.

Source file: arXiv PDF v1 (28 Apr 2022), 5 pages (body pp.1-4 with the references starting on p.4 and ending on p.5). Text passage retrieval distilled from a cross-encoder. Note on identifiers: a search-listing parse in this session first paired this title with 2204.01458, which is an unrelated image-retrieval paper; the PDF at 2204.13679 is the paper described here. The 2204.01458 PDF was fetched, read as far as its title page and abstract, found off topic and dropped.

## What it established

- A curriculum over the teacher's supervision rather than over the order of examples: in three successive iterations the student is trained with the top K of the teacher's re-ranked list of the student's own top-200 as "pseudo-relevant" (K = 5, 10, 30), with the number of sampled hard-negative and easy-negative documents shrinking so that the list length stays 30; pairs inside the pseudo-relevant group (which force the exact order) grow from 10 to 45 to 435 (Sec. 2.2.1, pp.2-3). Difficulty is therefore the fineness of the ordering demanded (coarse group distinctions first, exact order within the group last).
- Applied to a 66M single-vector retriever initialised from TAS-B, MS MARCO dev MRR@10 goes from 0.344 to 0.382 ("11% improvement"), nDCG@10 on TREC DL 2019 from 0.717 to 0.725 and on DL 2020 from 0.685 to 0.687 (Table 1, p.4). For a multi-vector model the dev MRR@10 changes from 0.384 to 0.394 (Table 1, p.4).
- A reverse curriculum (the same three iterations in the opposite order) ends lower: MS MARCO dev MRR@10 0.378 against the forward curriculum's 0.382, nDCG@10 0.715 and 0.683 on the two TREC sets (Sec. 3, p.5). The authors read the per-iteration curves of the forward run as rising on all three sets (Figure 2, p.4).

## What it did not establish

- The comparison "curriculum against a single training with the final K = 30 configuration for the same total epochs" is not run; the reverse curriculum is the only control, and it differs from the forward run by about 0.4 MRR@10 points on one run (0.378 against 0.382). No seeds are reported.
- Paired t-tests are over queries from a single run (Table 1 caption, p.4); the TREC sets have 43 and 54 queries. Nothing about code or about repositories as the unit.
- The teacher is a separate small cross-encoder (a published 6-layer model), so teacher independence is by construction, but no variation in teacher quality is tried.
- The first-iteration effect cannot be separated from the effect of distillation itself in the reported numbers (the comparison base TAS-B was trained with its own distillation).

## Numbers we may quote

All values are from this paper (label `paper_reported`, never `measured`). Page numbers are PDF pages.

The paper prints scores without a leading zero (".382"); they are copied in that form and were found again in the extracted text by hand, because the checker does not read them.

| Claim | Value | Where |
|---|---|---|
| MS MARCO dev MRR@10, single-vector retriever: base / with curriculum distillation | .344 / .382 | Table 1, p.4 |
| TREC DL 2019 nDCG@10: base / with curriculum | .717 / .725 | Table 1, p.4 |
| TREC DL 2020 nDCG@10: base / with curriculum | .685 / .687 | Table 1, p.4 |
| Multi-vector retriever dev MRR@10: base / with curriculum | .384 / .394 | Table 1, p.4 |
| Reverse curriculum: dev MRR@10 | .378 | Sec. 3, p.5 |
| Reverse curriculum: TREC DL 2019 / 2020 nDCG@10 | .715 / .683 | Sec. 3, p.5 |
| Pseudo-relevant group size per iteration (K) | 5, 10, 30 | Sec. 2.2.1, p.3 |
| Ordered pairs inside the pseudo-relevant group per iteration | 10 / 45 / 435 | Sec. 2.2.1, p.3 |
| Documents scored per query by the teacher | 200 | Sec. 2.2.1, p.2 |
| Training queries (MS MARCO) | 503K | Sec. 3, p.3 |
| Batch size / max passage length | 8 / 256 | Sec. 3, p.3 |

## Method details we need

- Per iteration: re-rank the student's current top-200 for each training query with the teacher; group 1 = teacher's first K, group 2 = next K', group 3 = remainder; sample N_h from group 2 and N_s from group 3 so that K + N_h + N_s = L = 30 (Fig. 1, Sec. 2.2.1, pp.2-3). Pseudo-labels 1, 0, -1; listwise loss of the LambdaRank form over pairs with different labels, weighted by the reciprocal-rank gap in the student's list (Eq. 2, p.3).
- Learning rates 7e-6, 3e-6, 3e-6 over the three iterations with a 4000-step warm-up; fixed epochs per iteration (Sec. 3, p.3).

## Relation to RQ1 / RQ2 / RQ3

- RQ1, RQ3: none.
- RQ2: the only curriculum in this reading whose "easy to hard" axis is defined by a teacher (rank-based, from a separate model) and which has a reverse-order control. It does not sort pairs by difficulty: it changes the supervision's granularity per phase, so it does not transfer one-to-one to an ordering of pool directories by K-rank. What it does show is that the control that matters for a curriculum claim is the reversed order, not a no-curriculum arm, and that its single run separates them by about 0.4 MRR@10 points. The project's CURRICULUM arm (stable sort by K-rank, with a constant-difficulty identity) is a different object.

## Discrepancies

- With the master document: not cited there; "curriculum" in the master means ordering by difficulty, which this paper does not do.
- With ADAM (`adam-2212.10192.md`): ADAM calls CL-DRD a data curriculum and reports it as a baseline (BEIR 42.0 against 42.8, ADAM Table 2); here the difficulty is the target's granularity.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| Curriculum improves the student | confirmed on one run with query-level tests | Table 1, p.4 | gain on dev 0.038 MRR@10 over the base |
| Forward beats reverse | confirmed, small | Sec. 3, p.5 | 0.382 against 0.378, one run |
| Curriculum beats a no-curriculum run at equal updates | not found | - | control not run |
