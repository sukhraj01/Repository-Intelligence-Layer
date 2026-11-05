#!/bin/bash
#SBATCH --job-name=ril_label_audit
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=08:00:00
#SBATCH --exclude=gnode004,gnode044
#SBATCH --output=ril_audit/logs/label_audit_%j.out
# CPU only. Label sheets of the noise audit (E-LABEL-AUDIT-SHEET): draws 400 positive-level pairs of the
# pilot mined set (non_test reading) stratified by the BM25 K = 20 cell, rebuilds the sampled directories
# from the de-duplicated store on node-local disk, fetches the compare response and pull request title
# of the sampled pull requests, maps the hunks to the edited functions with the miner's own steps, and
# writes the three sheets (OUT/sheets) and the key (KEYDIR, never shared with readers).
# Resumable: pairs_raw.jsonl in KEYDIR is appended per pull request and re-used on a resubmission.
# Needs GITHUB_TOKEN in the environment (read-only; the value is never printed or stored).
# Memory estimate: materialise peaked at 3.4 GB on the largest repository (E-MINE-STORE), parsing one
# snapshot at a time stayed inside the 12 GB of the mining jobs.
#   sbatch --export=ALL,SEED=0 ril_audit/scripts/ada/label_audit.sbatch
set -euo pipefail
A=$HOME/ril_audit
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
PY=$HOME/ril_x2/venv_gpu$PYV/bin/python
SEED=${SEED:-0}
BM25=${BM25:-$HOME/ril_mp/work/ranks_bm25.jsonl}
DENSE=${DENSE:-$HOME/ril_mine/ranks/pilot/non_test/limit300/ranks_dense.jsonl}
STORE=${STORE:-$HOME/ril_mine/store/pilot}
OUT=${OUT:-$A/out/pilot_v1}
KEYDIR=${KEYDIR:-$A/key/pilot_v1}
mkdir -p "$A/logs" "$OUT" "$KEYDIR"
cd "$A"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/ril_audit.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
export PYTHONPATH="$A"
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; df -h "$WORK" | tail -1; } | tee "$OUT/env_${SLURM_JOB_ID:-local}.txt"
$PY -I scripts/label_audit_build.py all --ranks-bm25 "$BM25" --ranks-dense "$DENSE" --store "$STORE" \
  --work "$WORK" --out "$OUT" --key-dir "$KEYDIR" --seed "$SEED"
ls -l "$OUT" "$KEYDIR"
echo done
