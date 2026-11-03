# How the published training pool was constructed: what the sources state, and what they leave open (Q61)

Scope: the pool is the Python part of `gangiswag/train_data` (`train.zip`, 24,285 pull requests, 2,448 repositories; `knowledge/datasets/sweloc.md`).
This note separates three things and does not mix them: **stated** (a source says it), **in the released code** (a script does it; the paper does not say so), and
**measured here** (our own tables, not a source). Where nothing is stated it says so. Nothing is inferred beyond what a sentence or a line of code shows.

## Sources and how they were read

| Source | Version | Read | Used for |
|---|---|---|---|
| SweRank paper, arXiv 2505.07849 | v2 (ICLR 2026), 20 pages | in full on 2026-10-17 (`knowledge/papers/swerank-2505.07849.md`: 20 extracted pages, none blank, appendices A-I); pages 3-5, 8 and 16-18 read again for this note | data section (pp. 3-5), filtering ablation (p. 8, Figure 5a), training details (p. 16) |
| SweRank+ paper, arXiv 2512.20482 | v1, 11 pages | in full on 2026-10-17 (`knowledge/papers/swerank-plus-2512.20482.md`; no separate appendix); pages 3-4 read again | Table 1 (p. 3), data and consistency filtering (pp. 3-4) |
| Code repository of SweRank (`SalesforceAIResearch/SweRank`, formerly `gangiswag/SweRank`), local clone at commit d3df508 of 2026-06-02 | README and the data scripts in `src/collect/`, `src/get_train_by_repo.py`, `src/get_repo_structure/`, `src/repo_negative_mining.py`, `src/run_negative_mining.sh`, `src/collect/filter_dataset.py` | each file listed was read in full; the training scripts of the reranker were not needed | corpus, positives, selection, filter |
| Dataset repository `gangiswag/train_data`, Hugging Face, revision 62422fe (last modified 2025-09-24) | three archives, no `README.md` (HTTP 404 for the card file, 2026-11-03; the API reports `cardData: null`) | member lists of all three archives (central directories); the contents of `train.zip` as measured in `knowledge/datasets/sweloc.md` | whether the data carries its own documentation |
| `retrieval_dataset_creation.zip` of the same repository | 3,509 entries | listing only | it holds the evaluation sets of SWE-bench Verified and SWE-bench Multilingual in the same layout (722 corpus files), **no script and no training data**; it does not document the pool |

**The dataset has no card.** The sentence "the dataset card says no pool positive lies in a test file", used in the first mined-set notes, refers to the
project's own card, `knowledge/datasets/sweloc.md` (a measurement with the D9 path rule), not to a publisher's statement. The publisher states nothing about it.

## What the paper states (SweRank, pp. 3-5, 8, 16)

- Repositories (p. 4, §3.1): "the top 11,000 PyPI packages on GitHub"; at least 80% Python; repositories already in SWE-Bench and LocBench excluded; deduplication "based on source code overlap"; result 3,387 repositories.
- Pull requests (p. 4, §3.1): "following the SWE-Bench methodology", PRs that "(1) resolve a linked GitHub issue and (2) include modifications to test files"; 67,341 initial (PR, codebase) pairs; the snapshot is "the codebase snapshot at the PR's base commit".
- Instances (p. 4, §3.2): the issue description is the query; "each function modified within the PR is designated as a positive example, corresponding to a distinct training instance. Thus, a PR modifying N functions yields N training instances"; the negatives are "the unmodified functions within the corresponding codebase".
- Consistency filtering (p. 4, §3.3): top-K consistency filtering with CodeRankEmbed over "the other unrelated functions F_i in the repository"; an instance is kept only if its positive "ranks within the top K"; K = 20 (ablation Figure 5a, p. 8). Hard negatives (p. 5): among the top M = 15 most similar functions to the query. Mining and filtering were done with the `contrastors` package (p. 16, Appendix A.1).
- The paper does **not** say: what counts as a "function" (nested functions, `async def`, methods, test files, vendored code), how "modified" is decided from the diff (removed lines, added lines, deleted functions), which commit is "the base commit", how a PR is linked to an issue, how instances became the per-PR directories of `train.zip`, or that the directories carry every modified function.

## What SweRank+ states (pp. 3-4)

