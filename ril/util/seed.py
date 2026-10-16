"""Seeding for deterministic runs.

Implements the determinism requirement: every entry point takes ``--seed``; same code, data and seed
give the same results.
"""

from __future__ import annotations

import os
import random

import numpy as np


def set_seed(seed: int) -> None:
    """Seed Python's and NumPy's global generators.

    ``PYTHONHASHSEED`` is also exported so subprocesses inherit stable hashing; it does not
    change hashing in the current interpreter, which is fixed at start-up.
    """
    if seed < 0:
        raise ValueError("seed must be non-negative")
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
