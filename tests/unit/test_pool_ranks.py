"""Tests of the pool-rank measurement: sampling, reading, ranks, cache, features, tables."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ril.analysis import x3_tables as xt
from ril.training import pool_rank_jobs as jobs
from ril.training import pool_ranks as pr


def _meta(n: int = 40) -> list[dict[str, Any]]:
    return [
        {
            "dir": f"own{i % 5}__repo{i % 5}-{i}",
            "corpus_bytes": 100 * (i + 1),
            "positives": 1 + i % 3,
        }
        for i in range(n)
    ]


def test_size_bins_and_edges() -> None:
    edges = pr.size_edges([1, 2, 3, 4, 5, 6, 7, 8], 4)
    assert len(edges) == 3 and list(edges) == sorted(edges)
    assert pr.size_bin(0, edges) == 0
    assert pr.size_bin(100, edges) == 3
    assert pr.size_bin(edges[0], edges) == 0  # an edge goes to the lower bin


def test_build_instances_rejects_bad_dir() -> None:
    with pytest.raises(ValueError):
        pr.build_instances(
            [{"dir": "nounderscore-1", "corpus_bytes": 1, "positives": 1}], lambda r: False
        )


def test_stratified_sample_is_deterministic_and_balanced() -> None:
    insts, _ = pr.build_instances(_meta(), lambda r: r.startswith("own0/"))
    a = pr.stratified_sample(insts, 2, seed=0)
    b = pr.stratified_sample(list(reversed(insts)), 2, seed=0)
    assert [i.dir for i in a] == [i.dir for i in b]
    counts: dict[str, int] = {}
    for i in a:
        counts[i.stratum] = counts.get(i.stratum, 0) + 1
    assert all(v <= 2 for v in counts.values())
    assert {i.stratum for i in a} == {i.stratum for i in insts}
    c = pr.stratified_sample(insts, 2, seed=1)
    assert [i.dir for i in c] != [i.dir for i in a]


def test_instance_record_round_trip() -> None:
    insts, _ = pr.build_instances(_meta(4), lambda r: False)
    rec = pr.instance_record(insts[0])
    assert pr.instance_from_record(json.loads(json.dumps(rec))) == insts[0]


def test_code_text_forms() -> None:
    assert pr.code_text("a.py/f", "a.py/f\ndef f(): pass") == "def f(): pass"
    assert pr.code_text("a.py/f", "a.py/f\ndef f(): pass", "pool") == "a.py/f\ndef f(): pass"
    assert pr.code_text("a.py/f", "def f(): pass") == "def f(): pass"  # no id line: unchanged
    with pytest.raises(ValueError):
        pr.code_text("x", "y", "other")


def _instance_bytes() -> tuple[bytes, bytes, bytes]:
    corpus = "\n".join(
        json.dumps(
            {
                "_id": i,
                "title": "",
                "text": f"{i}\ndef {i.split('/')[-1]}(): return 1",
                "metadata": {},
            }
        )
        for i in ("a.py/f", "a.py/g", "b.py/C/h")
    ).encode()
    queries = json.dumps({"_id": "o__r-1", "text": "issue g", "metadata": {}}).encode()
    qrels = b"query-id\tcorpus-id\tscore\no__r-1\ta.py/g\t1\n"
    return corpus, queries, qrels


def test_parse_instance_and_errors() -> None:
    c, q, r = _instance_bytes()
    d = pr.parse_instance("o__r-1", c, q, r)
    assert d.ids == ["a.py/f", "a.py/g", "b.py/C/h"]
    assert d.texts[1] == "def g(): return 1"
    assert d.positives == ["a.py/g"]
    with pytest.raises(ValueError):
        pr.parse_instance("o__r-1", c, q + b"\n" + q, r)
    with pytest.raises(ValueError):
        pr.parse_instance("o__r-1", c, q, b"o__r-1\tmissing\t1\n")


def _zip_member(name: str, data: bytes, offset: int) -> tuple[bytes, dict[str, Any]]:
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = comp.compress(data) + comp.flush()
    nb = name.encode()
    head = struct.pack(
        "<IHHHHHIIIHH", 0x04034B50, 20, 0, 8, 0, 0, 0, len(raw), len(data), len(nb), 0
    )
    blob = head + nb + raw
    return blob, {
        "name": name,
        "offset": offset,
        "compressed": len(raw),
        "uncompressed": len(data),
        "method": 8,
    }


def test_fetch_instance_from_fake_archive() -> None:
    c, q, r = _instance_bytes()
    buf = b""
    members: dict[str, dict[str, Any]] = {}
    for kind, data in (("corpus", c), ("queries", q), ("qrels", r)):
        blob, m = _zip_member(f"train/python/o__r-1/{kind}", data, len(buf))
        buf += blob
        members[kind] = m

    def fetch(url: str, first: int, last: int) -> bytes:
        return buf[first : last + 1]

    d = pr.fetch_instance("u", members, "o__r-1", fetch)
    assert d.positives == ["a.py/g"] and len(d.texts) == 3


def test_positive_ranks_exclude_other_positives() -> None:
    ids = ["p1", "p2", "n1", "n2", "n3"]
    scores = [0.9, 0.5, 0.95, 0.5, 0.1]
    out = {r["positive"]: r for r in pr.positive_ranks(ids, scores, ["p2", "p1"])}
    assert out["p1"]["rank"] == 2 and out["p1"]["rank_all"] == 2
    # p2: one non-positive strictly higher (n1), p1 higher but a positive; n2 ties
    assert out["p2"]["rank"] == 2 and out["p2"]["rank_all"] == 3 and out["p2"]["ties"] == 1
    with pytest.raises(ValueError):
        pr.positive_ranks(ids, scores[:3], ["p1"])


def test_bm25_scores_rank_matching_text_first() -> None:
    s = pr.bm25_scores(["def parse(config): pass", "def render(): pass"], "parse config crash")
    assert s[0] > s[1]


class FakeEncoder:
    def __init__(self) -> None:
        self.encoded = 0

    def encode_documents(self, texts: Any, batch_size: int = 32) -> Any:
        self.encoded += len(texts)
        return np.asarray([[len(t), 1.0] for t in texts], dtype=np.float32)

    def encode_query(self, query: str) -> Any:
        return np.asarray([1.0, 0.0], dtype=np.float32)


def test_repo_vector_cache_reuses_within_repo() -> None:
    enc = FakeEncoder()
    cache = pr.RepoVectorCache()
    s1, n1 = cache.scores("r", ["a", "bb", "a"], enc.encode_query(""), enc, 8)
    assert n1 == 2 and list(s1) == [1.0, 2.0, 1.0]
    _, n2 = cache.scores("r", ["bb", "ccc"], enc.encode_query(""), enc, 8)
    assert n2 == 1
    _, n3 = cache.scores("other", ["bb"], enc.encode_query(""), enc, 8)
    assert n3 == 1  # cleared on a new repository
    assert cache.hits == 2 and cache.misses == 4


def test_prefetch_keeps_order_and_reports_errors() -> None:
    def load(n: str) -> pr.InstanceData:
        if n == "bad":
            raise ValueError("boom")
        return pr.InstanceData(n, "q", [], [], [], 0)

    got = list(pr.prefetch(["a", "bad", "c"], load, ahead=2))
    assert [g[0] for g in got] == ["a", "bad", "c"]
    assert got[1][1] is None and "boom" in str(got[1][2])


def test_resumable_jsonl(tmp_path: Path) -> None:
    p = str(tmp_path / "r.jsonl")
    pr.append_jsonl(p, {"dir": "a"})
    with open(p, "a", encoding="utf-8") as h:
        h.write('{"dir": "torn')
    assert pr.done_dirs(p) == {"a"}


def test_feature_rows_have_no_text_and_all_teachers() -> None:
    insts, _ = pr.build_instances(
        [{"dir": "o__r-1", "corpus_bytes": 10, "positives": 2}], lambda r: True
    )
    d = pr.InstanceData("o__r-1", "q", ["x", "y", "z"], ["t"] * 3, ["x", "y"], 10)
    rows = [pr.rank_record("t1", d, [3, 1, 2], {}), pr.rank_record("t2", d, [1, 2, 3], {})]
    feats = pr.feature_rows({i.dir: i for i in insts}, rows, ["t1", "t2"])
    assert len(feats) == 2
    # x: t1 score 3 vs the only non-positive z at 2 -> 1; t2 score 1 vs z at 3 -> 2
    assert feats[0]["positive_key"] == pr.positive_key("x") and len(feats[0]["positive_key"]) == 16
    assert feats[0]["positive_id"] == "x" and feats[0]["rank_t1"] == 1 and feats[0]["rank_t2"] == 2
    assert feats[0]["rank_all_t2"] == 3
    assert feats[1]["rank_t1"] == 2 and feats[1]["held_out"] == 1
    assert set(feats[0]) <= set(pr.feature_columns(["t1", "t2"]))


def test_gpu_hours_estimate() -> None:
    assert pr.gpu_hours_estimate(3600 * 100, 100) == pytest.approx(1.0)
    assert pr.gpu_hours_estimate(3600 * 100, 100, 0.5, encoders=2) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        pr.gpu_hours_estimate(1, 0)


def test_dedup_bins() -> None:
    bins = jobs.dedup_bins({"a": [1], "b": [1] * 3, "c": [1] * 10, "d": [1] * 50})
    assert bins == {"d1": ["a"], "d2-9": ["b"], "d10-49": ["c"], "d50+": ["d"]}


def test_held_out_predicate(tmp_path: Path) -> None:
    doc = {
        "schema_version": 2,
        "repos": ["a/b"],
        "aliases": {},
        "tiers": {"loc_bench": {"repos": ["c/d"]}},
    }
    p = tmp_path / "h.json"
    p.write_text(json.dumps(doc))
    pred = jobs.held_out_predicate(str(p), None)
    assert pred("a/b") and pred("c/d") and not pred("e/f")


# ---- tables


def _fixture(tmp_path: Path) -> tuple[str, str, str]:
    meta = [{"dir": f"o{i}__r{i}-{i}", "corpus_bytes": 1000 + i, "positives": 2} for i in range(8)]
    insts, edges = pr.build_instances(meta, lambda r: r in {"o0/r0", "o1/r1"}, bins=2)
    sample = {
        "pool_instances": 8,
        "pool_positives": 16,
        "pool_strata": pr.stratum_totals(insts),
        "sample": [pr.instance_record(i) for i in insts],
    }
    sp = tmp_path / "sample.json"
    sp.write_text(json.dumps(sample))
    rows = []
    for j, inst in enumerate(insts):
        for t, base in (("a", 1), ("b", 3)):
            rows.append(
                {
                    "dir": inst.dir,
                    "teacher": t,
                    "functions": 100,
                    "corpus_bytes": 1000,
                    "encoded": 100,
                    "encode_seconds": 1.0,
                    "ranks": [
                        {
                            "positive": "p",
                            "rank": base + j * 10,
                            "rank_all": base + j * 10,
                            "ties": 0,
                        },
                        {"positive": "q", "rank": 50 + j, "rank_all": 51 + j, "ties": 0},
                    ],
                }
            )
    rp = tmp_path / "ranks.jsonl"
    rp.write_text("\n".join(json.dumps(r) for r in rows))
    cfg = {
        "experiment_id": "E",
        "teachers": ["a", "b"],
        "k_cuts": [10, 40],
        "bootstrap_draws": 50,
        "seed": 0,
        "table_prefix": "t",
    }
    cp = tmp_path / "cfg.yaml"
    cp.write_text(json.dumps(cfg))  # JSON is YAML
    return str(sp), str(rp), str(cp)


def test_write_tables_end_to_end(tmp_path: Path) -> None:
    sp, rp, cp = _fixture(tmp_path)
    out = xt.write_tables(sp, [rp], cp, str(tmp_path / "out"))
    top = {(r["teacher"], r["k"]): r for r in out["topk"]}
    # teacher a: positive p rank 1, 11, 21, ...: top10 holds only the first instance's p
    assert top[("a", 10)]["sample_pct_dirs_none"] == pytest.approx(87.5)
    assert top[("a", 10)]["pool_positives_inside"] == 1
    assert top[("a", 40)]["pool_positives_inside"] == 4
    lo, hi = top[("a", 40)]["pool_positives_inside_ci"]
    assert lo <= 4 <= hi
    agree = [r for r in out["agreement"] if r["measure"] == "spearman_rank"][0]
    assert agree["value"] > 0.95
    head = (tmp_path / "out" / "t_features.csv").read_text().splitlines()[0].split(",")
    assert "positive_key" in head and "positive_id" not in head
    assert out["feature_rows"] == 16
    assert out["cost"]["teachers"]["a"]["texts_per_second"] == 100.0
    assert len(out["config_hash"]) == 64


def test_stratified_estimates_need_every_stratum() -> None:
    with pytest.raises(ValueError):
        xt.stratified_estimates(
            ["x"],
            np.ones(1),
            np.ones(1),
            np.ones(1),
            {"x": {"positives": 1, "dirs": 1}, "y": {"positives": 1, "dirs": 1}},
        )


def test_spearman_and_kappa() -> None:
    a = np.asarray([1, 2, 3, 4.0])
    assert xt.spearman(a, a) == pytest.approx(1.0)
    assert xt.spearman(a, -a) == pytest.approx(-1.0)
    assert xt.kappa(np.asarray([1, 0, 1, 0]), np.asarray([1, 0, 1, 0])) == pytest.approx(1.0)
    assert np.isnan(xt.kappa(np.ones(3), np.ones(3)))


def test_relabel_other_text_form() -> None:
    assert xt.relabel({"teacher": "a", "form": "pool"}, "code")["teacher"] == "a@pool"
    assert xt.relabel({"teacher": "a", "form": "code"}, "code")["teacher"] == "a"
    assert xt.relabel({"teacher": "bm25", "form": "pool"}, "code")["teacher"] == "bm25"


def test_cost_estimate_weights_dedup_bins() -> None:
    sample = {"pool_strata": {"x": {"corpus_bytes": 1000}}}
    dense = [{"teacher": "a", "encoded": 100, "encode_seconds": 1.0}]
    dedup = [
        {"bin": "d1", "texts": 10, "distinct": 10},
        {"bin": "d50+", "texts": 100, "distinct": 10},
    ]
    out = xt.cost_estimate(sample, dense, dedup, 1.0, {"d1": 500, "d50+": 500, "d2-9": 0})
    assert out["dedup_ratio"] == pytest.approx(0.55)
    assert out["dedup_ratio_pooled"] == pytest.approx(20 / 110, abs=1e-4)
    assert out["teachers"]["a"]["gpu_hours_no_dedup"] == pytest.approx(round(1000 / 100 / 3600, 2))


def test_group_members_and_reference_instances() -> None:
    members = [
        {"name": "ref/", "offset": 0},
        {"name": "ref/p_o__r-7/corpus.jsonl", "uncompressed": 50, "offset": 1},
        {"name": "ref/p_o__r-7/queries.jsonl", "offset": 2},
        {"name": "ref/p_o__r-7/qrels/test.tsv", "offset": 3},
        {"name": "ref/p_o__r-8/corpus.jsonl", "uncompressed": 5, "offset": 4},
        {"name": "other/x/corpus.jsonl", "offset": 5},
    ]
    groups = pr.group_members(members, "ref/")
    assert list(groups) == ["p_o__r-7"]  # incomplete p_o__r-8 left out
    insts = pr.reference_instances(groups, "p_")
    assert insts[0].repo == "o/r" and insts[0].pr == 7 and insts[0].corpus_bytes == 50
    with pytest.raises(ValueError):
        pr.reference_instances({"noseparator-1": groups["p_o__r-7"]}, "p_")