- Table 1 (p. 3), Python row: 2,448 repositories, 24,285 PRs, 49,973 instances; all languages 4,060 repositories, 56,279 PRs, 155,663 instances. The PR and repository counts equal the number of directories and repositories of the Python part of `train.zip`.
- p. 3: the multilingual set "extends the data collection and filtering pipeline of SweLoc"; repositories with at least 40% code in the target language, more than 1,000 stars, a commit in the preceding six months; PRs "explicitly linked to GitHub issues that include test file modifications".
- p. 4: consistency filtering with "a pretrained embedding model (SweRankEmbed-Small)", "retaining only examples where the positive function ranks within the top-40 semantically similar functions repository-wide". This is stated for the multilingual set; whether the Python rows of Table 1 were built with this teacher or the one of the SweRank paper is **not stated**.
- It is not stated what "instances" in Table 1 are counted after (before or after filtering), or whether `train.zip` is that set.

## What the released code does (not in either paper)

All paths are under the cloned repository; the line numbers are those of commit d3df508.

**Link between issue and PR.** `src/collect/utils.py:71-102` (`extract_resolved_issues`): a regular expression over the PR title, body and commit messages; `(\w+)\s+\#(\d+)` with the word in {close, closes, closed, fix, fixes, fixed, resolve, resolves, resolved}; HTML comments removed. This is not the platform's closing reference. `src/collect/build_dataset.py:51-64` keeps merged PRs with at least one such issue.
**Query.** `src/collect/utils.py:236-262`: issue title and body, joined by a newline, concatenated over the resolved issues of the PR.
**Base commit.** `src/collect/build_dataset.py:42`: `pull["base"]["sha"]` (the base field of the PR object).
**Patch and test patch.** `src/collect/utils.py:313-335`: the PR diff is split per file; a file whose path contains any of `test`, `tests`, `e2e`, `testing` as a substring goes to the test patch, the rest to the patch.
**Test requirement.** `src/collect/build_dataset.py:83-94, 170-179`: instances with a non-empty test patch go to the output file, but every valid instance also goes to the `.all` file, and `src/collect/build_dataset_ft.py:26-38` reads the `*-task-instances.jsonl.all` files. So the released script does **not** require a test modification, which the papers state (SweRank p. 4; SweRank+ p. 3).
**Pull request listing.** `src/collect/print_pulls.py:27-40` and `src/collect/utils.py:204-232`: closed pull requests, newest first, 100 per page, `num_pages=30` (at most 3,000 per repository).
**Corpus (functions).** `src/get_repo_structure/get_repo_structure.py:107-173` and `src/get_repo_structure/get_patch_info.py:398-420`:
- every `ast.FunctionDef` found by `ast.walk` over the file (nested functions included) that is not a direct method, except one whose name equals the name of a method already collected in the same walk; direct `FunctionDef` children of every `ClassDef` (nested classes included) are methods;
- `ast.AsyncFunctionDef` is excluded, both as function and as method;
- a file is skipped if the lower-cased file name contains `test`, or the lower-cased path from the structure root contains `test` (directory names count; the structure's root key is the repository's folder name, `get_repo_structure.py:90-100, 176-190`, so in this code the tested string starts with it; `pytest-dev` instances bypass the path test); a substring, so names such as `latest` or `contest` match;
- vendored and build directories are not skipped;
- the corpus identifier is `<path>/<function>` or `<path>/<Class>/<function>`; the text is the identifier, a newline, then the source lines (methods: `class <Class>:` is glued before the method's first line, without a newline, `get_patch_info.py:414-418`).
**Positives.** `src/get_train_by_repo.py:23-60` with `src/get_repo_structure/get_patch_info.py:236-300, 142-200`: hunks are read from the patch; a removed line (`-`) is attributed to the function or method that contains its old-side line number in the base-commit structure, flagged `newly_added: False`; an added line (`+`) that does not itself contain `def ` or `class ` is attributed by the old-side position and flagged `newly_added: True`; only hunks with a function and `not newly_added` give a changed function. A function is therefore a positive if it owns a **removed** or rewritten line; a function that only gained lines is not; a function deleted by the patch is (its lines are removed) if it is in the corpus. The owner is the first function in the structure whose span contains the line (outer function before a nested one; for a line in a class, only its direct methods are looked at, so a nested class's method resolves to no function). Positives are looked up by name key, so only functions that are in the corpus (see above) can be positives; a positive in a test-named file, an `async def` or a nested class method cannot occur.
**One instance per positive.** `src/get_train_by_repo.py:54-58`: one row per positive with the PR's query, that positive, and all other functions of the snapshot as negatives.
**Consistency filter.** `src/repo_negative_mining.py:19-75` and `src/collect/filter_dataset.py:20-35`: the positive and all negatives are scored with `cornstack/CodeRankEmbed` (1,024 tokens, bf16, dot product, query prefix); an instance is dropped if the positive's 0-based rank is above 10 (rank index greater than 10) or the positive is missing from the results; of the negatives, those at rank indices 3 to 25 are kept. `src/run_negative_mining.sh:6-21` runs the three steps in order.
**Not in the repository.** The training script of the retriever ("not included", README), and any script that converts the filtered rows to the per-PR BEIR directories of `train.zip` (`corpus.jsonl`, `queries.jsonl`, `qrels/test.tsv`). The README names a mining script under another file name than the one in the repository (`src/run_negative_mining.sh`).

## Where the sources disagree with each other

| Point | Paper | Released code |
|---|---|---|
| Consistency teacher | CodeRankEmbed (SweRank p. 4); SweRankEmbed-Small for the multilingual set (SweRank+ p. 4) | CodeRankEmbed |
| Cut | K = 20 (SweRank p. 4); top-40 (SweRank+ p. 4) | rank index above 10 dropped |
| Hard negatives | top M = 15 by similarity (p. 5) | rank indices 3 to 25 |
| Test modification required | yes (SweRank p. 4, SweRank+ p. 3) | not required in the file that feeds the dataset |
| Issue link | "resolve a linked GitHub issue" | keyword regex over title, body and commit messages |

## What this settles for the mined set, and what it leaves open

Each line below pairs one observation of the mined-versus-pool comparison (`results/mining/m1_agreement.md`, measured here) with what the sources say.

| Observation (measured here) | What the sources say |
|---|---|
| The pool's corpora hold no test-file function | The code excludes any path containing `test` as a substring (also stated nowhere in the papers) |
| 43 mined extras not in the pool's corpus are `async def` | The code excludes `async def` |
| The pool's positives never include pure insertions (42 mined extras) | The code does not count a function that only gained lines |
| The pool contains whole-function removals as positives (87 of its positives) | The code counts a function whose lines were removed |
| Pool-only functions include nested functions and a vendored directory | The code includes nested functions and does not skip vendored directories |
| Pool ids are `<path>/<name>` with no leading repository folder, and 708 of 708 pool positives matched mined ids | The released code builds ids from the structure whose root key is the repository folder; the ids of `train.zip` do not carry it, so the unreleased conversion removed it or the data came from another version of the code: **not stated** |
| Corpus-id Jaccard 0.62 | The base commit is the PR object's base sha, not the merge base; whether this explains the rest is **not tested** |
| 9 mined extras not in the pool's corpus, not `async def`, not unexplained by a rule above | Candidates in the code: a `test` substring in a path (such as `latest`), the name-collision rule for functions, nested-class methods; **not tested** |
| Directories hold every modified function (307,996 qrels rows) and the shares of directories with no positive in the SweRankEmbed-Small top 10 is 1.7% (E-POOL-RANKS) | The code makes one row per positive and filters each row; the sources do not say how rows became directories. SweRank+ Table 1 counts 24,285 PRs and 49,973 instances for Python; the directories number 24,285. Whether a directory was kept because at least one of its rows passed a filter is **not stated** |

**Settled by the sources:** the definition of the corpus (functions and methods, no `async def`, no file whose path contains `test`), of the positives (functions with a removed or rewritten line; not added-only), of the base commit (PR base sha) and of the issue link (keyword regex), as far as the released code is the construction of the published data; the consistency step of the released code (CodeRankEmbed, rank index at most 10 per row).
**Left open by the sources:** whether the released code is what produced `train.zip` (no provenance statement, no card); the teacher and cut actually used for the Python rows (papers and code disagree); how rows were grouped into directories and which rows were kept; why the PR and repository counts of Table 1 equal the directory counts; the test-modification requirement; and the remaining mined-versus-pool differences listed above.

## Options for the engineer (the session decides none)

1. **Align the miner with the code's rules** as a labelled variant (no test-substring paths, no `async def`, no pure insertions, nested functions in the corpus, vendored directories kept, base sha as snapshot): the variant would be compared with the pool again on the 42 shared pull requests (cost: a CPU run of the M1 stage; the corpus-id Jaccard and the exact share are the readings).
2. **Keep the miner's rules** and report the differences as the definition of the unfiltered set (what the M1 tables already do).
3. **Ask the authors** for the conversion script and the card (the repository's issues, or the first author), since the sources are silent on the grouping into directories and the Python filter.
