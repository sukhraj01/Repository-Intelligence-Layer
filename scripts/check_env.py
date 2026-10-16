"""Thin wrapper: verify the Python version and numpy arithmetic (used by `make setup`)."""

from __future__ import annotations

from ril.util.log import get_logger
from ril.util.sanity import run_all

if __name__ == "__main__":
    run_all()
    get_logger("check_env").info("environment sanity check passed")
