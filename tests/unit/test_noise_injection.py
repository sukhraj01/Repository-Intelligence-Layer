"""Injected label noise (E-PILOT-NOISE, D45): rate, disjointness, determinism, hidden indicator."""

from __future__ import annotations

import dataclasses
import json
import math
import random

import numpy as np
import pytest

from ril.training import pool_ranks as pr
from ril.training.noise import (
    NoiseLedger,
    auc_injected_vs_clean,
    decode_scores,
    encode_scores,
    inject,
    noisy_ranks,
    noisy_signal,
    split_function_id,
)
from ril.training.pool_reader import PoolExample
from ril.training.supervision import (
    OracleClean,
    UnitWeight,
    arm_from_config,
)
from tests.unit._training_fixtures import synthetic_examples


@pytest.fixture(scope="module")
def pool() -> list[PoolExample]:
    return synthetic_examples(repos=20, prs=100, funcs=24)


def test_rate_within_binomial_tolerance(pool: list[PoolExample]) -> None:
    n = len(pool)
    for rate in (0.2, 0.4):
        _, led = inject(pool, rate, seed=0)
        sd = math.sqrt(n * rate * (1 - rate))
        assert abs(led.injected_count() - n * rate) < 4 * sd
        assert led.uninjectable == 0


def test_replacement_never_overlaps_true_positives(pool: list[PoolExample]) -> None:
    noised, led = inject(pool, 0.4, seed=1)
    for orig, new in zip(pool, noised, strict=True):
        assert new.instance_id == orig.instance_id and new.query == orig.query
        assert len(new.positive_ids) == len(orig.positive_ids)
        if led.is_injected(orig.instance_id):
            assert not set(new.positive_ids) & set(orig.positive_ids)
            assert set(orig.positive_ids) <= set(new.masked_ids)
            assert set(new.positive_ids) <= set(orig.candidate_ids)
            assert not set(new.positive_ids) & set(new.candidate_ids)
        else:
            assert new is orig


def test_rate_zero_is_the_identity(pool: list[PoolExample]) -> None:
    noised, led = inject(pool, 0.0, seed=3)
    assert all(a is b for a, b in zip(noised, pool, strict=True))
    assert led.injected_count() == 0 and led.clean_count() == len(pool)


def test_same_realisation_for_every_cell_and_any_order(pool: list[PoolExample]) -> None:
    a, la = inject(pool, 0.2, seed=5)
    shuffled = list(pool)
    random.Random(0).shuffle(shuffled)
    b, lb = inject(shuffled, 0.2, seed=5)
    assert la.digest() == lb.digest()
    assert {e.instance_id: e.positive_ids for e in a} == {e.instance_id: e.positive_ids for e in b}
    _, lc = inject(pool, 0.2, seed=6)
    assert lc.digest() != la.digest()


def test_realisations_are_nested_across_rates(pool: list[PoolExample]) -> None:
    _, low = inject(pool, 0.2, seed=2)
    _, high = inject(pool, 0.4, seed=2)
    assert all(high.is_injected(i) for i, v in low.injected.items() if v)
    assert high.injected_count() > low.injected_count()


def test_the_indicator_is_not_a_field_of_the_example(pool: list[PoolExample]) -> None:
    noised, _ = inject(pool, 0.4, seed=0)
    names = {f.name for f in dataclasses.fields(PoolExample)}
    assert not any("noise" in n or "inject" in n or "clean" in n for n in names)
    assert {f.name for f in dataclasses.fields(noised[0])} == names


def test_only_oracle_and_matched_subsample_read_the_ledger(pool: list[PoolExample]) -> None:
    noised, led = inject(pool, 0.4, seed=0)
    raw = arm_from_config({"name": "RAW"}, {}, 0, led)
    assert raw.filter.name == "keep_all" and isinstance(raw.weigher, UnitWeight)
    with pytest.raises(ValueError):
        arm_from_config({"name": "ORACLE_CLEAN"}, {}, 0)
    oracle = arm_from_config({"name": "ORACLE_CLEAN"}, {}, 0, led)
    assert isinstance(oracle.filter, OracleClean)
    kept, rep = oracle.filter.apply(noised)
    assert len(kept) == led.clean_count() == rep.examples_out
    assert not any(led.is_injected(e.instance_id) for e in kept)
    sub = arm_from_config(
        {"name": "RAW_SUBSAMPLE", "subsample": {"size": "match_clean", "draw": 0}}, {}, 0, led
    )
    out, _ = sub.filter.apply(noised)
    assert len(out) == led.clean_count()
    with pytest.raises(ValueError):
        arm_from_config({"name": "RAW_SUBSAMPLE", "subsample": {"size": "match_clean"}}, {}, 0)


