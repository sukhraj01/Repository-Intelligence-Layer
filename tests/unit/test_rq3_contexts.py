"""Retrieved contexts of the executable subset on synthetic inputs (E-RQ3-CONTEXTS, D108)."""

from __future__ import annotations

import tarfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ril.analysis.rq3_contexts_tables import (
    context_rows,
    coverage_summary,
    file_manifest,
    load_records,
    size_summary,
)
from ril.assembly.assemble import UnitText
from ril.assembly.rq3_contexts import (
    Arm,
    ContextSpec,
    InputGroup,
    build_instance,
    compare_dirs,
    decode_record,
    default_arms,
    draw_instances,
    encode_record,
    level_gold,
    locate,
    vector_checks,
    write_archive,
    write_atomic,
)
from ril.assembly.tokens import ApproxTokenizer

TOK = ApproxTokenizer()
META = {"instance": "o__r-1", "repo_id": "o/r", "base_commit": "abc"}


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


def _arrays() -> dict[str, Any]:
    bm25 = np.asarray([5.0, 4.0, 3.0, 2.0, 1.0, 0.5])
    return {
        "scores_L2": bm25,
        "gold_L2_units_all": np.asarray([1, 5], dtype=np.int32),
        "gold_L2_units_all_nomod": np.asarray([1], dtype=np.int32),
        "gold_L3_units_all": np.asarray([5], dtype=np.int32),
        "gold_L3_units_all_nomod": np.asarray([], dtype=np.int32),
    }


def _dense() -> dict[str, Any]:
    return {"dense_L2": np.asarray([0.1, 0.2, 0.3, 0.4, 0.5, 0.9])}


def _spec(budgets: tuple[int, ...] = (60, 100000)) -> ContextSpec:
    return ContextSpec(budgets=budgets, max_unit_tokens=1000, candidates=6, rrf_k=10)


def _record(budgets: tuple[int, ...] = (60, 100000)) -> dict[str, Any]:
    return build_instance(
        META, _arrays(), _dense(), _units(), _spec(budgets), default_arms(10), TOK
    )


def test_arms_rank_differently_and_every_cell_is_built() -> None:
    rec = _record()
    assert sorted(rec["contexts"]) == sorted(
        f"{a}|{b}" for a in ("bm25", "dense", "rrf") for b in (60, 100000)
    )
    first = {a: rec["contexts"][f"{a}|100000"]["manifest"]["entries"] for a in ("bm25", "dense")}
    ranks = {a: {e["unit_id"]: e["rank"] for e in v} for a, v in first.items()}
    assert ranks["bm25"]["a.py::u0"] == 1
    assert ranks["dense"]["d.py::u5"] == 1


def test_budget_is_respected_and_large_budget_includes_everything() -> None:
    rec = _record()
    for arm in ("bm25", "dense", "rrf"):
        small = rec["contexts"][f"{arm}|60"]["manifest"]
        large = rec["contexts"][f"{arm}|100000"]["manifest"]
        assert small["total_tokens"] <= 60
        assert len(large["entries"]) == 6


def test_same_inputs_give_the_same_bytes() -> None:
    assert encode_record(_record()) == encode_record(_record())
    assert decode_record(encode_record(_record())) == _record()


def test_scorer_is_an_input_so_another_arm_plugs_in() -> None:
    seen: list[int] = []

    def reversed_bm25(bm25: Any, dense: Any) -> Any:
        seen.append(len(bm25))
        return -np.asarray(bm25)

    arm = Arm("custom", None, reversed_bm25, ("custom",))
    rec = build_instance(META, _arrays(), _dense(), _units(), _spec(), (arm,), TOK)
    entries = rec["contexts"]["custom|100000"]["manifest"]["entries"]
    assert {e["unit_id"]: e["rank"] for e in entries}["d.py::u5"] == 1
    assert entries[0]["stages"] == ["custom"]
    assert seen


def test_missing_dense_scores_are_an_error() -> None:
    with pytest.raises(ValueError, match="no dense scores"):
        build_instance(META, _arrays(), {}, _units(), _spec(), default_arms(10), TOK)


def test_coverage_rows_use_the_stated_readings_and_levels() -> None:
    rec = _record()
    rows = [r for r in rec["coverage"] if r["arm"] == "bm25" and r["budget"] == 100000]
    keyed = {(r["level"], r["reading"]): r for r in rows}
    assert ("L3", "units_all_nomod") not in keyed  # empty gold: no row
    assert keyed[("L2", "units_all")]["n_gold_units"] == 2
    assert keyed[("L2", "units_all")]["n_gold_files"] == 2
    assert keyed[("L2", "units_all_nomod")]["units_in"] == 1
    assert keyed[("L3", "units_all")]["files_in"] == 1


