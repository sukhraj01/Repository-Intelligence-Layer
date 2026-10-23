#!/bin/bash
#SBATCH --job-name=x2_score
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=10G
#SBATCH --time=04:00:00
#SBATCH --output=ril_x2/logs/x2_score_%j.out
# CPU only. Dense measurements X2, scoring stage: per-instance unit scores of every encoded variant
# (encoder x cut) present under enc/, chunk-level ranks (BM25, dense, RRF) for the variants named in
# CHUNK_VARIANTS, and (MEASURE=1) query-encode, flat-search and encoding-throughput rows on this
# CPU node (4 threads), one process per encoder and cut so that peak memory is per encoder.
#   sbatch --export=ALL,MEASURE=1,RIL_COMMIT=<hash> ril_x2/scripts/ada/x2_score.sbatch
set -euo pipefail
W=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
GV=$W/venv_gpu$PYV
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
cd "$W"
CFG=configs/experiments/e1_bm25_reproduction.yaml
for d in "$W"/enc/*__t*; do
  v=$(basename "$d"); cut=${v##*__t}
  PYTHONPATH="$W" "$GV/bin/python" scripts/x2_run.py score-units "$W/prep" "$d" "$W/dense/$v" --cut $cut \
    --roles ${ROLES:-dev test} >> "$W/logs/x2_score_units.log" 2>&1
done
if [ -n "${CHUNK_VARIANTS:-}" ]; then
  VARGS=()
  for v in $CHUNK_VARIANTS; do VARGS+=("$v=$W/enc/$v"); done
  PYTHONPATH="$W" "$GV/bin/python" scripts/x2_run.py score-chunks $CFG "$W/raw" "$W/chunks_out" \
    --variants "${VARGS[@]}" --roles ${ROLES:-dev test} >> "$W/logs/x2_score_chunks.log" 2>&1
fi
if [ "${MEASURE:-0}" = 1 ]; then
  for enc in coderankembed qwen3-embedding-0.6b; do
    if [ "$enc" = coderankembed ]; then PP="$W/overlay_cre:$W"; else PP="$W"; fi
    for cut in 512 1024; do
      PYTHONPATH="$PP" RIL_COMMIT=${RIL_COMMIT:-none} RIL_DIRTY=${RIL_DIRTY:-0} "$GV/bin/python" scripts/x2_run.py measure \
        $enc $cut "$W/prep" "$W/enc/${enc}__t$cut" "$W/out/query_sets" "$W/out/latency" \
        "$W/out/measure_${enc}_t${cut}_cpu_${SLURM_JOB_ID}.json" --device cpu --store streamlink__streamlink \
        --sample ${SAMPLE:-128} --threads 4
    done
  done
fi
echo done
