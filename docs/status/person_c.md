# Person C status

Updated 2026-11-05. Branch `c/eval-rq3`, based on `foundation-v0`.

## Cuts, blockers and deviations

- Round-one corrections pushed at379e0c1; CI failed in two temporary Git commit fixtures.
  Follow-up supplies anonymous identity only to fixture subprocesses; engineer pushes the fix.
  No real repository identity, assertion, workflow or gate was changed.
- 2026-11-05: own Ada account/alias unavailable; no cluster job or allocation check performed.
  Colab remains the selected compute environment. No local scientific run substitutes for a cluster run.
- 2026-11-05: read-only GITHUB_TOKEN absent from this environment. No secret value is requested.
  Real C2 pilot remains blocked on token, admitted remote runtime and held-out content index.
- Real BM25 artifact audit remains blocked on export of the completed Colab native run directory,
  query-level rows, saved config/hardware/input identities, timing CSVs and sibling log.
  Export the existing completed run; do not rerun or upgrade its evidence class first.
- Five-paper full-reading/page-count claim is unverified. Complete corresponding versioned notes
  are absent from the tracked tree; no full reading performed here and no notes invented.
  Completion requires full PDFs, versioned notes and page/numeric checks before paper claims.
- Dense, agent and repeated paired real dev pilots remain gated on pinned inputs, reviewed fixed
  adapter/scaffold/model, official trusted grader and explicit spend authorization.
- Unfiltered training-set expansion requires a real bounded pilot and explicit post-pilot go.
  C2-C4 fixture outcomes remain synthetic; no new fixture rows enter scientific ledgers.
- Additional synthetic per-commit benchmark rows omitted under the fixture-row restriction;
  admission code changes no retrieval hot path. Existing benchmark artifacts remain intact.
- Teaching/defence and course disclosure requirements remain unresolved; build completion does
  not establish understanding. Actual remote compute and billing are not independently verified.

## Round-one corrections

Current origin/main merged, including the later integrated mining implementation. Its miner and
package initializer are preserved; C's existing miner now lives in `ril/data_mining/c_miner.py`
with its CLI/tests adapted. No mining policy or research design changed. Makefile retains eval,
review and review-flags. C experiment entries moved into `docs/experiments/C.md`; shared index
updates are requested below. Private files, hooks, exclusions, remotes and identity are preserved.

Boot identity reads use a common patchable function and explicitly reject unavailable identity;
Colab admission remains fail-closed. Generated kit metadata is documented as output.
Linux unit: 973 passed, 4 skipped in 170.74s (0:02:50); additional CPU: 62 passed, 5 skipped in 3.50s.
CI repair: 973 unit passes/4 existing skips with global/system Git
configuration disabled; lint/format/strict typing pass. Source and outputs:
`results/logs/c_ci_fixture_identity_validation_2026-11-05.json`.
Earlier round-one exact commands and source hashes:
`results/logs/c_rulings_validation_2026-11-05.json`. Native macOS execution is unavailable.

## C1 evidence: operator_reported

The stored dev BM25 stdout and aggregate JSON agree with the CSV. All metric rows and completion
record are **operator_reported**. No query-level interval or timing recomputation is claimed.
Command: `python scripts/c_review_evidence.py`; evidence:
`results/logs/c1_colab_bm25_dev_v1_2026-10-31.json` and its referenced stdout capture.
Config hash `ce0c977b4f6a93cd5c0615846170090e7389ebc341825fa4bc4f2f69d8b75452`, seed 0;
reported source kit `dcc19574386fc66c578bb42c872e38f9e95d0201`.

| Level | Metric | Rewrite-original (pp) | Reported 95% interval (pp) | n / repos |
|---|---|---:|---|---|
| L2 | ndcg10 | +1.9258 | [-2.4594, +8.7810] | 442 / 6 |
| L2 | recall100 | +2.4049 | [-1.3140, +8.0869] | 442 / 6 |
| L3 | ndcg10 | -2.0436 | [-2.6646, -0.9102] | 238 / 3 |
| L3 | recall100 | -1.6005 | [-1.7655, -1.3556] | 238 / 3 |

Reported intervals are repository-clustered. L2 intervals include zero; L3 uses few clusters.
Upgrade only after storing the native run under results/ and recomputing from query-level rows.
E-C1-COLAB-DEV in `docs/experiments/C.md` retains the registration and artifact requirements.
BM25/dense evaluation apparatus, staging and exact/clustered statistics remain implemented.

## C2-C4 apparatus

C2 retains all overlapping base functions/methods without retriever filtering; conservative
unsupported-history/partial-parse quarantine, current-name and held-out checks remain.
C3 has a scripted retrieval/repair boundary with independently graded trusted fixtures.
C4 has paired resumable checksummed storage, conservative reservations and failure diagnostics.
Stored historical fixture outputs remain labelled synthetic, outside scientific conclusions.
No new fixture outcome, model/provider choice, mining expansion or remote job was produced.

## Requests for the lead

| Question | Options | Evidence class | Cheapest experiment | Recommendation | Meanwhile |
|---|---|---|---|---|---|
| C experiment index? | add C entries; defer | stored registration | check unique IDs | index C-owned log | prepared rows at hand-back |
| Full reading / scaffold? | verify notes; defer | unverified / reasoned | complete versioned notes then pinned adapter test | retain provisional ADR-007 | scripted only |
| Data/access? | export completed run; defer | operator_reported / measured absence | audit native query rows | supply existing bundle/token/index | no rerun or local substitute |
| Mining histories/scale? | validate/expand; defer | synthetic plumbing | real bounded pilot with two diff audits | defer expansion | existing caps and held-out rules |
| Model/spend? | hosted; pinned-local | measured absence | explicitly capped dev pairs | obtain cost/noise | ADR-008; no calls |
| Q45 test/estimate? | hypothesis-test; interval-estimate | reasoned | repeated matched dev pairs | state worthwhile effect | unmeasured; no selection |

## Scaffold table update, 2026-11-09 (made on the lead's side while the owner is away)

Rows changed in the scaffold table of `docs/EVAL_API.md`, as asked in the third round of lead notes:
the opening paragraph now points to the five paper notes; the scaffold is named retrieval-supplied
one-shot repair; the SWE-agent (seed; one replaceable retrieval tool), OpenHands (retrieval extension
and bypass policy; retry and termination rules), LocAgent and CoSIL (whole-repair cost) and Agentless
(all-attempt cost) rows say "not described in the paper" with the section and page cited, and keep the
ask as a project requirement; one line records that none of the five states a seed, a run count or an
interval (SWE-agent Table 10, p.35; Agentless pair in CoSIL, Table IX, p.10); one sentence points to
the later decisions. No code or other page of this file changed. Merge main before the next block.

## Next work

Engineer pushes corrected branch and sends hand-back for re-review. Export/audit the existing
Colab BM25 run, then complete only the authorized real-data steps once their gates are met.
Hand back after real evaluation/pilot evidence and again after unfiltered training-set/C2 work.
