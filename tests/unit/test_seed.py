"""Unit tests for ril.util.seed."""

import random

import numpy as np
import pytest

from ril.util.seed import set_seed


def test_set_seed_is_deterministic() -> None:
    set_seed(7)
    a = (random.random(), float(np.random.rand()))
    set_seed(7)
    b = (random.random(), float(np.random.rand()))
    assert a == b


def test_different_seeds_differ() -> None:
    set_seed(1)
    a = random.random()
    set_seed(2)
    assert a != random.random()


def test_negative_seed_rejected() -> None:
    with pytest.raises(ValueError):
        set_seed(-1)
