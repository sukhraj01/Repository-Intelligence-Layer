# ADR-012: Edge-recovery definitions

- **Status:** Proposed — **not decided**. This ADR lists the definitions that were measured, with their trade-offs. None is chosen.
- **Date:** 2026-10-17
- **Decided by:** _pending — engineer / team_
- **Related:** `specs/parse_one_repo.md`, `specs/repo_graph.md` (status, Q-G8, Q-G13, Q-G15), ADR-011 (graph schema and storage),
  ADR-003 (graph role), `docs/05_structural_signals.md` (the "70-85%" expectation), `docs/DEVIATIONS.md` (DEV-007), open question Q27

## Context
The master document says static call-graph recovery in Python is "expected to be 70-85%" without saying what is counted.
The papers read give four incompatible definitions and none reaches that range as a general figure
(`knowledge/papers/LANDSCAPE.md`, claims checked). The first graph build measured the project's own graph under four
definitions at once so that the engineer can see how far they disagree before choosing one. What follows reports every number
with its n and its log; the choice, and whether a single "recovery percentage" should exist at all, is left open.

Method note. Definitions (a), (b) and (c) are computed by code. Definition (d) and the precision of the exploratory `tests` and
`configures` edges are **judged by one reader, the author of the build**, by reading the source at each site; no second reader has
checked them, and a spot-check of the listed edges (`results/tables/p_edge_inspection_sample.csv`) is the open step.

## Alternatives considered
All numbers are `measured` unless marked `paper_reported`. Repositories: flask at the pallets__flask-5014 base commit, requests
at the psf__requests-6028 base commit, django at the django__django-16145 base commit; the resolver is the project's own `ast`
resolver (`own-ast-resolver/v0`, `provisional: ADR-011`). Hardware per row in the logs. For flask and requests the edge counts per
family, status and rule are identical on the laptop (Python 3.11) and on Ada (Python 3.10); the graph digests differ only because the
metadata records the interpreter.

### (a) Share of call sites resolved to one in-repository unit
Counted from the graph alone. Each call site is one edge with a status. Variants of the denominator:

| Repository | sites | resolved | ambiguous | unresolved | external | resolved / all sites | resolved / non-external | (resolved + ambiguous) / non-external |
|---|---|---|---|---|---|---|---|---|
| flask | 4,036 | 1,137 | 975 | 125 | 1,799 | 28.2% | 50.8% | 94.4% |
| requests | 2,537 | 902 | 164 | 180 | 1,291 | 35.6% | 72.4% | 85.6% |
| django | 160,479 | 63,010 | 31,668 | 6,733 | 59,068 | 39.3% | 62.1% | 93.4% |

(`results/tables/p_graph_status_counts.csv`; counts include tests, examples and docs code; rule breakdown in
`results/tables/p_graph_rule_counts.csv`.)

- *Measures:* how much of the graph is usable as a hard edge. *Costs nothing* beyond the build.
- *Does not measure:* correctness (a resolved edge may be wrong), nor completeness (a site marked `external` may be in the
  repository). The `external` bucket is decided by rules (a name with no in-repository method of that name, a builtin, an import
  that leaves the repository), not by an installed environment (Q-G8).
- *Sensitive to:* the choice of denominator (a factor of two between the first and the second column), to whether test code is
  included, and to how `ambiguous` is treated (a site with one candidate is `ambiguous`, not `resolved`, when the receiver type is
  unknown).

### (b) Recall against a dynamic oracle (the flask test suite under a function-level tracer)
The suite (483 passed, 1 skipped; Python 3.10.12 on gnode002, `sys.setprofile`, job 25517) was traced; pairs are (caller unit,
callee unit) with both inside the repository (`results/logs/p_flask_recovery_2026-10-17.json`). A pair is recovered when a
`resolved` `invoke` edge joins the two units (class instantiation also counts for the `__init__` and `__new__` found through the
MRO); "or ambiguous" adds pairs whose callee is in the candidate set of an `ambiguous` edge from the caller.

| View | n pairs | recall, resolved | recall, resolved or ambiguous |
|---|---|---|---|
| all in-repository pairs | 1,057 | 47.9% | 65.8% |
| callee in non-test code | 1,027 | 47.4% | 65.8% |
| caller and callee in non-test code | 330 | 47.0% | 60.3% |
| excluding implicit-protocol dunder callees (`__enter__`, `__getitem__`, ...) | 854 | 59.3% | 81.4% |

