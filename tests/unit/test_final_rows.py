"""The converter from scoring results to the analysis row format (docs/RQ2_LAUNCH_PLAN.md 10.6)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from ril.analysis import rq2_final as R
from ril.analysis import rq2_final_pilot as P
from ril.evaluation import final_rows as fr
from ril.evaluation import final_sets, sealed

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
ID = "E-RQ2-DEV-1"
QCOLS = [
    "instance",
    "level",
    "repo",
    "role",
    "name",
    "units_all_nomod:ndcg10",
    "units_all_nomod:recall100",
    "units:ndcg10",
    "units:recall100",
]


def _query_csv(path: Path, variant: str, queries: list[tuple[str, str, str, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(QCOLS)
        for inst, level, repo, nd, rc in queries:
            w.writerow([inst, level, repo, "test", "bm25", 0.9, 0.9, 0.9, 0.9])  # never read
            w.writerow([inst, level, repo, "test", f"dense:{variant}", nd, rc, 0.1, 0.1])


def _final_result(tmp_path: Path, follows: str = ID) -> str:
    """A synthetic final-sets result: two runs, the eight and two parts of the executable 377."""
    index = tmp_path / "final" / final_sets.INDEX_NAME
    index.parent.mkdir(parents=True)
    lines = []
    for run_id in ("mined_raw_u100_s100", "mined_filter_bm25_u100_s100"):
        for spec, part, qs in (
            (
                "eight",
                "eight",
                [
                    ("org__a-1", "L2", "org/a", "0.5", "0.75"),
                    ("org__a-2", "L2", "org/a", "0.25", ""),
                ],
            ),
            (
                "exec377",
                "built337",
                [
                    ("django__django-1", "L2", "django/django", "0.4", "0.6"),
                    ("django__django-1", "L3", "django/django", "0.3", "0.5"),
                ],
            ),
            ("exec377", "stored36", [("sympy__sympy-9", "L2", "sympy/sympy", "0.15", "0.2")]),
        ):
            rd = tmp_path / "final" / run_id / spec / part
            _query_csv(rd / "query_rows.csv", f"{run_id}__{spec}__{part}", qs)
            lines.append(
                {
                    "run_id": run_id,
                    "set": spec,
                    "part": part,
                    "result_dir": str(rd),
                    "follows_dev_analysis": follows,
                }
            )
    index.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    return str(index)


def test_final_rows_convert_dense_values_under_the_primary_reading(tmp_path: Path) -> None:
    rows = fr.final_rows(_final_result(tmp_path), ID)
    assert len(rows) == 2 * (1 + 2 + 1)  # the eight's second query has no gold (empty recall)
    r = next(x for x in rows if x["query_id"] == "org__a-1" and x["run_id"].startswith("mined_raw"))
    assert r == {
        "run_id": "mined_raw_u100_s100",
        "cell": "mined_raw",
        "seed": 100,
        "eval_set": "eight",
        "level": "L2",
        "repo": "org/a",
        "query_id": "org__a-1",
        "n_positives": None,
        "ndcg10": 0.5,
        "recall100": 0.75,
    }
    assert {x["eval_set"] for x in rows} == {"eight", "exec377"}
    assert {x["cell"] for x in rows} == {"mined_raw", "mined_filter_bm25"}
    assert all(x["ndcg10"] != 0.9 and x["ndcg10"] != 0.1 for x in rows)  # bm25 / other readings


def test_the_converter_refuses_without_the_dev_analysis_id_before_reading(tmp_path: Path) -> None:
    index = _final_result(tmp_path)
    for bad in (None, "", "dev analysis", "e-lower"):
        with pytest.raises(sealed.SealedOrderError):
            fr.final_rows(index, bad)
    # not even an index file is needed to be refused
    with pytest.raises(sealed.SealedOrderError):
        fr.final_rows(str(tmp_path / "nowhere.jsonl"), None)
    # an id the results did not follow, and an id not in the registry
    with pytest.raises(final_sets.FinalSetsRefused, match="follow"):
        fr.final_rows(index, "E-RQ2-DEV-2")
    with pytest.raises(sealed.SealedOrderError, match="registry"):
        fr.final_rows(index, ID, docs_root=tmp_path)


def test_missing_and_duplicate_result_files_are_errors(tmp_path: Path) -> None:
    index = _final_result(tmp_path)
    victim = next((tmp_path / "final").rglob("query_rows.csv"))
    text = victim.read_text()
    victim.unlink()
    with pytest.raises(FileNotFoundError):
        fr.final_rows(index, ID)
    victim.write_text(text + text.splitlines()[2] + "\n")
    with pytest.raises(ValueError, match="two dense rows"):
        fr.final_rows(index, ID)
    with pytest.raises(ValueError, match="not a final run id"):
        fr.parse_run_id("mined_raw")


def test_converted_rows_feed_the_analysis_and_a_sealed_set_still_needs_the_id(
    tmp_path: Path,
) -> None:
    rows = fr.final_rows(_final_result(tmp_path), ID)
    out = tmp_path / "rows.csv"
    assert fr.write_csv(str(out), fr.ROW_FIELDS, rows) == len(rows)
    with pytest.raises(R.SealedOrderError):
        R.read_rows(out)
    back = R.read_rows(out, dev_analysis_id=ID)
    assert len(back) == len(rows) and back[0]["n_positives"] is None
    panels = R.build_panels(back, intersect=True)
    assert set(panels) == {("eight", "L2"), ("exec377", "L2"), ("exec377", "L3")}
    assert set(panels[("exec377", "L3")].cells) == {"mined_raw", "mined_filter_bm25"}


def test_script_refuses_without_the_id_and_writes_rows_with_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import rq2_rows

    index = _final_result(tmp_path)
    out = tmp_path / "o.csv"
    assert rq2_rows.main(["final", "--index", index, "--out-rows", str(out)]) == 2
    assert "sealed" in capsys.readouterr().err and not out.exists()
    args = ["final", "--index", index, "--follows-dev-analysis", ID, "--out-rows", str(out)]
    assert rq2_rows.main(args) == 0 and out.exists()
    assert json.loads(capsys.readouterr().out)["rows"] == 8


def _training_result(base: Path, exp_id: str, seed: int, updates: int = 100) -> str:
    d = base / f"{exp_id}_s{seed}"
    d.mkdir(parents=True)
    rec: dict[str, Any] = {
        "training": {
            "exp_id": exp_id,
            "seed": seed,
            "config_hash": f"h{seed}",
            "budget": {
                "optimizer_updates": updates,
                "examples_seen": updates * 32,
                "unique_examples_seen": updates * 32,
                "pool_examples": 5800,
            },
        }
    }
    (d / "results.json").write_text(json.dumps(rec))
    _query_csv(
        d / "query_rows.csv",
        "v",
        [("i-1", "L2", "o/r", "0.5", "0.5"), ("i-2", "L2", "o/r", "0.2", "0.4")],
    )
    return str(d)


def test_dev_rows_read_a_training_runs_own_results(tmp_path: Path) -> None:
    dirs = [_training_result(tmp_path, "rq2f_mined_raw", s) for s in (100, 101)]
    rows, runs = fr.dev_rows(dirs)
    assert {r["run_id"] for r in runs} == {"mined_raw_u100_s100", "mined_raw_u100_s101"}
    assert all(r["eval_set"] == "dev" and r["cell"] == "mined_raw" for r in rows)
    assert runs[0]["distinct_directories_seen"] == 3200 and set(runs[0]) == set(fr.RUN_FIELDS)
    summary = R.analyse(
        rows,
        runs,
        source_kind="synthetic",
        contrasts=[],
        draws=50,
    )
    assert summary["diagnostics"]["mined_raw"]["runs"] == 2


def test_the_converter_reproduces_the_pilot_format_rows() -> None:
    # the stored pilot runs carry the same files the training jobs write: the converter and the
    # pilot reader must give the same per-query values
    base = ROOT / "results" / "rq2" / "mp_raw"
    if not base.exists():
        pytest.skip("pilot results not present")
    rows, runs = fr.dev_rows(
        str(p) for p in sorted(base.iterdir()) if (p / "results.json").exists()
    )
    pilot_rows, pilot_runs = P.pilot_inputs(str(ROOT / "results"), {"mp_raw": "mp_raw"})
    key = lambda r: (r["seed"], r["level"], r["query_id"])  # noqa: E731
    mine = {key(r): (r["repo"], r["ndcg10"], r["recall100"]) for r in rows}
    theirs = {key(r): (r["repo"], r["ndcg10"], r["recall100"]) for r in pilot_rows}
    assert mine == theirs and len(mine) > 100
    assert {(r["seed"], r["config_hash"], r["distinct_directories_seen"]) for r in runs} == {
        (r["seed"], r["config_hash"], r["distinct_directories_seen"]) for r in pilot_runs
    }
