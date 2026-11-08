"""E-ASSEMBLY measurement and tables on synthetic inputs (specs/assembly.md, "Measurement")."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ril.analysis.assembly_tables import (
    cap_selection_rows,
    coverage_rows,
    load_rows,
    paired_rows,
    select_cap,
    summary_rows,
)
from ril.assembly.assemble import UnitText
from ril.assembly.measure import (
    MeasureSpec,
    first_stage_scores,
    measure_level,
    run_measure,
    snapshot_units,
    spec_from_config,
)
from ril.assembly.tokens import ApproxTokenizer
from ril.evaluation.e3_prepare import write_cache
from ril.evaluation.x2_eval import positions, rrf_scores

TOK = ApproxTokenizer()


def _units() -> list[UnitText]:
    out = []
    for i, f in enumerate(["a.py", "a.py", "b.py", "c.py", "c.py", "d.py"]):
        body = "\n".join(f"    v{i}_{j} = {j}" for j in range(8))
        out.append(
            UnitText(
                f"{f}::u{i}", f, 10 * i + 1, 10 * i + 9, "function", f"u{i}", f"def u{i}():\n{body}"
            )
        )
    return out


def _spec(
    budgets: tuple[int, ...] = (100, 100000), stages: tuple[str, ...] = ("bm25", "rrf")
) -> MeasureSpec:
    return MeasureSpec(
        budgets=budgets,
        max_unit_tokens=1000,
        candidates=6,
        first_stages=stages,
        dense_variant="v",
        rrf_k=10,
        readings=("units_all_nomod", "units_all"),
    )


def test_first_stage_scores() -> None:
    bm = np.asarray([0.0, 3.0, 1.0, 2.0])
    de = np.asarray([2.0, 0.0, 3.0, 1.0])
    assert first_stage_scores("bm25", bm, None, 10).tolist() == bm.tolist()
    want = rrf_scores([positions(bm), positions(de)], 10)
    assert first_stage_scores("rrf", bm, de, 10).tolist() == want.tolist()
    with pytest.raises(ValueError):
        first_stage_scores("rrf", bm, None, 10)


def test_measure_level_budget_and_gold() -> None:
    units = _units()
    bm = np.asarray([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])  # u5 first, u0 last
    arrays: dict[str, Any] = {
        "scores_L2": bm,
        "gold_L2_units_all_nomod": np.asarray([0], dtype=np.int32),
        "gold_L2_units_all": np.asarray([0, 5], dtype=np.int32),
    }
    meta = {"instance": "i1", "role": "dev", "dataset": "d", "folder": "f", "repo_id": "o/r"}
    rows = measure_level(meta, "L2", arrays, bm[::-1].copy(), units, _spec(), TOK)
    assert len(rows) == 2 * 2 * 2  # stages x budgets x readings
    big = [r for r in rows if r["budget"] == 100000 and r["first_stage"] == "bm25"]
    assert all(
        r["files_in"] == r["n_gold_files"] and r["units_in"] == r["n_gold_units"] for r in big
    )
    small = {(r["first_stage"], r["reading"]): r for r in rows if r["budget"] == 100}
    # 100 tokens hold one block (82 plus separator) at most: the best BM25 unit u5, not gold u0
    r = small[("bm25", "units_all_nomod")]
    assert (r["units_in"], r["files_in"], r["n_included"]) == (0, 0, 1)
    r = small[("bm25", "units_all")]
    assert (r["n_gold_units"], r["units_in"], r["n_gold_files"], r["files_in"]) == (2, 1, 2, 1)
    assert all(r["tokens"] <= r["budget"] for r in rows)


def test_measure_level_without_dense_skips_rrf() -> None:
    units = _units()
    arrays: dict[str, Any] = {
        "scores_L3": np.arange(6, dtype=float),
        "gold_L3_units_all_nomod": np.asarray([1], dtype=np.int32),
        "gold_L3_units_all": np.asarray([1], dtype=np.int32),
    }
    meta = {"instance": "i1", "role": "dev", "dataset": "d", "folder": "f", "repo_id": "o/r"}
    rows = measure_level(meta, "L3", arrays, None, units, _spec(), TOK)
    assert {r["first_stage"] for r in rows} == {"bm25"}


def test_spec_requires_confirm_for_test_role() -> None:
    cfg: dict[str, Any] = {
        "roles": ["dev", "test"],
        "assembly": {
            "budgets": [100],
            "max_unit_tokens": 100,
            "candidates": 5,
            "first_stages": ["bm25"],
            "dense_variant": "v",
            "rrf_k": 10,
            "readings": ["units_all"],
        },
    }
    with pytest.raises(ValueError):
        spec_from_config(cfg)
    cfg["confirm"] = True
    sp, roles = spec_from_config(cfg)
    assert roles == ("dev", "test") and sp.budgets == (100,)
    cfg["assembly"]["first_stages"] = ["bogus"]
    with pytest.raises(ValueError):
        spec_from_config(cfg)


def _row(
    inst: str, repo: str, stage: str, budget: int, reading: str = "units_all", **kw: Any
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "instance": inst,
        "level": "L2",
        "role": "dev",
        "dataset": "d",
        "folder": "f",
        "repo_id": repo,
        "first_stage": stage,
        "budget": budget,
        "reading": reading,
        "n_gold_units": 2,
        "units_in": 1,
        "units_intact": 1,
        "n_gold_files": 1,
        "files_in": 1,
        "tokens": 100,
        "n_included": 4,
    }
    base.update(kw)
    return base


def test_summary_rows_means_scopes_and_exclusions() -> None:
    rows = []
    for k, (inst, repo) in enumerate([("a1", "r1"), ("a2", "r1"), ("b1", "r2"), ("b2", "r2")]):
        for b in (4000, 8000):
            rows.append(_row(inst, repo, "bm25", b, files_in=k % 2, units_in=k % 2))
            if inst != "b2":  # no fused row for one query
                rows.append(_row(inst, repo, "rrf", b, files_in=1, units_in=2))
    rows.append(_row("e1", "r1", "bm25", 4000, n_gold_units=0, n_gold_files=0))  # empty gold
    out = summary_rows(rows, seed=0)
    pick = {(r["first_stage"], r["scope"], r["budget"]): r for r in out}
    assert set(pick) == {
        ("bm25", "matched", 4000),
        ("bm25", "matched", 8000),
        ("rrf", "matched", 4000),
        ("rrf", "matched", 8000),
        ("bm25", "all", 4000),
        ("bm25", "all", 8000),
    }
    m = pick[("bm25", "matched", 4000)]
    assert m["queries"] == 3 and m["repositories"] == 2
    assert m["file_share"] == pytest.approx(100 * (0 + 1 + 0) / 3, abs=0.01)
    assert m["no_gold_file"] == pytest.approx(100 * 2 / 3, abs=0.01)
    assert pick[("bm25", "all", 4000)]["queries"] == 4  # the empty-gold query is excluded
    assert pick[("rrf", "matched", 4000)]["unit_share"] == 100.0
    assert out == summary_rows(rows, seed=0)
    assert "[" in m["file_share_cl"] and "[" in m["file_share_q"]


def _git(args: list[str], cwd: Path) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def test_run_measure_on_a_tiny_repository(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "m.py").write_text(
        "def alpha(x):\n    return x + 1\n\n\nclass K:\n    def beta(self):\n        return 2\n"
    )
    (src / "n.py").write_text("def gamma():\n    return 3\n")
    _git(["init", "-q"], src)
    _git(["add", "."], src)
    _git(["commit", "-qm", "c"], src)
    commit = _git(["rev-parse", "HEAD"], src)
    repo_cache = tmp_path / "repo_cache"
    repo_cache.mkdir()
    _git(["clone", "-q", "--bare", str(src), str(repo_cache / "o__r.git")], tmp_path)
    units = snapshot_units(str(src), "o/r")
    n = len(units)
    assert [u.unit_type for u in units if u.unit_type == "class"] and n >= 4
    cache = tmp_path / "cache"
    ids = [u.unit_id for u in units]
    gamma = ids.index(next(i for i in ids if i.endswith("gamma")))
    arrays: dict[str, Any] = {
        "scores_L2": np.arange(n, dtype=float),
        "gold_L2_units_all_nomod": np.asarray([gamma], dtype=np.int32),
        "gold_L2_units_all": np.asarray([gamma], dtype=np.int32),
    }
    meta = {
        "instance": "inst-1",
        "role": "dev",
        "dataset": "d",
        "folder": "f",
        "repo_id": "o/r",
        "base_commit": commit,
        "units": n,
        "levels": ["L2"],
        "config_hash": "h",
    }
    write_cache(str(cache / "inst-1.npz"), arrays, meta)
    dense_dir = tmp_path / "dense" / "v"
    dense_dir.mkdir(parents=True)
    np.savez(dense_dir / "inst-1.npz", dense_L2=np.arange(n, dtype=float)[::-1].copy())
    cfg: dict[str, Any] = {
        "roles": ["dev"],
        "assembly": {
            "budgets": [40, 4000],
            "max_unit_tokens": 1000,
            "candidates": 50,
            "first_stages": ["bm25", "rrf"],
            "dense_variant": "v",
            "rrf_k": 10,
            "readings": ["units_all_nomod", "units_all"],
        },
    }
    out_dir = tmp_path / "out"
    counts = run_measure(
        cfg,
        str(cache),
        str(tmp_path / "dense"),
        str(repo_cache),
        str(tmp_path / "work"),
        str(out_dir),
    )
    assert counts["measured"] == 1 and counts["failed"] == 0 and counts["failures"] == []
    rows, coverage = load_rows(str(out_dir))
    assert len(rows) == 2 * 2 * 2 and coverage[0]["has_dense"] is True
    large = [r for r in rows if r["budget"] == 4000]
    assert all(r["units_in"] == 1 and r["files_in"] == 1 for r in large)
    assert coverage_rows(coverage, rows)[0]["with_dense"] == 1
    # a second run reuses the stored file; a changed configuration remeasures
    again = run_measure(
        cfg,
        str(cache),
        str(tmp_path / "dense"),
        str(repo_cache),
        str(tmp_path / "work"),
        str(out_dir),
    )
    assert again["reused"] == 1 and again["measured"] == 0
    # the class unit is in header form: the method text is not repeated in it
    cls = next(u for u in units if u.unit_type == "class")
    assert "return 2" not in cls.source
    stored = json.loads(next((out_dir / "instances").glob("*.json")).read_text())
    assert stored["units"] == n


def test_run_measure_reports_a_unit_count_mismatch(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "m.py").write_text("def alpha():\n    return 1\n")
    _git(["init", "-q"], src)
    _git(["add", "."], src)
    _git(["commit", "-qm", "c"], src)
    commit = _git(["rev-parse", "HEAD"], src)
    (tmp_path / "repo_cache").mkdir()
    _git(["clone", "-q", "--bare", str(src), str(tmp_path / "repo_cache" / "o__r.git")], tmp_path)
    meta = {
        "instance": "inst-2",
        "role": "dev",
        "dataset": "d",
        "folder": "f",
        "repo_id": "o/r",
        "base_commit": commit,
        "units": 999,
        "levels": ["L2"],
        "config_hash": "h",
    }
    write_cache(str(tmp_path / "cache" / "inst-2.npz"), {"scores_L2": np.zeros(999)}, meta)
    cfg: dict[str, Any] = {
        "roles": ["dev"],
        "assembly": {
            "budgets": [100],
            "max_unit_tokens": 100,
            "candidates": 5,
            "first_stages": ["bm25"],
            "dense_variant": "v",
            "rrf_k": 10,
            "readings": ["units_all"],
        },
    }
    counts = run_measure(
        cfg,
        str(tmp_path / "cache"),
        str(tmp_path / "dense"),
        str(tmp_path / "repo_cache"),
        str(tmp_path / "work"),
        str(tmp_path / "out"),
    )
    assert counts["failed"] == 1 and "unit_count" in counts["failures"][0]["reason"]


# ------------------------------------------------------------------ E-ASSEMBLY-CAP (decision D103)


def test_cap_grid_changes_intact_not_inclusion_of_a_long_gold_unit() -> None:
    body = "\n".join(f"    w{j} = {j}" for j in range(150))  # about 1,270 approximate tokens
    units = [UnitText("big.py::big", "big.py", 1, 151, "function", "big", f"def big():\n{body}")]
    arrays: dict[str, Any] = {
        "scores_L2": np.asarray([1.0]),
        "gold_L2_units_all_nomod": np.asarray([0], dtype=np.int32),
        "gold_L2_units_all": np.asarray([0], dtype=np.int32),
    }
    meta = {"instance": "i1", "role": "dev", "dataset": "d", "folder": "f", "repo_id": "o/r"}
    sp = MeasureSpec(
        budgets=(4000,),
        max_unit_tokens=1000,
        candidates=1,
        first_stages=("bm25",),
        dense_variant="v",
        rrf_k=10,
        readings=("units_all_nomod",),
        caps=(500, 1000, 2000),
    )
    rows = measure_level(meta, "L2", arrays, None, units, sp, TOK)
    by_cap = {r["max_unit_tokens"]: r for r in rows}
    assert set(by_cap) == {500, 1000, 2000}
    assert all(r["units_in"] == 1 for r in rows)
    assert [by_cap[c]["units_intact"] for c in (500, 1000, 2000)] == [0, 0, 1]
    assert all(r["tokens"] <= r["budget"] for r in rows)


def test_spec_reads_the_cap_grid_and_defaults_to_one_cap() -> None:
    a: dict[str, Any] = {
        "budgets": [100],
        "max_unit_tokens": 700,
        "candidates": 5,
        "first_stages": ["bm25"],
        "dense_variant": "v",
        "rrf_k": 10,
        "readings": ["units_all"],
    }
    sp, _ = spec_from_config({"roles": ["dev"], "assembly": a})
    assert sp.unit_caps == (700,)
    a["max_unit_tokens_grid"] = [500, 1000]
    sp, _ = spec_from_config({"roles": ["dev"], "assembly": a})
    assert sp.unit_caps == (500, 1000)


def test_select_cap_takes_the_best_and_the_smaller_cap_within_one_point() -> None:
    assert select_cap({500: 30.0, 1000: 33.0, 2000: 36.0}) == 2000
    assert select_cap({500: 30.0, 1000: 35.2, 2000: 36.0}) == 1000  # 0.8 below the best
    assert select_cap({500: 35.5, 1000: 35.2, 2000: 36.0}) == 500  # all three within 1.0
    assert select_cap({500: 34.9, 1000: 35.0, 2000: 36.0}) == 1000  # exactly 1.0 ties, 500 is 1.1
    assert select_cap({500: 10.0}) == 500


def _cap_rows(delta_rrf: int = 1) -> list[dict[str, Any]]:
    rows = []
    for lvl in ("L2", "L3"):
        for inst, repo in [("a1", "r1"), ("a2", "r1"), ("b1", "r2"), ("b2", "r2")]:
            for cap in (500, 1000, 2000):
                for b in (4000, 8000, 16000):
                    for stage in ("bm25", "rrf"):
                        intact = (1 if cap == 2000 else 0) + (delta_rrf if stage == "rrf" else 0)
                        rows.append(
                            _row(
                                f"{lvl}{inst}",
                                repo,
                                stage,
                                b,
                                reading="units_all_nomod",
                                level=lvl,
                                max_unit_tokens=cap,
                                units_intact=min(intact, 2),
                                files_in=1,
                            )
                        )
    return rows


def test_cap_selection_rows_metric_cells_and_flag() -> None:
    out = cap_selection_rows(_cap_rows())
    heads = {r["max_unit_tokens"]: r for r in out if "cell" not in r}
    # intact is 0/2 or 1/2 (bm25) and 1/2 or 2/2 (rrf) of two gold units; cells at 8,000 and 16,000
    assert heads[500]["intact_share_selection_metric"] == 25.0  # mean of 0 and 50
    assert heads[2000]["intact_share_selection_metric"] == 75.0  # mean of 50 and 100
    assert heads[500]["cells"] == 8 and heads[500]["file_share_beside"] == 100.0
    assert [c for c, r in heads.items() if r["selected"]] == [2000]
    cells = [r for r in out if r.get("cell") and r["max_unit_tokens"] == 500]
    assert len(cells) == 8 and not any("B4000" in r["cell"] for r in cells)
    with pytest.raises(ValueError):
        cap_selection_rows([r for r in _cap_rows() if r["budget"] != 16000])


def test_paired_rows_difference_intervals_and_exclusion_of_zero() -> None:
    rows = paired_rows(_cap_rows(), seed=0)
    pick = {(r["level"], r["max_unit_tokens"], r["budget"], r["metric"]): r for r in rows}
    r = pick[("L2", 500, 4000, "unit_intact_share")]
    assert r["rrf_minus_bm25"] == 50.0 and r["queries"] == 4 and r["repositories"] == 2
    assert r["excludes_0_q"] is True and r["excludes_0_cl"] is True
    f = pick[("L2", 500, 4000, "file_share")]  # identical file counts under both stages
    assert f["rrf_minus_bm25"] == 0.0 and f["excludes_0_q"] is False
    assert len(rows) == 2 * 3 * 3 * 2
    assert rows == paired_rows(_cap_rows(), seed=0)
