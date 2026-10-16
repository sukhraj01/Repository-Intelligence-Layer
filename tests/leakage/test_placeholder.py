"""Placeholder for the leakage suite.

The repository-disjointness and patch-text checks land with the held-out repository list; this
keeps the directory collected so `make test-all` exercises it from the start.
"""

from pathlib import Path


def test_leakage_directory_collected() -> None:
    assert Path(__file__).parent.name == "leakage"
