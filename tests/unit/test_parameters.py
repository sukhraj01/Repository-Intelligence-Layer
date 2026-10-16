"""Unit tests for ril.config.parameters and ril.util.sanity."""

from pathlib import Path

import pytest

from ril.config.parameters import RunConfig, load_run_config
from ril.util import sanity


def test_hash_is_stable_and_sensitive() -> None:
    assert RunConfig(seed=1).config_hash() == RunConfig(seed=1).config_hash()
    assert RunConfig(seed=1).config_hash() != RunConfig(seed=2).config_hash()


def test_load_from_yaml(tmp_path: Path) -> None:
    f = tmp_path / "c.yaml"
    f.write_text("seed: 5\nname: x\n", encoding="utf-8")
    assert load_run_config(f) == RunConfig(seed=5, name="x")


def test_unknown_key_rejected(tmp_path: Path) -> None:
    f = tmp_path / "c.yaml"
    f.write_text("bogus: 1\n", encoding="utf-8")
    with pytest.raises(TypeError):
        load_run_config(f)


def test_non_mapping_rejected(tmp_path: Path) -> None:
    f = tmp_path / "c.yaml"
    f.write_text("- 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_run_config(f)


def test_sanity_checks_pass() -> None:
    sanity.run_all()
