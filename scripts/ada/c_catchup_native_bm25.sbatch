#!/bin/bash
#SBATCH --job-name=c_native_bm25
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=ril_cc/logs/c_native_bm25_%j.out
# CPU only, one job. Native re-run of the paired original/Rewrite BM25 dev comparison
# (configs/experiments/c_rewrite_bm25_dev.yaml, seed 0, 2,000 draws) and its comparison with the stored
# operator summary (docs/experiments/B.md E-C-CATCHUP). The pinned dataset revision is staged on
# node-local scratch through the registered staging tool (checksums verified), the run files are written
# to node-local scratch and copied to $W/out at the end; nothing is deleted. Memory request 8G gives 4 CPUs.
#   rsync -aR --exclude __pycache__ ril scripts configs results/logs/c1_colab_bm25_dev_v1_2026-10-31.json ada:ril_cc/
#   ssh ada 'mkdir -p ril_cc/logs && cd ril_cc && UV=<uv binary> PY311=<python3.11> RIL_COMMIT=<commit> sbatch scripts/ada/c_catchup_native_bm25.sbatch'
set -euo pipefail
W=$HOME/ril_cc
REV=23da5d97a8a4495d4bd6d5616aa86d5a12a60699
MANIFEST_SHA=1b1e022998ab6ac7906514345ab8e82f4817a621d8e4c6a866a05915ccc385ac
SCRATCH=/tmp/ril_cc_${SLURM_JOB_ID:?requires Slurm}
OUT=$W/out/c_native_bm25_$SLURM_JOB_ID
mkdir -p "$SCRATCH" "$OUT"
cd "$W"
export PYTHONPATH="$W" RIL_CLUSTER=1 RIL_HOST_ALIAS="ada-account-A-$(hostname)"
export RIL_COMMIT="${RIL_COMMIT:-unknown}" UV_CACHE_DIR="$SCRATCH/uvcache"
echo "host $(hostname) $(date -u +%FT%TZ) commit $RIL_COMMIT"

# Python 3.11 with the pins of configs/experiments/c_colab_environment.yaml that the evaluator imports.
"${UV:?set the uv binary}" venv --python "${PY311:?set a Python 3.11 interpreter}" "$SCRATCH/venv"
PY=$SCRATCH/venv/bin/python
"$UV" pip install --python "$PY" numpy==2.4.6 pyyaml==6.0.3 pystemmer==3.1.0
"$PY" -c 'import sys, numpy, yaml, Stemmer; print(sys.version.split()[0], numpy.__version__, yaml.__version__, Stemmer.version())'

# Derived configuration: only data_root, output and log_path differ from the registered file.
CFG=$SCRATCH/native_bm25.yaml
"$PY" - "$SCRATCH" "$CFG" <<'PY'
import sys
from pathlib import Path
import yaml
scratch, out = Path(sys.argv[1]), Path(sys.argv[2])
cfg = yaml.safe_load(Path("configs/experiments/c_rewrite_bm25_dev.yaml").read_text())
cfg["data_root"] = str(scratch / "raw")
cfg["output"] = str(scratch / "run" / "bm25")
cfg["log_path"] = str(scratch / "run" / "bm25-log.json")
out.write_text(yaml.safe_dump(cfg, sort_keys=False))
PY

STAGE=(--config "$CFG" --manifest "$SCRATCH/manifest.json" --revision "$REV"
       --max-total-bytes 2147483648 --max-file-bytes 536870912)
"$PY" scripts/c_stage_rewrite.py manifest "${STAGE[@]}"
"$PY" scripts/c_stage_rewrite.py plan "${STAGE[@]}" | tee "$SCRATCH/plan.json"
"$PY" scripts/c_stage_rewrite.py fetch "${STAGE[@]}"
"$PY" scripts/c_stage_rewrite.py verify "${STAGE[@]}"
"$PY" - "$SCRATCH/plan.json" "$MANIFEST_SHA" <<'PY'
import json, sys
got = json.loads(open(sys.argv[1]).readline())["manifest_sha256"]
print("manifest_sha256", got, "registered", sys.argv[2], "equal", got == sys.argv[2])
assert got == sys.argv[2]
PY

# The original files staged now against the copies already held on this account (E1 dev data).
"$PY" - "$SCRATCH/raw" "$HOME/ril_e/raw" > "$SCRATCH/original_equality.txt" <<'PY'
import hashlib, json, sys
from pathlib import Path
new, old = Path(sys.argv[1]), Path(sys.argv[2])
prov = json.loads((new / "provenance.json").read_text())
equal = missing = differ = 0
for p, f in prov["completed"].items():
    if p.startswith("data/Rewrite-"):
        continue
    q = old / p
    if not q.exists():
        missing += 1
        print("not held:", p)
        continue
    h = hashlib.sha256(q.read_bytes()).hexdigest()
    if h == f["sha256"]:
        equal += 1
    else:
        differ += 1
        print("DIFFERS:", p)
print(f"original files equal {equal}, differ {differ}, not held {missing}")
PY
cat "$SCRATCH/original_equality.txt"

"$PY" -m ril.evaluation.run --config "$CFG" > "$SCRATCH/run_stdout.txt"
cat "$SCRATCH/run_stdout.txt" | head -c 600; echo

"$PY" scripts/c_native_compare.py "$SCRATCH/run/bm25-log.json" \
  results/logs/c1_colab_bm25_dev_v1_2026-10-31.json \
  --rows "$SCRATCH/c1_native_bm25_dev_query_rows.csv" --table "$SCRATCH/c1_native_vs_colab_dev_v1.csv" \
  --log "$SCRATCH/c1_native_bm25_dev_v1.json" --run-files "$SCRATCH/run"

cp -r "$SCRATCH/run" "$OUT/run_files"
cp "$SCRATCH/raw/provenance.json" "$SCRATCH/manifest.json" "$SCRATCH/plan.json" "$SCRATCH/native_bm25.yaml" \
   "$SCRATCH/run_stdout.txt" "$SCRATCH/original_equality.txt" "$SCRATCH/c1_native_bm25_dev_query_rows.csv" \
   "$SCRATCH/c1_native_vs_colab_dev_v1.csv" "$SCRATCH/c1_native_bm25_dev_v1.json" "$OUT/"
mkdir -p "$OUT/rewrite_queries"
(cd "$SCRATCH/raw" && find data -path 'data/Rewrite-*' -name queries.jsonl -exec cp --parents {} "$OUT/rewrite_queries" \;)
du -sh "$OUT"
echo "scratch left in $SCRATCH on $(hostname)"
echo done
