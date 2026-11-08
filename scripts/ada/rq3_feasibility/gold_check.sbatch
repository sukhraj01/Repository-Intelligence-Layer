#!/bin/bash
#SBATCH --job-name=ril_rq3_gold
#SBATCH --nodelist=gnode004   # the node whose /tmp already holds uv and the tools venv (reuse only)
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=ril_rq3/logs/probe_a5_%j.out
# Part A probe 5 (swebench 4.1.0 pinned: 5.x no longer carries the install specifications): the cluster's container module (extracted node-locally), uv, swebench specs, Verified census,
# gold-patch checks. Work in node-local /tmp; nothing is deleted.
set -u
echo "== node $(hostname) $(date -u +%FT%TZ)"
echo "/usr/local/apps on this node:"; ls /usr/local/apps 2>&1 | head -3
echo "max_user_namespaces: $(cat /proc/sys/user/max_user_namespaces)"
mkdir -p /tmp/ril_rq3 && cd /tmp/ril_rq3
echo "== uv (resumable download)"
curl -sL -C - --retry 8 --retry-delay 5 -m 1500 -o uv.tgz -w "uv http=%{http_code} bytes=%{size_download}\n" https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz
tar xzf uv.tgz && export PATH=/tmp/ril_rq3/uv-x86_64-unknown-linux-gnu:$PATH && uv --version
mkdir -p ~/ril_rq3/data
sha256sum ~/ril_rq3/data/verified.parquet
echo "== tools venv"; date -u +%T
[ -e tools/bin/python ] || uv venv --python 3.11 tools 2>&1 | tail -1
uv pip install --python tools/bin/python pyarrow swebench==4.1.0 2>&1 | tail -4; date -u +%T
uv pip list --python tools/bin/python 2>&1 | grep -i -E "^(pyarrow|swebench) "
echo "== census + gold checks"
tools/bin/python -c "import swebench.harness.constants as C,pkgutil;print([m.name for m in pkgutil.walk_packages(C.__path__,C.__name__+'.')])"
tools/bin/python ~/ril_rq3/a2_gold.py 2>&1 | tail -150
echo done
