"""Environment sanity checks run by ``make setup``.

An earlier project used a numpy built against an unsupported interpreter that silently returned
wrong array results; this compares numpy with pure Python so such an environment fails loudly.
"""

from __future__ import annotations

import sys

import numpy as np

REQUIRED_PYTHON = (3, 11)


def check_python_version() -> None:
    """Raise if the interpreter is not the pinned minor version."""
    if sys.version_info[:2] != REQUIRED_PYTHON:
        raise RuntimeError(
            f"Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]} is required, "
            f"found {sys.version_info.major}.{sys.version_info.minor}"
        )


def check_numpy_arithmetic() -> None:
    """Raise if numpy disagrees with pure Python on small integer and float computations."""
    values = list(range(1, 101))
    arr = np.array(values, dtype=np.int64)
    if int(arr.sum()) != sum(values):
        raise RuntimeError("numpy sum disagrees with pure Python")
    if int((arr * arr).sum()) != sum(v * v for v in values):
        raise RuntimeError("numpy sum of squares disagrees with pure Python")
    mat = np.arange(12, dtype=np.float64).reshape(3, 4)
    expected = [[sum(mat[i, k] * mat[j, k] for k in range(4)) for j in range(3)] for i in range(3)]
    if not np.allclose(mat @ mat.T, np.array(expected)):
        raise RuntimeError("numpy matmul disagrees with pure Python")


def run_all() -> None:
    """Run every sanity check."""
    check_python_version()
    check_numpy_arithmetic()
