#!/bin/bash
#SBATCH --job-name=ril_rq3_egress
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=ril_rq3/logs/probe_egress_%j.out
# Reachability of the model API host from a compute node. No key is sent; a 400 or 403 means reachable.
set -u
echo "== node: $(hostname) date: $(date -u +%FT%TZ)"
for u in https://generativelanguage.googleapis.com/v1beta/models https://generativelanguage.googleapis.com/; do
  r=$(curl -s -o /dev/null -m 20 -w "%{http_code} %{time_total}" "$u" 2>&1); echo "$u -> $r"; done
