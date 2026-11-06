#!/bin/bash
#SBATCH --job-name=rq3_units_encode
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --output=ril_rq3u/logs/rq3_units_encode_%j.out
# GPU. Dense stores of the executable subset (E-RQ3-UNITS, D107): the base encoder at 512 tokens
# over the de-duplicated unit texts and the issue-text stores of rq3_units_cpu.sbatch. Submitted
# only when the encoding rule of D107 allows it (implied GPU-hours at 109 texts/s <= Block 4's
# 6.0). Encoding only. Text stores are unpacked and vectors written on node-local space, vectors
# are copied to $HOME at the end. The run log records the CUDA gate and the seconds per store.
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_rq3u/scripts/ada/rq3_units_encode.sbatch
set -euo pipefail
W=$HOME/ril_rq3u
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
GV=$X2/venv_gpu$PYV
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
NODE_FREE=$(df -Pm /tmp | awk 'NR==2{print $4}')
[ "$NODE_FREE" -gt 20000 ] || { echo "node-local /tmp on $(hostname) has only $NODE_FREE MB free"; exit 4; }
TMPW=$(mktemp -d /tmp/ril_rq3u_enc.XXXXXX)
trap 'rm -rf "$TMPW"' EXIT
cd "$W"
mkdir -p out "$TMPW/prep/texts_units" "$TMPW/enc"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "$W/out/nvidia_${SLURM_JOB_ID}.txt" || true
echo "ril_commit=${RIL_COMMIT:-none}" > "$W/out/env_encode_${SLURM_JOB_ID}.txt"
for f in "$W"/prep/texts_units_gz/*.gz; do gunzip -c "$f" > "$TMPW/prep/texts_units/$(basename "$f" .gz)"; done
cp -r "$W/prep/queries" "$TMPW/prep/queries"
PYTHONPATH="$X2/overlay_cre:$W" "$GV/bin/python" scripts/x2_run.py encode "$TMPW/prep" "$TMPW/enc" \
  "$W/out/encode_coderankembed_${SLURM_JOB_ID}.json" --cuts 512 --kinds units queries --encoders coderankembed
mkdir -p "$W/enc/coderankembed__t512"
cp -n "$TMPW"/enc/coderankembed__t512/*.npz "$W/enc/coderankembed__t512/"
du -sh "$W/enc"
echo done
