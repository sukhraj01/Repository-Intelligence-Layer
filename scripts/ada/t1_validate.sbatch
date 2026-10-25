#!/bin/bash
#SBATCH --job-name=t1_validate
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=ril_t1/logs/t1_validate_%j.out
# CPU only. Training-stack validation on real pool directories (no GPU held):
#  1. selection: held-out list v2 (core plus Loc-Bench tier, rename cache) and the E-POOL-RANKS
#     feature table, at most 24 directories by the seeded order;
#  2. example cache by HTTP range requests (text, stays in ~/ril_t1/work);
#  3. BM25 mining (teacher scores of positives and the top 64 candidates);
#  4. tiny-model training (FILTER hook, teacher-mined negatives, 30 updates, checkpoints) and the
#     evaluation hook on the X2 development preparation, paired against CodeRankEmbed at 512 tokens;
#  5. CodeRankEmbed (sentence-transformers path) for 4 updates on the CPU, interrupted after 2 and
#     resumed, half-precision final model, reloaded and used to encode two texts. Checkpoints go to
#     node-local temporary space ($HOME has under 2 GB free; docs/COMPUTE.md).
# Reuses ~/ril_x2/venv_gpu310 (torch 2.4.1) with the CodeRankEmbed overlay. Resumable per stage.
# Submit from $HOME after
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_t1/
#   rsync -a data/held_out/held_out_repos.json data/held_out/rename_cache.json ada:ril_t1/data/held_out/
#   rsync -a results/tables/x3_pool_ranks_features.csv ada:ril_t1/results/tables/
#   rsync -a data/processed/x2/e3_cache/ ada:ril_t1/work/e3_cache/   (the E3 cache with the D18 no-module
#     readings, as the X2 evaluation used it; ~/ril_e/e3_cache lacks them)
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_t1/scripts/ada/t1_validate.sbatch
set -euo pipefail
W=$HOME/ril_t1
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
LIST=$HOME/ril_s2/raw/ziplist_train.json
FT=$W/results/tables/x3_pool_ranks_features.csv
DATE=${DATE:-$(date -u +%F)}
mkdir -p "$W/logs" "$W/work" "$W/out"
cd "$W"
export HF_HOME=$E/hf_cache TOKENIZERS_PARALLELISM=false RIL_THREADS=4
{ echo "host=$(hostname)"; echo "python=$(python3 -V)"; echo "cpus=$(nproc)"; \
  echo "mem=$(grep MemTotal /proc/meminfo)"; echo "cpu_model=$(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; df -h /tmp "$HOME" | tail -2; } > "$W/out/env_validate_${SLURM_JOB_ID}.txt"
export PYTHONPATH="$X2/overlay_cre:$W"
T="$PY scripts/train.py"
[ -f work/selection.json ] || $T select "$LIST" data/held_out/held_out_repos.json data/held_out/rename_cache.json \
  work/selection.json --feature-table "$FT" --max 24 --seed 0 > "out/select_${SLURM_JOB_ID}.json"
[ -f work/pool.jsonl.gz ] || $T cache "$LIST" work/selection.json work/pool.jsonl.gz --feature-table "$FT" \
  > "out/cache_${SLURM_JOB_ID}.json"
[ -f work/mined_bm25.jsonl.gz ] || $T mine work/pool.jsonl.gz work/mined_bm25.jsonl.gz --teacher bm25 --keep 64 \
  > "out/mine_${SLURM_JOB_ID}.json"
$T train configs/experiments/t1_validate_tiny.yaml work/pool.jsonl.gz --results-root "$W/results" \
  --work-root "$W/work/ckpt" --date "$DATE" --feature-table "$FT" --mined work/mined_bm25.jsonl.gz \
  > "out/train_tiny_${SLURM_JOB_ID}.json"
RES=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["result_dir"])' "out/train_tiny_${SLURM_JOB_ID}.json")
MODEL=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["final_model"])' "out/train_tiny_${SLURM_JOB_ID}.json")
mkdir -p work/dense && ln -sfn "$X2/dense/coderankembed__t512" work/dense/coderankembed__t512
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $T eval configs/experiments/t1_validate_tiny.yaml "$MODEL" "$RES" \
  --e1-config configs/experiments/e1_bm25_reproduction.yaml --prep "$X2/prep" --e3-cache "$W/work/e3_cache" \
  --data-root "$X2/raw" --work "$W/work/eval" --dense-root "$W/work/dense" \
  --baseline "coderankembed__t512=$X2/enc/coderankembed__t512" > "out/eval_tiny_${SLURM_JOB_ID}.json"
# released-checkpoint path on the CPU, checkpoints in node-local space
CK=${TMPDIR:-/tmp}/ril_t1_${SLURM_JOB_ID}
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
$T train configs/experiments/t1_validate_cre.yaml work/pool.jsonl.gz --results-root "$W/results" \
  --work-root "$CK" --date "$DATE" --stop-after 2 > "out/train_cre_part_${SLURM_JOB_ID}.json"
$T train configs/experiments/t1_validate_cre.yaml work/pool.jsonl.gz --results-root "$W/results" \
  --work-root "$CK" --date "$DATE" > "out/train_cre_${SLURM_JOB_ID}.json"
"$PY" - "out/train_cre_${SLURM_JOB_ID}.json" > "out/reload_cre_${SLURM_JOB_ID}.json" <<'PY'
import json, os, sys
from ril.training.encoders import load_trained
rec = json.load(open(sys.argv[1]))
enc = load_trained(rec["final_model"], device="cpu")
d = enc.encode_documents(["def f(x):\n    return x + 1", "class A:\n    pass"])
q = enc.encode_queries(["f returns the wrong value"])
size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(rec["final_model"]) for f in fs)
print(json.dumps({"shape": list(d.shape), "scores": [float(x) for x in d @ q[0]], "final_bytes": size,
                  "updates_this_process": rec["updates_this_process"], "finished": rec["finished"]}))
PY
du -sh "$CK" >> "out/env_validate_${SLURM_JOB_ID}.txt" || true
rm -rf "$CK"
echo done
