"""Trained arms of RQ3 on synthetic inputs: plan and cost, encode guards, contexts, prompts, plan.

Covers ``ril.evaluation.rq3_trained``, ``ril.assembly.rq3_trained_contexts`` and
``ril.agent.providers.trained_arms`` (``docs/RQ3_PILOT.md``, "Trained arms"). The dry run at the
bottom chains encode, score, retrieve, assemble, pseudonymise and restore on a fake encoder.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ril.agent.providers import trained_arms as ta
from ril.agent.providers.pilot_run import load_items
from ril.agent.providers.rq3_prompts import check_prefix_identity
from ril.analysis.rq3_results import analyse
from ril.assembly import rq3_trained_contexts as tc
from ril.assembly.rq3_contexts import (
    ContextSpec,
    InputGroup,
    build_instance,
    decode_record,
    default_arms,
    encode_record,
)
from ril.assembly.tokens import ApproxTokenizer
from ril.evaluation import eval_sets, final_sets
from ril.evaluation import rq3_trained as rt
from ril.training import retention
from tests.unit import _rq3_trained_fixtures as fx
from tests.unit.test_rq3_results import row

CELLS5 = ("mined_raw", "mined_filter_bm25", "mined_sub", "mined_weight", "mined_curriculum")


def _models(
    tmp_path: Path, seeds: tuple[int, ...] = (100, 101, 102), cells: tuple[str, ...] = CELLS5
) -> list[rt.RetainedModel]:
    root = tmp_path / "retained"
    for s in seeds:
        for cell in cells:
            fx.retained_folder(root, f"rq2f_{cell}", s)
    return rt.models_from_root(str(root))


# ------------------------------------------------------------------ names, order, cost


def test_arm_names_are_keys_and_paths() -> None:
    assert rt.arm_name(fx.RUN_ID) == "tr_mined_raw_u100_s100"
    for bad in ("a|b", "a/b", "A_b"):
        with pytest.raises(rt.TrainedArmsRefused):
            rt.arm_name(bad)


def test_mined_cell_order_is_the_seed_job_order() -> None:
    assert rt.MINED_CELL_ORDER[:5] == (
        "mined_raw",
        "mined_filter_bm25",
        "mined_sub",
        "mined_weight",
        "mined_curriculum",
    )


def test_protocol_order_is_by_seed_then_arm_order(tmp_path: Path) -> None:
    ordered = rt.order_models(_models(tmp_path), "protocol")
    assert [(m.seed, m.cell_id) for m in ordered[:6]] == [
        (100, "mined_raw"),
        (100, "mined_filter_bm25"),
        (100, "mined_sub"),
        (100, "mined_weight"),
        (100, "mined_curriculum"),
        (101, "mined_raw"),
    ]
    with pytest.raises(rt.TrainedArmsRefused):
        rt.order_models(ordered, "other")


def test_primary_first_keeps_the_confirmatory_pair_complete(tmp_path: Path) -> None:
    ordered = rt.order_models(_models(tmp_path), "primary_first")
    assert all(m.primary for m in ordered[:6]) and not any(m.primary for m in ordered[6:])
    assert {m.seed for m in ordered[:6]} == {100, 101, 102}


def test_plan_cost_against_the_block4_cap(tmp_path: Path) -> None:
    plan = rt.plan_jobs(_models(tmp_path, (100, 101, 102)))
    assert plan["models"] == 15 and plan["cost_per_model_gpu_hours"] == 0.68
    # 6.0 - 0.377 = 5.623 GPU-hours: eight models at 0.68 (5.44), the ninth would pass the cap
    assert plan["max_models_by_cap"] == 8 and plan["models_within_cap"] == 8
    fits = [j["fits"] for j in plan["jobs"]]
    assert fits[:8] == [True] * 8 and not any(fits[8:])
    assert plan["jobs"][7]["block4_total_gpu_hours"] == pytest.approx(0.377 + 8 * 0.68)
    assert plan["over_cap_by"] == pytest.approx(0.377 + 15 * 0.68 - 6.0)
    primary_first = rt.plan_jobs(
        rt.models_from_root(str(tmp_path / "retained")), order="primary_first"
    )
    assert [j["primary"] for j in primary_first["jobs"][:8]] == [True] * 6 + [False] * 2


def test_the_eighteen_mined_models_cost_more_than_block4_holds(tmp_path: Path) -> None:
    models = _models(tmp_path, cells=(*CELLS5, "mined_filter_srs"))
    plan = rt.plan_jobs(models)
    assert plan["models"] == 18 and plan["total_gpu_hours_all"] == pytest.approx(12.24)
    assert plan["models_within_cap"] == 8 and plan["over_cap_by"] == pytest.approx(6.617)


def test_unknown_run_id_is_refused(tmp_path: Path) -> None:
    _models(tmp_path)
    with pytest.raises(rt.TrainedArmsRefused, match="no retained model"):
        rt.models_from_root(str(tmp_path / "retained"), ["mined_raw_u100_s999"])


# ------------------------------------------------------------------ encode stage


def _record(tmp_path: Path, runs: tuple[str, ...] = (fx.RUN_ID,)) -> dict[str, Any]:
    path = str(tmp_path / "dev_record.json")
    final_sets.write_dev_analysis_record(path, "E-RQ2-DEV-1", runs, "ab" * 32)
    return final_sets.load_dev_analysis_record(path, "E-RQ2-DEV-1", runs)


def _encode(tmp_path: Path, out: str = "out", **kw: Any) -> dict[str, Any]:
    home = tmp_path / "home"
    spec = kw.pop("spec", None) or (
        fx.build_prepared_store(home) if not (home / "prep").exists() else _spec(home)
    )
    folder = tmp_path / "retained" / "rq2f_mined_raw__s100__abcd100"
    if not folder.exists():
        fx.retained_folder(tmp_path / "retained", "rq2f_mined_raw", 100)
    return rt.encode_model(
        str(folder),
        ids=list(fx.INSTANCES),
        out_root=str(tmp_path / out),
        home=str(home),
        work=str(tmp_path / "work"),
        follows="E-RQ2-DEV-1",
        record=kw.pop("record", None) or _record(tmp_path),
        commit="c0ffee",
        device="cpu",
        encoder=fx.fake_encoder(),
        spec=spec,
    )


def _spec(home: Path) -> eval_sets.EvalSetSpec:
    part = eval_sets.EvalPart("p", str(home / "e1.yaml"), "prep", "e3", "raw")
    return eval_sets.EvalSetSpec("exec377", eval_sets.FINAL, ("test",), (part,), "test", "D127")


def test_encode_writes_scores_of_the_subset_only_and_a_model_record(tmp_path: Path) -> None:
    row_ = _encode(tmp_path)
    directory = rt.scores_dir(str(tmp_path / "out"), fx.RUN_ID)
    assert sorted(os.listdir(directory)) == sorted(f"{i}.npz" for i in fx.INSTANCES)
    assert row_["extra_files_removed"] == 1 and row_["instances"] == 3
    assert row_["arm"] == "tr_mined_raw_u100_s100" and row_["follows_dev_analysis"] == "E-RQ2-DEV-1"
    assert len(row_["model_sha256"]) == 64 and row_["config_hash"] == f"{100:064x}"
    assert rt.check_scores(directory, list(fx.INSTANCES))["present"] == 3
    with np.load(os.path.join(directory, f"{fx.INSTANCES[0]}.npz"), allow_pickle=False) as d:
        assert d[rt.DENSE_KEY].shape == (6,) and d[rt.DENSE_KEY].dtype == np.float32
    assert (tmp_path / "out" / fx.RUN_ID / rt.DONE_NAME).is_file()
    assert (tmp_path / "out" / fx.RUN_ID / rt.MODEL_RECORD).is_file()


def test_encode_is_deterministic_and_a_finished_model_is_not_redone(tmp_path: Path) -> None:
    first = _encode(tmp_path, "out_a")
    _encode(tmp_path, "out_b")
    for iid in fx.INSTANCES:
        a = np.load(os.path.join(rt.scores_dir(str(tmp_path / "out_a"), fx.RUN_ID), f"{iid}.npz"))
        b = np.load(os.path.join(rt.scores_dir(str(tmp_path / "out_b"), fx.RUN_ID), f"{iid}.npz"))
        assert np.array_equal(a[rt.DENSE_KEY], b[rt.DENSE_KEY])
    again = _encode(tmp_path, "out_a")
    assert again == first  # DONE.json read back, nothing encoded twice


def test_encode_refuses_a_run_the_dev_analysis_does_not_cover(tmp_path: Path) -> None:
    with pytest.raises(final_sets.FinalSetsRefused, match="not covered"):
        _encode(tmp_path, record=_record(tmp_path, ("mined_sub_u100_s100",)))


def test_encode_refuses_a_model_that_differs_from_its_manifest(tmp_path: Path) -> None:
    fx.retained_folder(tmp_path / "retained", "rq2f_mined_raw", 100)
    weights = tmp_path / "retained" / "rq2f_mined_raw__s100__abcd100" / "model" / "weights.bin"
    weights.write_bytes(b"tampered")
    with pytest.raises(final_sets.FinalSetsRefused, match="does not match its manifest"):
        _encode(tmp_path)


def test_encode_refuses_a_training_stage_set(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fx.build_prepared_store(home)
    with pytest.raises(final_sets.FinalSetsRefused, match="training-stage"):
        _encode(tmp_path, spec=eval_sets.DEV)


def test_a_dry_run_takes_a_training_set_and_never_a_final_one(tmp_path: Path) -> None:
    home = tmp_path / "home"
    final = fx.build_prepared_store(home)
    dev = eval_sets.EvalSetSpec("dev", eval_sets.TRAINING, ("test",), final.parts, None, "D131")
    folder = fx.retained_folder(tmp_path / "retained", "rq2f_mined_raw", 100)
    kw: dict[str, Any] = {
        "ids": list(fx.INSTANCES),
        "out_root": str(tmp_path / "o"),
        "home": str(home),
        "work": str(tmp_path / "w"),
        "follows": "dry run",
        "record": {"runs": []},
        "commit": "c",
        "device": "cpu",
        "encoder": fx.fake_encoder(),
        "dry_run": True,
    }
    with pytest.raises(final_sets.FinalSetsRefused, match="never scores the final set"):
        rt.encode_model(str(folder), spec=final, **kw)
    out = rt.encode_model(str(folder), spec=dev, **kw)
    assert out["dry_run"] is True and out["set"] == "dev" and out["instances"] == 3


def test_encode_fails_loudly_when_a_member_has_no_scores(tmp_path: Path) -> None:
    home = tmp_path / "home"
    spec = fx.build_prepared_store(home, instances=("o__r-1", "o__r-2"))
    with pytest.raises(rt.TrainedArmsRefused, match="scores missing for 1"):
        _encode(tmp_path, spec=spec)


def test_the_cli_refuses_more_than_one_model_and_a_missing_id(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    import rq3_trained_arm as cli

    root = tmp_path / "retained"
    fx.retained_folder(root, "rq2f_mined_raw", 100)
    fx.retained_folder(root, "rq2f_mined_filter_bm25", 100)
    base = ["encode", "--retained-root", str(root), "--dev-record", "x", "--out", "o"]
    base += ["--home", "h", "--work", "w"]
    ids = ["mined_raw_u100_s100", "mined_filter_bm25_u100_s100"]
    assert cli.main([*base, "--only", *ids, "--follows-dev-analysis", "E-RQ2-DEV-1"]) == 3
    os.environ["RIL_COMMIT"] = "abc"
    try:
        assert cli.main([*base, "--only", ids[0]]) == 3  # no id: sealed
    finally:
        del os.environ["RIL_COMMIT"]


# ------------------------------------------------------------------ contexts


SPEC = ContextSpec(budgets=(60, 100000), max_unit_tokens=1000, candidates=6, rrf_k=10)
TOK = ApproxTokenizer()


def _world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[list[InputGroup], dict[str, int]]:
    """Group directories with a dummy cache file and the stored untrained dense scores."""
    cache, dense = tmp_path / "e3", tmp_path / "dense"
    cache.mkdir()
    dense.mkdir()
    for n, iid in enumerate(fx.INSTANCES):
        (cache / f"{iid}.npz").write_bytes(b"x")
        rng = np.random.default_rng(50 + n)
        np.savez(dense / f"{iid}.npz", dense_L2=rng.random(6), dense_L3=rng.random(6))
    inputs = {iid: fx.instance_inputs(iid) for iid in fx.INSTANCES}
    monkeypatch.setattr(
        tc, "read_cache", lambda path: inputs[os.path.basename(path).removesuffix(".npz")]
    )
    calls = {"loads": 0}
    return [InputGroup(str(cache), str(dense))], calls


def _loader(calls: dict[str, int]) -> Any:
    def load(meta: Any, repo_cache: str, work_dir: str) -> Any:
        calls["loads"] += 1
        return fx.unit_records(str(meta["instance"]))

    return load


def _model_scores(tmp_path: Path, name: str, same_as_untrained: bool) -> str:
    d = tmp_path / name
    d.mkdir()
    for n, iid in enumerate(fx.INSTANCES):
        if same_as_untrained:
            arr = np.load(tmp_path / "dense" / f"{iid}.npz")["dense_L2"]
        else:
            arr = np.random.default_rng(900 + n).random(6).astype(np.float32)
        np.savez(d / f"{iid}.npz", dense_L2=arr)
    return str(d)


def test_the_untrained_arms_built_by_the_new_path_equal_the_old_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    groups, calls = _world(tmp_path, monkeypatch)
    cfg = {"dense_key": "dense_L2", "arms": ["bm25", "dense", "rrf"]}
    untrained = tc.untrained_target(cfg, SPEC)
    res = tc.run_build_targets(
        list(fx.INSTANCES), groups, "rc", "wk", str(tmp_path / "ctx"), [untrained], SPEC,
        load_units=_loader(calls),
    )  # fmt: skip
    assert res["counts"]["untrained"] == {"built": 3, "reused": 0, "failed": 0}
    for iid in fx.INSTANCES:
        arrays, meta = fx.instance_inputs(iid)
        dense = {k: np.load(tmp_path / "dense" / f"{iid}.npz")[k] for k in ("dense_L2", "dense_L3")}
        old = encode_record(
            build_instance(meta, arrays, dense, fx.unit_records(iid), SPEC, default_arms(10), TOK)
        )
        new = (tmp_path / "ctx" / "untrained" / "instances" / f"{iid}.json.gz").read_bytes()
        assert new == old  # byte for byte


def test_a_pass_parses_each_instance_once_for_all_targets_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    groups, calls = _world(tmp_path, monkeypatch)
    targets = [
        tc.trained_target("m1", "tr_m1", _model_scores(tmp_path, "s1", False), SPEC.rrf_k),
        tc.trained_target("m2", "tr_m2", _model_scores(tmp_path, "s2", False), SPEC.rrf_k),
    ]
    kw: dict[str, Any] = {"load_units": _loader(calls)}
    res = tc.run_build_targets(
        list(fx.INSTANCES), groups, "rc", "wk", str(tmp_path / "ctx"), targets, SPEC, **kw
    )
    assert calls["loads"] == 3  # one parse per instance for both models
    assert res["counts"]["m1"]["built"] == 3 and res["counts"]["m2"]["built"] == 3
    again = tc.run_build_targets(
        list(fx.INSTANCES), groups, "rc", "wk", str(tmp_path / "ctx"), targets, SPEC, **kw
    )
    assert calls["loads"] == 3 and again["counts"]["m1"]["reused"] == 3


def test_trained_targets_do_not_need_the_stored_untrained_scores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    groups, calls = _world(tmp_path, monkeypatch)
    for f in (tmp_path / "dense").iterdir():
        f.unlink()  # the account that builds trained contexts may hold only the caches
    t = tc.trained_target("m1", "tr_m1", _model_scores(tmp_path, "s1", False), SPEC.rrf_k)
    res = tc.run_build_targets(
        list(fx.INSTANCES), groups, "rc", "wk", str(tmp_path / "ctx"), [t], SPEC,
        load_units=_loader(calls),
    )  # fmt: skip
    assert res["counts"]["m1"]["built"] == 3 and not res["failures"]


def test_same_model_hash_gives_the_same_contexts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    groups, calls = _world(tmp_path, monkeypatch)
    t = tc.trained_target("m1", "tr_m1", _model_scores(tmp_path, "s1", False), SPEC.rrf_k)
    for out in ("a", "b"):
        tc.run_build_targets(
            list(fx.INSTANCES), groups, "rc", "wk", str(tmp_path / out), [t], SPEC,
            load_units=_loader(calls),
        )  # fmt: skip
    for iid in fx.INSTANCES:
        fa = tmp_path / "a" / "m1" / "instances" / f"{iid}.json.gz"
        fb = tmp_path / "b" / "m1" / "instances" / f"{iid}.json.gz"
        assert fa.read_bytes() == fb.read_bytes()


def test_a_model_without_a_score_file_is_listed_not_skipped_silently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    groups, calls = _world(tmp_path, monkeypatch)
    scores = _model_scores(tmp_path, "s1", False)
    os.remove(os.path.join(scores, f"{fx.INSTANCES[1]}.npz"))
    res = tc.run_build_targets(
        list(fx.INSTANCES), groups, "rc", "wk", str(tmp_path / "ctx"),
        [tc.trained_target("m1", "tr_m1", scores, SPEC.rrf_k)], SPEC, load_units=_loader(calls),
    )  # fmt: skip
    assert res["counts"]["m1"] == {"built": 2, "reused": 0, "failed": 1}
    assert res["failures"] == [{"instance": fx.INSTANCES[1], "target": "m1", "reason": "no_scores"}]


# ------------------------------------------------------------------ prompts (dry run)


def test_dry_run_encode_retrieve_assemble_pseudonymise_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Checkpoint (fake) -> encode -> scores -> contexts -> prompts -> restore, then the arm pairs
    with the untrained arm like for like."""
    # the unit texts carry an address: encode and retrieve with the retained model's scores
    row_ = _encode(tmp_path, "scores")
    groups, calls = _world(tmp_path, monkeypatch)
    cfg = {"dense_key": "dense_L2", "arms": ["bm25", "dense", "rrf"]}
    targets = [
        tc.untrained_target(cfg, SPEC),
        tc.trained_target(
            fx.RUN_ID, row_["arm"], rt.scores_dir(str(tmp_path / "scores"), fx.RUN_ID), SPEC.rrf_k
        ),
    ]
    res = tc.run_build_targets(
        list(fx.INSTANCES), groups, "rc", "wk", str(tmp_path / "ctx"), targets, SPEC,
        load_units=_loader(calls),
    )  # fmt: skip
    assert not res["failures"]
    rec = decode_record(
        (tmp_path / "ctx" / fx.RUN_ID / "instances" / f"{fx.INSTANCES[0]}.json.gz").read_bytes()
    )
    assert set(rec["contexts"]) == {f"{row_['arm']}|60", f"{row_['arm']}|100000"}
    issues = {i: f"The call to u3 fails in {i}. Please fix." for i in fx.INSTANCES}
    out_t, out_u = str(tmp_path / "prep_t"), str(tmp_path / "prep_u")
    got = ta.prepare_trained(str(tmp_path / "ctx" / fx.RUN_ID), row_["arm"], issues, 100000, out_t)
    assert got["written"] == 3 and not got["rejected"] and not got["skipped"]
    base = ta.prepare_trained(str(tmp_path / "ctx" / "untrained"), "rrf", issues, 100000, out_u)
    assert base["written"] == 3
    items = load_items(out_t) + load_items(out_u)
    # the address in a unit text is replaced before the screen and restored for the reply
    touched = [it for it in items if it["arm"] == row_["arm"] and it.get("restore") is not None]
    assert touched and all(fx.EMAIL not in it["prompt"] for it in touched)
    from ril.agent.providers.pseudonymise import restore_text

    for it in touched:
        assert fx.EMAIL in restore_text(it["prompt"], it["restore"])
    assert check_prefix_identity(items)["identical"] is True  # same text before the excerpts


