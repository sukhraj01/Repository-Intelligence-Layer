# results/rq3_pseudonymise/

Prompts of the 377 executable instances rebuilt after the pseudonymise-and-restore transform (D120, entry `E-RQ3-PSEUDONYMISE`
in `docs/experiments/B.md`). No model was called. Mappings (placeholder to original) are not stored here.

| File | What |
|---|---|
| `prepare_report.json` | job 65086: prompts written and rejected, prefix identity, touched prompts by kind and arm, token effect and overshoot |
| `rejections.json` | empty rejection list |
| `pseudonym_check_report.json` | job 65087: excerpt-line and gold-derived round trips, replay sample |
| `pseudonym_roundtrip_excerpt_lines.csv`, `pseudonym_roundtrip_gold.csv` | one row per placeholder-bearing excerpt line / per touched prompt |
| `replay_table_touched.csv` | the replay of 10 touched instances through the driver on the real executor |

Code: `ril/agent/providers/{pseudonymise,pseudonym_check,rq3_prompts}.py`, `scripts/rq3_driver.py` (`prepare`, `pseudonym-check`, `replay --prepared`), job `scripts/ada/rq3_driver/pseudonym_check.sbatch`.
