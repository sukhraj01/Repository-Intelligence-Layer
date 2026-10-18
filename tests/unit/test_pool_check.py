"""Tests for the pool metadata check (ril.training.pool_check)."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from ril.training import pool_check as pc


def _zip_with_instances() -> tuple[bytes, list[dict[str, object]]]:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("train/python/", b"")
        for name, pos in (("Own__repo-12", ["a.py/f", "a.py/C/g"]), ("o2__re-po-7", ["b.py/h"])):
            zf.writestr(
                f"train/python/{name}/corpus.jsonl",
                "\n".join(
                    json.dumps({"_id": i, "text": "x" * 50, "metadata": {}}) for i in pos + ["z/n"]
                ),
            )
            q = {
                "_id": name,
                "text": "issue",
                "metadata": {"repo": "Own/repo", "base_commit": "abc"},
            }
            zf.writestr(f"train/python/{name}/queries.jsonl", json.dumps(q) + "\n")
            zf.writestr(
                f"train/python/{name}/qrels/test.tsv",
                "query-id\tcorpus-id\tscore\n" + "".join(f"{name}\t{i}\t1\n" for i in pos),
            )
    data = buf.getvalue()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = [
            {
                "name": i.filename,
                "uncompressed": i.file_size,
                "compressed": i.compress_size,
                "method": i.compress_type,
                "offset": i.header_offset,
            }
            for i in zf.infolist()
        ]
    return data, members


def test_split_instance_dir() -> None:
    assert pc.split_instance_dir("Own__Repo-12") == ("own/repo", 12)
    assert pc.split_instance_dir("o__re-po-2-7/") == ("o/re-po-2", 7)
    assert pc.split_instance_dir("o__name2-100") == ("o/name2", 100)


@pytest.mark.parametrize("bad", ["noseparator-1", "o__r", "o__-3", "__r-3", ""])
def test_split_instance_dir_unreadable(bad: str) -> None:
    assert pc.split_instance_dir(bad) is None


def test_reference_pair_skips_pro_ids() -> None:
    assert pc.reference_pair("pallets__flask-5014") == ("pallets/flask", 5014)
    assert pc.reference_pair("instance_NodeBB__NodeBB-04998908ba67-vnan") is None


def test_pool_instances_and_decode_roundtrip() -> None:
    data, members = _zip_with_instances()
    inst = pc.pool_instances(members)
    assert sorted(inst) == ["Own__repo-12", "o2__re-po-7"]
    q, r = inst["o2__re-po-7"]["queries"], inst["o2__re-po-7"]["qrels"]
    first, last = pc.span_for([q, r])
    blob = data[first : last + 1]
    qt = pc.decode_member(blob, int(q["offset"]) - first, q).decode()
    rt = pc.decode_member(blob, int(r["offset"]) - first, r).decode()
    assert pc.parse_query(qt.splitlines()[0])["base_commit"] == "abc"
    assert pc.parse_qrels(rt) == [("b.py/h", 1)]


def test_incomplete_instances_dropped() -> None:
    _, members = _zip_with_instances()
    kept = [m for m in members if not str(m["name"]).endswith("o2__re-po-7/queries.jsonl")]
    assert "o2__re-po-7" not in pc.pool_instances(kept)


def test_decode_member_rejects_corruption() -> None:
    data, members = _zip_with_instances()
    m = next(x for x in members if str(x["name"]).endswith("Own__repo-12/queries.jsonl"))
    off = int(m["offset"])
    with pytest.raises(ValueError):
        pc.decode_member(data, off + 1, m)  # not a header
    with pytest.raises(ValueError):
        pc.decode_member(data[: off + 40], off, m)  # truncated
    with pytest.raises(ValueError):
        pc.decode_member(data, off, {**m, "uncompressed": int(m["uncompressed"]) + 1})


def test_parse_corpus_counts_duplicates() -> None:
    text = (
        "\n".join(json.dumps({"_id": i, "text": "t", "metadata": {}}) for i in ["a", "b", "a"])
        + "\n"
    )
    info = pc.parse_corpus(text)
    assert info["functions"] == 3 and info["distinct_ids"] == 2


def test_sample_names_deterministic_and_seed_sensitive() -> None:
    names = [f"o__r-{i}" for i in range(500)]
    a = pc.sample_names(names, 50, 0)
    assert a == pc.sample_names(reversed(names), 50, 0)
    assert a != pc.sample_names(names, 50, 1)
    assert len(set(a)) == 50
    assert len(pc.sample_names(names[:5], 50, 0)) == 5


def test_percentile_and_describe() -> None:
    assert pc.percentile([1, 2, 3, 4], 50) == 2.5
    assert pc.describe([5])["p95"] == 5
    assert pc.describe([])["n"] == 0
    with pytest.raises(ValueError):
        pc.percentile([], 50)


def test_pr_overlap_exact_and_name_only() -> None:
    pool = [("a/b", 1), ("c/d", 2), ("x/same", 9)]
    refs = {"v": ["a__b-1", "a__b-3", "other__same-9", "instance_a__b-ff00-vx"]}
    out = pc.pr_overlap(pool, refs)["v"]
    assert out["exact_pairs"] == 1 and out["exact_list"] == ["a/b#1"]
    assert out["name_only_pairs"] == 2  # a/b#1 and other/same#9 (owner ignored)
    assert out["reference_pairs"] == 3


def test_positives_summary_zero_positive_instance() -> None:
    s = pc.positives_summary([{"positives": 0}, {"positives": 2}, {"positives": 15}])
    assert s["instances_with_zero_positives"] == 1 and s["positives_total"] == 17
    assert s["positives_histogram"] == {0: 1, 2: 1, 10: 1}


def test_split_rows_keeps_unicode_line_separators_inside_strings() -> None:
    row = json.dumps({"_id": "x", "text": "a\u2028b\x0bc"}, ensure_ascii=False)
    assert "\u2028" in row and len(row.splitlines()) > 1  # the trap
    assert pc.split_rows(row + "\n\n") == [row]
    assert pc.parse_query(row)["id"] == "x"
    info = pc.parse_corpus(row + "\n")
    assert info["functions"] == 1


def test_tables_from_minimal_summary() -> None:
    pos = {
        "positives_per_instance": {"mean": 2.0, "p50": 2.0, "p95": 5.0, "max": 6.0},
        "instances_with_zero_positives": 0,
    }
    summary = {
        "instances": 2,
        "distinct_repos": 1,
        "distinct_pairs": 2,
        "query_metadata_key_sets": {"base_commit|repo": 2},
        "qrel_rows_total": 4,
        "positives_all_instances": pos,
        "sample": {
            "read": 2,
            "functions_per_instance": {
                "mean": 10.0,
                "p50": 9.0,
                "p5": 1.0,
                "p95": 20.0,
                "min": 1.0,
                "max": 21.0,
            },
            "positives": {"positives_per_instance": {"mean": 2.0, "p50": 2.0}},
            "positives_found_in_corpus": 4,
            "positives_total": 4,
            "instances_with_corpus_at_most_40_functions": 2,
        },
        "base_commit_hits_with_verified": 0,
        "fetch_errors": 0,
        "overlap": {
            "v": {
                "reference_ids": 3,
                "reference_pairs": 3,
                "exact_pairs": 0,
                "exact_repos": 0,
                "name_only_pairs": 0,
            }
        },
    }
    assert pc.overlap_table(summary)[0]["reference"] == "v"
    facts = {r["quantity"]: r["value"] for r in pc.facts_table(summary)}
    assert facts["sample_positives_found_in_corpus"] == "4 of 4" and facts["qrel_rows_total"] == 4
