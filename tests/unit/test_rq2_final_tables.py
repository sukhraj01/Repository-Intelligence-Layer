"""Tables and files of the RQ2 final analysis: provenance, refusals, byte-identical reruns.

The summaries here are built from synthetic rows and relabelled ``final`` only inside a temporary
directory, to exercise the table builders; nothing synthetic is written under ``results/``.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from ril.analysis import report_tables as rt
from ril.analysis import rq2_final as R
from ril.analysis import rq2_final_tables as T
from tests.unit._rq2_final_fixtures import run_table, synthetic_rows

ROOT = Path(__file__).resolve().parents[2]
FILTER = "mined_filter_bm25"


def _rows() -> list[dict[str, Any]]:
    final = synthetic_rows(
        effects={FILTER: 4.0}, seed=1, eval_set="exec377", repos=8, cells=R_CELLS
    )
    dev = synthetic_rows(effects={FILTER: 3.0}, seed=2, eval_set="dev", repos=5, cells=R_CELLS)
    return final + dev


R_CELLS = ("mined_raw", "mined_sub", FILTER)


def _final_summary() -> dict[str, Any]:
    rows = _rows()
    return R.analyse(
        rows,
        run_table(rows),
        source_kind="final",
        dev_analysis_id="E-RQ2-DEV-ANALYSIS",
        draws=300,
    )


def _write(root: Path, summary: dict[str, Any]) -> None:
    R.write_summary(summary, root / T.SUMMARY_REL)


def test_nothing_is_built_before_the_summary_exists(tmp_path: Path) -> None:
    assert T.build_if_present(tmp_path) == []
    assert T.build_if_present(ROOT) == []  # no final row exists in the repository yet


def test_four_fragments_whose_numbers_all_come_from_the_summary(tmp_path: Path) -> None:
    _write(tmp_path, _final_summary())
    tables = T.build_tables(tmp_path)
    assert [t.name for t in tables] == [
        "rq2_final_arms",
        "rq2_final_confirmatory",
        "rq2_final_exploratory",
        "rq2_final_claims",
    ]
    for t in tables:
        t.check()  # raises on any digit string that was not read from the summary
        assert T.ENTRY in t.render()
        assert t.trace.sources == {T.SUMMARY_REL}


def test_confirmatory_rows_show_both_intervals_the_reading_and_distinct_directories(
    tmp_path: Path,
) -> None:
    summary = _final_summary()
    _write(tmp_path, summary)
    conf = next(t for t in T.build_tables(tmp_path) if t.name == "rq2_final_confirmatory")
    rows = [r for r in conf.rows if r]
    assert len(rows) == 4 + 4  # four contrasts on each of the two sets
    assert all("3200 / 3200" in r[-1] for r in rows)
    assert any("reported effect" in r[-2] for r in rows)
    first = next(r for r in rows if "exec377" in r[0] and r[2] == "L2" and r[1].endswith("raw"))
    c = next(
        x
        for x in summary["contrasts"]
        if x["eval_set"] == "exec377"
        and x["level"] == "L2"
        and x["reference"] == "mined_raw"
        and x["arm"] == FILTER
        and x["primary"]
    )
    lo, hi = c["holm"]["ci"]
    assert f"{lo:.1f}".replace("-", "$-$") in first[3]
    assert f"{c['ci_uncorrected'][0]:.1f}".replace("-", "$-$") in first[4]


def test_claims_fragment_states_the_rq3_contrast(tmp_path: Path) -> None:
    _write(tmp_path, _final_summary())
    claims = next(t for t in T.build_tables(tmp_path) if t.name == "rq2_final_claims")
    last = claims.rows[-1]
    assert last[0] == "RQ3" and "arms separate" in last[2]


@pytest.mark.parametrize("kind", ["pilot", "synthetic"])
def test_only_final_summaries_reach_a_headline_table(tmp_path: Path, kind: str) -> None:
    rows = synthetic_rows(effects={FILTER: 2.0}, seed=3, repos=4, cells=R_CELLS)
    _write(tmp_path, R.analyse(rows, run_table(rows), source_kind=kind, draws=200))
    with pytest.raises(ValueError, match="cannot enter a headline table"):
        T.build_tables(tmp_path)


def test_report_tables_writes_the_fragments_and_hashes_the_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, _final_summary())
    monkeypatch.setattr(rt, "build_all", lambda root: [])
    out = tmp_path / "generated"
    tables = rt.write_all(tmp_path, out)
    assert len(tables) == 4
    assert (out / "rq2_final_arms.tex").exists()
    with open(out / "SOURCES.csv", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    digest = hashlib.sha256((tmp_path / T.SUMMARY_REL).read_bytes()).hexdigest()
    assert {(r["fragment"], r["sha256"]) for r in rows} >= {("rq2_final_claims.tex", digest)}


def _write_csvs(tmp_path: Path) -> tuple[Path, Path]:
    rows = _rows()
    rp, up = tmp_path / "rows.csv", tmp_path / "runs.csv"
    with open(rp, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=R.ROW_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r[k] is None else r[k]) for k in R.ROW_COLUMNS})
    with open(up, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=R.RUN_COLUMNS)
        w.writeheader()
        for r in run_table(rows):
            w.writerow({k: r[k] for k in R.RUN_COLUMNS})
    return rp, up


def test_file_analysis_hashes_inputs_and_reruns_byte_identical(tmp_path: Path) -> None:
    rp, up = _write_csvs(tmp_path)
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    kw: dict[str, Any] = {
        "dev_analysis_id": "E-RQ2-DEV-ANALYSIS",
        "source_kind": "final",
        "draws": 300,
    }
    sa = R.analyse_files(rp, up, a, **kw)
    R.analyse_files(rp, up, b, **kw)
    assert a.read_bytes() == b.read_bytes()
    inputs = {i["path"]: i["sha256"] for i in sa["inputs"]}
    assert inputs[str(rp)] == hashlib.sha256(rp.read_bytes()).hexdigest()
    assert inputs[str(up)] == hashlib.sha256(up.read_bytes()).hexdigest()
    assert sa["dev_analysis_entry"] == "E-RQ2-DEV-ANALYSIS"
    assert set(sa["diagnostics"]["mined_raw"]["config_hashes"].values())  # config hashes carried
    assert json.loads(a.read_text(encoding="utf-8"))["analysis_hash"] == sa["analysis_hash"]


def test_file_analysis_refuses_the_sealed_sets_without_the_id(tmp_path: Path) -> None:
    rp, up = _write_csvs(tmp_path)
    with pytest.raises(R.SealedOrderError):
        R.analyse_files(rp, up, tmp_path / "x.json", dev_analysis_id=None)


def test_command_line_wrapper(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rp, up = _write_csvs(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "rq2_analysis_cli", ROOT / "scripts" / "rq2_analysis.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with pytest.raises(R.SealedOrderError):
        mod.main([str(rp), str(up), str(tmp_path / "o.json")])
    code = mod.main(
        [
            str(rp),
            str(up),
            str(tmp_path / "o.json"),
            "--source-kind",
            "synthetic",
            "--draws",
            "200",
            "--dev-analysis-id",
            "E-STORED-ANALYSIS",
        ]
    )
    assert code == 0 and (tmp_path / "o.json").exists()
    assert "contrasts" in capsys.readouterr().out