def test_a_model_with_the_untrained_scores_gives_the_untrained_rrf_arms_contexts_and_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    groups, calls = _world(tmp_path, monkeypatch)
    cfg = {"dense_key": "dense_L2", "arms": ["bm25", "dense", "rrf"]}
    same = tc.trained_target("same", "tr_same", _model_scores(tmp_path, "s_same", True), SPEC.rrf_k)
    tc.run_build_targets(
        list(fx.INSTANCES), groups, "rc", "wk", str(tmp_path / "ctx"),
        [tc.untrained_target(cfg, SPEC), same], SPEC, load_units=_loader(calls),
    )  # fmt: skip
    issues = {i: f"Issue text of {i}." for i in fx.INSTANCES}
    ta.prepare_trained(
        str(tmp_path / "ctx" / "same"), "tr_same", issues, 100000, str(tmp_path / "p1")
    )
    ta.prepare_trained(
        str(tmp_path / "ctx" / "untrained"), "rrf", issues, 100000, str(tmp_path / "p2")
    )
    a = {r["instance_id"]: r for r in load_items(tmp_path / "p1")}
    b = {r["instance_id"]: r for r in load_items(tmp_path / "p2")}
    assert a.keys() == b.keys()
    for iid in a:
        assert (
            a[iid]["prompt"] == b[iid]["prompt"]
        )  # only the dense component differs, and here it does not
        assert a[iid]["context_sha256"] == b[iid]["context_sha256"]


