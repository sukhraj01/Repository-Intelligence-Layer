#!/bin/bash
#SBATCH --job-name=ril_rq3_tab
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
#SBATCH --nodelist=gnode004
#SBATCH --output=ril_rq3/logs/probe_a7_%j.out
cd /tmp/ril_rq3 && tools/bin/python ~/ril_rq3/a7_joint.py; echo done
