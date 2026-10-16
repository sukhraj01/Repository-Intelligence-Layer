"""Same seed, same draws, across repeated calls."""

import numpy as np

from ril.util.seed import set_seed


def test_numpy_stream_reproducible() -> None:
    set_seed(123)
    first = np.random.rand(16)
    set_seed(123)
    second = np.random.rand(16)
    assert first.tobytes() == second.tobytes()
