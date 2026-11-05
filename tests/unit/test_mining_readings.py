"""The labelled readings of the mined data: the pool-aligned view (decision D95)."""

from __future__ import annotations

import ast
import json
import os
import sysconfig
import textwrap

import pytest

from ril.data_mining import readings
from ril.data_mining.miner import MinedInstance
from ril.data_mining.pack import instance_bytes, pack_zip
from ril.data_mining.readings import NON_TEST, POOL_ALIGNED, UNRESTRICTED
from ril.data_mining.store import MiningStore
from ril.parsing.repository_parser import parse_repository
from ril.parsing.unit_id import id_to_pool


def test_async_rows_are_recognised_with_decorators_and_methods() -> None:
    assert readings.is_async_row("a.py/f\nasync def f():\n    pass")
    assert not readings.is_async_row("a.py/f\ndef f():\n    pass")
    assert readings.is_async_row(
        "a.py/C/m\n    @staticmethod\n    @x(1,\n      2)\n    async def m():\n        pass"
    )
    assert not readings.is_async_row("a.py/C/m\n    @x\n    def m():\n        return 'async def'")
    assert not readings.is_async_row("a.py/f\ndef f():\n    async def inner(): pass")


def test_async_detection_agrees_with_the_syntax_tree_on_real_code() -> None:
    root = os.path.join(sysconfig.get_paths()["stdlib"], "asyncio")
    units = [
        u
        for u in parse_repository(root, "py/asyncio").units
        if u.unit_type in ("function", "method")
    ]
    assert len(units) > 200
    n_async = 0
    for u in units:
        node = ast.parse(textwrap.dedent(u.source)).body[0]
        truth = isinstance(node, ast.AsyncFunctionDef)
        n_async += truth
        assert readings.is_async_row(f"{id_to_pool(u.id)}\n{u.source}") is truth, u.id
    assert n_async > 20  # the check is not vacuous


def test_path_rule_is_a_case_insensitive_substring() -> None:
    assert readings.has_test_substring("pkg/tests/x.py/f")
    assert readings.has_test_substring("pkg/latest.py/f")  # the released rule is a substring
    assert readings.has_test_substring("pkg/TestUtil.py/C/m")
    assert not readings.has_test_substring("pkg/core.py/f")


def _row(pid: str, source: str) -> tuple[str, str]:
    return pid, f"{pid}\n{source}"


def _positive(pid: str, removed: int, inserted: int = 0, in_corpus: bool = True) -> dict:
    return {
        "pool_id": pid,
        "removed_lines": removed,
        "inserted_lines": inserted,
        "in_corpus": in_corpus,
    }


def _write(tmp_path) -> MiningStore:
    store = MiningStore(str(tmp_path / "run"))
    corpus = [
        _row("pkg/core.py/edited", "def edited():\n    return 1"),
        _row("pkg/core.py/grown", "def grown():\n    return 2"),
        _row("pkg/core.py/coro", "async def coro():\n    return 3"),
        _row("pkg/latest.py/f", "def f():\n    return 4"),
        _row("pkg/tests/t.py/test_x", "def test_x():\n    pass"),
        _row("pkg/core.py/other", "def other():\n    return 5"),
    ]
    positives = [
        "pkg/core.py/edited",
        "pkg/core.py/grown",
        "pkg/core.py/coro",
        "pkg/latest.py/f",
        "pkg/tests/t.py/test_x",
    ]
    meta = {
        "repo": "acme/widgets",
        "pr": 1,
        "counters": {"positives": 5},
        "positives": [
            _positive("pkg/core.py/edited", 2),
            _positive("pkg/core.py/grown", 0, 3),  # received inserted lines only
            _positive("pkg/core.py/coro", 1),
            _positive("pkg/latest.py/f", 1),
            _positive("pkg/tests/t.py/test_x", 1),
            _positive("pkg/core.py/SideClass", 4, in_corpus=False),
        ],
    }
    store.write_instance(
        MinedInstance(
            "acme/widgets", 1, "acme__widgets-1", "q", "m" * 40, corpus, sorted(positives), meta
        )
    )
    only_async = {**meta, "pr": 2, "positives": [_positive("pkg/core.py/coro", 1)]}
    store.write_instance(
        MinedInstance(
            "acme/widgets",
            2,
            "acme__widgets-2",
            "q",
            "m" * 40,
            corpus,
            ["pkg/core.py/coro"],
            only_async,
        )
    )
    return store


def _ids(blob: bytes) -> list[str]:
    return [json.loads(line)["_id"] for line in blob.splitlines() if line.strip()]


def test_the_three_readings_of_one_directory(tmp_path) -> None:
    base = _write(tmp_path).pr_path("acme__widgets-1")
    corpus, qrels = instance_bytes(base, UNRESTRICTED)  # type: ignore[misc]
    assert len(_ids(corpus)) == 6 and qrels.decode().count("\t1\n") == 5
    corpus, qrels = instance_bytes(base, NON_TEST)  # type: ignore[misc]
    assert "pkg/tests/t.py/test_x" not in _ids(corpus) and "pkg/core.py/coro" in _ids(corpus)
    assert "test_x" not in qrels.decode() and "coro" in qrels.decode()
    corpus, qrels = instance_bytes(base, POOL_ALIGNED)  # type: ignore[misc]
    assert _ids(corpus) == ["pkg/core.py/edited", "pkg/core.py/grown", "pkg/core.py/other"]
    lines = qrels.decode().splitlines()
    assert lines[0] == "query-id\tcorpus-id\tscore"
    assert [x.split("\t")[1] for x in lines[1:]] == ["pkg/core.py/edited"]


def test_a_directory_left_without_a_positive_is_dropped(tmp_path) -> None:
    store = _write(tmp_path)
    assert instance_bytes(store.pr_path("acme__widgets-2"), NON_TEST) is not None
    assert instance_bytes(store.pr_path("acme__widgets-2"), POOL_ALIGNED) is None
    zpath = str(tmp_path / "z.zip")
    assert pack_zip(store.root, zpath, reading=POOL_ALIGNED) == 1
    assert pack_zip(store.root, zpath, reading=UNRESTRICTED) == 2


def test_the_view_does_not_touch_the_run_root(tmp_path) -> None:
    from ril.data_mining.cas import directory_digest

    store = _write(tmp_path)
    before = directory_digest(store.root)
    pack_zip(store.root, str(tmp_path / "z.zip"), reading=POOL_ALIGNED)
    assert directory_digest(store.root) == before


def test_an_unknown_reading_and_a_positive_without_a_meta_row_are_errors(tmp_path) -> None:
    with pytest.raises(ValueError):
        readings.check_reading("pool-aligned")
    corpus = b'{"_id":"a.py/f","text":"a.py/f\\ndef f(): pass"}\n'
    qrels = b"query-id\tcorpus-id\tscore\nq\ta.py/f\t1\n"
    with pytest.raises(ValueError):
        readings.apply(POOL_ALIGNED, corpus, qrels, {"positives": []})
    assert readings.DEFAULT_READING == POOL_ALIGNED
