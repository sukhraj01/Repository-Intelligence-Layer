"""Dense-teacher cost measurement (D125): time a seeded sample, project over the whole cache.

  rq2_teacher_measure.py CACHE OUT --teacher NAME [--n 100] [--seed 0] [--cut 1024]
                         [--batch-size 64] [--device cuda]

Prints and writes one JSON document. Logic in ``ril/training/teacher_measure.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.training import teacher_measure as tm  # noqa: E402
from ril.training.pool_reader import read_cache  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cache")
    p.add_argument("out")
    p.add_argument("--teacher", required=True)
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--cut", type=int, default=1024)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--device", default="cuda")
    a = p.parse_args()
    from ril.retrieval.dense_encoder import ENCODERS, DenseEncoder, local_snapshot

    gate = None
    if a.device.startswith("cuda"):
        from ril.util.gpu import cuda_gate

        gate = cuda_gate()
    examples = read_cache(a.cache)
    sample = tm.sample_examples(examples, a.n, a.seed)
    spec = ENCODERS[a.teacher].with_max_tokens(a.cut)
    enc = DenseEncoder.load(
        spec,
        device=a.device,
        dtype="float16" if a.device.startswith("cuda") else "float32",
        local_dir=local_snapshot(spec),
    )
    sync = lambda: None  # noqa: E731
    if a.device.startswith("cuda"):
        import torch

        sync = torch.cuda.synchronize
    out = tm.measure(examples, sample, enc, batch_size=a.batch_size, sync=sync)
    out.update(teacher=a.teacher, seed=a.seed, cut=a.cut, batch_size=a.batch_size, cuda_gate=gate)
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(
        json.dumps({k: v for k, v in out.items() if k != "per_directory"}, indent=1, sort_keys=True)
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
