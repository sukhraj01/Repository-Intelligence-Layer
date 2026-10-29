#!/bin/bash
#SBATCH --job-name=ril_dev_ansible
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=3
#SBATCH --mem=12G
#SBATCH --time=03:00:00
#SBATCH --output=ril_e/logs/dev_ansible_prepare_%j.out
# CPU only. Makes SWE-bench Pro ansible usable as a third development repository (decision D32,
# configs/experiments/e1_bm25_dev3.yaml): instance cache (pilot-E3 layout, gold readings of D18),
# unit-text, query and chunk-text stores for the evaluation hook. Everything is added next to the
# existing files, nothing is overwritten (new cache directory ~/ril_e/e3_cache_ansible, new files in
# ~/ril_x2/prep and ~/ril_t1/work/e3_cache). Working clones go to node-local space ($HOME has ~1 GB free).
# Needs the unit records and raw folders the L3 census made (~/ril_x1/out_census, ~/ril_x1/raw_census,
# ~/ril_x1/repo_cache_census, ~/ril_x1/census_meta.json).  Submit from $HOME after
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_e/
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_e/scripts/ada/dev_ansible_prepare.sbatch
set -euo pipefail
E=$HOME/ril_e
X1=$HOME/ril_x1
X2=$HOME/ril_x2
FOLDER=instance_ansible__ansible
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
CFG=configs/experiments/e1_bm25_dev3.yaml
FREE=$(df -Pm "$HOME" | awk 'NR==2{print $4}')
[ "$FREE" -gt 500 ] || { echo "only $FREE MB free in HOME"; exit 3; }
mkdir -p "$E/logs" "$E/e3_cache_ansible" "$E/e3_out_ansible"
# 1. inputs, linked or copied without overwriting
for lv in LEVEL-2 LEVEL-3; do
  d=$E/raw/data/$lv/SWE-bench_Pro/$FOLDER
  [ -e "$d" ] || ln -s "$X1/raw_census/data/$lv/SWE-bench_Pro/$FOLDER" "$d"
done
[ -e "$E/repo_cache/ansible__ansible.git" ] || ln -s "$X1/repo_cache_census/ansible__ansible.git" "$E/repo_cache/ansible__ansible.git"
cp -n "$X1/out_census/$FOLDER/units/"*.json "$E/out/units/"
cd "$E"
export PYTHONPATH="$E"
"$PY" -I - <<PY
import json
m = json.load(open("$X1/census_meta.json"))
json.dump({k: {"base_commit": v["base_commit"], "repo": v["repo"]} for k, v in m.items() if k.startswith("instance_ansible__ansible")},
          open("$E/meta_ansible.json", "w"))
PY
TMPW=$(mktemp -d /tmp/ril_dev_ansible.XXXXXX)
trap 'rm -rf "$TMPW"' EXIT
# 2. instance cache, K shards
K=3
pids=()
for i in $(seq 0 $((K-1))); do
  "$PY" scripts/e3_run.py prepare $CFG "$E/raw" "$E/meta_ansible.json" "$E/repo_cache" "$E/e3_cache_ansible" "$TMPW" "$E/e3_out_ansible" \
    "$E/out/units" --roles dev --only $FOLDER --shard $i $K > "$E/logs/dev_ansible_e3_shard$i.log" 2>&1 &
  pids+=($!)
done
rc=0
for p in "${pids[@]}"; do wait "$p" || rc=$?; done
echo "e3 prepare rc=$rc"
[ $rc -eq 0 ] || exit $rc
"$PY" scripts/e3_add_readings.py "$E/e3_cache_ansible" "$E/out/units"
# 3. text stores for the evaluation hook (only the ansible folder: a config copy with that folder alone)
"$PY" -I - <<PY
import yaml
c = yaml.safe_load(open("$CFG"))
c["folders"] = [f for f in c["folders"] if f["folder"] == "$FOLDER"]
yaml.safe_dump(c, open("$TMPW/ansible_only.yaml", "w"))
PY
mkdir -p "$X2/prep/units"
for i in 0 1 2; do
  "$PY" scripts/x2_run.py prep-units "$TMPW/ansible_only.yaml" "$E/meta_ansible.json" "$E/repo_cache" "$E/e3_cache_ansible" "$TMPW" "$X2/prep" \
    --roles dev --shard $i 3 > "$E/logs/dev_ansible_prep_units_s$i.log" 2>&1 &
done
wait
for i in 0 1 2; do mv "$X2/prep/prep_units_s$i.json" "$X2/prep/prep_units_ansible_s$i.json" 2>/dev/null || true; done
"$PY" - <<PY
import json, sys
sys.path.insert(0, "$E")
from ril.evaluation import x2_dense as xd
r1 = xd.prepare_queries("$TMPW/ansible_only.yaml", {"dev"}, "$E/raw", "$X2/prep")
r2 = xd.prepare_chunks("$TMPW/ansible_only.yaml", {"dev"}, "$E/raw", "$X2/prep")
json.dump({"queries": r1, "chunks": r2}, open("$X2/prep/prep_ansible.json", "w"), indent=1)
print(json.dumps({"queries": r1, "chunks_keys": list(r2)}))
PY
# 4. the cache copy the training evaluation reads (new files only)
cp -n "$E/e3_cache_ansible/"*.npz "$HOME/ril_t1/work/e3_cache/"
ls "$E/e3_cache_ansible" | wc -l
du -sh "$E/e3_cache_ansible" "$X2/prep"
echo done
