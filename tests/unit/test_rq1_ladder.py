"""Tests for the RQ1 ladder: sources, controls, intervals, latency selection (E-RQ1-LADDER)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from ril.analysis import rq1_ladder as lt
from ril.analysis.e3_tables import COLUMN, load_eval_dir
from ril.evaluation.e3_eval import write_eval
from ril.evaluation.e3_prepare import READINGS
from ril.evaluation.rq1_ladder import (
    EDGE_SETS,
    SOURCES,
    STAGES,
    all_keys,
    evaluate_instance,
    ladder_hash,
    spec_from_config,
)
from ril.evaluation.x2_eval import minmax

ROOT = Path(__file__).resolve().parents[2]

CFG: dict[str, Any] = {
    "roles": ["dev"],
    "graph": {
        "variant": "enc__t512",
        "k": 20,
        "alpha": 0.2,
        "seeds": 3,
        "gamma": 0.7,
        "hops": 2,
        "weight": 0.5,
        "cap": 10,
        "draws": 2,
    },
    "recency": {"lam": 0.2, "tau_days": 30},
}


def _instance(seed: int = 1, n: int = 40) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    rng = np.random.default_rng(seed)
    arrays: dict[str, Any] = {
        "scores_L2": rng.random(n),
        "scores_L3": rng.random(n),
        "file_of_unit": np.arange(n) // 5,
        "age_days": rng.random(n) * 90,
        "pairs_contain": np.asarray([[i, i + 1] for i in range(0, n - 1, 2)], dtype=np.int32),
        "pairs_invoke": np.asarray([[0, 17], [3, 29]], dtype=np.int32),
    }
    for lv in ("L2", "L3"):
        for r in READINGS:
            arrays[f"gold_{lv}_{r}"] = np.asarray([2, 31], dtype=np.int32)
    meta = {"units": n, "levels": ["L2", "L3"], "instance": f"x__y-{seed}"}
    dense = {f"dense_{lv}": rng.random(n).astype(np.float32) for lv in ("L2", "L3")}
    return arrays, meta, dense


def test_spec_refuses_any_role_but_dev() -> None:
    sp, roles = spec_from_config(CFG)
    assert roles == ("dev",) and sp.cap == 10 and sp.lam == 0.2
    for bad in (["dev", "test"], ["test"], []):
        with pytest.raises(ValueError):
            spec_from_config({**CFG, "roles": bad})


def test_key_layout_and_matched_sizes() -> None:
    arrays, meta, dense = _instance()
    sp, _ = spec_from_config(CFG)
    info, out = evaluate_instance(arrays, meta, sp, dense)
    keys = [str(k) for k in out["keys"]]
    assert keys == all_keys()
    assert keys[:2] == ["ref|bm25", "r1|dense"]
    for stage in STAGES:
        assert f"{stage}|first" in keys
        for v in EDGE_SETS:
            for src in SOURCES:
                assert f"{stage}|{src}|{v}" in keys
    assert out["metrics_L2"].shape == (len(keys), 2 * len(READINGS))
    aux = {str(k): out["aux_L2"][i] for i, k in enumerate(out["aux_keys"])}
    for stage in STAGES:
        for v in EDGE_SETS:
            sizes = {aux[f"E|{stage}|{v}|{s}"][0] for s in SOURCES}
            assert len(sizes) == 1, "every source is size-matched to the graph expansion"
    assert info["levels"]["L3"]["gold_units"] == 2


def test_alone_rows_and_first_stages_equal_their_definitions() -> None:
    arrays, meta, dense = _instance(seed=3)
    sp, _ = spec_from_config(CFG)
    _, out = evaluate_instance(arrays, meta, sp, dense)
    idx = {str(k): i for i, k in enumerate(out["keys"])}
    from ril.evaluation.x2_eval import _Scorer

    golds = {r: arrays[f"gold_L2_{r}"] for r in READINGS}
    sc = _Scorer(golds)
    d = dense["dense_L2"].astype(np.float64)
    assert out["metrics_L2"][idx["r1|dense"]].tolist() == sc.metrics(d)
    assert out["metrics_L2"][idx["ref|bm25"]].tolist() == sc.metrics(arrays["scores_L2"])
    sl = sp.alpha * minmax(arrays["scores_L2"]) + (1 - sp.alpha) * minmax(d)
    assert out["metrics_L2"][idx["s|first"]].tolist() == sc.metrics(sl)


def test_recency_with_constant_age_leaves_the_ranking() -> None:
    arrays, meta, dense = _instance(seed=4)
    arrays["age_days"] = np.zeros(40)  # prior is 1 for every unit: a constant shift
    sp, _ = spec_from_config(CFG)
    _, out = evaluate_instance(arrays, meta, sp, dense)
    idx = {str(k): i for i, k in enumerate(out["keys"])}
    assert out["metrics_L2"][idx["r|first"]].tolist() == out["metrics_L2"][idx["p|first"]].tolist()


def test_determinism_and_hash() -> None:
    arrays, meta, dense = _instance(seed=5)
    sp, _ = spec_from_config(CFG)
    _, a = evaluate_instance(arrays, meta, sp, dense)
    _, b = evaluate_instance(arrays, meta, sp, dense)
    assert np.array_equal(a["metrics_L3"], b["metrics_L3"], equal_nan=True)
    assert ladder_hash(CFG, "x") == ladder_hash(dict(CFG), "x") != ladder_hash(CFG, "y")


def _write_dir(tmp_path: Path, repos: list[str]) -> str:
    sp, _ = spec_from_config(CFG)
    out_dir = tmp_path / "eval"
    for i, repo in enumerate(repos):
        arrays, meta, dense = _instance(seed=10 + i)
        info, res = evaluate_instance(arrays, meta, sp, dense)
        info.update(
            instance=meta["instance"], role="dev", dataset="d", folder="f", repo_id=repo, units=40
        )
        write_eval(str(out_dir / f"{i}.npz"), info, res)
    return str(out_dir)


def test_tables_on_synthetic_rows(tmp_path: Path) -> None:
    out = lt.build(_write_dir(tmp_path, ["a/a", "b/b", "c/c", "d/d"]), "cre", draws=200)
    assert len(out["query_rows"]) == 4 * 2 * len(all_keys())
    prim = [r for r in out["summary"] if r["primary"] and r["key"] == "p|first"]
    assert {r["level"] for r in prim} == {"L2", "L3"}
    assert all(r["ci_kind"] == "repository-clustered" and r["df"] == 3 for r in prim)
    cmp_rows = {(r["pair"], r["level"], r["metric"], r["reading"]): r for r in out["compare"]}
    r = cmp_rows[("R2 minus R1", "L2", "ndcg10", "units_all_nomod")]
    assert r["verdict"] in {"gain", "loss", "not distinguishable"}
    assert r["t_lo"] <= r["mean"] <= r["t_hi"]
    # a difference of a key with itself is exactly zero
    tab = load_eval_dir(_write_dir(tmp_path / "again", ["a/a", "b/b", "c/c", "d/d"]))
    idx, repos = lt.level_panel(tab, "L2", lt.PRIMARY_READING)
    d = lt._vector(tab, idx, "p|first", lt.PRIMARY_READING, "ndcg10") - lt._vector(
        tab, idx, "p|first", lt.PRIMARY_READING, "ndcg10"
    )
    f = lt.interval_fields(d, repos, lt.Boot(repos, 0, 100))
    assert f["mean"] == 0 and f["t_lo"] == f["t_hi"] == 0


def test_two_repositories_fall_back_to_query_level(tmp_path: Path) -> None:
    out = lt.build(_write_dir(tmp_path, ["a/a", "a/a", "b/b"]), "cre", draws=100)
    row = next(r for r in out["summary"] if r["key"] == "p|first" and r["level"] == "L2")
    assert (
        row["repos"] == 2 and row["ci_kind"] == "query-level" and row["boot_kind"] == "query-level"
    )
    assert row["df"] == row["n"] - 1


def test_verdict_rule() -> None:
    assert lt.verdict(0.1, 2.0) == "gain"
    assert lt.verdict(-2.0, -0.1) == "loss"
    assert lt.verdict(-0.5, 1.5) == "not distinguishable"
    assert lt.verdict(0.0, 1.0) == "not distinguishable"


def test_query_rows_carry_percent_and_blank_for_missing(tmp_path: Path) -> None:
    tab = load_eval_dir(_write_dir(tmp_path, ["a/a", "b/b"]))
    rows = lt.query_rows(tab, "cre")
    r = next(x for x in rows if x["key"] == "r1|dense" and x["level"] == "L2")
    i = next(
        j for j, q in enumerate(tab.rows) if q["level"] == "L2" and q["instance"] == r["instance"]
    )
    want = 100.0 * tab.metrics[i, tab.index["r1|dense"], COLUMN[("units_all_nomod", "ndcg10")]]
    assert r["units_all_nomod_ndcg10"] == pytest.approx(want, abs=1e-5)


def test_regression_rows_compare_with_stored_values(tmp_path: Path) -> None:
    tab = load_eval_dir(_write_dir(tmp_path, ["a/a", "b/b", "c/c"]))
    idx, _ = lt.level_panel(tab, "L2", lt.PRIMARY_READING)
    mean = float(lt._vector(tab, idx, "r1|dense", lt.PRIMARY_READING, "ndcg10").mean())
    dense_name, _ = lt.stored_names("cre")
    stored = [
        {
            "group": "dev",
            "level": "L2",
            "reading": lt.PRIMARY_READING,
            "metric": "ndcg10",
            "name": dense_name,
            "against": "bm25",
            "queries": "3",
            "value": f"{mean:.2f}",
        }
    ]
    rows = lt.regression_rows(tab, "cre", stored, [], tol=0.05)
    assert len(rows) == 1 and rows[0]["reproduces"] and rows[0]["key"] == "r1|dense"
    stored[0]["value"] = f"{mean + 1:.2f}"
    assert not lt.regression_rows(tab, "cre", stored, [], tol=0.05)[0]["reproduces"]


# ---- stored rows: the latency log and the stored regression tables ----------------------------


def _latency_cfg() -> dict[str, Any]:
    with open(ROOT / "configs/experiments/rq1_ladder_latency.yaml", encoding="utf-8") as fh:
        cfg: dict[str, Any] = yaml.safe_load(fh)
    return cfg


def test_stored_latency_selection_and_unmeasured_stages() -> None:
    log = lt.read_csv_rows(str(ROOT / "results/latency/latency_log.csv"))
    lat = lt.latency_rows(log, _latency_cfg())
    costs = lt.rung_costs(lat, "django")
    assert costs["R1"]["complete"] and costs["R1"]["hosts"] == ["gnode044"]
    # the three stages that had no row were measured in E-FREEZE-AND-LATENCY (django size, M3)
    assert costs["R2"]["stages_not_measured"] == [] and costs["R2"]["complete"]
    for rung, stage in (
        ("R2", "rrf_fusion"),
        ("R3", "same_file_expansion"),
        ("R5", "recency_prior"),
    ):
        assert stage in costs[rung]["stages_measured"]
        assert costs[rung]["hosts"][-1] == "Sukhraj.local" and costs[rung]["added_p50_ms"] > 0
    assert costs["R3"]["complete"] and costs["R5"]["complete"]
    assert costs["R4"]["complete"] and costs["R4"]["hosts"] == ["Sukhraj.local"]
    enc = next(r for r in lat if r["scale"] == "django" and r["stage"] == "query_encode")
    assert enc["p50_ms"] == pytest.approx(18.0691, abs=1e-4) and enc["rows_matched"] >= 1
    assert enc["p50_ms"] <= enc["p95_ms"] <= enc["p99_ms"]
    # the CPU scale uses the CPU node's rows, about twenty times slower
    cpu = lt.rung_costs(lat, "django_cpu")["R1"]["added_p50_ms"]
    assert cpu is not None and cpu > 10 * costs["R1"]["added_p50_ms"]


def test_latency_pick_takes_the_latest_row() -> None:
    base = {
        "stage": "bm25",
        "query_set_id": "q",
        "host": "h1",
        "cache_state": "warm",
        "gpu_name": "none",
        "cpu_model": "c",
        "commit": "x",
        "config_hash": "h",
        "p95_ms": "2",
        "p99_ms": "3",
        "n": "5",
    }
    log = [
        {**base, "timestamp_utc": "2026-01-01", "p50_ms": "1"},
        {**base, "timestamp_utc": "2026-02-01", "p50_ms": "9"},
        {**base, "timestamp_utc": "2026-03-01", "p50_ms": "7", "cache_state": "cold"},
    ]
    row = lt.pick_latency(log, {"stage": "bm25", "query_set_id": "q", "host": "h"})
    assert row is not None and row["p50_ms"] == 9.0 and row["rows_matched"] == 2
    assert lt.pick_latency(log, {"stage": "bm25", "query_set_id": "-", "host": "-"}) is None


def test_gain_per_ms() -> None:
    assert lt.gain_per_ms(2.0, 4.0) == 0.5
    assert lt.gain_per_ms(2.0, None) is None and lt.gain_per_ms(2.0, 0.0) is None
    assert lt.gain_per_ms(-1.0, 2.0) == -0.5


def test_stored_names_exist_in_the_stored_tables() -> None:
    x2 = lt.read_csv_rows(str(ROOT / "results/tables/x2_first_dev.csv"))
    names = {r["name"] for r in x2}
    for label in ("cre", "qwen3"):
        for n in lt.stored_names(label):
            assert n in names
    s1 = lt.read_csv_rows(str(ROOT / "results/tables/s1/s1_graph_role_cre_compare.csv"))
    snames = {r["name"] for r in s1}
    assert {"a_none", "graph|b", "sfscore|b"} <= snames


def test_experiment_configs_load_and_are_dev_only() -> None:
    for name in ("cre", "qwen3"):
        with open(ROOT / f"configs/experiments/rq1_ladder_{name}.yaml", encoding="utf-8") as fh:
            cfg: dict[str, Any] = yaml.safe_load(fh)
        sp, roles = spec_from_config(cfg)
        assert roles == ("dev",) and sp.cap == 50 and sp.seeds == 5 and sp.weight == 0.5
    with open(ROOT / "configs/experiments/rq1_ladder_cre.yaml", encoding="utf-8") as fh:
        cre: dict[str, Any] = yaml.safe_load(fh)
    assert (cre["graph"]["variant"], cre["graph"]["k"], cre["graph"]["alpha"]) == (
        "coderankembed__t1024",
        100,
        0.4,
    )


def test_ladder_tables_build_from_synthetic_stored_files(tmp_path: Path) -> None:
    """The report builder traces every digit and reads only stored tables (synthetic rows)."""
    import shutil

    from ril.analysis import rq1_ladder_tables as tb

    root = tmp_path / "root"
    (root / "results/tables").mkdir(parents=True)
    (root / "results/latency").mkdir(parents=True)
    shutil.copy(ROOT / "results/latency/latency_log.csv", root / "results/latency/latency_log.csv")
    (root / "configs/experiments").mkdir(parents=True)
    shutil.copy(
        ROOT / "configs/experiments/rq1_ladder_latency.yaml",
        root / "configs/experiments/rq1_ladder_latency.yaml",
    )
    from ril.analysis.x2_tables import write_csv

    eval_dir = _write_dir(tmp_path, ["a/a", "b/b", "c/c", "d/d"])
    out = lt.build(eval_dir, "cre", draws=100)
    for part in ("summary", "compare"):
        write_csv(str(root / f"results/tables/rq1_ladder_cre_{part}.csv"), out[part])
    with open(root / "configs/experiments/rq1_ladder_latency.yaml", encoding="utf-8") as fh:
        lat_cfg: dict[str, Any] = yaml.safe_load(fh)
    log = lt.read_csv_rows(str(root / "results/latency/latency_log.csv"))
    write_csv(str(root / "results/tables/rq1_ladder_latency.csv"), lt.latency_rows(log, lat_cfg))
    tables = tb.build_if_present(root)
    names = [t.name for t in tables]
    assert names == ["rq1_ladder", "rq1_ladder_pairs", "rq1_ladder_latency"]
    text = tables[0].render()
    assert "R4 plus typed graph expansion" in text
    # every stage of the ladder has a stored row since E-FREEZE-AND-LATENCY
    assert "(partial)" not in text and "not measured &" not in text
    assert tb.build_if_present(tmp_path / "empty") == []


def test_stored_ladder_rows_reproduce_the_earlier_entries() -> None:
    """The committed run: every control equals its stored value; query rows match the summary."""
    import json

    reg = lt.read_csv_rows(str(ROOT / "results/tables/rq1_ladder_regression.csv"))
    assert len(reg) == 24 and all(r["reproduces"] == "True" for r in reg)
    for label in ("cre", "qwen3"):
        rows = lt.read_csv_rows(str(ROOT / f"results/tables/rq1_ladder_{label}_query_rows.csv"))
        per_key: dict[tuple[str, str], list[float]] = {}
        for r in rows:
            if r["units_all_nomod_ndcg10"] != "" and r["level"] == "L2":
                per_key.setdefault((r["key"], r["level"]), []).append(
                    float(r["units_all_nomod_ndcg10"])
                )
        summ = lt.read_csv_rows(str(ROOT / f"results/tables/rq1_ladder_{label}_summary.csv"))
        for s in summ:
            if s["level"] == "L2" and s["reading"] == "units_all_nomod" and s["metric"] == "ndcg10":
                vals = per_key[(s["key"], "L2")]
                assert len(vals) == int(s["n"])
                assert sum(vals) / len(vals) == pytest.approx(float(s["mean"]), abs=1e-4)
    rec = json.loads(next((ROOT / "results/logs").glob("rq1_ladder_run_files_*.json")).read_text())
    assert len(rec["cre"]["files"]) == len(rec["qwen3"]["files"]) == 355
    assert all(len(h) == 64 for h in rec["cre"]["files"].values())


def test_ladder_fragments_are_in_the_normal_build_and_hashed(tmp_path: Path) -> None:
    """The default report build includes the five ladder fragments; ``extra`` stays accepted."""
    from ril.analysis import report_tables as rt

    plain = rt.write_all(ROOT, tmp_path / "plain")
    more = rt.write_all(ROOT, tmp_path / "more", extra=("rq1_ladder",))
    added = [t.name for t in plain if t.name.startswith("rq1_ladder")]
    assert added == [
        "rq1_ladder",
        "rq1_ladder_pairs",
        "rq1_ladder_qwen3",
        "rq1_ladder_pairs_qwen3",
        "rq1_ladder_latency",
    ]
    assert [t.name for t in more] == [t.name for t in plain]
    with open(tmp_path / "more" / "SOURCES.csv", encoding="utf-8") as fh:
        rows = [r for r in fh.read().splitlines()[1:] if r.startswith("rq1_ladder")]
    assert rows and all(len(r.split(",")[2]) == 64 for r in rows)
    with pytest.raises(ValueError):
        rt.write_all(ROOT, tmp_path / "bad", extra=("nope",))
