"""Trained arms fuse with BM25 like the untrained arm, retained scores replace the encode stage,
and the plan costs a model with retained scores nothing (D152, DEV-042; Q72 to Q74).

No torch, no cluster: fake score files stand for the sealed job's retained scores.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ril.agent.providers import trained_arms as ta
from ril.assembly import rq3_trained_contexts as tc
from ril.assembly.rq3_contexts import default_arms, rrf_arm_score
from ril.evaluation import rq3_trained as rt
from ril.evaluation import score_retention as sr
from tests.unit import _rq3_trained_fixtures as fx
from tests.unit.test_rq3_trained_arms import CELLS5, SPEC, _loader, _models, _world

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
IDS = list(fx.INSTANCES)


def _retain(root: Path, model: rt.RetainedModel, ids: list[str] = IDS, seed: int = 1) -> str:
    """Score files for ``ids`` kept for one model through the real retention writer."""
    src = root / f"src_{model.run_id}"
    src.mkdir(parents=True, exist_ok=True)
    for n, iid in enumerate(ids):
        arr = np.random.default_rng(seed + n).random(6).astype(np.float32)
        np.savez(src / f"{iid}.npz", dense_L2=arr)
    sr.retain_part(
        str(src),
        ids,
        scores_root=str(root / "scores"),
        run_id=model.run_id,
        part="p",
        model_sha256=model.model_sha256,
        config_hash=model.config_hash,
        follows="E-RQ2-DEV-1",
        dev_record_sha256="d" * 64,
        commit="c0ffee",
    )
    return str(root / "scores")


# ------------------------------------------------------------------ the arm is fused


def test_the_trained_arm_is_rrf_of_bm25_and_the_models_scores() -> None:
    arm = tc.trained_arm("tr_x", 10)
    untrained = {a.name: a for a in default_arms(10)}["rrf"]
    assert arm.stages == untrained.stages == ("bm25", "dense")
    assert arm.dense_key == untrained.dense_key == "dense_L2"
    rng = np.random.default_rng(3)
    bm25, dense = rng.random(40), rng.random(40)
    assert np.array_equal(arm.score(bm25, dense), rrf_arm_score(10)(bm25, dense))
    assert np.array_equal(arm.score(bm25, dense), untrained.score(bm25, dense))
    # BM25 takes part: changing it moves the ranking, which a dense-only arm would not do
    other = rng.random(40)
    assert not np.array_equal(arm.score(bm25, dense), arm.score(other, dense))
    dense_only = {a.name: a for a in default_arms(10)}["dense"]
    assert np.array_equal(dense_only.score(bm25, dense), dense_only.score(other, dense))
    # no silent default for the constant: a build cannot use another k than the spec's
    with pytest.raises(TypeError):
        tc.trained_arm("tr_x")  # type: ignore[call-arg]


def test_a_model_with_the_untrained_scores_reproduces_the_untrained_rrf_arm_byte_for_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The equality test of D152: contexts (the instance records, arm name aside) and prompts."""
    from ril.agent.providers.pilot_run import load_items

    groups, calls = _world(tmp_path, monkeypatch)
    scores = tmp_path / "same"
    scores.mkdir()
    for iid in fx.INSTANCES:
        arr = np.load(tmp_path / "dense" / f"{iid}.npz")["dense_L2"]
        np.savez(scores / f"{iid}.npz", dense_L2=arr)
    cfg = {"dense_key": "dense_L2", "arms": ["bm25", "dense", "rrf"]}
    same = tc.trained_target("same", "tr_same", str(scores), SPEC.rrf_k)
    res = tc.run_build_targets(
        IDS, groups, "rc", "wk", str(tmp_path / "ctx"),
        [tc.untrained_target(cfg, SPEC), same], SPEC, load_units=_loader(calls),
    )  # fmt: skip
    assert not res["failures"]
    from ril.assembly.rq3_contexts import decode_record

    for iid in IDS:
        a = decode_record(
            (tmp_path / "ctx" / "untrained" / "instances" / f"{iid}.json.gz").read_bytes()
        )
        b = decode_record((tmp_path / "ctx" / "same" / "instances" / f"{iid}.json.gz").read_bytes())
        for budget in SPEC.budgets:
            assert b["contexts"][f"tr_same|{budget}"] == a["contexts"][f"rrf|{budget}"]
    issues = {i: f"Issue text of {i}." for i in IDS}
    ta.prepare_trained(
        str(tmp_path / "ctx" / "same"), "tr_same", issues, 100000, str(tmp_path / "p1")
    )
    ta.prepare_trained(
        str(tmp_path / "ctx" / "untrained"), "rrf", issues, 100000, str(tmp_path / "p2")
    )
    left = {r["instance_id"]: r for r in load_items(tmp_path / "p1")}
    right = {r["instance_id"]: r for r in load_items(tmp_path / "p2")}
    assert left.keys() == right.keys() == set(IDS)
    for iid in IDS:
        assert left[iid]["prompt"] == right[iid]["prompt"]
        assert left[iid]["context_sha256"] == right[iid]["context_sha256"]


