# Held-out repository list

Contract: `specs/held_out_repos.md`. List: `held_out_repos.json` (sha256 `7ba5c9d8d27dd9a92092dff04275fc2b6ec4c15e5641c834ddc6d93a9f477783`, file `held_out_repos.sha256`).

## Form and method

- Canonical form: `owner/name`, case-folded (`Owner/Repo`, `owner__repo` and `owner/repo` are one entry).
- CORE-Bench folder names are truncated and are not repository names, so the repository of a folder is read from the instance ids in its `queries.jsonl` (`owner__name-<PR>`; the Pro split `instance_owner__name-<hash>`). Every one of the 1,458 folders resolved; unresolved folders: none. Nothing was guessed from a folder name.
- Union held out: all L2 datasets, all L3 datasets, the Rewrite variants (same repositories, checked below) and SWE-bench Verified metadata.
- Not applied: any fork or near-duplicate rule, and Loc-Bench (both are open questions; counts under each are below).

## Result

**605 distinct repositories held out.**

| source | folders | distinct repositories | folders without `__` | folders holding more than one repository |
|---|---|---|---|---|
| LEVEL-2 Multi-SWE-bench | 35 | 39 | 4 | 2 |
| LEVEL-2 SWE-Bench-plus-plus | 319 | 338 | 74 | 12 |
| LEVEL-2 SWE-bench-Live | 209 | 213 | 56 | 3 |
| LEVEL-2 SWE-bench-plus | 6 | 6 | 2 | 0 |
| LEVEL-2 SWE-bench_Multilingual | 41 | 41 | 0 | 0 |
| LEVEL-2 SWE-bench_Pro | 10 | 10 | 3 | 0 |
| LEVEL-2 SWE-bench_Verified | 12 | 12 | 4 | 0 |
| LEVEL-3 Multi-SWE-bench | 35 | 39 | 4 | 2 |
| LEVEL-3 SWE-bench_Multilingual | 40 | 40 | 0 | 0 |
| LEVEL-3 SWE-bench_Pro | 10 | 10 | 3 | 0 |
| LEVEL-3 SWE-bench_Verified | 12 | 12 | 4 | 0 |
| Verified (metadata) | - | 12 | - | - |


Rewrite variants: the repository set of every Rewrite dataset equals that of its original (checked per dataset; repositories added by Rewrite folders: 0).

| level | folders | distinct repositories | folders whose name is not the repository | folders without `__` | folders holding several repositories |
|---|---|---|---|---|---|
| L2 | 632 | 605 | 242 | 143 | 17 |
| L3 | 97 | 92 | 17 | 11 | 2 |


The card's 632 and 97 are folder counts. Distinct repositories are 605 (L2) and 92 (L3). 17 L2 folders hold more than one repository (a truncated name such as `open` or `python` is shared by several owners). Folders of one dataset whose names differ only by letter case (they would collide on a case-insensitive file system): 3 groups (LEVEL-2 SWE-bench-Live: Flexget__Flexget / flexget__flexget; LEVEL-2 SWE-bench-Live: Kozea__WeasyPrint / kozea__weasyprint; LEVEL-2 SWE-bench-Live: PyPSA__PyPSA / pypsa__pypsa). Each pair holds the same repository.

## Pairwise overlaps (distinct repositories)

| pair | shared |
|---|---|
| L2 & L3 | 92 |
| L2 & Verified | 12 |
| L3 & Verified | 12 |


L2 union L3 union Verified = 605. L3 is wholly inside L2 (92 of 92), and the 12 Verified repositories are inside both. The per-dataset overlap matrix is `results/tables/held_out_pairwise_overlaps.csv`.

## Loc-Bench (reported separately, not in the list)

| version | rows | repositories | already in the list | not in the list |
|---|---|---|---|---|
| Loc-Bench_V1 | 560 | 165 | 37 | 128 |
| Loc-Bench_V0.2 | 660 | 210 | 41 | 169 |


Whether Loc-Bench repositories are held out of training is ADR-005 and is not decided here.

## Paired analysis n (instance ids)

| quantity | n |
|---|---|
| L2 SWE-bench_Verified queries that are SWE-bench Verified instances | 432 |
| L3 SWE-bench_Verified queries that are SWE-bench Verified instances | 302 |
| in both L2 and L3 Verified | 302 |
| L2/L3 Verified query ids absent from the Verified metadata | 0 |

Details per repository: `results/tables/paired_n.json`.

## Fork and near-duplicate counts

See the pool reports below. The held-out list itself is exact names only. Measured on candidate pools: repositories that were renamed or transferred since the pool was built still carry their old name and pass an exact-name filter.

## Pool reports

| pool | instances before | after | repos before | after |
|---|---|---|---|---|
| codesearchnet_python | 457,461 | 449,440 | 13,590 | 13,546 |
| gangiswag_train_data_python | 24,285 | 20,854 | 2,448 | 2,359 |

Files: `pool_filter_report_<pool>.md` (CodeSearchNet python, the gangiswag candidate), `pool_filter_report_cornstack_python.md` (cannot be filtered), `pool_filter_report_sweloc.md` (does not exist).
