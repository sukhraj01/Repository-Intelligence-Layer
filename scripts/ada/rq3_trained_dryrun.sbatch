#!/bin/bash
#SBATCH --job-name=rq3_trained_dry
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=ril_rq3t/logs/%x_%j.out
# CPU only, no GPU, no model call, nothing deleted (E-RQ3-TRAINED-ARMS). Dry run of the trained-arm path with the
# retained smoke model (a 16-dimension hashing encoder, 6 updates, 18.6 kB, kept under ril_fp/keep_id) on the DEV
# set and five dev instances, never a final set: checkpoint load and manifest check, encode and score (CPU), the
# per-instance score files, contexts through the build path of the trained arms (node-local checkout at the base
# commit, assembly unchanged), prompts through the driver's pseudonymise-and-screen path, and the restore of
# the reply. The sealed final sets are not read (the encode stage runs with --dry-run-dev, which refuses a final set).
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_rq3t/scripts/ada/rq3_trained_dryrun.sbatch
set -euo pipefail
W=${RQ3T_DIR:-$HOME/ril_rq3t}
X2=$HOME/ril_x2
E=$HOME/ril_e
RUN_ID=t1_test_u6_s3
ROOT=$HOME/ril_fp/keep_id
IDS="conan-io__conan-15377 conan-io__conan-15422 conan-io__conan-15457 conan-io__conan-15485 conan-io__conan-15499"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PYG=$X2/venv_gpu$PYV/bin/python
PYC=$E/venv_ril$PYV/bin/python
TMPW=$(mktemp -d "${TMPDIR:-/tmp}/ril_rq3t_dry.XXXXXX")
trap 'rm -rf "$TMPW"' EXIT
mkdir -p "$W/logs" "$W/dry"
cd "$W"
{ echo "host=$(hostname)"; echo "cpus=$(nproc)"; echo "ril_commit=${RIL_COMMIT:-none}"; echo "job=${SLURM_JOB_ID:-none}"; \
  echo "run_id=$RUN_ID"; } > "$W/dry/env_${SLURM_JOB_ID:-0}.txt"
export PYTHONPATH="$X2/overlay_cre:$W" RIL_COMMIT=${RIL_COMMIT:-none} CUDA_VISIBLE_DEVICES=""
echo "== 1. plan"
$PYC scripts/rq3_trained_arm.py plan --retained-root "$ROOT" --only "$RUN_ID" > "$W/dry/plan_${SLURM_JOB_ID:-0}.json"
cat "$W/dry/plan_${SLURM_JOB_ID:-0}.json" | head -30
echo "== 2. encode and score (CPU, dev set, five instances)"
$PYG scripts/rq3_trained_arm.py encode --retained-root "$ROOT" --only "$RUN_ID" --dry-run-dev --ids $IDS \
  --out "$W/dry/scores" --home "$HOME" --work "$TMPW/enc" --device cpu > "$W/dry/encode_${SLURM_JOB_ID:-0}.json"
ls "$W/dry/scores/$RUN_ID/dense_scores"
echo "== 3. contexts (checkout at the base commit, node-local)"
mkdir -p "$TMPW/repo_cache"
ln -s "$E/repo_cache/conan-io__conan.git" "$TMPW/repo_cache/conan-io__conan.git"
$PYC scripts/rq3_trained_arm.py contexts configs/experiments/rq3_contexts_v1.yaml "$W/dry/scores" "$TMPW/repo_cache" \
  "$TMPW/work" "$W/dry/ctx" --models "$RUN_ID" --members $IDS
echo "== 4. prompts, pseudonymise, restore"
$PYC -I - "$W/dry" "$RUN_ID" $IDS <<'PY'
import json, sys
sys.path.insert(0, ".")
from ril.agent.providers.pilot_run import load_items
from ril.agent.providers.pseudonymise import restore_text
from ril.agent.providers.trained_arms import prepare_trained
from ril.evaluation.rq3_trained import arm_name

dry, rid, *ids = sys.argv[1:]
arm = arm_name(rid)
issues = {i: f"Dry-run issue text for {i}. Contact someone.real@corp.example, see /home/someone/x.py." for i in ids}
res = prepare_trained(f"{dry}/ctx/{rid}", arm, issues, 8000, f"{dry}/prepared/{rid}")
items = load_items(f"{dry}/prepared/{rid}")
restored = [
    restore_text(it["prompt"], it["restore"]) == it["prompt"] for it in items if it.get("restore") is not None
]
report = {
    "arm": arm,
    "prompts_written": res["written"],
    "rejected": len(res["rejected"]),
    "skipped": len(res["skipped"]),
    "touched": sum(1 for it in items if it.get("restore") is not None),
    "restore_changes_prompt": all(not r for r in restored),
    "approx_tokens_max": max(it["approx_tokens_prompt"] for it in items),
}
print(json.dumps(report, indent=1))
open(f"{dry}/dry_run_report.json", "w").write(json.dumps(report, indent=1, sort_keys=True))
PY
du -sh "$W/dry"
echo done
