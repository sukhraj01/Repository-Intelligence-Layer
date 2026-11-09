"""Cell table, budget, job graph and configuration checks of the RQ2 final plan (no torch).

``ril.training.rq2_plan`` and ``ril.training.config_io``; implements ``docs/RQ2_LAUNCH_PLAN.md``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ril.training import rq2_plan as rp
from ril.training.config_io import config_hash, load_train_config
from ril.training.supervision import MappingKRank, arm_from_config

ROOT = Path(__file__).resolve().parents[2]
MINED = ROOT / "configs/experiments/rq2_final/_template_mined.yaml"
INJECTED = ROOT / "configs/experiments/rq2_final/_template_injected.yaml"
PILOT_MINED = ROOT / "configs/experiments/mp/mp_raw_s0.yaml"
PILOT_INJECTED = ROOT / "configs/experiments/n1/n1_r40_raw_s0.yaml"


def _templates() -> dict[str, dict]:
    return {
        "mined": yaml.safe_load(MINED.read_text(encoding="utf-8")),
        "injected": yaml.safe_load(INJECTED.read_text(encoding="utf-8")),
    }


def test_hash_unchanged_by_the_move() -> None:
    """The directory of a stored run is named by its configuration hash prefix."""
    stored = ROOT / "results/rq2/mp_raw/2026-11-03_5aa72933/config.yaml"
    assert config_hash(load_train_config(str(stored))).startswith("5aa72933")


def test_option_e_shape() -> None:
    runs = rp.plan_runs()
    assert len(rp.CELLS) == 12 and len(runs) == 36
    assert sum(c.family == "mined" for c in rp.CELLS) == 6
    confirmatory = {c.cell_id for c in rp.CELLS if c.status == "confirmatory"}
    assert confirmatory == {"mined_raw", "mined_sub", "mined_filter_bm25"}


def test_option_e_scope_on_the_protocol_basis_reproduces_38_9() -> None:
    b = rp.budget(rp.plan_runs(), basis="protocol", scope="option_e")
    assert b["total"] == pytest.approx(rp.OPTION_E_TOTAL, abs=0.15)
    assert b["margin"] > 0


def test_rulings_scope_scores_the_final_sets_for_the_retained_models_only() -> None:
    runs = rp.plan_runs()
    assert len(rp.retained_runs(runs)) == 18
    m = rp.budget(runs, basis="measured")
    assert m["retained_models"] == 18
    assert m["eight_repositories"] == pytest.approx(18 * 0.178, abs=0.01)
    assert m["verified_look"] == pytest.approx(18 * (0.388 + 0.292), abs=0.01)
    assert m["total"] == pytest.approx(36 * 0.42 + 18 * (0.178 + 0.680), abs=0.02)
    assert m["margin"] > 0 and m["margin_with_conditional"] > 0
    assert m["conditional_dense_teacher_at_most"] == pytest.approx(6.4)
    p = rp.budget(runs, basis="protocol")
    assert p["total"] < rp.budget(runs, basis="protocol", scope="option_e")["total"]
    with pytest.raises(ValueError, match="scope"):
        rp.budget(runs, scope="nope")


def test_measured_basis_is_cheaper_than_the_registered_design_and_labelled() -> None:
    runs = rp.plan_runs()
    measured = rp.budget(runs, basis="measured", scope="option_e")
    assert measured["total"] < rp.budget(runs, basis="protocol", scope="option_e")["total"]
    assert rp.COSTS["verified_look"].evidence == "placeholder"
    assert rp.COSTS["executable_377_built"].evidence == "measured"
    assert rp.COSTS["executable_377_stored"].evidence == "projected"


def test_default_seeds_give_fresh_noise() -> None:
    assert rp.fresh_noise_check(rp.plan_runs()) == []
    reused = rp.fresh_noise_check(rp.plan_runs(seeds=(0, 1, 2)))
    assert len(reused) == 18 and all(r.startswith("inj_") for r in reused)


def test_all_runs_validate_and_hash_apart() -> None:
    rows = rp.validate_runs(rp.plan_runs(), _templates(), filter_size=3800)
    assert len({r["config_hash"] for r in rows}) == 36
    assert all(r["optimizer_updates"] == 100 for r in rows)
    assert all(r["retain_final"] == (r["family"] == "mined") for r in rows)
    assert {r["account"] for r in rows if r["family"] == "mined"} == {"C"}
    assert {r["account"] for r in rows if r["family"] == "injected"} == {"A"}
    assert {r["memory_mb"] for r in rows if r["family"] == "mined"} == {30 * 1024}
    assert all(r["hash_final"] for r in rows)
    assert all(r["example_visits"] == 3200 for r in rows)


def test_subsample_needs_the_filter_size() -> None:
    run = next(r for r in rp.plan_runs() if r.cell.cell_id == "mined_sub")
    with pytest.raises(ValueError, match="FILTER size"):
        rp.render_config(_templates()["mined"], run)
    cfg = rp.render_config(_templates()["mined"], run, filter_size=3800)
    assert cfg["arm"]["subsample"]["size"] == 3800


def test_arms_are_accepted_by_the_training_stack() -> None:
    """Every arm section builds through ``arm_from_config`` (stub signals)."""
    stub = {t: MappingKRank({}, t) for t in ("bm25", "swerankembed-small")}
    for cell in rp.CELLS:
        arm = dict(cell.arm_config)
        sub = arm.get("subsample")
        if sub is not None:
            arm["subsample"] = {**sub, "size": 10}
        if cell.arm == "ORACLE_CLEAN":
            continue  # needs the noise ledger, built in the training run
        arm_from_config(arm, stub, seed=100)


def test_held_identical_across_arms_is_enforced() -> None:
    t = _templates()
    runs = rp.plan_runs(seeds=(100,))
    t["mined"]["optimizer"]["lr"] = 1e-3  # the same change everywhere is comparable, not registered
    with pytest.raises(ValueError, match="registered design"):
        rp.validate_runs(runs, t, filter_size=10)
    bad = rp.render_config(t["mined"], runs[0], filter_size=10)
    bad["batch"] = {**bad["batch"], "batch_size": 64}
    from ril.training.config_io import check_comparable

    with pytest.raises(ValueError, match="outside the arm"):
        check_comparable([rp.render_config(t["mined"], runs[1], filter_size=10), bad])


def test_unique_example_shortfall() -> None:
    enough = rp.unique_example_check(3200, 5800, 3500)
    assert enough["filter_reaches_unique"] and enough["shortfall_filter"] == 0
    short = rp.unique_example_check(32000, 5800, 3500)
    assert not short["raw_reaches_unique"] and short["shortfall_filter"] == 28500


def test_one_gpu_job_per_run_chained_per_account() -> None:
    runs = rp.plan_runs()
    jobs = rp.job_graph(runs)
    ids = {j.job_id: j for j in jobs}
    train = [j for j in jobs if j.job_id.startswith("run_")]
    assert len(train) == 36 and len({j.job_id for j in train}) == 36
    assert {j.account for j in train if "injected" in j.stage} == {"A"}
    assert {j.account for j in train if "mined" in j.stage} == {"C"}
    for acct in ("A", "C"):
        gpu = [j for j in jobs if j.kind == "gpu" and j.account == acct]
        for prev, nxt in zip(gpu, gpu[1:], strict=False):
            assert prev.job_id in nxt.chain_after  # one GPU job at a time per account
    assert ids["overlap"].after == ("report",) and ids["prep"].after == ("overlap",)
    assert all("filter_size" in j.after for j in train if "mined" in j.stage)
    inj = [j for j in train if "injected" in j.stage]
    assert all(j.after == () for j in inj)  # injected cells wait for nothing


def test_conditional_dense_teacher_is_measured_first_and_gates_its_cell() -> None:
    jobs = rp.job_graph(rp.plan_runs())
    ids = {j.job_id: j for j in jobs}
    assert ids["teacher_measure"].gpu_hours == pytest.approx(0.4)
    assert ids["teacher_pass"].gpu_hours == pytest.approx(rp.DENSE_TEACHER_CAP_GPU_H)
    assert ids["teacher_pass"].after == ("teacher_measure",)
    srs = [j for j in jobs if "mined_filter_srs" in j.job_id and j.job_id.startswith("run_")]
    assert len(srs) == 3 and all("teacher_pass" in j.after for j in srs)
    assert all(j.conditional == "D123" for j in srs)
    mined_gpu = [j for j in jobs if j.kind == "gpu" and j.account == "C"]
    assert mined_gpu[0].job_id == "teacher_measure"  # the cheap decision comes first
    dropped = rp.job_graph(rp.plan_runs(), include_conditional=False)
    names = {j.job_id for j in dropped}
    assert "teacher_pass" not in names and not any(
        "filter_srs" in n and n.startswith("run_") for n in names if "mined" in n
    )
    assert len([j for j in dropped if j.job_id.startswith("run_")]) == 33


def test_final_sets_follow_the_dev_analysis_and_cover_the_retained_models() -> None:
    jobs = rp.job_graph(rp.plan_runs())
    ids = {j.job_id: j for j in jobs}
    train = {j.job_id for j in jobs if j.job_id.startswith("run_")}
    assert set(ids["collect_results"].after) == train
    assert ids["dev_analysis"].after == ("collect_results",)
    finals = [j for j in jobs if j.job_id.startswith("final_")]
    assert len(finals) == 18 and all("dev_analysis" in j.after for j in finals)
    assert all(j.account == "C" and "mined" in j.job_id for j in finals)
    assert sum(j.gpu_hours for j in finals) == pytest.approx(18 * 0.858, abs=0.02)


def test_critical_path_shortens_when_families_run_on_two_accounts() -> None:
    runs = rp.plan_runs()
    split = rp.critical_path_hours(rp.job_graph(runs))
    one = rp.critical_path_hours(
        rp.job_graph(runs, family_accounts={"mined": "C", "injected": "C"})
    )
    assert split < one
    # with a queue wait on every job the chain grows by that wait per job on the longest path
    assert rp.critical_path_hours(rp.job_graph(runs), 0.5) > split


def test_final_configurations_hold_the_registered_block_and_the_pilots_values() -> None:
    """The final templates equal the pilots' templates in every held-identical section."""
    from ril.training.config_io import held_identical_view

    for final, pilot in ((MINED, PILOT_MINED), (INJECTED, PILOT_INJECTED)):
        f = yaml.safe_load(final.read_text(encoding="utf-8"))
        p = yaml.safe_load(pilot.read_text(encoding="utf-8"))
        vf, vp = held_identical_view(f), held_identical_view(p)
        for key in ("pool", "provisional"):
            vf.pop(key, None)
            vp.pop(key, None)
        assert vf == vp


