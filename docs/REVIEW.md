# Review standard

How a branch is checked before it is merged into `main`. The aim is that a reviewer can check a
teammate's work quickly and that a shortcut is found by a mechanical rule, not by someone's attention
on a given day. The standard applies to every branch, including the lead's.

Two commands carry most of it:

```
make review-flags BASE=main   # the flags and the trace-to-source check, on this branch only
make review                   # lint, the fast tests, then the flags
```

The continuous-integration run executes the same three steps on every pull request and every push to
a branch other than `main`. **Its result is a minimum, not a verdict.** A green run says the branch
passed the mechanical rules; it does not say the work is correct, complete or honestly described.
A red run stops the review. A reviewer still does the checks below.

## What a reviewer checks on every branch

1. **Hygiene.** The branch contains the current tip of `main`. The history is readable: one clear
   change per commit, messages that say why. `git status` is clean. Nothing from the untracked
   categories (data, checkpoints, caches, credentials, personal notes) is in the diff.
2. **Ownership.** Every changed path belongs to the branch's owner or is listed under "Scope" in the
   pull request. `configs/frozen/` changes only on a lead branch (`b/`). Shared modules (`ril/util`,
   `ril/config`, the metrics and statistics code) change only with a stated reason and a test.
3. **Gates.** `make lint` and `make test` pass on the head commit, run by the reviewer or read from
   the run for that exact commit. The latency row required for a change to `ril/` exists.
4. **Flags.** `make review-flags` prints no blocking finding. Each warning is either fixed or
   answered in the pull request in one line.
5. **Trace to source.** Every number added to a ledger row or a "Result" line can be found in a file
   under `results/` that the row or its section names (next section). A number that cannot be found
   is a defect until the author stores it.
6. **Independent re-derivation of five claims.** The reviewer picks five claims from the branch's
   text and re-derives each from the stored outputs, without running the author's analysis script
   and without reading the author's arithmetic first (see "Re-deriving a number"). The five include
   at least one headline number, one derived figure (a ratio, a difference or an interval), one
   count, and one statement of what was held fixed. Choose after reading the diff, not from the
   author's list of highlights.
7. **Scope of the claim.** Python only; the wording in `02_research_questions.md` is unchanged; a
   null result is reported as a null result; absolute resolved rates are not described as agent
   capability.

## Flags and trace-to-source

`scripts/review_flags.py` reads the diff between the merge base of the two revisions and the head,
and the stored blobs at the head. It does not read the working tree. Exit status 1 means at least
one blocking finding.

### Blocking findings, and why

| Rule | What it matches | Why it blocks |
|---|---|---|
| `test-skip` | an added skip, conditional skip or expected-failure mark in a test file | a test that does not run cannot fail |
| `suppression-without-reason` | an added lint, type or coverage suppression with no one-line reason after it | a suppression is a claim that the tool is wrong; the reason is the evidence |
| `bare-except`, `swallowed-exception` | an added bare handler, a broad handler whose body does nothing, or a suppress of a broad exception | errors disappear and results are produced from partial work |
| `assert-removed` | more assertion lines removed than added in an existing test file | the check was weakened to make the test pass |
| `tolerance-widened` | a tolerance argument or tolerance constant changed to a looser value in an existing test | same, in smaller steps |
| `expected-number-changed` | a number changed inside an assertion of an existing test | an expectation that moves with the output proves nothing; the change needs an explanation |
| `frozen-config` | any change under `configs/frozen/` on a branch that is not a lead branch | the frozen configuration is the experiment's control |
| `large-file` | an added or changed file over 5 MB | the repository is not storage for data |
| `forbidden-file` | model weights, archives, environment files, key and credential files | they must not be published |
| `secret` | text shaped like an access token, secret key or private key block | published credentials must be revoked |
| `home-path` | an absolute home-directory path in an added line | it exposes a login name and does not run on another machine |
| `verified-in-tuning-config` | the Verified split named in a file under `configs/experiments/` whose name or `purpose` field says tuning, sweep, search or dev, outside an entry marked `role: test` | the split is the final test; a choice made on it is leakage |
| `unsourced-number` | a number in a ledger row or a "Result" line that is found in no file the row or its section names under `results/` | a figure with no stored source cannot be re-derived |

### Warnings, and why

| Rule | What it matches | Why it is a warning |
|---|---|---|
| `unfinished-marker` | an added line carrying one of the conventional markers for unfinished or stopgap work | each is a debt; it needs an owner or a deletion |
| `untested-definition` | a top-level function or class added in `ril/` whose name appears in no test | untested code is unverified code; sometimes the test is indirect |
| `config-no-seed`, `config-no-marker` | a new configuration with no seed, or with neither a hash field nor a `provisional:` or frozen marker | a run must be reproducible and its status must be visible |
| `changed-default` | a changed default argument in a shared module | every caller changes silently |
| `deleted-file` | a deleted file under `results/` or `tests/` | evidence or a check was removed (empty placeholder files are exempt) |
| `done-without-output` | a registry row marked done whose row and section name no path under `results/` | done means there is an output to look at |

### What the trace-to-source check does

