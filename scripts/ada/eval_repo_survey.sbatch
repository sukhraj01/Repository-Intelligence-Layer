#!/bin/bash
#SBATCH --job-name=eval_repo_survey
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=6G
#SBATCH --time=02:00:00
#SBATCH --output=ril_fp/logs/eval_repo_survey_%j.out
# CPU, read-only. Survey for the evaluation-repository inventory (E-EVAL-REPOS): the stored unit records and
# dense stores per repository, the pool and mining-population repositories (listing of the published pool),
# bare-clone file counts, and a language sample of the 632 L2 corpora by HTTP range requests (6 ranges of
# 48 KiB per folder, about 180 MB in all, 8 threads). Reads under ~/ril_x2 and ~/ril_s2; writes one JSON.
# Memory estimate (new step): the pool listing is 38 MB of JSON (about 0.4 GB parsed, as in the mining
# population step), the unit-text shards are only line-counted, numpy opens the 521 unit files one at a time:
# peak under 1.5 GB; 6 GB asked.
#   cd ~ && sbatch --export=ALL,IN=$HOME/ril_fp/work/survey_input.json,OUT=$HOME/ril_fp/work/survey.json ril_fp/scripts/ada/eval_repo_survey.sbatch
set -euo pipefail
W=$HOME/ril_fp
PY=$HOME/ril_x2/venv_gpu$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')/bin/python
export PYTHONPATH="$HOME/ril_x2/overlay_cre:$W"
cd "$W"
"$PY" scripts/ada/eval_repo_survey.py "${OUT:?set OUT}" "${IN:?set IN}"
