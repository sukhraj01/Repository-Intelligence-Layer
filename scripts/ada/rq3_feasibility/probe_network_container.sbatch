#!/bin/bash
#SBATCH --job-name=ril_rq3_probe
#SBATCH --partition=u22-cpu
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=ril_rq3/logs/probe_a1_%j.out
# Read-only probe: container runtime, user namespaces, network allowlist, Verified metadata. Work in node-local TMPDIR.
set -u
echo "== node: $(hostname) date: $(date -u +%FT%TZ)"; echo "== kernel: $(uname -r)  os: $(grep PRETTY /etc/os-release)"
echo "== id: $(id)"; echo "TMPDIR=${TMPDIR:-unset}"; df -h /tmp | tail -1
echo "== container runtimes on PATH"
for c in apptainer singularity docker podman; do printf "%s: " $c; command -v $c || echo none; done
module load u22/singularity-ce/4.2.2 2>&1 | head -2
command -v singularity && singularity --version
echo "== user namespaces"; cat /proc/sys/user/max_user_namespaces 2>&1; unshare -U -r true 2>&1 && echo "unshare -Ur ok" || echo "unshare -Ur failed"
echo "== singularity config (setuid / fakeroot)"; ls -l $(dirname $(command -v singularity))/../libexec/singularity/bin/starter-suid 2>&1 | head -2
grep -E "^(allow setuid|allow user ns|enable fakeroot|mount hostfs|sif fuse)" $(dirname $(dirname $(command -v singularity)))/etc/singularity/singularity.conf 2>&1 | head; command -v squashfuse fusermount fuse2fs 2>&1 | head
echo "== network (code, seconds)"
for u in https://pypi.org/simple/pip/ https://files.pythonhosted.org/ https://github.com https://codeload.github.com https://objects.githubusercontent.com https://github.com/astral-sh/python-build-standalone/releases https://huggingface.co https://registry-1.docker.io/v2/ https://ghcr.io/v2/ https://quay.io/v2/ https://repo.anaconda.com https://conda.anaconda.org https://astral.sh https://download.pytorch.org https://api.github.com https://index.docker.io https://auth.docker.io/token https://cloud.sylabs.io https://hub.docker.com; do
  r=$(curl -s -o /dev/null -m 20 -w "%{http_code} %{time_total}" -I "$u" 2>&1); echo "$u -> $r"; done
echo "== throughput probe (pythonhosted wheel)"
curl -s -m 60 -o /tmp/ril_probe_wheel -w "bytes=%{size_download} speed=%{speed_download} B/s time=%{time_total}\n" https://files.pythonhosted.org/packages/py3/p/pip/pip-24.0-py3-none-any.whl
rm -f /tmp/ril_probe_wheel
echo "== SWE-bench Verified metadata"
mkdir -p /tmp/ril_rq3_probe && cd /tmp/ril_rq3_probe
curl -sL -m 120 -o verified.parquet -w "http=%{http_code} bytes=%{size_download} t=%{time_total}\n" https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/resolve/main/data/test-00000-of-00001.parquet
ls -l verified.parquet; sha256sum verified.parquet
python3 -c "import pyarrow" 2>&1 | head -1
echo done