def test_the_fused_trained_arm_differs_from_the_dense_only_arm_when_the_scores_differ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    groups, calls = _world(tmp_path, monkeypatch)
    scores = tmp_path / "other"
    scores.mkdir()
    for n, iid in enumerate(IDS):
        np.savez(scores / f"{iid}.npz", dense_L2=np.random.default_rng(900 + n).random(6))
    res = tc.run_build_targets(
        IDS, groups, "rc", "wk", str(tmp_path / "ctx"),
        [tc.trained_target("m", "tr_m", str(scores), SPEC.rrf_k)], SPEC, load_units=_loader(calls),
    )  # fmt: skip
    assert res["counts"]["m"]["built"] == 3
    from ril.assembly.rq3_contexts import decode_record

    rec = decode_record((tmp_path / "ctx" / "m" / "instances" / f"{IDS[0]}.json.gz").read_bytes())
    assert rec["spec_hash"] == SPEC.spec_hash(
        tc.ApproxTokenizer().name, (tc.trained_arm("tr_m", SPEC.rrf_k),)
    )
    # the arm's name is part of the build's hash, so a build of the old dense-only form is rebuilt
    assert set(rec["contexts"]) == {"tr_m|60", "tr_m|100000"}


# ------------------------------------------------------------------ retained scores, no encoding


def test_resolve_prefers_verified_retained_scores_and_falls_back_to_the_encode_output(
    tmp_path: Path,
) -> None:
    models = _models(tmp_path, (100,), ("mined_raw",))
    m = models[0]
    root = _retain(tmp_path, m)
    got = rt.resolve_scores(m.run_id, IDS, retained_scores=root, model_sha256=m.model_sha256)
    assert got is not None and got["source"] == "retained" and got["model_sha256"] == m.model_sha256
    assert got["dir"] == sr.scores_dir(root, m.run_id) and got["retained_problems"] == []
    # another checkpoint, an incomplete set and a damaged file are not used
    assert rt.resolve_scores(m.run_id, IDS, retained_scores=root, model_sha256="0" * 64) is None
    assert rt.resolve_scores(m.run_id, [*IDS, "o__r-9"], retained_scores=root) is None
    # with an encode output the fallback is taken and says why
    enc = tmp_path / "enc" / m.run_id
    enc.mkdir(parents=True)
    (enc / rt.DONE_NAME).write_text(json.dumps({"model_sha256": "e" * 64, "config_hash": "c"}))
    victim = Path(sr.scores_dir(root, m.run_id)) / f"{IDS[0]}.npz"
    victim.write_bytes(b"damaged")
    fell = rt.resolve_scores(
        m.run_id, IDS, encode_root=str(tmp_path / "enc"), retained_scores=root,
        model_sha256=m.model_sha256,
    )  # fmt: skip
    assert fell is not None and fell["source"] == "encoded"
    assert any("differs" in p for p in fell["retained_problems"])
    assert fell["dir"] == rt.scores_dir(str(tmp_path / "enc"), m.run_id)
    assert rt.resolve_scores("nothing", IDS, encode_root=str(tmp_path / "enc")) is None
    assert rt.encoded_run_ids(str(tmp_path / "enc")) == [m.run_id]
    assert rt.retained_run_ids(root) == [m.run_id]


def test_the_plan_costs_a_model_with_retained_scores_nothing(tmp_path: Path) -> None:
    models = _models(tmp_path, (100, 101, 102))
    kept = {m.run_id: "d" for m in models}
    plan = rt.plan_jobs(models, retained=kept)
    assert plan["total_gpu_hours_all"] == 0 and plan["over_cap_by"] == 0
    assert plan["models_with_retained_scores"] == 15 and plan["models_to_encode"] == 0
    assert plan["models_within_cap"] == 15 and all(j["gpu_hours"] == 0 for j in plan["jobs"])
    assert all(j["scores"] == "retained" and j["fits"] for j in plan["jobs"])
    # a mix: only the models without scores are charged, in order, until the cap
    some = {m.run_id: "d" for m in models if m.cell_id == "mined_sub"}
    mixed = rt.plan_jobs(models, retained=some)
    assert mixed["models_with_retained_scores"] == 3 and mixed["models_to_encode"] == 12
    assert mixed["total_gpu_hours_all"] == pytest.approx(12 * 0.68)
    assert mixed["encode_models_within_cap"] == 8
    assert [j["scores"] for j in mixed["jobs"]].count("retained") == 3
    assert all(j["fits"] for j in mixed["jobs"] if j["scores"] == "retained")


