"""``neutral_paths`` rewrites home-directory prefixes in stored records and nothing else."""

from __future__ import annotations

from ril.util.portable import NEUTRAL_HOME, neutral_paths

# Synthetic login names, built so this file does not hold a home path itself.
LINUX = "/home2/" + "alice" + "/ril/results/rq2/x/2026-01-01_abcd1234"
MAC = "/Users/" + "bob" + "/work/ckpt"
WIN = "C:\\Users\\" + "carol" + "\\run"


def test_each_platform_spelling_becomes_the_token() -> None:
    assert neutral_paths(LINUX) == f"{NEUTRAL_HOME}/ril/results/rq2/x/2026-01-01_abcd1234"
    assert neutral_paths(MAC) == f"{NEUTRAL_HOME}/work/ckpt"
    assert neutral_paths(WIN) == f"{NEUTRAL_HOME}\\run"


def test_nested_structures_are_walked_and_input_is_unchanged() -> None:
    rec = {"a": [LINUX, {"b": MAC}], "n": 3, "f": 0.5, "none": None, "t": (WIN,)}
    out = neutral_paths(rec)
    assert out["a"] == [
        f"{NEUTRAL_HOME}/ril/results/rq2/x/2026-01-01_abcd1234",
        {"b": f"{NEUTRAL_HOME}/work/ckpt"},
    ]
    assert (out["n"], out["f"], out["none"]) == (3, 0.5, None)
    assert rec["a"][0] == LINUX


def test_relative_and_already_neutral_paths_pass_through() -> None:
    for text in ("results/rq2/x", "/tmp/run", NEUTRAL_HOME + "/x", "/home/user/x"):
        assert neutral_paths(text) == text.replace("/home/user", NEUTRAL_HOME)
