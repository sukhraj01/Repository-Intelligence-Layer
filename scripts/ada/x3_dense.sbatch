#!/bin/bash
#SBATCH --job-name=x3_dense
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=02:30:00
#SBATCH --output=ril_x3/logs/x3_dense_%j.out
# GPU. Pool-rank measurement (E-POOL-RANKS), dense stage: CUDA gate (real matrix product checked
# against the CPU), then for each teacher the sample's directories are fetched ahead in threads
# while the GPU encodes snapshot and issue; ranks of the positives and encode timings are appended
# per directory (resumable). Needs x3_prepare (models in the cache, loaded offline once).
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_x3/scripts/ada/x3_dense.sbatch
# Full pool (not run by default): SELECT=all SHARD="i n" (repositories split by hash) with a longer
# --time; see scripts/ada/README.md for the estimate.
set -euo pipefail
W=$HOME/ril_x3
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
GV=$X2/venv_gpu$PYV
LIST=$HOME/ril_s2/raw/ziplist_train.json
META=$HOME/ril_pc/work/pool_meta.jsonl
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
cd "$W"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "$W/out/nvidia_${SLURM_JOB_ID}.txt" || true
SHARD=${SHARD:-"0 1"}
if [ "${SELECT:-sample}" = all ]; then
  SEL="--meta $META"; OUT=$W/work/full_ranks_dense_s${SHARD// /of}.jsonl
else
  SEL="--sample $W/work/sample.json"; OUT=$W/work/ranks_dense.jsonl
fi
PYTHONPATH="$X2/overlay_cre:$W" RIL_COMMIT=${RIL_COMMIT:-none} "$GV/bin/python" scripts/pool_ranks.py dense \
  "$LIST" "$OUT" "$W/out/dense_${SLURM_JOB_ID}.json" --teachers ${TEACHERS:-swerankembed-small coderankembed} \
  --cut ${CUT:-1024} --batch-size ${BATCH:-64} $SEL --shard $SHARD --ahead 4
echo done
