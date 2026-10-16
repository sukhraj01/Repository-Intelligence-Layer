"""Filesystem locations, resolved from the repository root.

Implements docs/ARCHITECTURE.md "config". Nothing here is an absolute path: the root is found
from this file's location, so the same code runs on the local box and on the cluster. The data
root can be redirected with the ``RIL_DATA_ROOT`` environment variable (e.g. to a larger volume).
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_ROOT_ENV = "RIL_DATA_ROOT"


def repo_root() -> Path:
    """Return the repository root (the directory that contains ``ril/``)."""
    return Path(__file__).resolve().parents[2]


def data_root() -> Path:
    """Return the data directory: ``$RIL_DATA_ROOT`` if set, else ``<repo>/data``."""
    override = os.environ.get(DATA_ROOT_ENV)
    return Path(override).expanduser().resolve() if override else repo_root() / "data"


def configs_dir() -> Path:
    """Return ``<repo>/configs``."""
    return repo_root() / "configs"


def results_dir() -> Path:
    """Return ``<repo>/results``."""
    return repo_root() / "results"


def raw_dir() -> Path:
    """Return the directory for untouched downloaded data."""
    return data_root() / "raw"


def processed_dir() -> Path:
    """Return the directory for derived data."""
    return data_root() / "processed"


def index_dir() -> Path:
    """Return the directory for per-repository indexes."""
    return data_root() / "index"