Including the callees that are not in-repository units (matched by the callee's last name against the caller's call sites, so a
hit does not prove the same function): in-repository 1,057 pairs, builtin/extension callees 578 pairs (493 matched), external
Python callees 1,723 pairs (644 matched); over all 3,358 pairs the recall is 48.9%, and 61.1% over in-repository plus builtin
callees only (999 of 1,635).

The 362 in-repository pairs recovered neither as `resolved` nor as `ambiguous` (a further 189 are recovered only through an
`ambiguous` set), by cause: implicit protocol calls with no call site (203; operators, `with`, item access), property access
(40), instantiation whose class is defined inside a function or reached without a site (18), a site carrying the callee's name
that was not recovered (11), a site with another target (14), and no site carrying the callee's name (76, mostly closures,
decorators and framework callbacks).

Precision among the edges whose caller executed: 506 of 821 resolved edges are supported by a dynamic pair (61.6%; both ends
executed: 506 of 799, 63.3%). This is a lower bound: an edge on a branch the suite did not take counts as unsupported.

Suite coverage (reported with every number above): 301 of 363 non-test functions and methods entered (82.9%; functions 61.5%,
methods 90.6%); line and branch coverage of `src/flask` 89.6% (coverage.py, 91.5% of statements; job 25517).
A further 796 pairs call a function nested inside another unit (a closure, a view defined in a test); they are not units, so
they are reported apart and not counted as misses.

- *Measures:* what the code does, including implicit calls, so it is the closest to "does the graph contain the edges that matter
  at run time".
- *Costs:* a working environment per repository and a test run (11 s traced for flask; DyPyBench needed 215 minutes per project
  on average, `paper_reported`, `dypybench-2403.00539.md`, Sec. 4.1.2, p.10). Run here for flask only; requests needs an HTTP test
  server and django a database settings module.
- *Does not measure:* anything the suite does not execute. Test-based baselines can mis-state precision and recall in either
  direction (`total-recall-helm-2024.md`: Java, so a warning and not a rate for Python).

### (c) Agreement of a second static resolver (Jedi 0.20.1) on a stratified sample
300 call sites, 75 per status, drawn with seed 0 from flask and requests (150 each; dependencies not installed, so third-party
receivers are unknown to Jedi) (`results/tables/p_jedi_agreement_sample.csv`, `results/logs/p_jedi_agreement_2026-10-17.json`).

| Own status | n | Jedi agrees | Jedi finds an in-repository target the own resolver did not | Jedi finds none |
|---|---|---|---|---|
| resolved | 75 | 75 (same unit, exact) | - | 0 |
| ambiguous | 75 | 37 (answer inside the candidate set) | - | 38 |
| external | 75 | 75 (no in-repository target) | 0 | - |
| unresolved | 75 | 20 (also no target) | 43 | 12 sites with no callee name to ask about |

- *Measures:* whether two independent static analyses reach the same conclusion; cheap (8 s for the sample).
- *Does not measure:* accuracy. Jedi has its own failures and a shared failure (both wrong) is invisible. It says the resolved
  edges are consistent with Jedi (75 of 75) and that Jedi recovers 43 of 63 answered sites the own resolver leaves unresolved,
  mostly values it reads out of class attributes and local assignments.

### (d) Inspection of a stratified 100-edge sample by reading the source
100 call sites from flask (60) and requests (40), stratified by recorded status (resolved 40, ambiguous 20, unresolved 20,
external 20; seed 0), each judged by reading the source around the site (`results/tables/p_edge_inspection_sample.csv`; labels by
the author of the build).

| Recorded status | n | claim holds | Wilson 95% | what the failures were |
|---|---|---|---|---|
| resolved | 40 | 39 correct, 1 unclear | 91-100% of decided | - (the unclear one depends on an optional library) |
| ambiguous | 20 | 8 contain the true target | 22-61% | 12 of 20 are calls on dictionaries, sockets, test-client objects: the true target is outside the repository and the candidate set is spurious |
| external | 20 | 20 | 84-100% | - |
| unresolved | 20 | 4 genuinely dynamic, 10 are in fact external, 2 in-repository by name, 2 closures, 2 depend on an optional library | - | - |

Weighted by the status populations of flask and requests (bootstrap 95% intervals): about 39.6% of call sites (35-44%) have an
in-repository target; among those the share recorded `resolved` with the right target is 77.4% (69-87%) and the share that is
`resolved` or whose `ambiguous` set contains the target is 97.9% (96-100%); in-repository sites left `unresolved` are about 2%
(0.4-4%) (`results/logs/p_edge_inspection_summary_2026-10-17.json`).

- *Measures:* the thing the others approximate (is this edge right?) at the call-site level; the only one that sees the `external`
  bucket's errors.
