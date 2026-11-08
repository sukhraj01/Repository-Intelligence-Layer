#!/bin/bash
#SBATCH --job-name=rq3_units_score
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=02:00:00
#SBATCH --output=ril_rq3u/logs/rq3_units_score_%j.out
# CPU only. Dense scores of every member from the stored vectors, then the per-text check that
# every unit text has a vector (E-RQ3-UNITS, D107). No retrieval result is evaluated.
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_rq3u/scripts/ada/rq3_units_score.sbatch
set -euo pipefail
W=${RQ3U_DIR:-$HOME/ril_rq3u}
E=$HOME/ril_e
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$E/venv_ril$PYV/bin/python
cd "$W"
export PYTHONPATH="$W"
ENC=$W/enc/coderankembed__t512
$PY scripts/rq3_units.py check "$W/prep" "$ENC" "$W/out/vector_check.json"
$PY scripts/rq3_units.py score "$W/prep" "$ENC" "$W/dense_scores" --cut 512
ls "$W/dense_scores" | wc -l
du -sh "$W/dense_scores"
