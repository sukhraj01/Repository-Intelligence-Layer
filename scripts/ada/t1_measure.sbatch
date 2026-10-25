#!/bin/bash
#SBATCH --job-name=t1_measure
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:45:00
#SBATCH --output=ril_t1/logs/t1_measure_%j.out
# GPU. Training throughput and peak device memory per batch shape (stage train_step) of the
# CodeRankEmbed path: CUDA gate, then for each shape 3 warmup and 10 timed updates on a throwaway
# model; a shape that does not fit is recorded as oom. Needs an example cache with at least as many
# examples as the largest batch (CPU stage first, e.g.
#   sbatch --wrap "cd ril_t1 && PYTHONPATH=. ~/ril_x2/venv_gpu310/bin/python scripts/train.py select ... --max 80 && ... cache ..."
# ). Rows go to ~/ril_t1/out/latency/throughput_log.csv (appended to results/latency/ locally).
#   sbatch --export=ALL,CACHE=work/pool80.jsonl.gz,RIL_COMMIT=<hash> ril_t1/scripts/ada/t1_measure.sbatch
set -euo pipefail
W=$HOME/ril_t1
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
mkdir -p "$W/logs" "$W/out/latency"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export PYTHONPATH="$X2/overlay_cre:$W"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "$W/out/nvidia_${SLURM_JOB_ID}.txt" || true
# one process per shape and setting, so that an out-of-memory shape cannot hold memory for the next
SHAPES=${SHAPES:-"2,1,1,256 4,1,1,256 4,1,1,512 8,1,1,512 8,3,2,512 16,1,1,512 16,3,2,512 32,1,1,512 8,1,1,1024"}
SETTINGS=${SETTINGS:-"fp32 amp amp_gc"}
for st in $SETTINGS; do
  case $st in fp32) OPT="";; amp) OPT="--precision amp_fp16";; amp_gc) OPT="--precision amp_fp16 --grad-ckpt";; esac
  for sh in $SHAPES; do
    "$PY" scripts/train.py measure configs/experiments/t1_validate_cre.yaml "$CACHE" \
      "out/measure_${SLURM_JOB_ID}_${st}_${sh//,/-}.json" out/latency --device cuda --shapes $sh $OPT \
      > /dev/null 2>> "out/measure_${SLURM_JOB_ID}.stderr" || echo "failed $st $sh" >> "out/measure_${SLURM_JOB_ID}.stderr"
  done
done
echo done
