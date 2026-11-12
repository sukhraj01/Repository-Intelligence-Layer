"""Retention round trip: a retained model folder against the finished run's final folder.

  rq2_retention_roundtrip.py RETAINED_FOLDER FINAL_FOLDER OUT [--device cuda]

Checks the manifest against the files, loads the retained model, encodes a fixed handful of code
snippets with it and with the final folder written by the same run, and reports the largest
difference. Both are float16 under ``checkpoint.final_dtype``, so the vectors should be equal.
Prints and writes one JSON document. Logic is small enough to stay here (a smoke check).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.training import retention as rt  # noqa: E402

SNIPPETS = [
    "def add(a, b):\n    return a + b\n",
    "class Stack:\n    def push(self, x):\n        self.items.append(x)\n",
    "def read_config(path):\n    with open(path) as f:\n        return json.load(f)\n",
    "def parse_args(argv):\n    p = argparse.ArgumentParser()\n    return p.parse_args(argv)\n",
    "async def fetch(url):\n    return await client.get(url)\n",
]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("retained")
    p.add_argument("final")
    p.add_argument("out")
    p.add_argument("--device", default="cuda")
    a = p.parse_args()
    import numpy as np

    from ril.retrieval.dense_encoder import ENCODERS, DenseEncoder

    problems = rt.verify_retained(a.retained)
    spec = ENCODERS["coderankembed"].with_max_tokens(512)
    dtype = "float16" if a.device.startswith("cuda") else "float32"
    retained_model = str(Path(a.retained) / rt.MODEL_SUBDIR)
    ra = {r["path"]: r["sha256"] for r in rt.tree_files(retained_model)}
    rb = {r["path"]: r["sha256"] for r in rt.tree_files(a.final)}
    files_equal = ra == rb
    differing = sorted(k for k in set(ra) | set(rb) if ra.get(k) != rb.get(k))
    vecs = []
    again = None
    for i, folder in enumerate((retained_model, a.final)):
        enc = DenseEncoder.load(spec, device=a.device, dtype=dtype, local_dir=folder)
        vecs.append(np.asarray(enc.encode_documents(SNIPPETS, 8), dtype=np.float32))
        if i == 0:  # the same model twice: run-to-run difference of the encoder itself
            again = np.asarray(enc.encode_documents(SNIPPETS, 8), dtype=np.float32)
    assert again is not None
    self_diff = float(np.abs(vecs[0] - again).max())
    diff = float(np.abs(vecs[0] - vecs[1]).max())
    cos = [
        float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y)))
        for x, y in zip(vecs[0], vecs[1], strict=True)
    ]
    out = {
        "manifest_problems": problems,
        "snippets": len(SNIPPETS),
        "max_abs_difference": diff,
        "min_cosine": min(cos),
        "equal": diff == 0.0,
        "files_equal": files_equal,
        "files_differing": differing,
        "same_model_twice_max_abs_difference": self_diff,
        "retained": a.retained,
    }
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return 0 if not problems and (files_equal or diff < 1e-3) else 1


if __name__ == "__main__":
    raise SystemExit(main())
