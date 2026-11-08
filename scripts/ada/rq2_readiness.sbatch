#!/bin/bash
#SBATCH --job-name=ril_rq2_ready
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=02:00:00
#SBATCH --exclude=gnode004,gnode044,gnode012
#SBATCH --output=ril_rdy/logs/rq2_readiness_%j.out
# CPU only. Dry run of the stages between a mined store and the RQ2 final runs, at minimal scale
# (docs/RQ2_LAUNCH_PLAN.md, part C): materialise N directories of a store, rank inputs under the
# non_test reading, BM25 ranks, feature table, held-out selection, example cache, FILTER size, the
# overlap audit on the same directories, the plan-only launcher (cells, hashes, budget, job graph) and
# the evaluation-set check. No GPU, no model, nothing deleted; everything heavy is node-local and
# only small JSON summaries land under $HOME/ril_rdy/out.
#   sbatch --export=ALL,STORE=$HOME/ril_mine/store/pilot,N=20,RIL_COMMIT=<hash> ril_rdy/scripts/ada/rq2_readiness.sbatch
set -uo pipefail
R=$HOME/ril_rdy
STORE=${STORE:?set STORE}
N=${N:-20}
PY=$HOME/ril_x2/venv_gpu310/bin/python
T=${TMPDIR:-/tmp}/ril_rdy_${SLURM_JOB_ID}
OUT=$R/out/${SLURM_JOB_ID}
HELD=$HOME/ril_mine/data/held_out/held_out_repos.json
REN=$HOME/ril_mine/data/held_out/rename_cache.json
mkdir -p "$T" "$OUT" "$R/logs"
cd "$R"
export PYTHONPATH="$R"
{ echo "host=$(hostname)"; echo "ril_commit=${RIL_COMMIT:-none}"; echo "N=$N"; df -h /tmp | tail -1; } > "$OUT/env.txt"
step() { # name, command...
  local name=$1; shift
  local t0=$(date +%s)
  "$@" > "$OUT/$name.json" 2> "$OUT/$name.err"
  local rc=$?
  echo "$name rc=$rc seconds=$(( $(date +%s) - t0 ))" | tee -a "$OUT/steps.txt"
  return 0
}
ls "$STORE/pr" | sort | head -n "$N" > "$T/names.txt"
step materialise "$PY" -I scripts/mine_pilot.py materialise "$STORE" "$T/view" --names "$T/names.txt"
step rank_prepare "$PY" -I scripts/mine_pilot.py rank-prepare "$T/view" "$T/work" --reading non_test
step rank_bm25 "$PY" -I scripts/mine_pilot.py rank-bm25 "$T/work" "$T/ranks_bm25.jsonl"
step features "$PY" -I scripts/train.py features "$T/ranks_bm25.jsonl" --out "$T/features.csv" --teachers bm25 \
  --held-out "$HELD" --rename-cache "$REN"
step select "$PY" -I scripts/train.py select "$T/work/mined.listing.json" "$HELD" "$REN" "$T/selection.json" \
  --feature-table "$T/features.csv" --seed 0
step cache "$PY" -I scripts/train.py cache "$T/work/mined.listing.json" "$T/selection.json" "$T/mined.jsonl.gz" \
  --feature-table "$T/features.csv" --form code --local
step filter_size "$PY" -I scripts/train.py filter-size "$T/mined.jsonl.gz" "$T/features.csv" --teacher bm25 --k 20
step overlap_audit "$PY" -I scripts/mine_overlap_audit.py audit "$STORE" "$HOME/ril_ov/index/v1" "$T/overlap" \
  --names-file "$T/names.txt"
step overlap_apply "$PY" -I scripts/mine_overlap_audit.py apply "$T/overlap" --floor 20
read -r FS POOL < <("$PY" -c "import json;d=json.load(open('$OUT/filter_size.json'));print(d['examples_kept'], d['examples_in'])" 2>/dev/null || echo "1 $N")
step plan "$PY" -I scripts/rq2_plan.py plan --filter-size "${FS:-1}" --pool-examples "${POOL:-$N}" --accounts A C
step eval_plan "$PY" -I scripts/rq2_plan.py eval --set \
  "dev=configs/experiments/e1_bm25_dev3.yaml:$HOME/ril_x2/prep:dev:$HOME/ril_t1/work/e3_cache" \
  "eight=configs/experiments/eval_repos_v1_build.yaml:$HOME/ril_eval/prep:test:$HOME/ril_eval/e3_cache"
for f in features.csv selection.json; do cp "$T/$f" "$OUT/$f" 2>/dev/null; done
cp "$T/overlap"/*.json "$OUT/" 2>/dev/null
rm -rf "$T"
echo done
