#!/bin/bash
#SBATCH --job-name=rq2f_retcheck
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --exclude=gnode004,gnode044,gnode057,gnode060
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:30:00
#SBATCH --output=ril_rq2f/logs/%x_%j.out
# GPU. Retention round trip (docs/RQ2_LAUNCH_PLAN.md, launch smoke): the retained model of one run is
# loaded back from disk and scored on the dev set with the same evaluation entry point the training job
# used (scripts/train.py eval), then its per-query dense rows are compared with the run's own. The
# retained float16 copy is made from the in-memory model after training, so equal rows show that the
# copy carries the trained weights. Needs the run's result directory (RESULT) and retained folder (RET).
#   sbatch --export=ALL,CONFIG=<yaml>,RET=<retained folder>,RESULT=<result dir>,RIL_COMMIT=<hash> \
#          ril_rq2f/scripts/ada/rq2f_retention_check.sbatch
set -euo pipefail
W=${W:-$HOME/ril_rq2f}
X2=$HOME/ril_x2
E=$HOME/ril_e
CONFIG=${CONFIG:?set CONFIG}
RET=${RET:?set RET}
RESULT=${RESULT:?set RESULT}
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
CK=${TMPDIR:-/tmp}/ril_rq2f_retcheck_${SLURM_JOB_ID}
mkdir -p "$W/logs" "$W/out" "$CK/eval"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
export RIL_COMMIT=${RIL_COMMIT:-none}
{ echo "host=$(hostname)"; echo "ril_commit=$RIL_COMMIT"; echo "ret=$RET"; } > "out/env_retcheck_${SLURM_JOB_ID}.txt"
OUT=$W/out/retcheck_${SLURM_JOB_ID}
mkdir -p "$OUT"
"$PY" scripts/train.py eval "$CONFIG" "$RET/model" "$OUT/result" --eval-set dev --home "$HOME" --work "$CK/eval" --device cuda \
  > "out/retcheck_eval_${SLURM_JOB_ID}.json"
"$PY" scripts/rq2_retention_compare.py "$RESULT/query_rows.csv" "$OUT/result/query_rows.csv" "$OUT/compare.json"
rm -rf "$CK"
echo done