- *Costs:* human reading time (not timed here) and a reader's judgement; one reader here.
- *Does not measure:* implicit calls (no site). n is small; strata are not proportional to the populations, hence the weighting.

### Definitions in the literature (`paper_reported`, notes read in full)

| Source | Ground truth | Edge scope | Reported |
|---|---|---|---|
| PyCG (`pycg-2103.00587.md`) | hand-built, five packages under 3.5k lines | external and module-level callers included | precision 99.2%, recall 69.9% (Table IV, p.9) |
| Jarvis (`jarvis-2305.05949.md`) | test traces plus manual additions, six applications | application functions, library callees when analysed | 0.99 / 0.82 application-only; 0.35 / 0.60 application-centred with dependencies (Table V, p.10) |
| DyPyBench (`dypybench-2403.00539.md`) | executed edges of the test suites, 39 projects | all callees including builtin methods | 49% of dynamic edges in PyCG's graph; 59% of the missing callees are builtin-type methods (Sec. 4.1.2, pp.11-12) |
| Total Recall (`total-recall-helm-2024.md`) | executed edges from fixed entry points (Java) | whole graph or core package | test-based baselines can be arbitrarily wrong |

Closest in kind to this build's numbers: DyPyBench's 49% against definition (b) with external and builtin callees included, 48.9%
(n = 3,358 pairs), with a different tool, different projects and a name-matching rule for non-repository callees; the agreement
is not evidence of anything. PyCG's and Jarvis's figures use hand-built truth and count external edges, so they are not
comparable with in-repository-only numbers. No source reports in-repository-only recovery for library-style repositories; the
70-85% range of the master document is not reproduced by any definition here.

## Decision
_Pending._ No definition is chosen and none is declared the "edge-recovery percentage". `specs/parse_one_repo.md` asked for a
provisional metric: the reporting functions are `ril.parsing.report.invoke_shares` (definition (a)) and
`ril.evaluation.edge_recovery.recovery_report` (definition (b)); both are reporting code, not a selection.

## Rationale
_Pending._ Inputs: the four tables above and the literature table.

## Trade-offs
Cheap definitions (a, c) say how much of the graph is a hard edge or agrees with another tool; expensive ones (b, d) say how much
of what matters is present or correct. (a) depends heavily on a denominator choice; (b) on a test suite and its coverage, and
on how the callees that are not units are counted; (c) cannot see shared errors; (d) is slow and subjective. A single number
hides that the `ambiguous` bucket (about a quarter of flask's sites) is mostly spurious while containing the right target
about 40% of the time, and that the `unresolved` bucket is in large part not in-repository at all.

## Evidence class and the experiment that could change it
- **Evidence class:** (a), (b), (c) measured here; (d) measured here by one judge reading the source; the literature column read in
  full.
- **Cheapest experiments that could settle the open points:** (1) the same oracle on requests (needs the test HTTP server) and
  one more repository, to see whether (b) is stable across repositories (hours); (2) a second reader for the 100-edge sample
  (about an hour); (3) re-bucketing `ambiguous` sets above a size threshold as `unresolved`, and the `external` rule against an
  installed environment, to see how far (a) moves (minutes, offline); (4) the graph signal itself: pilot E3 with edge subsets
  restricted to `resolved` only against `resolved` plus `ambiguous`, which is the test of whether any of this matters for
  retrieval.

## Evidence
`results/tables/p_graph_status_counts.csv`, `p_graph_rule_counts.csv`, `p_jedi_agreement_sample.csv`,
`p_edge_inspection_sample.csv`; `results/logs/p_flask_recovery_2026-10-17.json`, `p_jedi_agreement_2026-10-17.json`,
`p_edge_inspection_summary_2026-10-17.json`, `p_stats_*_2026-10-17.json`; `RESULTS.md` rows of 2026-10-17 (`p-*`).
Notes: `pycg-2103.00587.md`, `jarvis-2305.05949.md`, `dypybench-2403.00539.md`, `total-recall-helm-2024.md`.

## Related benchmarks
Build and storage measurements are in ADR-011 (addendum); the oracle run (job 25517, Python 3.10.12, 4 CPU, 11 s traced).

## References
`docs/05_structural_signals.md`, `knowledge/papers/LANDSCAPE.md` ("Claims checked").

## Conditions to revisit
- The same oracle on a second repository changes (b) by more than ten points.
- A second reader disagrees with the first on more than one site in ten.
- The graph role (ADR-003) is settled and needs one definition for a threshold or a report.

## Addenda
_None yet._