def test_protocol_check_refuses_departures() -> None:
    runs = rp.plan_runs()
    t = _templates()
    by = {r.run_id: r for r in runs}
    raw = by["mined_raw_u100_s100"]
    ok = rp.render_config(t["mined"], raw, filter_size=10)
    assert rp.check_protocol(ok, raw) == []
    for mutate, needle in (
        (lambda c: c["batch"].update(batch_size=64), "batch"),
        (lambda c: c["budget"].update(stop_after=1000), "budget"),
        (lambda c: c["evaluation"].update(roles=["dev", "test"]), "evaluation"),
        (lambda c: c["checkpoint"].update(retain_final=False), "retain_final"),
        (lambda c: c.update(noise={"rate": 0.4}), "noise"),
    ):
        bad = rp.render_config(t["mined"], raw, filter_size=10)
        mutate(bad)
        assert any(needle in x for x in rp.check_protocol(bad, raw)), needle
    seed0 = rp.Run(raw.cell, 0, 100)
    assert any(
        "wave" in x
        for x in rp.check_protocol(rp.render_config(t["mined"], seed0, filter_size=10), seed0)
    )
    inj = by["inj_raw_u100_s100"]
    c = rp.render_config(t["injected"], inj)
    assert rp.check_protocol(c, inj) == []
    c["checkpoint"]["retain_final"] = True
    assert any("retain_final" in x for x in rp.check_protocol(c, inj))
    w = by["mined_weight_u100_s100"]
    c = rp.render_config(t["mined"], w)
    c["arm"]["weight"]["teacher"] = "swerankembed-small"
    assert any("BM25" in x for x in rp.check_protocol(c, w))
    f = by["mined_filter_bm25_u100_s100"]
    c = rp.render_config(t["mined"], f)
    c["arm"]["filter"]["k"] = 10
    assert any("K = 20" in x for x in rp.check_protocol(c, f))