def test_too_small_a_snapshot_is_counted_not_noised() -> None:
    ex = synthetic_examples(repos=1, prs=1, funcs=24)[0]
    tiny = dataclasses.replace(
        ex,
        candidate_ids=ex.candidate_ids[:1],
        candidate_texts=ex.candidate_texts[:1],
    )
    if len(tiny.positive_ids) == 1:
        tiny = dataclasses.replace(
            tiny,
            positive_ids=tiny.positive_ids + ("x/y",),
            positive_texts=tiny.positive_texts + ("t",),
        )
    out, led = inject([tiny], 1.0, seed=0)
    assert out[0] is tiny and led.uninjectable == 1 and led.injected_count() == 0


def test_score_store_round_trip_is_exact() -> None:
    s = np.array([0.1, -3.5, 7.25, 1e-3], dtype=np.float32)
    back = decode_scores(encode_scores(s.tolist()))
    assert np.array_equal(back.astype(np.float32), s)


def test_noisy_ranks_match_brute_force_and_clean_pairs_match_the_published_rank(
    pool: list[PoolExample],
) -> None:
    noised, led = inject(pool, 0.4, seed=0)
    rng = np.random.default_rng(0)
    store = {e.instance_id: rng.random(len(e.ids)) for e in pool}
    for orig, new in list(zip(pool, noised, strict=True))[:60]:
        s = store[orig.instance_id]
        rows = {r["positive"]: r["rank"] for r in noisy_ranks(orig, new, s)}
        index = {f: i for i, f in enumerate(orig.ids)}
        for p in new.positive_ids:
            better = sum(
                1 for f in orig.ids if f not in new.positive_ids and s[index[f]] > s[index[p]]
            )
            assert rows[p] == 1 + better
        if not led.is_injected(orig.instance_id):
            ref = {
                r["positive"]: r["rank"] for r in pr.positive_ranks(orig.ids, s, orig.positive_ids)
            }
            assert rows == ref
    sig = noisy_signal(pool, noised, store, "t")
    ex = noised[0]
    assert sig.example_rank(ex) == min(sig.positive_rank(ex, p) for p in ex.positive_ids)


def test_auc_known_values() -> None:
    assert auc_injected_vs_clean([5, 6, 7], [1, 2, 3]) == 1.0
    assert auc_injected_vs_clean([1, 2, 3], [5, 6, 7]) == 0.0
    assert auc_injected_vs_clean([2, 2], [2, 2]) == 0.5
    assert math.isnan(auc_injected_vs_clean([], [1]))
    assert auc_injected_vs_clean([1, 3], [2]) == 0.5


def test_ledger_summary_is_json_ready(pool: list[PoolExample]) -> None:
    _, led = inject(pool, 0.2, seed=0)
    assert isinstance(led, NoiseLedger)
    s = led.summary()
    assert s["pairs"] == len(pool) and s["injected"] + s["clean"] == len(pool)
    assert len(s["digest"]) == 64


# --------------------------------------------------------------------------- sibling kind (D54)


def _sibling_pool() -> list[PoolExample]:
    return synthetic_examples(repos=10, prs=60, funcs=24)


def test_split_function_id_forms() -> None:
    assert split_function_id("pkg/mod0.py/Klass1/run") == ("pkg", "pkg/mod0.py", "Klass1")
    assert split_function_id("pkg/mod0.py/run") == ("pkg", "pkg/mod0.py", None)
    assert split_function_id("a/b/c.py/A/B/run") == ("a/b", "a/b/c.py", "A/B")
    assert split_function_id("top.py/run") == ("", "top.py", None)


def test_sibling_same_pairs_as_uniform_and_rate_in_tolerance() -> None:
    pool = _sibling_pool()
    _, uni = inject(pool, 0.4, seed=0)
    _, sib = inject(pool, 0.4, seed=0, kind="sibling")
    assert uni.injected == sib.injected  # the same pairs are noised; only the replacement differs
    sd = math.sqrt(len(pool) * 0.4 * 0.6)
    assert abs(sib.injected_count() - len(pool) * 0.4) < 4 * sd


