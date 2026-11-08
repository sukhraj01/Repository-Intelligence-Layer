#!/bin/bash
#SBATCH --job-name=ril_rq3_gold
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=ril_rq3/logs/probe_a3_%j.out
# Part A probe 3: the cluster's container module (extracted node-locally), uv, swebench specs, Verified census,
# gold-patch checks. Work in node-local /tmp; nothing is deleted.
set -u
echo "== node $(hostname) $(date -u +%FT%TZ)"
echo "/usr/local/apps on this node:"; ls /usr/local/apps 2>&1 | head -3
echo "max_user_namespaces: $(cat /proc/sys/user/max_user_namespaces)"
mkdir -p /tmp/ril_rq3 && cd /tmp/ril_rq3
echo "== container module tarball, extracted node-locally"
mkdir -p sing && tar xf /data3/u22/singularity-ce-4.2.2.tar -C sing 2>&1 | tail -2
SB=/tmp/ril_rq3/sing/usr/local/apps/singularity-ce-4.2.2
ls -l $SB/bin $SB/libexec/singularity/bin 2>&1 | head -20
$SB/bin/singularity --version 2>&1 | head -2
grep -E "^(allow setuid|allow user ns|enable fakeroot|mount hostfs|sif fuse|enable overlay)" $SB/etc/singularity/singularity.conf 2>&1 | head
command -v mksquashfs unsquashfs squashfuse fusermount 2>&1 | head
echo "== try a container as the engineer (python:3.11-slim)"
export SINGULARITY_TMPDIR=/tmp/ril_rq3/stmp SINGULARITY_CACHEDIR=/tmp/ril_rq3/scache; mkdir -p $SINGULARITY_TMPDIR $SINGULARITY_CACHEDIR
timeout 900 $SB/bin/singularity pull py311.sif docker://python:3.11-slim 2>&1 | tail -6; ls -l py311.sif 2>&1 | head -1
timeout 120 $SB/bin/singularity exec py311.sif python -V 2>&1 | tail -4
echo "== uv (resumable download)"
curl -sL -C - --retry 8 --retry-delay 5 -m 1500 -o uv.tgz -w "uv http=%{http_code} bytes=%{size_download}\n" https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz
tar xzf uv.tgz && export PATH=/tmp/ril_rq3/uv-x86_64-unknown-linux-gnu:$PATH && uv --version
mkdir -p ~/ril_rq3/data
sha256sum ~/ril_rq3/data/verified.parquet
echo "== tools venv"; date -u +%T
uv venv --python 3.11 tools 2>&1 | tail -1
uv pip install --python tools/bin/python pyarrow swebench 2>&1 | tail -3; date -u +%T
uv pip list --python tools/bin/python 2>&1 | grep -i -E "^(pyarrow|swebench) "
echo "== census + gold checks"
tools/bin/python ~/ril_rq3/a2_gold.py 2>&1 | tail -150
echo done
