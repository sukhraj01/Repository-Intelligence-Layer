"""Context assembly is byte-identical for the same ranked list (specs/assembly.md, ADR-014)."""

from __future__ import annotations

import shutil
from pathlib import Path

from ril.assembly.assemble import Candidate, assemble
from ril.assembly.config import AssemblyConfig
from ril.assembly.measure import snapshot_units
from ril.assembly.snapshot import snapshot_from_units
from ril.assembly.tokens import ApproxTokenizer
from ril.parsing.build import BuildConfig, build_repository

FILES = {
    "pkg/a.py": (
        "def alpha(x):\n    return x + 1\n\n\n"
        "class K:\n    '''doc'''\n\n    def beta(self):\n        return 2\n"
    ),
    "pkg/b.py": "def gamma():\n    return 3\n\n\ndef delta(y):\n    return gamma() + y\n",
}


def _tree(root: Path) -> str:
    for rel, text in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return str(root)


def test_same_list_gives_same_bytes_across_independent_builds(tmp_path: Path) -> None:
    tok = ApproxTokenizer()
    outs = []
    for name in ("one", "two"):
        root = _tree(tmp_path / name)
        units = snapshot_units(root, "o/r")
        ids = [u.unit_id for u in units][::-1]
        outs.append(
            assemble(
                [Candidate(i, 1.0) for i in ids],
                {u.unit_id: u for u in units},
                AssemblyConfig(budget=400, max_unit_tokens=64),
                tok,
            )
        )
        shutil.rmtree(root)
    assert outs[0].context == outs[1].context
    assert outs[0].manifest.to_json() == outs[1].manifest.to_json()


def test_scores_and_stage_labels_do_not_change_the_bytes(tmp_path: Path) -> None:
    tok = ApproxTokenizer()
    units = snapshot_units(_tree(tmp_path / "t"), "o/r")
    snap = {u.unit_id: u for u in units}
    ids = [u.unit_id for u in units]
    cfg = AssemblyConfig(budget=600)
    arm_a = assemble([Candidate(i, 9.0 - k, ("bm25",)) for k, i in enumerate(ids)], snap, cfg, tok)
    arm_b = assemble(
        [Candidate(i, 0.1 * k, ("bm25", "dense")) for k, i in enumerate(ids)], snap, cfg, tok
    )
    assert arm_a.context == arm_b.context
    assert arm_a.manifest.context_sha256 == arm_b.manifest.context_sha256


def test_snapshot_from_parsed_units_matches_the_measurement_view(tmp_path: Path) -> None:
    root = _tree(tmp_path / "s")
    result = build_repository(
        root, BuildConfig(repo_id="o/r", class_source="header", with_history=False, seed=0)
    )
    snap = snapshot_from_units(result.parsed.units)
    assert set(snap) == {u.unit_id for u in snapshot_units(root, "o/r")}
    cls = next(u for u in snap.values() if u.unit_type == "class")
    assert "return 2" not in cls.source  # the method is its own unit, not repeated in the class
