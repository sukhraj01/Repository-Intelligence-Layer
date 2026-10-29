#!/bin/bash
#SBATCH --job-name=t3_prep
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=03:00:00
#SBATCH --output=ril_t3/logs/t3_prep_%j.out
# CPU only. Pool of the learning curve (E-PILOT-CURVE): the next 3,000 pool directories after
# selection A (the first 2,000 outside the held-out list in the seeded order sha256("0:<directory>");
# the 5,000-prefix minus A's names), cached by HTTP range request into an untracked file that is
# read together with A's cache (ril_t2/work/pool_A.jsonl.gz, linked into work/).
# Memory estimate: streaming holds ahead+1 directories (mean 1.0 MB), peak 1.1 GB measured for the
# 2,000-directory job (38821); 4 GB requested. Disk: 0.27 GB per 2,000 directories, so about 0.4 GB
# ($HOME had 547 MB free). Resumable by file existence.
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_t3/scripts/ada/t3_prep.sbatch
set -euo pipefail
W=$HOME/ril_t3
X2=$HOME/ril_x2
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$X2/venv_gpu$PYV/bin/python
LIST=$HOME/ril_s2/raw/ziplist_train.json
HO=data/held_out/held_out_repos.json
RC=data/held_out/rename_cache.json
mkdir -p "$W/logs" "$W/work" "$W/out"
cd "$W"
export PYTHONPATH="$W"
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; df -h "$HOME" | tail -1; } > "out/env_prep_${SLURM_JOB_ID}.txt"
T="$PY scripts/train.py"
[ -f work/selection_T3x.json ] || $T select "$LIST" $HO $RC work/selection_T3x.json --max 5000 --seed 0 \
  --exclude work/selection_A.json > "out/select_T3x_${SLURM_JOB_ID}.json"
[ -f work/pool_T3x.jsonl.gz ] || $T cache "$LIST" work/selection_T3x.json work/pool_T3x.jsonl.gz \
  > "out/cache_T3x_${SLURM_JOB_ID}.json"
du -sh work/pool_T3x.jsonl.gz >> "out/env_prep_${SLURM_JOB_ID}.txt"; df -h "$HOME" | tail -1 >> "out/env_prep_${SLURM_JOB_ID}.txt"
echo done