# ------------------------------------------------------------------ the order of Q73


def test_the_order_of_q73_pair_first_then_seed_100_then_the_rest(tmp_path: Path) -> None:
    models = _models(tmp_path, (100, 101, 102), (*CELLS5, "mined_filter_srs"))
    ordered = rt.order_models(models)  # the default
    assert rt.ORDERS[0] == rt.ORDER_Q73 == "pair_seed100"
    keys = [(m.cell_id, m.seed) for m in ordered]
    assert {c for c, _ in keys[:6]} == {"mined_raw", "mined_filter_bm25"}
    assert sorted(s for _, s in keys[:6]) == [100, 100, 101, 101, 102, 102]
    assert keys[6:8] == [("mined_weight", 100), ("mined_curriculum", 100)]
    assert sorted(keys[8:12]) == sorted(
        (c, s) for c in ("mined_weight", "mined_curriculum") for s in (101, 102)
    )
    assert {c for c, _ in keys[12:]} == {"mined_sub", "mined_filter_srs"}
    assert ordered == rt.order_models(models, rt.ORDER_Q73)
    # the other two orders are as they were
    assert rt.order_models(models, "protocol")[1].cell_id == "mined_filter_bm25"
    with pytest.raises(rt.TrainedArmsRefused):
        rt.order_models(models, "nope")


def test_plan_output_records_the_order_and_what_the_cap_covers(tmp_path: Path) -> None:
    models = _models(tmp_path, (100, 101, 102), (*CELLS5, "mined_filter_srs"))
    plan = rt.plan_jobs(models)  # nothing retained: the fallback encode stage
    assert plan["order"] == "pair_seed100" and plan["order_rule"][0].startswith("1. RAW and FILTER")
    rows = plan["jobs"]
    # six models of the primary contrast cost 4.08 and eight fit (5.44, total 5.817); the ninth not
    assert rows[5]["cumulative_gpu_hours"] == pytest.approx(4.08)
    assert [r["fits"] for r in rows[:8]] == [True] * 8 and not any(r["fits"] for r in rows[8:])
    assert rows[7]["block4_total_gpu_hours"] == pytest.approx(0.377 + 5.44)
    assert [r["cell"] for r in rows[6:8]] == ["mined_weight", "mined_curriculum"]
    assert plan["encode_models_within_cap"] == 8 and plan["models_to_encode"] == 18
    assert plan["total_gpu_hours_all"] == pytest.approx(12.24)


# ------------------------------------------------------------------ the command line


def _cli_args(tmp_path: Path, **kw: Any) -> argparse.Namespace:
    base: dict[str, Any] = dict(
        scores_root=str(tmp_path / "enc"), models=None, retained_scores=None, retained_root=None
    )
    base.update(kw)
    return argparse.Namespace(**base)


