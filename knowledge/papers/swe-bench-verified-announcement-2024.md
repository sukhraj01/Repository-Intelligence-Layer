read: web capture — 24422 characters of extracted text, archive capture of 2024-12-31, capture SHA-256 dcafd11646b7a9f47d1d58d20332ae9afebe907001f0642a515d04b237593389, extracted-text SHA-256 8804d1c17b0f106fb3853a06abb9b3d7d701d3ca3b029f5d24e33e89c5183a9c, read 2026-11-14

# Introducing SWE-bench Verified — Chowdhury, Aung, Shern, Jaffe, Sherburn, Starace, Mays, Dias, Aljubeh, Glaese, Jimenez, Yang, Liu and Madry (web announcement, 13 August 2024)

Source: the announcement page of the company that ran the annotation. The live page answered HTTP 403 to every fetch tool on 2026-11-12, so the source is the Internet Archive capture of 2024-12-31 (`web.archive.org/web/20241231052539id_/https://openai.com/index/introducing-swe-bench-verified/`). **Capture rule for a web source:** the capture is stored unmodified under `data/raw/web/swe-bench-verified-announcement-2024/capture.html` (352,484 bytes, SHA-256 in the header; the folder is untracked like all raw data and holds a `provenance.json` with the URL, capture date and fetch date), its extracted text beside it (`capture_extracted.txt`, scripts and styles removed, tags replaced by line breaks, entities unescaped, blank lines dropped, no trailing newline; length and SHA-256 in the header), and the header form is the one `ril/util/paper_note.py` checks (`scripts/check_paper_note.py NOTE EXTRACTED.txt` confirms the length and the hash and re-finds every number of the table below). The capture was read from title to the footnotes on 2026-11-12 (first extraction: 24,942 characters, SHA-256 `7a70b258be81ff1d5e4dfa778e5ceb63057ce459403b4199a384184fac158085`, a different extraction of the archive's wrapped page) and fetched again on 2026-11-14 in its unmodified form; every claim below was found again in that text. No PDF exists and the page declares no version. A claim below is a statement of the page, nothing re-derived; the page is a web announcement, not a reviewed paper.

## What the page states (claims relied on)

- It is a subset of the original benchmark's test set, released together with the benchmark's authors, of 500 samples "verified to be non-problematic" by human annotators; it "supersedes the original SWE-bench and SWE-bench Lite test sets" (section "SWE-bench Verified").
- Annotation: 93 software developers experienced in Python annotated 1,699 random samples of the test set; each sample was labelled three times by separate annotators, and the highest-severity label of the three was kept (section "Our Approach").
- Two criteria, each on a 0 to 3 scale: whether the issue text is underspecified, and whether the tests that must go from failing to passing could reject valid solutions; a difficulty estimate and a free-text field for other major issues were collected but the difficulty was not used for filtering ("Annotation Criteria").
- Construction: a sample is dropped if either criterion has an ensemble label of 2 or more, or any other major issue is flagged; the 500 are drawn by including as many samples of the two hardest difficulty buckets as possible and sampling the rest at random ("Dataset construction").
- Result of the annotation on the 1,699: 38.3% flagged as underspecified, 61.1% flagged for tests that may reject valid solutions, 68.3% filtered out in all; the authors call the filtering "likely to be overzealous" ("Annotation Results").
- Difficulty: most samples of the original benchmark were estimated at under an hour for an experienced engineer (77.8% of the 1,699); in the 500, fewer than 10% are estimated to take longer than an hour ("Annotation Results").
- The sampling of the 500 is stratified toward the hardest buckets and is not a uniform sample of the original test set (inference from "Dataset construction").
- Authors state the benchmark is built from scrapes of public repositories and that large models pretrained on internet text are "likely to be contaminated on the tasks" ("Discussion & Limitations").
- Alongside, a containerised evaluation harness was developed with the original authors; the annotations and the rubric are released.

## What it did not establish

- Any retrieval label: nothing about which files or functions a fix touches.
- The 500 are not a random sample of the benchmark, and the resolved rate on them is not an estimate of the rate on the original set.
- Annotator agreement beyond the three-label ensemble: no agreement statistic is given.
- The page describes the annotation of tests as a judgement of coverage by humans; a later study found test-insufficient instances among the 500 (`utboost-2506.09289.md`, 26 of 500 by its own method).

## Numbers we may quote

| Claim | Value | Where |
|---|---|---|
| samples in the released subset | 500 | section SWE-bench Verified |
| annotators | 93 | section Our Approach |
| samples annotated | 1,699 | section Our Approach |
| annotations per sample | 3 | section Our Approach |
| flagged as underspecified | 38.3% | section Annotation Results |
| flagged for tests that may reject valid solutions | 61.1% | section Annotation Results |
| filtered out in all | 68.3% | section Annotation Results |
| severity at which a criterion filters a sample | 2 | section Dataset construction |

## Relation to RQ1 / RQ2 / RQ3

- RQ3 and the report's evaluation section cite it for what the subset is. The project's executable subset of 377 instances (E-RQ3-EXEC) is a further selection on top of these 500 (gold patch passes in two agreeing runs without a container), so a result there does not carry to the excluded instances; the benchmark's construction filter is therefore not the project's filter.
- The original benchmark paper does not describe the subset (`swe-bench-2310.06770.md`); this announcement is the source for its construction.

## Discrepancies

- A secondary website lists difficulty bin counts of 194, 261, 42 and 3 for the 500, from the dataset's difficulty field; the announcement gives percentages in its chart instead, and no count of the first two bins was found in its text. The counts were not verified and are not used.
- The page's chart percentages and the prose agree where both exist (38.3% is 31.9% plus 6.4%, and 61.1% is 32.8% plus 28.3%).
- UTBoost (`utboost-2506.09289.md`) restates the 500 and the 93 annotators and cites this page, so the two agree on those two figures.

## Claims checked

| Claim | Verdict | Where | Note |
|---|---|---|---|
| The original benchmark paper describes the subset | not found | `swe-bench-2310.06770.md` | The subset is described only here. |
| 500 samples, human-validated, with the benchmark's authors | confirmed | section "SWE-bench Verified" | Page text; no PDF. |
| 93 annotators, 1,699 samples annotated, three labels per sample | confirmed | section "Our Approach" | Page text; no PDF. |
