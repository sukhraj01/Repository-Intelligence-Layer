"""Empty evaluation folders, the label manifest and the CPU dry run of the final-sets path.

Regression for the sealed scoring stopping on a part whose members have no labels (DEV-043
addendum): the shared loader still raises on an empty folder by default; the scoring job opts in
only when the label manifest shows no labelled member.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ril.analysis.e3_tables import load_eval_dir
from ril.bench import rq2_final_dryrun as dr
from ril.evaluation import eval_sets
from ril.evaluation import final_sets as fs
from ril.evaluation.checkpoint_eval import eval_checkpoint
from ril.evaluation.e3_prepare import READINGS, write_cache
from ril.evaluation.label_manifest import label_manifest
from ril.evaluation.x2_dense import query_key

DATASET, FOLDER = "SWE-bench_Verified", "pytest"
VARIANT = "m__x__p"


def _member(cache: Path, inst: str, labelled: bool, levels: tuple[str, ...] = ("L2",)) -> None:
    n = 12
    rng = np.random.default_rng(1)
    arrays: dict[str, Any] = {
        "file_of_unit": np.arange(n) // 3,
        "age_days": np.zeros(n),
    }
    for lv in levels:
        arrays[f"scores_{lv}"] = rng.random(n)
        if labelled:
            for r in READINGS:
                arrays[f"gold_{lv}_{r}"] = np.asarray([2, 5], dtype=np.int32)
    meta = {
        "units": n,
        "levels": list(levels),
        "instance": inst,
        "role": "test",
        "dataset": DATASET,
        "folder": FOLDER,
        "repo_id": "o/r",
        "config_hash": "h",
    }
    write_cache(str(cache / f"{inst}.npz"), arrays, meta)


def _dense(root: Path, inst: str, levels: tuple[str, ...] = ("L2",)) -> None:
    d = root / "dense" / VARIANT
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(2)
    np.savez_compressed(d / f"{inst}.npz", **{f"dense_{lv}": rng.random(12) for lv in levels})


def _cfg() -> dict[str, Any]:
    return {
        "variant": VARIANT,
        "roles": ["test"],
        "rrf_k": 60,
        "batch_size": 8,
        "chunks": False,
        "seed": 0,
        "baselines": [],
        "deliberate_test": "test",
    }


def _run(tmp: Path, cache: Path, **kw: Any) -> dict[str, Any]:
    return eval_checkpoint(
        None,
        _cfg(),
        e1_config="unused",
        prep_dir=str(tmp / "prep"),
        cache_dir=str(cache),
        data_root=str(tmp),
        work_dir=str(tmp / "eval"),
        result_dir=str(tmp / "result"),
        dense_root=str(tmp / "eval" / "dense"),
        scores_ready=True,
        **kw,
    )


def test_the_loader_raises_on_an_empty_folder_unless_told_otherwise(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no evaluation files"):
        load_eval_dir(str(tmp_path))
    tab = load_eval_dir(str(tmp_path), allow_empty=True)
    assert tab.rows == [] and tab.metrics.shape[0] == 0


def test_a_part_without_labels_returns_zero_rows_and_writes_its_tables(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    _member(cache, "p-1", False)
    _dense(tmp_path / "eval", "p-1")
    m = label_manifest(str(cache), ["test"])
    assert m["labelled"] == 0 and m["members"] == 1 and m["unlabelled"] == ["p-1"]
    with pytest.raises(ValueError, match="no evaluation files"):
        _run(tmp_path, cache)  # the default stays strict for every caller
    out = _run(tmp_path, cache, allow_empty=True)
    assert out["unit_queries"] == 0
    assert (tmp_path / "result" / "unit_rows.csv").is_file()
    fs.check_label_counts(m, out["unit_queries"], "part")


def test_a_part_with_a_label_and_an_empty_folder_still_raises(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    _member(cache, "p-1", True)
    m = label_manifest(str(cache), ["test"])
    assert m["labelled"] == 1 and m["levels"] == {"L2": 1}
    # no dense scores for the labelled member: nothing is evaluated, and the empty folder raises
    (tmp_path / "eval" / "dense" / VARIANT).mkdir(parents=True)
    allow = m["labelled"] == 0
    with pytest.raises(ValueError, match="no evaluation files"):
        _run(tmp_path, cache, allow_empty=allow)


def test_labelled_and_unlabelled_members_evaluate_only_the_labelled(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    _member(cache, "p-1", True)
    _member(cache, "p-2", False)
    _dense(tmp_path / "eval", "p-1")
    _dense(tmp_path / "eval", "p-2")
    m = label_manifest(str(cache), ["test"])
    out = _run(tmp_path, cache, allow_empty=m["labelled"] == 0)
    assert out["unit_queries"] == 1 == sum(m["levels"].values())
    fs.check_label_counts(m, out["unit_queries"], "part")
    with pytest.raises(fs.FinalSetsRefused, match="label manifest lists"):
        fs.check_label_counts(m, 0, "part")


def test_the_manifest_refuses_a_cache_with_no_member_of_the_roles(tmp_path: Path) -> None:
    (tmp_path / "cache").mkdir()
    with pytest.raises(ValueError, match="no instance caches"):
        label_manifest(str(tmp_path / "cache"), ["test"])


def _part(tmp: Path, store_levels: tuple[str, ...]) -> eval_sets.ResolvedPart:
    prep = tmp / "prep"
    (prep / "units").mkdir(parents=True)
    (prep / "queries").mkdir()
    cache = tmp / "cache"
    cache.mkdir()
    _member(cache, "p-1", True, ("L2", "L3"))
    _member(cache, "p-2", False)
    for inst in ("p-1", "p-2"):
        (prep / "units" / f"{inst}.npz").write_bytes(b"x")
    for lv in store_levels:
        row = {"h": query_key(lv, DATASET, FOLDER, "p-1"), "t": "issue"}
        (prep / "queries" / f"{lv}__{DATASET}__{FOLDER}.jsonl").write_text(
            json.dumps(row) + "\n", encoding="utf-8"
        )
    cfg = tmp / "e1.yaml"
    cfg.write_text("folders: []\n", encoding="utf-8")
    return eval_sets.ResolvedPart("p", str(cfg), str(prep), str(cache), str(tmp), False)


def test_the_dry_run_finds_a_missing_level_store_and_passes_once_it_is_there(
    tmp_path: Path,
) -> None:
    bad, found = dr.check_part(_part(tmp_path / "a", ("L2",)), ["test"], str(tmp_path / "sa"), "v")
    assert any("labelled at L3 but no query text" in p for p in found)
    good, found = dr.check_part(
        _part(tmp_path / "b", ("L2", "L3")), ["test"], str(tmp_path / "sb"), "v"
    )
    assert found == [] and good["unit_queries"] == 2
    assert good["label_manifest"]["levels"] == {"L2": 1, "L3": 1}
    assert os.path.isdir(tmp_path / "sb" / "eval" / "dense" / "v")
    assert bad["label_manifest"]["labelled"] == 1
