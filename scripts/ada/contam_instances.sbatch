#!/bin/bash
#SBATCH --job-name=ril_contam_inst
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=3G
#SBATCH --time=02:00:00
#SBATCH --output=ril_c/logs/contam_instances_%j.out
# CPU only. Hashes (syntax tree, with node counts) of the functions at each Verified instance's own
# base commit, for the restriction of corpus hits in the full contamination scan (E-CONTAM-SCAN).
# Needs the bare clones listed in ~/ril_c/work/clones.json and ~/ril_pc/work/verified_ref.json.
#   sbatch ril_c/scripts/ada/contam_instances.sbatch      (submit from $HOME)
set -euo pipefail
cd "$HOME/ril_c"
python3 -I scripts/ada/contam_probe.py instances "$HOME/ril_pc/work/verified_ref.json" work/clones.json out/instance_hashes.json.gz "${MIN_NODES:-20}"
