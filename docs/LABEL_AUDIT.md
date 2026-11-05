# Label audit: instructions for the readers

This page explains the sheet you were given. It is for people with a spreadsheet program and no access to the cluster. Read it once before you start; the rules below are the same for every reader.

## What the audit is for

Training pairs for the retriever were mined automatically: a merged pull request that closes an issue gives the issue text as the query, and every Python function the pull request edited counts as a *positive* for that query. Some of those positives are wrong (a refactoring, a test helper, a formatting change). The audit asks people to read a sample of pairs and say which ones are wrong, so that the share of wrong positives is a measured number and not a guess (`docs/RQ2_PROTOCOL.md`, section 7).

Your judgements are the human sample against which any automatic judge would later be checked; no automatic judge has been chosen. Your answers are treated as judgements, not as ground truth.

## What one row is

One row is one pair: an issue, and one function that the pull request closing it edited. Several rows may share the same issue (the same pull request edited several functions) and you will meet an issue more than once. Judge each row on its own.

| Column | Meaning |
|---|---|
| `pair_id` | Opaque identifier. Do not edit it. |
| `repository` | The GitHub repository (`owner/name`). |
| `issue_title`, `issue_body` | The issue the pull request closes. The body is cut at 3,000 characters; the cut is marked `[... truncated, N characters omitted]`. |
| `pull_request_title` | The title of the pull request (up to 300 characters). |
| `function_path`, `function_name`, `function_kind` | The edited function: file, qualified name (`Class.method` for a method), and kind (`function` or `method`). |
| `function_text_before` | The function as it was before the pull request, cut at 4,000 characters (marker as above). |
| `diff_hunk` | The hunks of the pull request's diff that touch this function, each with three lines of context. `-` lines were removed, `+` lines added. Cut at 4,000 characters. A cell beginning with a space before `@@` is intentional (so that a spreadsheet does not read it as a formula). |
| `other_edited_functions` | The other functions the same pull request edited (`path::name`, up to 30; `(+N more)` if there are more). Names and paths only. |
| `verdict` | **You fill this.** One of the three values below. |
| `reason` | **You fill this.** A few words (free text). Required for `not relevant` and `cannot tell`; optional for `relevant`. |
| `issue_function_not_edited` | **You fill this.** The second question, below. |
| `reader_id` | Pre-filled with your reader name. Do not edit it. |

Some rows may say that the diff could not be matched or fetched. Judge such a row from the issue and the function text, and put `cannot tell` if that is not enough.

## The verdict

Decide whether the edit to this function is part of the change that the issue asks for.

| Value | Use it when |
|---|---|
| `relevant` | The edit is part of the change the issue asks for: the function had to change for the issue to be resolved. |
| `not relevant` | The edit is incidental or a refactoring, a test helper, a formatting or style change, a rename with no bearing on the issue, or otherwise unrelated to the issue. |
| `cannot tell` | The text on the sheet does not allow a decision. Use it when you honestly cannot decide, not as a way to skip a hard row. |

Type the value exactly as written (capitals and underscores instead of spaces are tolerated; any other word is rejected when the sheets are scored).

**Decide from the sheet.** Do not look up the pull request or the repository on GitHub. Anyone or anything that is later compared with your answers will see only what the sheet shows, so using more would make the comparison meaningless. If the truncated text is the reason you cannot decide, answer `cannot tell` and say so in `reason`.

## The second question

`issue_function_not_edited`: reading the issue and the list in `other_edited_functions`, is there a function that the issue is about that the pull request did **not** edit? (For example, the issue names a function or a code path that is missing from the list of edited functions.) Answer `yes`, `no` or `cannot tell`. This estimates how many true positives the pair's own pull request missed, which matters because a missed function can later be drawn as a negative.

## How `cannot tell` and disagreements are counted

The scorer reports every rate three ways, and you do not need to do anything for this beyond answering honestly:

* *excluded*: pairs with an unresolved answer are left out of the denominator;
* *lower*: unresolved pairs stay in the denominator and count as not wrong;
* *upper*: unresolved pairs stay in the denominator and count as wrong.

A pair is *unresolved* if its answer is `cannot tell`, or if it was read by both readers and they gave different answers. Nobody adjudicates disagreements in the score; they are reported as disagreements.

## Who reads

Reader 1 and reader 2 are two team members who are not the lead. The lead reads no pair, so that the lead's knowledge of how the arms are built cannot influence the sample. The 100 pairs both of you read are used for the agreement between readers (kappa).

## What you are given

Each reader has a file with 250 rows: 100 pairs that both readers read (in a different order for each reader) and 150 pairs that only you read. You are not told which are which, and the order is shuffled. Do not discuss rows with the other reader until both of you have finished: the agreement between you is one of the numbers the audit measures.

## Time

The estimate in the protocol is about one hour per 50 pairs, so about 5 hours for 250 rows. Take breaks; accuracy matters more than speed. If you find that a row takes much longer than a few minutes, answer `cannot tell` and go on.

## How to fill the sheet

1. Open the CSV as UTF-8 in a spreadsheet program (LibreOffice Calc, Excel, Numbers or Google Sheets). The file begins with a byte-order mark so that Excel reads the encoding correctly. Cells contain line breaks; widen the columns and turn on wrapping to read them.
2. Fill only `verdict`, `reason` and `issue_function_not_edited`. Do not insert, delete, rename or reorder columns, do not sort the rows by anything that would lose the `pair_id` of a row, and do not edit any other cell.
3. Save as CSV (UTF-8), keeping the same columns, with the name `<your reader name>_filled.csv` (for example reader_1_filled.csv), and send it back to the engineer who gave you the sheet.

Rows you leave empty are counted as unanswered, not as `cannot tell`.

## What is not claimed

The sample is of the mined pilot set for Python repositories only. A rate measured here is a rate for this sample of readers' judgements; it says nothing about other languages, other mining rules, or the published training pool.
