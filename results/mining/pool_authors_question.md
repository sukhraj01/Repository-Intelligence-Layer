# Draft question to the authors of the published training pool (for the engineer to send; not sent)

Status: draft. Nothing here was sent to anyone. The questions follow `docs/POOL_CONSTRUCTION.md`, which lists what the papers and the released scripts state and what they leave open.

**Subject:** How was `train.zip` of `gangiswag/train_data` produced from the per-positive rows?

Hello,

We are using the Python part of `train.zip` (24,285 pull-request directories, 2,448 repositories) as training data for a study of retriever supervision, and we are building a
second, independently mined set from pull requests to compare with it. The released data-construction scripts produce one row per positive function (a query, one positive, the
other functions of the snapshot as negatives) and filter each row with a retriever. We could not find how those rows became the per-pull-request directories (`corpus.jsonl`,
`queries.jsonl`, `qrels/test.tsv`) of `train.zip`, and the dataset repository has no card. Three short questions:

1. **Grouping.** Was `train.zip` written by the released scripts, or by a separate conversion step? If separate, could you share it or describe it? In particular: does a directory
   hold every modified function of its pull request as a positive, or only the rows that passed the filter?
2. **Filter.** Which retriever and which cut were applied to the Python rows of `train.zip`? The papers state CodeRankEmbed with K = 20 (first paper) and SweRankEmbed-Small with the
   top 40 (second paper, for the multilingual set); the released script drops a row whose positive ranks below index 10 under CodeRankEmbed. Was a pull request kept if at least
   one of its rows passed, or only if all did?
3. **Corpus identifiers.** The released structure code builds identifiers that start with the repository folder; the identifiers in `train.zip` do not. Was the folder prefix removed
   in the conversion, or was a different version of the code used?

A short answer, or a pointer to where this is written down, would be enough. We will cite the answer as a personal communication and will not describe the pool beyond what you confirm.

Thank you,
<name of the engineer>
