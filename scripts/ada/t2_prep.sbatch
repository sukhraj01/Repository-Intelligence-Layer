#!/bin/bash
#SBATCH --job-name=t2_prep
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=03:00:00
#SBATCH --output=ril_t2/logs/t2_prep_%j.out
# CPU only. Smoke-pilot inputs (E-PILOT-K, E-PILOT-NEG, E-PILOT-LEAK), no GPU held:
#  1. selection A: the first 2,000 pool directories outside the held-out list (v2, core plus the
#     Loc-Bench tier, rename cache) by the seeded order sha256("0:<directory>");
#  2. selection L (leakage pilot only): the first 2,000 directories of the whole listing by the same
#     order, held-out repositories included (--include-held-out), so it shares every non-held-out
#     directory of its prefix with A and differs only by held-out directories in place of A's tail;
#  3. example caches of both by HTTP range request (pool text; stays in ~/ril_t2/work).
# Memory estimate (written before the first run): streaming keeps at most ahead+1 directories in
# memory (mean 1.0 MB of corpus per directory, measured over the pool; heavy tail up to tens of
# MB), so well under 1 GB; 4 GB requested. Disk: the 80-directory cache of T1 is 12 MB, so about
# 0.3 GB per 2,000-directory cache ($HOME had 1.8 GB free on 2026-10-25). Resumable per stage.
# Submit from $HOME after
#   rsync -a --exclude __pycache__ ril scripts configs ada:ril_t2/
#   rsync -a data/held_out/held_out_repos.json data/held_out/rename_cache.json ada:ril_t2/data/held_out/
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_t2/scripts/ada/t2_prep.sbatch
set -euo pipefail
W=$HOME/ril_t2
X2=$HOME/ril_x2
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
LIST=$HOME/ril_s2/raw/ziplist_train.json
HO=data/held_out/held_out_repos.json
RC=data/held_out/rename_cache.json
N=${N:-2000}
mkdir -p "$W/logs" "$W/work" "$W/out"
cd "$W"
export PYTHONPATH="$W"
{ echo "host=$(hostname)"; echo "python=$(python3 -V)"; echo "cpus=$(nproc)"; \
  echo "ril_commit=${RIL_COMMIT:-none}"; df -h "$HOME" | tail -1; } > "out/env_prep_${SLURM_JOB_ID}.txt"
T="$PY scripts/train.py"
[ -f work/selection_A.json ] || $T select "$LIST" $HO $RC work/selection_A.json --max "$N" --seed 0 \
  > "out/select_A_${SLURM_JOB_ID}.json"
[ -f work/selection_L.json ] || $T select "$LIST" $HO $RC work/selection_L.json --max "$N" --seed 0 \
  --include-held-out > "out/select_L_${SLURM_JOB_ID}.json"
[ -f work/pool_A.jsonl.gz ] || $T cache "$LIST" work/selection_A.json work/pool_A.jsonl.gz \
  > "out/cache_A_${SLURM_JOB_ID}.json"
[ -f work/pool_L.jsonl.gz ] || $T cache "$LIST" work/selection_L.json work/pool_L.jsonl.gz \
  > "out/cache_L_${SLURM_JOB_ID}.json"
du -sh work/pool_A.jsonl.gz work/pool_L.jsonl.gz >> "out/env_prep_${SLURM_JOB_ID}.txt"
echo done