def test_level_gold_maps_indices_to_ids_and_files() -> None:
    units = _units()
    ids = [u.unit_id for u in units]
    gold = level_gold(_arrays(), "L2", ids, {u.unit_id: u.file for u in units})
    assert gold["units_all"] == (["a.py::u1", "d.py::u5"], ["a.py", "d.py"])


def test_tables_denominators_are_separate_for_files_and_units(tmp_path: Path) -> None:
    write_atomic(str(tmp_path / "instances" / "o__r-1.json.gz"), encode_record(_record()))
    records = load_records(str(tmp_path))
    cov = {(r["level"], r["arm"], r["budget"], r["view"]): r for r in coverage_summary(records)}
    assert cov[("L2", "bm25", 100000, "file")]["instances"] == 1
    assert cov[("L2", "bm25", 100000, "unit")]["pct_gold_unit_in_context"] == 100.0
    assert ("L3", "bm25", 100000, "unit") not in cov  # no unit-level gold at L3 here
    assert ("L3", "bm25", 100000, "file") in cov
    sizes = {(r["arm"], r["budget"]): r for r in size_summary(records)}
    assert sizes[("bm25", 60)]["pct_budget_binding"] == 100.0
    assert sizes[("bm25", 100000)]["pct_budget_binding"] == 0.0
    assert len(context_rows(records)) == 6
    man = file_manifest(str(tmp_path))
    assert man[0]["path"] == "instances/o__r-1.json.gz" and len(man[0]["sha256"]) == 64


def test_compare_dirs_detects_a_difference(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    write_atomic(str(a / "instances" / "x.json.gz"), encode_record(_record()))
    write_atomic(str(b / "instances" / "x.json.gz"), encode_record(_record()))
    assert compare_dirs(str(a), str(b), ["x"])["differ"] == 0
    other = _record((60, 200000))
    write_atomic(str(b / "instances" / "x.json.gz"), encode_record(other))
    assert compare_dirs(str(a), str(b), ["x"])["differ"] == 1


def test_archive_is_deterministic_and_holds_only_the_budget(tmp_path: Path) -> None:
    write_atomic(str(tmp_path / "instances" / "o__r-1.json.gz"), encode_record(_record()))
    one = write_archive(str(tmp_path), str(tmp_path / "a.tar.gz"), 100000)
    two = write_archive(str(tmp_path), str(tmp_path / "b.tar.gz"), 100000)
    assert one["sha256"] == two["sha256"] and one["files"] == 6
    with tarfile.open(tmp_path / "a.tar.gz") as tar:
        names = sorted(tar.getnames())
        text = tar.extractfile("contexts_b100000/bm25/o__r-1.txt")
        assert text is not None and b"### a.py:1-9" in text.read()
    assert names[0] == "contexts_b100000/bm25/o__r-1.manifest.json"
    assert not any("|60" in n or "_b60/" in n for n in names)


def test_vector_checks_report_equality_of_the_two_levels() -> None:
    arrays = {"scores_L2": np.ones(3), "scores_L3": np.ones(3)}
    assert vector_checks(arrays, {"dense_L2": np.ones(2), "dense_L3": np.zeros(2)}) == {
        "bm25_L3_equals_L2": True,
        "dense_L3_equals_L2": False,
    }
    assert vector_checks({"scores_L2": np.ones(3)}, {"dense_L2": np.ones(2)}) == {}


def test_locate_takes_the_first_group_with_both_files(tmp_path: Path) -> None:
    for g, files in {"g1": ("c",), "g2": ("c", "d")}.items():
        for kind, ok in (("cache", "c" in files), ("dense", "d" in files)):
            if ok:
                write_atomic(str(tmp_path / g / kind / "i.npz"), b"x")
    groups = [
        InputGroup(str(tmp_path / g / "cache"), str(tmp_path / g / "dense")) for g in ("g1", "g2")
    ]
    assert locate(groups, "i") == (
        str(tmp_path / "g2/cache/i.npz"),
        str(tmp_path / "g2/dense/i.npz"),
    )
    assert locate(groups, "missing") is None


def test_draw_is_seeded_and_independent_of_order() -> None:
    ids = [f"i{n}" for n in range(50)]
    assert draw_instances(ids, 5, 0) == draw_instances(list(reversed(ids)), 5, 0)
    assert draw_instances(ids, 5, 0) != draw_instances(ids, 5, 1)
    assert len(draw_instances(ids[:3], 5, 0)) == 3
