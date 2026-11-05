"""Resolver typing options (session A2b): each one changes only the sites it is meant to."""

from __future__ import annotations

from pathlib import Path

import pytest

from ril.parsing.call_graph import GraphBuilder, ResolverOptions
from ril.parsing.repo_graph import Edge
from ril.parsing.repository_parser import parse_repository

FILES = {
    "pkg/__init__.py": "",
    "pkg/models.py": (
        "class Engine:\n"
        "    def start(self):\n        return 1\n\n"
        "def make():\n    e = Engine()\n    return e\n\n"
        "def make_or_none(flag):\n    if flag:\n        return None\n    return Engine()\n\n"
        "def gen():\n    yield Engine()\n\n"
        "def either(flag):\n    if flag:\n        return Engine()\n    return Builder()\n\n"
        "class Builder:\n"
        "    def step(self):\n        return self\n\n"
        "    def finish(self):\n        return 1\n\n"
        "    @property\n    def engine(self):\n        return Engine()\n"
    ),
    "pkg/use.py": (
        "from .models import Builder, Engine, either, gen, make, make_or_none\n\n"
        "def a():\n    return make().start()\n\n"
        "def b():\n    return make_or_none(1).start()\n\n"
        "def c():\n    return gen().start()\n\n"
        "def d():\n    return Builder().step().finish()\n\n"
        "def e():\n    return Builder().engine.start()\n\n"
        "def f():\n    x = None\n    x = Engine()\n    return x.start()\n\n"
        "def g(eng=Engine()):\n    return eng.start()\n\n"
        "def h():\n    return either(1).start()\n"
    ),
}

START = "pkg/models.py::Engine.start"


def _site(root: Path, options: ResolverOptions, unit: str) -> Edge:
    parsed = parse_repository(str(root), "acme/opts")
    graph = GraphBuilder(parsed, options=options).build()
    calls = [
        e
        for e in graph.edges
        if e.type == "invoke"
        and e.src == f"pkg/use.py::{unit}"
        and e.target_text.endswith((".start", ".finish"))
    ]
    assert len(calls) == 1, calls
    return calls[0]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for rel, text in FILES.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    return tmp_path


STORED = ResolverOptions()
RETURNS = ResolverOptions(infer_returns=True)


@pytest.mark.parametrize("unit", ["a", "b", "d", "e"])
def test_inferred_returns_resolve_calls_on_call_results(repo: Path, unit: str) -> None:
    assert _site(repo, STORED, unit).status != "resolved"
    edge = _site(repo, RETURNS, unit)
    assert edge.status == "resolved"
    assert edge.dst == ("pkg/models.py::Builder.finish" if unit == "d" else START)


@pytest.mark.parametrize("unit", ["c", "h"])
def test_generators_and_disagreeing_returns_stay_unresolved(repo: Path, unit: str) -> None:
    assert _site(repo, RETURNS, unit).status != "resolved"


def test_merged_locals_take_the_one_typed_binding(repo: Path) -> None:
    assert _site(repo, STORED, "f").status != "resolved"
    edge = _site(repo, ResolverOptions(merge_locals=True), "f")
    assert (edge.status, edge.dst) == ("resolved", START)


def test_parameter_defaults_type_unannotated_parameters(repo: Path) -> None:
    assert _site(repo, STORED, "g").status != "resolved"
    edge = _site(repo, ResolverOptions(param_defaults=True), "g")
    assert (edge.status, edge.dst) == ("resolved", START)


def test_each_option_leaves_the_other_sites_alone(repo: Path) -> None:
    for options, own in (
        (ResolverOptions(merge_locals=True), {"f"}),
        (ResolverOptions(param_defaults=True), {"g"}),
    ):
        for unit in "abcdeh":
            if unit not in own:
                assert _site(repo, options, unit) == _site(repo, STORED, unit)


def test_options_label() -> None:
    assert STORED.label() == "stored"
    assert ResolverOptions(True, False, True).label() == "infer_returns+param_defaults"
