"""The RQ2 arms differ only through the three supervision hooks.

``docs/08_experimental_design.md``: "Varies: the supervision strategy, and nothing else." Each
non-RAW arm is run with its hook at the identity limit (FILTER at K = infinity, WEIGHT with a form
whose weights are all 1, CURRICULUM with a constant difficulty); then the batches, the first
gradients and the trained parameters must be bit-identical to RAW's, which proves the code path
outside the hooks is the same. Positive controls show that each hook, away from its identity,
does change what it should and only that.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")  # Ada only: the local machine has no torch (Makefile header)
pytestmark = pytest.mark.torch

import zlib
from pathlib import Path
from typing import Any

from ril.training.encoders import build_encoder
from ril.training.supervision import ARM_HOOK_FIELDS, Arm, MappingKRank
from ril.training.training import (
    batch_loss,
    check_comparable,
    make_planner,
    prepare_arm,
    train,
)
from tests.unit._training_fixtures import synthetic_examples, train_config

IDENTITY_ARMS: dict[str, dict[str, Any]] = {
    "RAW": {"name": "RAW"},
    "FILTER": {"name": "FILTER", "filter": {"teacher": "t", "k": None, "level": "positive"}},
    "WEIGHT": {
        "name": "WEIGHT",
        "weight": {"teacher": "t", "form": "power", "k": 1e12, "param": 1.0},
    },
    "CURRICULUM": {"name": "CURRICULUM", "ordering": {"teacher": "flat"}},
}


def _signals() -> tuple[list[Any], dict[str, MappingKRank]]:
    exs = synthetic_examples(repos=3, prs=4)
    ranks = {
        (e.instance_id, p): 1 + (zlib.crc32(p.encode()) % 50) for e in exs for p in e.positive_ids
    }
    flat = {k: 1 for k in ranks}
    return exs, {"t": MappingKRank(ranks, "t"), "flat": MappingKRank(flat, "flat")}


def _first_grads(cfg: dict[str, Any], exs: list[Any], sig: dict[str, MappingKRank]) -> list[Any]:
    arm, kept, weights, _ = prepare_arm(cfg, exs, sig)
    batch = next(make_planner(cfg, arm, kept, weights, None).batches(1))
    enc = build_encoder(cfg["model"], device="cpu", seed=int(cfg["seed"]))
    loss, _ = batch_loss(enc, batch, cfg["loss"])
    loss.backward()  # type: ignore[no-untyped-call,unused-ignore]
    return [p.grad.clone() for p in enc.module.parameters() if p.grad is not None]


def test_arm_is_exactly_three_hooks() -> None:
    assert ARM_HOOK_FIELDS == ("filter", "weigher", "ordering")
    assert tuple(Arm.__dataclass_fields__) == ("name", *ARM_HOOK_FIELDS)


def test_identity_hooks_give_identical_batches_gradients_and_weights(tmp_path: Path) -> None:
    exs, sig = _signals()
    cfgs = {n: train_config(arm=a, exp_id=f"id_{n}") for n, a in IDENTITY_ARMS.items()}
    check_comparable(list(cfgs.values()))
    plans, grads, params = {}, {}, {}
    for name, cfg in cfgs.items():
        arm, kept, weights, _ = prepare_arm(cfg, exs, sig)
        planner = make_planner(cfg, arm, kept, weights, None)
        plans[name] = [b.fingerprint() for b in planner.batches(int(cfg["budget"]["updates"]))]
        grads[name] = _first_grads(cfg, exs, sig)
        rec = train(
            cfg,
            exs,
            results_root=str(tmp_path / "res"),
            work_root=str(tmp_path / "w"),
            date="2026-01-01",
            signals=sig,
        )
        assert rec["finished"]
        state = torch.load(Path(rec["final_model"]) / "tiny.pt", weights_only=True)
        params[name] = state
        assert rec["plan_sha256"]
    for name in IDENTITY_ARMS:
        assert plans[name] == plans["RAW"], name
        for g, r in zip(grads[name], grads["RAW"], strict=True):
            assert torch.equal(g, r), name
        for k in params["RAW"]:
            assert torch.equal(params[name][k], params["RAW"][k]), (name, k)


def test_each_hook_away_from_identity_changes_only_its_part() -> None:
    exs, sig = _signals()
    raw = train_config(arm=IDENTITY_ARMS["RAW"])

    def plan(cfg: dict[str, Any]) -> list[Any]:
        arm, kept, weights, _ = prepare_arm(cfg, exs, sig)
        return list(make_planner(cfg, arm, kept, weights, None).batches(6))

    base = plan(raw)
    filt = plan(
        train_config(
            arm={"name": "FILTER", "filter": {"teacher": "t", "k": 25, "level": "positive"}}
        )
    )
    assert [b.fingerprint() for b in filt] != [b.fingerprint() for b in base]
    weight = plan(
        train_config(
            arm={
                "name": "WEIGHT",
                "weight": {"teacher": "t", "form": "power", "k": 5, "param": 1.0},
            }
        )
    )
    # WEIGHT changes the weights and nothing else in the batches
    for a, b in zip(weight, base, strict=True):
        assert a.instance_ids == b.instance_ids and a.docs == b.docs
        assert (a.pos_mask == b.pos_mask).all() and (a.valid_mask == b.valid_mask).all()
    assert any((a.weights != b.weights).any() for a, b in zip(weight, base, strict=True))
    cur = plan(train_config(arm={"name": "CURRICULUM", "ordering": {"teacher": "t"}}))
    assert [b.instance_ids for b in cur] != [b.instance_ids for b in base]


def test_configurations_differing_outside_the_arm_are_refused() -> None:
    a = train_config(arm=IDENTITY_ARMS["RAW"])
    b = train_config(arm=IDENTITY_ARMS["FILTER"], exp_id="other")
    check_comparable([a, b])
    c = train_config(arm=IDENTITY_ARMS["WEIGHT"])
    c["optimizer"] = {**c["optimizer"], "lr": 0.01}
    with pytest.raises(ValueError, match="optimizer"):
        check_comparable([a, c])
    d = train_config(arm=IDENTITY_ARMS["WEIGHT"], negatives={"name": "teacher_top_m", "m": 5})
    with pytest.raises(ValueError, match="negatives"):
        check_comparable([a, d])


def test_teacher_equal_to_base_is_recorded_not_refused() -> None:
    from ril.training.training import teacher_equals_base

    cfg = train_config(
        arm={"name": "FILTER", "filter": {"teacher": "coderankembed", "k": 20, "level": "positive"}}
    )
    assert not teacher_equals_base(cfg)
    cfg["model"] = {"kind": "sentence_transformers", "encoder": "coderankembed", "max_tokens": 512}
    assert teacher_equals_base(cfg)
