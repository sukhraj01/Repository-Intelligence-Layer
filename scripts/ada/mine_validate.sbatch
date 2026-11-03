#!/bin/bash
#SBATCH --job-name=ril_mine_val
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --output=ril_mine/logs/validate_%j.out
# CPU only. Stage M1 after the mining run: the mined positives against the published pool's for every
# pull request in both (range requests on the pool archive), and the hand-check file for 20 seeded
# mined pull requests (20 compare requests, token needed; presence only is tested).
#   sbatch --export=ALL,RUN=m1 ril_mine/scripts/ada/mine_validate.sbatch
# Output: runs/$RUN/agreement.json, runs/$RUN/handcheck_20.md (issue text: stays on the cluster until read).
set -euo pipefail
cd "$HOME/ril_mine"
V="$HOME/ril_mine/venv_$(python3 -c 'import sys;print("%d%d" % sys.version_info[:2])')"
if [ ! -x "$V/bin/pip" ]; then python3 -m venv "$V" && "$V/bin/pip" install -q numpy pyyaml; fi
R="runs/${RUN:?set RUN}"
"$V/bin/python" -I scripts/mine_pilot.py agreement "$R" "$R/agreement.json" --listing "$HOME/ril_s2/raw/ziplist_train.json"
"$V/bin/python" -I scripts/mine_pilot.py handcheck "$R" "$R/handcheck_20.md" --n 20 --seed 0
echo done