def test_written_configurations_round_trip_and_keep_the_subsample_symbolic(tmp_path: Path) -> None:
    runs = rp.plan_runs()
    rows = rp.write_configs(runs, _templates(), str(tmp_path))
    assert len(rows) == 36 and len(list(tmp_path.glob("*.yaml"))) == 36
    sub = load_train_config(str(tmp_path / "mined_sub_u100_s100.yaml"))
    assert sub["arm"]["subsample"]["size"] == "filter_size"
    assert [r["hash_final"] for r in rows if r["cell"] == "mined_sub"] == [False] * 3
    with pytest.raises(ValueError):  # a symbolic size can never train
        arm_from_config(sub["arm"], {}, seed=100)
    resolved = tmp_path / "resolved"
    rows2 = rp.write_configs(runs, _templates(), str(resolved), filter_size=3450)
    sub2 = load_train_config(str(resolved / "mined_sub_u100_s100.yaml"))
    assert sub2["arm"]["subsample"]["size"] == 3450
    assert all(r["hash_final"] for r in rows2)
    assert (
        config_hash(sub2)
        == next(r for r in rows2 if r["run_id"] == "mined_sub_u100_s100")["config_hash"]
    )


def test_committed_configurations_match_the_cell_table_and_their_hashes() -> None:
    committed = ROOT / "configs/experiments/rq2_final"
    runs = rp.plan_runs()
    names = {p.name for p in committed.glob("*_u100_s10?.yaml")}
    assert names == {f"{r.run_id}.yaml" for r in runs}
    rows = {r["run_id"]: r for r in rp.validate_runs(runs, _templates(), filter_size=3450)}
    for r in runs:
        cfg = load_train_config(str(committed / f"{r.run_id}.yaml"))
        sub = cfg["arm"].get("subsample")
        if sub is not None and sub["size"] == "filter_size":
            cfg["arm"]["subsample"] = {**sub, "size": 3450}
        assert rp.check_protocol(cfg, r) == []
        assert config_hash(cfg) == rows[r.run_id]["config_hash"], r.run_id


def test_cell_table_digest_is_stable_and_sensitive() -> None:
    d = rp.cell_table_digest()
    assert d == rp.cell_table_digest()
    assert d != rp.cell_table_digest(rp.CELLS[:-1])


def test_cli_places_jobs_by_family(capsys: pytest.CaptureFixture[str]) -> None:
    import json
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import rq2_plan

    rc = rq2_plan.main(["plan", "--family-accounts", "mined=C", "injected=A"])
    assert rc == 0
    jobs = json.loads(capsys.readouterr().out)["jobs"]
    by_family = {
        ("mined" if "mined" in j["stage"] else "injected"): j["account"]
        for j in jobs
        if j["job_id"].startswith("run_")
    }
    assert by_family == {"mined": "C", "injected": "A"}