def test_sibling_replacements_are_non_positives_from_the_stated_level() -> None:
    pool = _sibling_pool()
    noised, led = inject(pool, 0.4, seed=1, kind="sibling")
    seen = set()
    for orig, new in zip(pool, noised, strict=True):
        if not led.is_injected(orig.instance_id):
            assert new is orig
            continue
        assert not set(new.positive_ids) & set(orig.positive_ids)
        assert set(new.positive_ids) <= set(orig.candidate_ids)
        assert len(new.positive_ids) == len(orig.positive_ids)
        assert set(orig.positive_ids) <= set(new.masked_ids)
        level = led.levels[orig.instance_id]
        seen.add(level)
        files = {split_function_id(p)[1] for p in orig.positive_ids}
        dirs = {split_function_id(p)[0] for p in orig.positive_ids}
        if level == "file":
            assert {split_function_id(p)[1] for p in new.positive_ids} <= files
        elif level == "directory":
            assert {split_function_id(p)[0] for p in new.positive_ids} <= dirs
    assert "file" in seen


def test_sibling_falls_back_when_the_file_is_too_small() -> None:
    ex = synthetic_examples(repos=1, prs=1, funcs=24)[0]
    pos = ("pkg/lonely.py/only", "pkg/other.py/a")
    cand = ("pkg/other.py/b", "pkg/third.py/c", "pkg/third.py/d", "z/y.py/e")
    ex = dataclasses.replace(
        ex,
        positive_ids=pos,
        positive_texts=("p0", "p1"),
        candidate_ids=cand,
        candidate_texts=("c0", "c1", "c2", "c3"),
    )
    new, led = inject([ex], 1.0, seed=0, kind="sibling")
    # files {lonely, other} hold one other function (< 2 positives): the directory level (pkg) does
    assert led.levels[ex.instance_id] == "directory"
    assert set(new[0].positive_ids) <= {"pkg/other.py/b", "pkg/third.py/c", "pkg/third.py/d"}
    assert led.level_shares()["directory"] == 1.0


def test_sibling_uniform_level_is_the_last_resort() -> None:
    ex = synthetic_examples(repos=1, prs=1, funcs=24)[0]
    ex = dataclasses.replace(
        ex,
        positive_ids=("a/x.py/p",),
        positive_texts=("p",),
        candidate_ids=("b/y.py/q", "c/z.py/r"),
        candidate_texts=("q", "r"),
    )
    _, led = inject([ex], 1.0, seed=3, kind="sibling")
    assert led.levels[ex.instance_id] == "uniform"


def test_sibling_is_deterministic_hidden_and_distinct_from_uniform() -> None:
    pool = _sibling_pool()
    a, la = inject(pool, 0.4, seed=4, kind="sibling")
    shuffled = list(pool)
    random.Random(1).shuffle(shuffled)
    b, lb = inject(shuffled, 0.4, seed=4, kind="sibling")
    assert la.digest() == lb.digest()
    assert {e.instance_id: e.positive_ids for e in a} == {e.instance_id: e.positive_ids for e in b}
    _, uni = inject(pool, 0.4, seed=4)
    assert uni.digest() != la.digest()
    assert not hasattr(a[0], "injected") and "levels" not in {
        f.name for f in dataclasses.fields(a[0])
    }
    summary = la.summary()
    assert summary["kind"] == "sibling" and abs(sum(summary["level_shares"].values()) - 1) < 1e-9
    json.dumps(summary)


def test_uniform_digest_and_summary_are_unchanged_by_the_new_kind() -> None:
    pool = _sibling_pool()
    _, led = inject(pool, 0.2, seed=0)
    assert led.kind == "uniform" and led.level_shares() == {} and "kind" not in led.summary()
    assert led.summary()["version"] == "noise-dose/v1"


def test_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError):
        inject(_sibling_pool(), 0.2, seed=0, kind="nearby")


def test_sibling_ranks_come_from_stored_scores_for_every_replacement() -> None:
    pool = _sibling_pool()[:40]
    noised, led = inject(pool, 0.5, seed=2, kind="sibling")
    rng = np.random.default_rng(0)
    store = {ex.instance_id: rng.random(len(ex.ids)) for ex in pool}
    sig = noisy_signal(pool, noised, store, "t")
    for ex in noised:
        for p in ex.positive_ids:
            assert sig.positive_rank(ex, p) >= 1
    del store[pool[0].instance_id]
    with pytest.raises(KeyError):
        noisy_signal(pool, noised, store, "t")
