"""GPU capability gate and model-revision lookup shared by cluster jobs.

The gate refuses to start a GPU job unless a real CUDA matrix product agrees with the CPU result on
a card of compute capability 7.0 or more (``docs/COMPUTE.md``: one node had a card the installed
torch build cannot drive while ``torch.cuda.is_available()`` still said yes). Lives in ``util`` so
that training and evaluation jobs can both use it without the training package reaching
evaluation code (leakage check (d)).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import os
from typing import Any

Record = dict[str, Any]


def cuda_gate() -> Record:
    """Real CUDA matrix product checked against the CPU; raises if the card is unusable."""
    import torch  # type: ignore[import-not-found,unused-ignore]

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available")
    cap = torch.cuda.get_device_capability(0)
    if cap < (7, 0):
        raise RuntimeError(f"compute capability {cap} not supported by this build")
    g = torch.Generator().manual_seed(0)
    a = torch.randn(1024, 1024, generator=g)
    b = torch.randn(1024, 1024, generator=g)
    ref = a @ b
    got = (a.cuda() @ b.cuda()).cpu()
    torch.cuda.synchronize()
    err = float((got - ref).abs().max())
    if not err < 1e-2:
        raise RuntimeError(f"CUDA matmul disagrees with CPU (max abs error {err})")
    return {
        "device": torch.cuda.get_device_name(0),
        "capability": list(cap),
        "matmul_max_abs_error": err,
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
    }


def model_revision(model_id: str) -> str | None:
    """Commit of the downloaded model repository (from the Hugging Face cache refs)."""
    home = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    ref = os.path.join(home, "hub", "models--" + model_id.replace("/", "--"), "refs", "main")
    try:
        with open(ref, encoding="ascii") as handle:
            return handle.read().strip()
    except OSError:
        return None
