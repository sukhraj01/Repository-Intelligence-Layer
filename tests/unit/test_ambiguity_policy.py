"""Receiver evidence and the reader-side policies for ambiguous invoke sites (Q35, Q36)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ril.parsing.ambiguity_policy import (
    POLICIES,
    AmbiguousSite,
    ambiguous_sites,
    evidence_counts,
    keeps,
    policy_pairs,
)
from ril.parsing.call_graph import GraphBuilder
from ril.parsing.repository_parser import parse_repository

FILES = {
    "pkg/__init__.py": "",
    "pkg/a.py": (
        "import socket\n"
        "from typing import Optional, Dict\n\n"
        "class Store:\n"
        "    def get(self, k):\n        return k\n\n"
        "    def close(self):\n        return 1\n\n"
        "class Other:\n"
        "    def get(self, k):\n        return k\n\n"
        "def f(cfg, **kwargs):\n"
        "    d = {}\n"
        "    d.get(1)\n"
        "    kwargs = kwargs or {}\n"
        "    kwargs.get('x')\n"
        "    cfg.get(2)\n\n"
        "def g(sock: Optional[socket.socket], m: Dict[str, int]):\n"
        "    sock.close()\n"
        "    m.get('k')\n\n"
        "class Holder:\n"
        "    def __init__(self):\n"
        "        self.items = []\n"
        "        self.later = None\n\n"
        "    def use(self):\n"
        "        self.items.get(0)\n"
        "        self.later.get(0)\n"
    ),
    "tests/test_a.py": (
        "def test_one(client):\n    client.get('/')\n\ndef helper(client):\n    client.get('/')\n"
    ),
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for rel, text in FILES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return tmp_path


def _sites(repo: Path) -> dict[str, AmbiguousSite]:
    parsed = parse_repository(str(repo), "acme/amb")
    graph = GraphBuilder(parsed).build()
    return {f"{s.site}|{s.target_text}": s for s in ambiguous_sites(parsed, graph)}


def _by_text(sites: dict[str, AmbiguousSite], path: str, text: str, line: int) -> AmbiguousSite:
    hits = [
        s for k, s in sites.items() if s.site.startswith(f"{path}:{line}:") and k.endswith(text)
    ]
    assert len(hits) == 1, (text, line, sorted(sites))
    return hits[0]


def test_receiver_evidence_kinds(repo: Path) -> None:
    sites = _sites(repo)
    assert _by_text(sites, "pkg/a.py", "kwargs.get", 19).evidence == ("kwargs",)
    assert _by_text(sites, "pkg/a.py", "cfg.get", 20).evidence == ()
    assert _by_text(sites, "pkg/a.py", "m.get", 24).evidence == ("annotated_external",)
    assert _by_text(sites, "pkg/a.py", "self.items.get", 32).evidence == ("literal",)
    # a None placeholder is not evidence
    assert _by_text(sites, "pkg/a.py", "self.later.get", 33).evidence == ()
    # a test function's parameter is a fixture; a helper's parameter is not
    assert _by_text(sites, "tests/test_a.py", "client.get", 2).evidence == ("fixture_param",)
    assert _by_text(sites, "tests/test_a.py", "client.get", 5).evidence == ()


def test_evidence_only_on_sites_the_resolver_left_ambiguous(repo: Path) -> None:
    sites = _sites(repo)
    # ``d = {}`` is read as a builtin receiver by the resolver itself: external, not ambiguous
    assert not [s for s in sites.values() if s.target_text == "d.get"]
    # an ``Optional[...]`` annotation is not unwrapped by the resolver; the evidence rule reads it
    assert _by_text(sites, "pkg/a.py", "sock.close", 23).evidence == ("annotated_external",)


def test_policies() -> None:
    small = AmbiguousSite("a", "p:1:0", "x.get", "r", ("b", "c"), ())
    big = AmbiguousSite("a", "p:2:0", "x.run", "r", ("b", "c", "d", "e"), ())
    lit = AmbiguousSite("a", "p:3:0", "y.get", "r", ("a", "f"), ("literal",))
    sites = [small, big, lit]
    assert policy_pairs(sites, "drop") == set()
    assert policy_pairs(sites, "keep") == {
        ("a", "b"),
        ("a", "c"),
        ("a", "d"),
        ("a", "e"),
        ("a", "f"),
    }  # the self pair (a, a) is never an edge
    assert policy_pairs(sites, "rebucket") == {("a", "b"), ("a", "c"), ("a", "d"), ("a", "e")}
    assert policy_pairs(sites, "max3") == {("a", "b"), ("a", "c"), ("a", "f")}
    assert [keeps(lit, p) for p in POLICIES] == [True, False, False, True]
    with pytest.raises(ValueError):
        keeps(small, "sometimes")
    counts = evidence_counts(sites)
    assert counts["sites"] == 3 and counts["any_evidence"] == 1 and counts["size_gt_3"] == 1
