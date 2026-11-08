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
MINED = ROOT / "configs/experiments/mp/mp_raw_s0.yaml"
INJECTED = ROOT / "configs/experiments/n1/n1_r40_raw_s0.yaml"


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


def test_protocol_basis_reproduces_38_9() -> None:
    b = rp.budget(rp.plan_runs(), basis="protocol")
    assert b["total"] == pytest.approx(rp.OPTION_E_TOTAL, abs=0.15)
    assert b["margin"] > 0


def test_measured_basis_is_cheaper_and_labelled() -> None:
    measured = rp.budget(rp.plan_runs(), basis="measured")
    assert measured["total"] < rp.budget(rp.plan_runs(), basis="protocol")["total"]
    assert rp.COSTS["verified_look"].evidence == "placeholder"


def test_default_seeds_give_fresh_noise() -> None:
    assert rp.fresh_noise_check(rp.plan_runs()) == []
    reused = rp.fresh_noise_check(rp.plan_runs(seeds=(0, 1, 2)))
    assert len(reused) == 18 and all(r.startswith("inj_") for r in reused)


def test_all_runs_validate_and_hash_apart() -> None:
    rows = rp.validate_runs(rp.plan_runs(), _templates(), filter_size=3800)
    assert len({r["config_hash"] for r in rows}) == 36
    assert all(r["retain_final"] and r["optimizer_updates"] == 100 for r in rows)
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
    t["mined"]["optimizer"]["lr"] = 1e-3  # same change in the template: still comparable
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


def test_job_graph_chains_per_account_and_orders_stages() -> None:
    runs = rp.plan_runs()
    one = rp.job_graph(runs, train_accounts=("A",))
    two = rp.job_graph(runs, train_accounts=("A", "C"))
    assert sum(j.gpu_hours for j in one) == pytest.approx(sum(j.gpu_hours for j in two))
    assert rp.critical_path_hours(two) < rp.critical_path_hours(one)
    ids = {j.job_id: j for j in one}
    assert ids["overlap"].after == ("report",) and ids["prep"].after == ("overlap",)
    gpu = [j for j in one if j.stage.startswith("train")]
    assert all("filter_size" in j.after for j in gpu if "mined" in j.stage)
    assert len(gpu) == 6 and all(j.account == "A" for j in gpu)
    for a, b in zip(gpu, gpu[1:], strict=False):
        assert a.job_id in b.after  # one GPU job at a time per account


def test_family_placement_lets_injected_cells_start_without_the_store() -> None:
    runs = rp.plan_runs()
    jobs = rp.job_graph(runs, family_accounts={"mined": "C", "injected": "A"})
    inj = [j for j in jobs if j.stage.startswith("train") and "injected" in j.stage]
    mined = [j for j in jobs if j.stage.startswith("train") and "mined" in j.stage]
    assert {j.account for j in inj} == {"A"} and {j.account for j in mined} == {"C"}
    assert inj[0].after == ()  # no dependence on mining or the overlap audit
    assert all("filter_size" in j.after for j in mined[:1])
    one = rp.critical_path_hours(rp.job_graph(runs, train_accounts=("A",)))
    split = rp.critical_path_hours(jobs)
    assert split < one


def test_verified_look_follows_the_dev_analysis_and_all_training() -> None:
    jobs = rp.job_graph(rp.plan_runs())
    ids = {j.job_id: j for j in jobs}
    train = {j.job_id for j in jobs if j.stage.startswith("train")}
    assert set(ids["dev_analysis"].after) == train
    looks = [j for j in jobs if j.job_id.startswith("verified_look")]
    assert len(looks) == 3 and looks[0].after == ("dev_analysis",)
    assert all("dev_analysis" in j.after for j in looks)
    assert looks[1].after[-1] == looks[0].job_id  # one GPU job at a time on the account
    assert sum(j.gpu_hours for j in looks) == pytest.approx(7.2)
