"""Every subpackage imports."""

import importlib

import pytest

SUBPACKAGES = [
    "ril",
    "ril.config",
    "ril.util",
    "ril.parsing",
    "ril.retrieval",
    "ril.training",
    "ril.evaluation",
    "ril.bench",
    "ril.analysis",
]


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_import(name: str) -> None:
    assert importlib.import_module(name) is not None
