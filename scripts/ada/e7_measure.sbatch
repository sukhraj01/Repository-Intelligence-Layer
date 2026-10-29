#!/bin/bash
#SBATCH --job-name=e7_measure
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --gres=gpu:1
#SBATCH --constraint=2080ti
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:40:00
#SBATCH --output=ril_t1/logs/e7_measure_%j.out
# GPU. Training throughput and peak device memory of Qwen3-Embedding-0.6B at the batch shape of the
# pilots (and smaller shapes if that one does not fit), plus CodeRankEmbed at the same shape in the
# same job as the control. The CUDA gate (real matrix product, compute capability >= 7.0) runs inside
# the measurement before any model loads. 3 warmup and 10 timed updates on a throwaway model, one
# process per shape so that an out-of-memory shape cannot hold memory for the next. Rows go to
# ~/ril_t1/out/latency/throughput_log.csv (appended to results/latency/ locally). $HOME is nearly
# full: only small JSON and CSV files are written.
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_t1/scripts/ada/e7_measure.sbatch
set -euo pipefail
W=$HOME/ril_t1
X2=$HOME/ril_x2
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
CACHE=${CACHE:-work/pool80.jsonl.gz}
mkdir -p "$W/logs" "$W/out/latency"
cd "$W"
export HF_HOME=$E/hf_cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv > "$W/out/nvidia_${SLURM_JOB_ID}.txt" || true
J=${SLURM_JOB_ID}
# Qwen3 needs the newer transformers of the base environment; CodeRankEmbed needs the overlay.
QS=${QWEN_SHAPES:-"32,1,1,512 16,1,1,512 8,1,1,512 4,1,1,512"}
for sh in $QS; do
  sh=${sh//\//,}
  PYTHONPATH="$W" "$PY" scripts/train.py measure configs/experiments/e7_train_step_qwen3.yaml "$CACHE" \
    "out/e7_qwen3_${J}_${sh//,/-}.json" out/latency --device cuda --shapes $sh --precision amp_fp16 --grad-ckpt \
    > /dev/null 2>> "out/e7_${J}.stderr" || echo "failed qwen3 $sh" >> "out/e7_${J}.stderr"
done
CS=${CRE_SHAPES:-"32,1,1,512"}
for sh in $CS; do
  sh=${sh//\//,}
  PYTHONPATH="$X2/overlay_cre:$W" "$PY" scripts/train.py measure configs/experiments/t1_validate_cre.yaml "$CACHE" \
    "out/e7_cre_${J}_${sh//,/-}.json" out/latency --device cuda --shapes $sh --precision amp_fp16 --grad-ckpt \
    > /dev/null 2>> "out/e7_${J}.stderr" || echo "failed cre $sh" >> "out/e7_${J}.stderr"
done
if [ "${PROBE:-0}" = 1 ]; then  # memory held by weights, gradients and optimizer state after one update at batch 1
  PYTHONPATH="$W" "$PY" - <<'PYEOF' > "out/e7_probe_${J}.json" 2>> "out/e7_${J}.stderr"
import json, torch
from ril.training.encoders import build_encoder
from ril.training.training import load_train_config
cfg = load_train_config("configs/experiments/e7_train_step_qwen3.yaml")
enc = build_encoder(cfg["model"], device="cuda", seed=0)
n = sum(p.numel() for p in enc.module.parameters())
out = {"parameters": n, "weights_mb": round(torch.cuda.memory_allocated() / 2**20, 1)}
enc.module.train()
x = enc.embed(["def f(x):\n    return x"], False)
x.float().sum().backward()
out["after_backward_mb"] = round(torch.cuda.memory_allocated() / 2**20, 1)
out["peak_after_backward_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
for foreach in (None, False):  # default AdamW (as the training path builds it), then per-tensor update
    opt = torch.optim.AdamW(enc.module.parameters(), lr=1e-5, foreach=foreach)
    key = "foreach_default" if foreach is None else "foreach_false"
    try:
        opt.step()
        out[key] = {"status": "ok", "allocated_mb": round(torch.cuda.memory_allocated() / 2**20, 1),
                    "peak_mb": round(torch.cuda.max_memory_allocated() / 2**20, 1)}
    except torch.cuda.OutOfMemoryError:
        out[key] = {"status": "oom", "peak_mb": round(torch.cuda.max_memory_allocated() / 2**20, 1)}
    del opt
    torch.cuda.empty_cache()
print(json.dumps(out))
PYEOF
fi
echo done