# ------------------------------------------------------------------ plan and analysis


def _arms(seeds: tuple[int, ...] = (100, 101)) -> list[ta.TrainedArm]:
    out = []
    for s in seeds:
        for cell in ("mined_raw", "mined_filter_bm25", "mined_weight"):
            rid = f"{cell}_u100_s{s}"
            out.append(ta.TrainedArm(rt.arm_name(rid), rid, cell, s, "f" * 64))
    return out


def test_plan_names_one_primary_pair_and_estimates_for_the_rest() -> None:
    plan = ta.build_plan(_arms(), [0, 1, 2])
    assert plan["arms"][0] == "rrf" and len(plan["arms"]) == 7
    assert plan["primary"] == ["tr_mined_raw_u100_s100", "rrf"] and plan["primary_seed"] == 100
    est = {tuple(p) for p in plan["estimates"]}
    assert ("tr_mined_raw_u100_s101", "rrf") in est
    assert ("tr_mined_filter_bm25_u100_s100", "tr_mined_raw_u100_s100") in est
    assert ("tr_mined_filter_bm25_u100_s101", "tr_mined_raw_u100_s101") in est
    assert ("tr_mined_weight_u100_s101", "tr_mined_raw_u100_s101") in est
    assert tuple(plan["primary"]) not in est and len(est) == len(plan["estimates"])
    with pytest.raises(ValueError, match="no RAW model"):
        ta.build_plan([a for a in _arms() if a.cell != "mined_raw"], [0])
    with pytest.raises(ValueError, match="same arm name"):
        ta.arms_from_records(
            [
                {"arm": "x", "run_id": "a", "cell": "mined_raw", "seed": 1},
                {"arm": "x", "run_id": "b", "cell": "mined_raw", "seed": 2},
            ]
        )


