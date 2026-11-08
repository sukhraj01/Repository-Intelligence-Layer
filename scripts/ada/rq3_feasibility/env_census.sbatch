#!/bin/bash
#SBATCH --job-name=ril_rq3_env
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --nodelist=gnode004
#SBATCH --output=ril_rq3/logs/probe_a6_%j.out
# Part A probe 6: environment census of Verified under the install specifications; flask retry with a pinned pytest. Nothing deleted.
set -u
cd /tmp/ril_rq3 && export PATH=/tmp/ril_rq3/uv-x86_64-unknown-linux-gnu:$PATH
echo "node $(hostname) $(date -u +%FT%TZ)"
tools/bin/python ~/ril_rq3/a6_census2.py 2>&1 | tail -80
echo done
