# Spec: Held-out repository list and disjointness filter

Source: `docs/04_data_and_ground_truth.md` ("The overlap: a trap and an opportunity"). This is the
guard against the single most damaging failure in the project: **repository leakage** between the
training pool and CORE-Bench L2/L3 or SWE-bench Verified. A model that saw `django` functions in
training has an advantage on *every* django instance, so instance-level disjointness is insufficient.

## Purpose

1. Build the list of repositories that must never appear in training data.
2. Provide a filter that removes them from any candidate training pool and reports what survived.
3. Enforce the rule with a test that always passes.

## Inputs

- CORE-Bench Level-2 and Level-3 repositories (HF dataset `zhangfw123/CORE-Bench`, layout `LEVEL-2/<dataset>/<repository>/`; Level-3 likewise; plus the REWRITE variants).
- SWE-bench Verified repositories.
- (Recommended extra guard, not required by the master doc: Loc-Bench repositories — see ADR-005, contamination check.)
- Candidate training pools as they become available (SweLoc, own PR-mined set).

Only what is needed to **enumerate repositories** should be fetched. The full corpora are not needed
for this deliverable. Acquire via Ada (`docs/COMPUTE.md`); the engineer does not download by hand.

## Outputs

| Path | Content | Tracked in git? |
|---|---|---|
| `data/held_out/held_out_repos.json` | sorted canonical repo list; for each repo, which sources it appears in (L2 dataset(s), L3 dataset(s), Verified) | yes |
| `data/held_out/held_out_repos.sha256` | hash of the canonical JSON | yes |
| `data/held_out/report.md` | counts: repos per source, union size, overlap between sources | yes |
| `ril/...` or `scripts/...` | `filter_pool(pool, held_out) -> (kept, dropped, report)` | yes |
| `data/held_out/pool_filter_report_<pool>.md` | per pool: instances and repos before/after, % surviving, top dropped repos | yes |
| `data/raw/<dataset>/provenance.json` | source, date, sha256 | no (data/raw ignored) |

## Settled

- Disjointness is at the **repository** level, not instance level.
- The held-out list is built **first**; the pool is filtered **against** it; surviving counts are **reported**.
- Union of L2, L3 and SWE-bench Verified repositories is held out.

## Implementation choices (decide, document, move on)

- Canonical repository naming (`owner/name` vs `owner__name`, case, forks/renames) — pick one canonical form, normalise all sources to it, document it in `report.md`.
- File formats beyond the above; script names.

## Open design questions (the engineer decides)

- Whether repositories that are **forks or near-duplicates** of held-out repositories are also held out (affects how much of any pool survives). Report the counts of both options; the engineer decides.
- Whether Loc-Bench repositories are held out of training (ADR-005).

## Acceptance criteria

- [ ] `held_out_repos.json` exists, is deterministic (same inputs ⇒ same bytes) and its hash is recorded.
- [ ] `report.md` states, per source, how many repositories were found and how many are shared between sources.
- [ ] `filter_pool` is implemented, unit-tested on a synthetic pool, and applied to every pool currently available; the surviving-instance and surviving-repository counts are written down.
- [ ] A test in `tests/leakage/` fails if any training-pool repository is in the held-out list.
- [ ] If Ada could not reach a source, the job + exact command are written and the blocker is recorded as a *data* blocker (not silently skipped).

## Tests (`tests/leakage/`)

- Synthetic pool containing one held-out repo ⇒ filter drops it and reports it.
- Name normalisation: `Owner/Repo`, `owner__repo`, `owner/repo` collapse to one entry.
- Determinism: building twice yields identical bytes.
- Guard: loading the real pool through the project's data loader and asserting empty intersection with the held-out list.

## Addendum 2026-10-17 — list schema 2 (decisions D1, D2, D3; engineer's decisions, closed Q8, Q9, Q22)

**What changed.** `held_out_repos.json` carries `schema_version: 2`:
- `repos` is the **core tier** (CORE-Bench L2/L3 and SWE-bench Verified), unchanged.
- `tiers.loc_bench` is the **Loc-Bench tier** (D3): the 169 repositories of Loc-Bench V1 and V0.2 that
  are not in the core tier, each with the version(s) it appears in. It is held out by default and can
  be switched off: `load_held_out_lists(doc).blocked(include_loc_bench=False)`.
- `aliases` maps a held-out repository's recorded name to its current GitHub name where they differ
  (none of the 605 differs among those resolved so far; see below).

**Matching (D1).** A pool repository is held out if its name or its current name equals a held-out
name or a held-out current name. Current names come from `data/held_out/rename_cache.json` (names
and flags only, written by `ril/training/rename_resolution.py`, filled on the cluster by
`scripts/ada/resolve_renames.py`). The fork network (parent or source held out) is a **sensitivity
row only**. A **content-overlap audit** is reported, never applied.

**Counts per rule** are produced by `rule_counts` for every pool: `exact`, `+current_name`,
`+loc_bench` (the default rule set), and `sensitivity: +fork_network`. `data/held_out/pool_filter_report_*.md`
and `results/tables/pool_filter_summary.csv` hold them; `results/logs/d_held_out_v2_2026-10-17.json`
holds the config hash.

**Resolution coverage.** Without a token, resolution reaches the unauthenticated limit (60 requests
per hour). The cache holds 108 repositories (the 59 same-name candidates of the first audit, the 12
Verified repositories, the 37 largest `gangiswag/train_data` python repositories that were unresolved).
Every count after `exact` is a **lower bound** until the pool is fully resolved: rerun
`scripts/ada/resolve_renames.py` with `GITHUB_TOKEN` set. The token is read from the environment,
used only as a request header, and never printed or written.

**Content-overlap audit (design).** `ril/training/content_overlap.py`. Held-out side: hashes of the
normalised informative lines (25 or more characters, not comments) of the held-out corpora; pool
side: a function is covered if at least 80% of its informative lines (at least 3) occur on the
held-out side; a repository's score is the share of covered functions. Controls: held-out chunks
offered as pool units must score 1.0; unrelated repositories give the chance level. It finds copies,
forks, mirrors and vendored code that name matching cannot; it does not find code with renamed
identifiers or reordered lines. Run: `scripts/ada/content_overlap_audit.py`.

**Tests.** `tests/unit/test_held_out.py`, `test_rename_resolution.py`, `test_content_overlap.py`;
`tests/leakage/test_repo_disjointness.py` checks schema 2, the tier, and that every filtered pool is
disjoint from the core and Loc-Bench tiers under current names.