def test_the_analysis_runs_the_trained_plan_on_synthetic_rows() -> None:
    arms = _arms((100,))
    plan = ta.plan_from_record(ta.build_plan(arms, [0, 1]))
    raw, filt, weight = (a.arm for a in arms)
    rows = []
    for i in range(40):
        for arm, p in (("rrf", 0.2), (raw, 0.5), (filt, 0.7), (weight, 0.5)):
            for run in (0, 1):
                ok = ((i * 7 + run * 3 + len(arm)) % 10) / 10 < p
                rows.append(row(f"i{i}", arm, run, "resolved" if ok else "executed_unresolved"))
    repo_of = {f"i{i}": "r1" if i < 20 else "r2" for i in range(40)}
    tables = analyse(
        rows, [f"i{i}" for i in range(40)], repo_of, plan, resamples=200, permutations=200
    )
    contrasts = tables["contrasts"]
    exact = [c for c in contrasts if c["reading"] == "exact"]
    primary = [c for c in exact if c["role"] == "primary"]
    assert len(primary) == 1 and (primary[0]["first"], primary[0]["second"]) == (raw, "rrf")
    assert primary[0]["difference"] > 0 if "difference" in primary[0] else True
    assert {c["role"] for c in exact} == {"primary", "estimate"} and len(exact) == 1 + len(
        plan.estimates
    )
    assert not tables["missing"] and not tables["exec_errors"]


def test_the_driver_cli_reads_a_plan_file(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(ta.build_plan(_arms((100,)), [0])), encoding="utf-8")
    plan = ta.read_plan(str(path))
    assert plan.primary == ("tr_mined_raw_u100_s100", "rrf") and plan.runs == (0,)
    assert isinstance(retention.MODEL_SUBDIR, str)
