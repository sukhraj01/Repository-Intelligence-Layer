#!/bin/bash
#SBATCH --job-name=t1_tests
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=ril_t1/logs/t1_tests_%j.out
# CPU only. The torch tests of the training stack (tiny model end to end with resumption and the
# evaluation hook, reproducibility, the arms-identity gate, the loss, the throughput measurement)
# and the leakage tests, on Ada: the local machine runs no torch (Makefile header). Memory estimate:
# torch import about 0.4 GB plus a 512x16 tiny model on synthetic data, under 1.5 GB peak (4 GB asked).
# Uses ~/ril_x2/venv_gpu310 (torch 2.4.1) and adds pytest, pyyaml and pystemmer once as a --target
# overlay. Submit after rsync -a --exclude __pycache__ ril scripts configs tests pyproject.toml data/held_out results/tables ada:ril_t1/
#   sbatch --export=ALL,RIL_COMMIT=<hash> ril_t1/scripts/ada/t1_tests.sbatch
set -euo pipefail
W=$HOME/ril_t1
PY=$HOME/ril_x2/venv_gpu$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')/bin/python
OV=$W/overlay_test
cd "$W"
mkdir -p logs out
[ -d "$OV/_pytest" ] || "$PY" -m pip install --no-cache-dir -q --target "$OV" pytest pyyaml pystemmer
export PYTHONPATH="$W:$OV:$HOME/ril_x2/overlay_cre"
/usr/bin/time -v "$PY" -m pytest -q -p no:cacheprovider -p no:xdist -rs \
  tests/unit/test_contrastive_loss.py tests/unit/test_arms_only_differ_through_hooks.py \
  tests/unit/test_train_measure.py tests/integration/test_training_end_to_end.py tests/integration/test_run_batch.py \
  tests/reproducibility/test_training_repro.py tests/leakage \
  > "out/tests_${SLURM_JOB_ID}.txt" 2> "out/tests_${SLURM_JOB_ID}.time"
echo done
