#!/bin/bash
#SBATCH --job-name=a_fetch_dev
#SBATCH --partition=u22
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=03:00:00
#SBATCH --output=ril_a/logs/a_fetch_dev_%j.out
# CPU only. Fetches the CORE-Bench development folders of e1_bm25_dev3.yaml (role dev: SWE-bench Pro
# openlibrary, qutebrowser, ansible at L2 and L3; SWE-bench-Live conan, deepset, streamlink at L2)
# into ~/ril_a/raw, and builds the Python environment of workstream A inside the job (compute nodes
# run another Python than the login node). Resumable and idempotent: listings and files already
# present are kept (hf_fetch.py checks byte sizes). Account and QOS are given at submission:
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_a/
#   ssh ada 'mkdir -p ril_a/logs && sbatch -A <account> -q <qos> ril_a/scripts/ada/a_fetch_dev.sbatch'
set -euo pipefail
W=$HOME/ril_a
mkdir -p "$W/logs" "$W/raw/listings"
cd "$W"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
VENV=$W/venv_a$PYV
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check numpy pyyaml PyStemmer
fi
FOLDERS=(
  LEVEL-2/SWE-bench_Pro/instance_internetarchive__openlibrary
  LEVEL-3/SWE-bench_Pro/instance_internetarchive__openlibrary
  LEVEL-2/SWE-bench_Pro/instance_qutebrowser__qutebrowser
  LEVEL-3/SWE-bench_Pro/instance_qutebrowser__qutebrowser
  LEVEL-2/SWE-bench_Pro/instance_ansible__ansible
  LEVEL-3/SWE-bench_Pro/instance_ansible__ansible
  LEVEL-2/SWE-bench-Live/conan
  LEVEL-2/SWE-bench-Live/deepset
  LEVEL-2/SWE-bench-Live/streamlink__streamlink
)
P=()
for f in "${FOLDERS[@]}"; do
  out="raw/listings/$(echo "$f" | tr '/' '_').json"
  [ -s "$out" ] || python3 scripts/ada/hf_list_tree.py zhangfw123/CORE-Bench "data/$f" "$out"
  P+=("data/$f/")
done
python3 - raw/listings raw/listing_dev.json <<'EOF'
import glob, json, sys
entries = []
for path in sorted(glob.glob(sys.argv[1] + "/*.json")):
    entries.extend(json.load(open(path))["entries"])
json.dump({"entries": entries}, open(sys.argv[2], "w"))
print("listed files:", sum(e["type"] == "file" for e in entries),
      "bytes:", sum(e.get("size", 0) for e in entries if e["type"] == "file"))
EOF
python3 scripts/ada/hf_fetch.py zhangfw123/CORE-Bench raw/listing_dev.json "$W/raw" "${P[@]}"
"$VENV/bin/python" -V
du -sh "$W/raw"
echo done