For each ledger row added in `RESULTS.md` or a `results/ledger_*.md` file it reads the
"headline result" cell; for each added line beginning "**Result" in `EXPERIMENTS.md` it reads that
line. In those places it extracts numbers with decimals and integers written with thousands
separators. It then looks for each number, at the precision printed (and as a fraction when the
printed value is a percentage), in the files under `results/` that the ledger row names (paths,
globs and directories) or, for a "Result" line, that the enclosing section names. A row that names
no file, or only files that do not exist at the head, is reported with every number it carries.

### What the scan does not catch

Keep this list in mind; the flags are a floor.

- It is a screen for numbers typed by hand, not proof of a number. A number can match another value
  by chance; in a trial that perturbed the existing ledger's headline numbers, about three in ten were
  still found in the named files. Low-precision numbers are the weakest. Re-derive (item 6).
- It ignores small integers and numbers without decimals (counts such as "100 of 100", rank
  positions), numbers outside the headline cell or the "Result" line, and the rows of a table that
  follow the "Result" line.
- A derived value (a ratio, a difference) that is not itself stored is reported as unsourced. The fix
  is to store the derivation in a table, not to remove the number.
- Weakened tests are found line by line: it misses a changed number on the continuation line of a
  multi-line assertion, changed fixture data, an expectation moved into a helper, a test that no
  longer reaches its assertion, and a test deleted together with its file (this last one warns).
- Suppressions are found as comments. A suppression placed in a configuration file, a per-file
  setting or an exclusion list is not seen.
- A skip written as ordinary control flow (an early return, a condition that is always false) is
  not seen.
- Secrets are matched by the shape of common tokens only. A token of an unusual shape passes.
- Ownership is judged from the branch name only; it does not know who pushed the commits.
- The Verified rule reads the structure of the file. A split referred to by another name, or by a
  path to a file that lists it, passes; an entry marked `role: test` is trusted.
- It does not judge whether the experiment measures what the text says it measures.

A rule that fires on ordinary code is narrowed in `ril/util/review_flags.py` with a test that pins the
narrowing. A rule is never switched off for a path.

## Re-deriving a number

1. Find the row. Read its config hash, seed, hardware and the files it names.
2. Open the named log or table and find the raw quantity the number is computed from (per-query
   scores, per-cell counts, per-run values). A summary that only restates the headline is not a source.
3. Recompute with a few lines written fresh by the reviewer, using the same definition the text
   states (the metric, the aggregation, the interval method, the set of queries or runs). Do not
   run the author's analysis script for this step; running it only repeats the author's reading.
4. Compare at the printed precision. A difference in the last printed digit is a rounding question;
   a larger one is a finding.
5. For an interval, re-derive both ends and the resampling unit stated in the text.
6. For a comparison between two arms, re-derive both values and the difference, and read the number
   of seeds or clusters behind them. If the arms overlap within one standard deviation, the text must
   say they are indistinguishable at this sample size.
7. Write down what was recomputed and what came out (see "Recording a verdict").

If the stored output is not enough to re-derive the number, that is a finding against the branch: the
number needs a stored source.

## Proxies

A proxy is a measurement that stands in for the quantity the claim is about: a smaller model for the
final one, a subsample for the whole pool, a development repository for the test set, a retrieval
metric for resolution, a count of tokens for latency, a different machine for the target machine.

Every proxy is labelled where it is used, in the same sentence as the number: what it stands in for,
what differs, and which direction the difference is expected to bias the result, if known. A proxy is
never reported in a table or sentence in the place of the quantity itself, and a result that rests on
a proxy is not described with the strength of one that does not. A proxy that is unlabelled is a
finding. An exploratory run is labelled as exploratory, with n and intervals, and kept out of the
pre-registered tables.

## What a hand-back contains

When a branch is handed back for review, the pull request, filled from the template, holds:

- the branch owner, the paths changed, and the commit hash that was checked;
- the end of `make review` pasted as text, not described;
- **a list of every cut or skipped item** from the plan, with the reason and what it affects. An item
  that was shortened (fewer seeds, a smaller subsample, a shorter schedule) is listed too. An empty
  list is stated as "none" and is checked against the plan;
- every ledger row added, with the command that produced it and the file holding the number;
- the evidence class of each claim, proxies labelled as above;
- a statement that the Verified split was not used for any choice;
- requests for the lead: decisions, settings and compute needed.

A hand-back that omits the list of cut or skipped items is returned without review.

## Recording a verdict

The verdict is written in the pull request by the reviewer, in this form, and repeated in one
sentence in the body of the merge commit:

```
Verdict: accept | accept with changes | reject
Head reviewed: <commit hash>
Gates: lint <pass|fail>, tests <pass|fail>, flags <n blocking, m warning>
Flag answers: <each warning and how it was resolved, or "none">
Claims re-derived: <five lines: claim, source file, recomputed value, matches yes/no>
Cut or skipped items checked against the plan: <yes/no, differences>
Changes required: <list, or "none">
```

A verdict names the head it was given on. A commit pushed afterwards makes it stale; the changed
paths are reviewed again. A rejected branch is not merged; the reasons are in the record, and the
record stays after the branch is deleted.
