# results/rq2_final/

Plan-only outputs of the final-cell apparatus (entry `E-RQ2-FINAL-CELLS` in `docs/experiments/B.md`). Nothing here is a result of the
experiment: no run was trained and no checkpoint was scored.

| Path | What |
|---|---|
| `plan_only/{A,C}/plan.json` | the plan on each account: 36 runs, hashes (illustrative FILTER size 3,450 and 5,800 examples), budget on two bases and two evaluation scopes, job graph, critical path (identical on both accounts) |
| `plan_only/{A,C}/plan_drop_conditional.json` | the same without the conditional dense-teacher cell (33 runs) |
| `plan_only/{A,C}/eval_sets.json` | stores found and counted for the dev set, the eight repositories and the three stored parts of the executable 377 |
| `plan_only/{A,C}/preflight_*.json` | the real preflight (open items listed) and the rehearsal on a synthetic work directory (all checks pass) |
| `plan_only/{A,C}/submit_graph.json`, `submit_*.err` | the job graph the submit script prints and its two refusals |
| `plan_only/{A,C}/steps.txt`, `render_vs_committed.diff`, `mem_requests.txt` | step exit codes and timings, the diff of the re-rendered configurations against the committed ones (empty), the memory requests of the scripts |
| `dev_analysis_record.json`, `final_sets/` | written later by the dev analysis and the final-sets scoring (not present yet) |
