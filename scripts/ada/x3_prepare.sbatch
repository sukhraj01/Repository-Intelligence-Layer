#!/bin/bash
#SBATCH --job-name=x3_prepare
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=ril_x3/logs/x3_prepare_%j.out
# CPU only. Pool-rank measurement (E-POOL-RANKS), preparation stage; no GPU is held:
#  1. downloads the SweRankEmbed-Small teacher (pinned revision) and the modelling code its
#     configuration points to into the shared model cache, then loads both dense teachers offline
#     on the CPU (two texts) so the GPU stage cannot fail on loading;
#  2. BM25 ranks of the sample's positives (directories fetched by HTTP range request);
#  3. the dedup measurement (distinct function texts over all directories of a seeded set of
#     repositories), which the full-pool cost estimate needs.
# Reuses the environment of the dense measurements (~/ril_x2/venv_gpu310 with the CodeRankEmbed
# overlay) and the pilot-E venv for BM25. Resumable: finished directories and repositories are skipped.
# Submit from $HOME after
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_x3/ ; rsync sample.json ada:ril_x3/work/
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_x3/scripts/ada/x3_prepare.sbatch
set -euo pipefail
W=$HOME/ril_x3
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
GV=$X2/venv_gpu$PYV
PY=$E/venv_ril$PYV/bin/python
LIST=$HOME/ril_s2/raw/ziplist_train.json
META=$HOME/ril_pc/work/pool_meta.jsonl
mkdir -p "$W/logs" "$W/work" "$W/out"
cd "$W"
export HF_HOME=$E/hf_cache TOKENIZERS_PARALLELISM=false
{ echo "host=$(hostname)"; echo "python=$(python3 -V)"; echo "cpus=$(nproc)"; \
  echo "mem=$(grep MemTotal /proc/meminfo)"; echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; } > "$W/out/env_prepare_${SLURM_JOB_ID}.txt"
if [ ! -f "$W/work/models.ok" ]; then
  PYTHONPATH="$X2/overlay_cre:$W" "$GV/bin/python" - <<'PY'
from huggingface_hub import snapshot_download
print(snapshot_download("Salesforce/SweRankEmbed-Small", revision="745d2a06103a66d3cfa600aa52fc0d3523010daa"))
print(snapshot_download("Snowflake/snowflake-arctic-embed-m-long", allow_patterns=["*.py", "*.json"]))
PY
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH="$X2/overlay_cre:$W" "$GV/bin/python" - <<'PY'
from ril.retrieval.dense_encoder import ENCODERS, DenseEncoder, local_snapshot
for name in ("swerankembed-small", "coderankembed"):
    spec = ENCODERS[name].with_max_tokens(1024)
    enc = DenseEncoder.load(spec, device="cpu", threads=4, local_dir=local_snapshot(spec))
    v = enc.encode_documents(["def f(x):\n    return x + 1", "class A:\n    pass"])
    q = enc.encode_query("f returns the wrong value")
    print(name, v.shape, float(v[0] @ q), float(v[1] @ q))
PY
  touch "$W/work/models.ok"
fi
export PYTHONPATH="$W"
$PY scripts/pool_ranks.py bm25 "$LIST" "$W/work/ranks_bm25.jsonl" --sample "$W/work/sample.json" --ahead 4 \
  > "$W/out/bm25_${SLURM_JOB_ID}.json"
$PY scripts/pool_ranks.py dedup "$LIST" "$META" "$W/work/dedup.jsonl" --repos-per-bin ${DEDUP_REPOS:-4} --seed 0 \
  > "$W/out/dedup_${SLURM_JOB_ID}.json"
echo done
