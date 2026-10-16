"""Unit tests for ril.config.paths."""

from pathlib import Path

import pytest

from ril.config import paths


def test_repo_root_contains_package() -> None:
    assert (paths.repo_root() / "ril" / "__init__.py").is_file()


def test_data_root_default_is_under_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(paths.DATA_ROOT_ENV, raising=False)
    assert paths.data_root() == paths.repo_root() / "data"
    assert paths.raw_dir() == paths.repo_root() / "data" / "raw"


def test_data_root_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(paths.DATA_ROOT_ENV, str(tmp_path))
    assert paths.index_dir() == tmp_path.resolve() / "index"