def test_contexts_read_retained_scores_with_the_fused_arm_and_record_the_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import rq3_trained_arm as cli

    models = _models(tmp_path, (100,), ("mined_raw", "mined_filter_bm25"))
    root = _retain(tmp_path, models[0])  # only the first model has retained scores
    enc = tmp_path / "enc" / models[1].run_id
    (enc / "dense_scores").mkdir(parents=True)
    (enc / rt.DONE_NAME).write_text(json.dumps({"model_sha256": models[1].model_sha256}))
    cfgfile = tmp_path / "cfg.yaml"
    cfgfile.write_text(
        "assembly: {budgets: [60], max_unit_tokens: 1000, candidates: 6, rrf_k: 10,"
        " query_level: L2, tokenizer: approx}\n"
        "groups: [{cache_dir: c, dense_dir: d}]\ndense_key: dense_L2\narms: [bm25, dense, rrf]\n"
        "subset: s.json\n"
    )
    subset = tmp_path / "subset.json"
    subset.write_text(json.dumps({"executable": [{"instance_id": i} for i in IDS]}))
    seen: dict[str, Any] = {}

    def fake_build(
        members: Any, groups: Any, rc: Any, wk: Any, out: Any, targets: Any, spec: Any, **kw: Any
    ) -> Any:
        seen["targets"], seen["spec"] = targets, spec
        return {"counts": {}, "failures": [], "infos": [], "spec_hashes": {}}

    monkeypatch.setattr(tc, "run_build_targets", fake_build)
    args = argparse.Namespace(
        config=str(cfgfile), scores_root=str(tmp_path / "enc"), repo_cache="rc", work="w",
        out_root=str(tmp_path / "out"), models=None, retained_scores=root,
        retained_root=str(tmp_path / "retained"), untrained=False, shard=[0, 1], only=None,
        subset=str(subset), members=None,
    )  # fmt: skip
    assert cli.cmd_contexts(args) == 0
    by_name = {t.name: t for t in seen["targets"]}
    assert set(by_name) == {m.run_id for m in models}
    assert by_name[models[0].run_id].scores_dir == sr.scores_dir(root, models[0].run_id)
    assert by_name[models[1].run_id].scores_dir == rt.scores_dir(
        str(tmp_path / "enc"), models[1].run_id
    )
    for t in seen["targets"]:  # every trained arm is the fused form at the spec's constant
        assert t.arms[0].stages == ("bm25", "dense")
    src = json.loads((tmp_path / "out" / models[0].run_id / "scores_source.json").read_text())
    assert src["source"] == "retained" and src["rrf_k"] == 10
    assert src["model_sha256"] == models[0].model_sha256
    src2 = json.loads((tmp_path / "out" / models[1].run_id / "scores_source.json").read_text())
    assert src2["source"] == "encoded"


def test_contexts_refuse_a_model_with_no_usable_scores(tmp_path: Path) -> None:
    import rq3_trained_arm as cli

    models = _models(tmp_path, (100,), ("mined_raw",))
    root = _retain(tmp_path, models[0])
    (Path(sr.scores_dir(root, models[0].run_id)) / f"{IDS[1]}.npz").write_bytes(b"damaged")
    args = _cli_args(
        tmp_path, models=[models[0].run_id], retained_scores=root,
        retained_root=str(tmp_path / "retained"),
    )  # fmt: skip
    with pytest.raises(rt.TrainedArmsRefused, match="no usable scores"):
        cli._resolve_models(args, IDS)


def test_plan_command_reads_the_retained_scores_and_the_analysis_plan_uses_rrf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import rq3_trained_arm as cli

    models = _models(tmp_path, (100, 101), ("mined_raw", "mined_filter_bm25"))
    for m in models:
        _retain(tmp_path, m)
    subset = tmp_path / "subset.json"
    subset.write_text(json.dumps({"executable": [{"instance_id": i} for i in IDS]}))
    retained_root = str(tmp_path / "retained")
    out = tmp_path / "analysis_plan.json"
    argv = ["plan", "--retained-root", retained_root, "--retained-scores", str(tmp_path / "scores")]
    assert cli.main([*argv, "--subset", str(subset)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["order"] == "pair_seed100" and printed["total_gpu_hours_all"] == 0
    assert printed["models_with_retained_scores"] == 4
    # with the scores of one model removed that model is charged and the rest is not
    (tmp_path / "scores" / models[0].run_id / sr.RECORD_NAME).unlink()
    assert cli.main([*argv, "--subset", str(subset)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["models_to_encode"] == 1 and printed["total_gpu_hours_all"] == pytest.approx(
        0.68
    )
    _retain(tmp_path, models[0])  # the record is written again from the files
    # the analysis plan compares the trained arms with the untrained fused arm
    raw = next(m for m in models if m.cell_id == "mined_raw" and m.seed == 100)
    filt = next(m for m in models if m.cell_id == "mined_filter_bm25" and m.seed == 100)
    assert cli.main(
        ["analysis-plan", str(tmp_path / "enc"), str(out), "--runs", "0", "--retained-root",
         retained_root, "--retained-scores", str(tmp_path / "scores"), "--subset", str(subset),
         "--models", raw.run_id, filt.run_id]
    ) == 0  # fmt: skip
    plan = json.loads(out.read_text())
    assert plan["arms"][0] == "rrf" and plan["primary"] == [raw.arm, "rrf"]
    assert [filt.arm, "rrf"] in plan["estimates"] and [filt.arm, raw.arm] in plan["estimates"]
    assert plan["arm_form"].startswith("RRF of BM25") and ta.UNTRAINED_ARM == "rrf"
