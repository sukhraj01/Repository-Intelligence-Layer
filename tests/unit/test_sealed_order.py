"""One guard for the sealed final sets: every reader calls it, none carries its own copy (D100)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from ril.analysis import rq2_final as R
from ril.evaluation import final_rows as fr
from ril.evaluation import final_sets as fs
from ril.evaluation import sealed

ROOT = Path(__file__).resolve().parents[2]


class _Spy:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    def __call__(self, entry_id: str | None, docs_root: Path | None = None) -> str:
        self.calls.append(entry_id)
        raise sealed.SealedOrderError("spy: stop here")


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> _Spy:
    s = _Spy()
    monkeypatch.setattr(sealed, "require_dev_analysis", s)
    return s


def test_the_analysis_module_calls_the_shared_guard(spy: _Spy, tmp_path: Path) -> None:
    with pytest.raises(sealed.SealedOrderError):
        R.check_sealed({"exec377"}, "E-X-1", None)
    with pytest.raises(sealed.SealedOrderError):
        R.require_dev_analysis("E-X-1")
    rows = tmp_path / "r.csv"
    rows.write_text(",".join(R.ROW_COLUMNS) + "\n" + "r,c,1,eight,L2,o/r,q,,0.5,0.5\n")
    with pytest.raises(sealed.SealedOrderError):
        R.read_rows(rows, dev_analysis_id="E-X-1")
    with pytest.raises(sealed.SealedOrderError):
        R.analyse(
            [
                {
                    "run_id": "r",
                    "cell": "c",
                    "seed": 1,
                    "eval_set": "exec377",
                    "level": "L2",
                    "repo": "o/r",
                    "query_id": "q",
                    "n_positives": None,
                    "ndcg10": 0.5,
                    "recall100": 0.5,
                }
            ],
            [],
            source_kind="synthetic",
            dev_analysis_id="E-X-1",
        )
    assert len(spy.calls) == 4


def test_the_final_sets_scoring_and_the_converter_call_the_shared_guard(
    spy: _Spy, tmp_path: Path
) -> None:
    with pytest.raises(fs.FinalSetsRefused):
        fs.check_id("E-X-1")
    with pytest.raises(fs.FinalSetsRefused):
        fs.load_dev_analysis_record(str(tmp_path / "r.json"), "E-X-1", [])
    with pytest.raises(fs.FinalSetsRefused):
        fs.read_final_sets(str(tmp_path / "i.jsonl"), "E-X-1")
    with pytest.raises(sealed.SealedOrderError):
        fr.final_rows(str(tmp_path / "i.jsonl"), "E-X-1")
    assert len(spy.calls) == 4


def test_the_guards_agree_on_what_an_id_is() -> None:
    for ok in ("E-RQ2-DEV-1", "E-A1"):
        assert fs.check_id(ok) == R.require_dev_analysis(ok) == sealed.require_dev_analysis(ok)
    for bad in (None, "", "e-x", "E-", "E- x"):
        with pytest.raises(fs.FinalSetsRefused):
            fs.check_id(bad)
        with pytest.raises(R.SealedOrderError):
            R.require_dev_analysis(bad)


def test_no_other_module_carries_its_own_copy_of_the_check() -> None:
    # the entry-id pattern lives in ril/evaluation/sealed.py only
    pattern = re.compile(r"\^E-\[A-Z0-9\]")
    offenders = [
        str(p.relative_to(ROOT))
        for p in list((ROOT / "ril").rglob("*.py")) + list((ROOT / "scripts").glob("*.py"))
        if p.name != "sealed.py" and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_every_reader_of_sealed_sets_imports_the_shared_module() -> None:
    for rel in (
        "ril/analysis/rq2_final.py",
        "ril/evaluation/final_sets.py",
        "ril/evaluation/final_rows.py",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "sealed.require_dev_analysis(" in text, rel
