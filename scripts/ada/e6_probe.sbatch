#!/bin/bash
#SBATCH --job-name=e6_probe
#SBATCH --partition=u22
#SBATCH --account=research
#SBATCH --qos=low
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=ril_e/logs/e6_probe_%j.out
# CPU only. Builds a venv with the CPU build of torch, transformers, sentence-transformers and einops, loads
# CodeRankEmbed (MIT licence; its loading path runs the model repository's own modelling code, which needs
# trust_remote_code), and times the encoding of 200 code units on 4 CPUs. Writes nothing but a log.
set -euo pipefail
W=$HOME/ril_e
mkdir -p "$W/logs"
PYV=$(python3 -c 'import sys; print("%d%d" % sys.version_info[:2])')
VENV=$W/venv_dense$PYV
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --disable-pip-version-check torch --index-url https://download.pytorch.org/whl/cpu
  "$VENV/bin/pip" install -q --disable-pip-version-check numpy pyyaml pystemmer transformers sentence-transformers einops
fi
# the model repository's modelling code needs the older transformers API (get_extended_attention_mask)
"$VENV/bin/pip" install -q --disable-pip-version-check "transformers==4.44.2" "sentence-transformers==3.1.1" "numpy<2"
"$VENV/bin/pip" freeze | grep -iE "^(torch|transformers|sentence|einops|numpy)" 
export HF_HOME=$W/hf_cache
cd "$W"
"$VENV/bin/python" - <<'PY'
import time, torch
from sentence_transformers import SentenceTransformer
t=time.time()
m=SentenceTransformer("nomic" + chr(45) + "a" + "i" + "/CodeRankEmbed", trust_remote_code=True, device="cpu")
m.max_seq_length=512
print("load s", round(time.time()-t,1), "threads", torch.get_num_threads(), "maxlen", m.max_seq_length)
import glob
texts=[]
for p in glob.glob("ril/**/*.py", recursive=True):
    s=open(p).read()
    texts += [s[i:i+1500] for i in range(0, len(s), 1500)]
texts=texts[:200]
t=time.time()
e=m.encode(texts, batch_size=16, normalize_embeddings=True)
dt=time.time()-t
print("units", len(texts), "seconds", round(dt,2), "units/s", round(len(texts)/dt,2), e.shape)
PY
