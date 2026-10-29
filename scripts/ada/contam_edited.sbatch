#!/bin/bash
#SBATCH --job-name=ril_contam_edit
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=ril_c/logs/contam_edited_%j.out
# CPU only. Edited-function follow-up of the contamination scan (E-CONTAM-EDITED): hashes of the
# functions each reference patch edits (before and after the patch), then the join with the scan hits.
# Needs ~/ril_c/work/{clones.json,verified_patches.json}, ~/ril_pc/work/verified_ref.json,
# ~/ril_c/out/instance_hashes.json.gz and ~/ril_c/out/scan/ (all from the full scan).
#   sbatch ril_c/scripts/ada/contam_edited.sbatch      (submit from $HOME)
set -euo pipefail
cd "$HOME/ril_c"
PY="$HOME/ril_e/venv_ril310/bin/python"
"$PY" -I scripts/ada/contam_probe.py edited "$HOME/ril_pc/work/verified_ref.json" work/clones.json work/verified_patches.json out/edited_functions.json.gz
"$PY" -I scripts/ada/contam_probe.py edited-tables work/x4_contam_scan.yaml out/instance_hashes.json.gz out/edited_functions.json.gz out/scan out/x5_edited_tables.json
