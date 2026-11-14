"""Retention of the executable-377 scores of the sealed scoring (no torch).

``ril.evaluation.score_retention`` and its use in ``ril.evaluation.final_sets``; implements
DEV-042 (E-RQ3-SCORE-RETENTION): the job keeps what it computes anyway, changes no metric and
leaves the sealed order as it was.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ril.evaluation import eval_sets
from ril.evaluation import final_sets as fs
from ril.evaluation import score_retention as sr
from tests.unit._rq3_trained_fixtures import RUN_ID, retained_folder

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

IDS = ["o__r-1", "o__r-2", "o__r-3"]
EXTRA = "o__r-extra"
PARTS = {"stored36": ["o__r-1", EXTRA], "built337": ["o__r-2", "o__r-3"], "built_xarray": []}


def _scores(instance: str, part: str) -> dict[str, Any]:
    """Distinct arrays per (instance, part) so a wrong copy shows."""
    seed = sum(map(ord, instance + part))
    return {"dense_L2": np.random.default_rng(seed).random(5).astype(np.float32)}


def _install_fakes(monkeypatch: pytest.MonkeyPatch, members: dict[str, list[str]]) -> None:
    """A scorer that writes metric files and score files as the real one does, deterministically."""

    def fake_eval_checkpoint(encoder: Any, cfg: Any, **kw: Any) -> dict[str, Any]:
        variant = str(cfg["variant"])
        part = variant.rsplit("__", 1)[1]
        sdir = Path(kw["work_dir"]) / "dense" / variant
        sdir.mkdir(parents=True)
        for iid in members.get(part, []):
            np.savez_compressed(sdir / f"{iid}.npz", **_scores(iid, part))
        result = Path(kw["result_dir"])
        result.mkdir(parents=True, exist_ok=True)
        (result / "unit_rows.csv").write_text(f"variant,{variant}\nndcg10,0.25\n")
        (result / "query_rows.csv").write_text(
            "instance,ndcg10\n" + "".join(f"{i},0.5\n" for i in members.get(part, []))
        )
        return {"variant": variant, "unit_queries": len(members.get(part, []))}

    monkeypatch.setitem(
        sys.modules,
        "ril.evaluation.checkpoint_eval",
        types.SimpleNamespace(eval_checkpoint=fake_eval_checkpoint),
    )
    monkeypatch.setitem(
        sys.modules,
        "ril.training.encoders",
        types.SimpleNamespace(load_trained=lambda *a, **k: object()),
    )
    monkeypatch.setitem(
        sys.modules, "ril.util.gpu", types.SimpleNamespace(cuda_gate=lambda: {"gate": "fake"})
    )
    monkeypatch.setattr(fs, "unpack_prep", lambda prep, dest: dest)

    def fake_manifest(cache_dir: str, roles: Any) -> dict[str, Any]:
        name = (
            "stored36"
            if "ril_t1" in cache_dir
            else "built_xarray"
            if "ril_rq3u_x" in cache_dir
            else "eight"
            if "ril_eval" in cache_dir
            else "built337"
        )
        n = len(members.get(name, []))
        return {"members": n, "labelled": n, "levels": {"L2": n} if n else {}, "unlabelled": []}

    monkeypatch.setattr(fs, "label_manifest", fake_manifest)


def _record(tmp_path: Path) -> dict[str, Any]:
    path = str(tmp_path / "dev_record.json")
    fs.write_dev_analysis_record(path, "E-RQ2-DEV-1", [RUN_ID], "ab" * 32)
    return fs.load_dev_analysis_record(path, "E-RQ2-DEV-1", [RUN_ID])


def _score(
    tmp_path: Path, tag: str, set_name: str = "exec377", **kw: Any
) -> tuple[Path, Path, list[dict[str, Any]]]:
    root = tmp_path / f"retained_{tag}"
    root.mkdir(exist_ok=True)
    folder = retained_folder(root, "rq2f_mined_raw", 100)
    out = tmp_path / f"out_{tag}"
    work = tmp_path / f"work_{tag}"
    work.mkdir()
    rows = fs.evaluate_retained(
        str(folder),
        set_name,
        out_root=str(out),
        home="/h",
        work=str(work),
        follows="E-RQ2-DEV-1",
        record=_record(tmp_path),
        commit="c0ffee",
        device="cpu",
        **kw,
    )
    return out, root, rows


def _tree_bytes(base: Path) -> dict[str, bytes]:
    """Metric files only: result.json and the two csv tables of every part."""
    keep = {"result.json", "unit_rows.csv", "query_rows.csv"}
    return {
        str(p.relative_to(base)): p.read_bytes()
        for p in sorted(base.rglob("*"))
        if p.is_file() and p.name in keep
    }


def test_metrics_are_byte_identical_with_and_without_retention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fakes(monkeypatch, PARTS)
    out_a, _, rows_a = _score(tmp_path, "plain")
    root_b = tmp_path / "scores_b"
    out_b, _, rows_b = _score(tmp_path, "kept", retain_scores=str(root_b), subset_ids=IDS)
    a, b = _tree_bytes(out_a), _tree_bytes(out_b)
    assert a and a == b  # result.json, unit_rows.csv, query_rows.csv of the three parts
    assert len(a) == 9
    for ra, rb in zip(rows_a, rows_b, strict=True):
        assert "retained_scores" not in ra
        extra = rb.pop("retained_scores")
        for r in (ra, rb):
            r.pop("seconds")
            r.pop("result_dir")
        assert ra == rb  # the scoring record differs by the retained-scores entry only
        assert len(extra["scores_sha256"]) == 64 and len(extra["record_sha256"]) == 64


def test_only_the_executable_instances_are_kept_as_byte_copies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fakes(monkeypatch, PARTS)
    root = tmp_path / "scores"
    _, _, rows = _score(tmp_path, "k", retain_scores=str(root), subset_ids=IDS)
    kept = sorted(p.stem for p in Path(sr.scores_dir(str(root), RUN_ID)).glob("*.npz"))
    assert kept == IDS and EXTRA not in kept
    for iid, part in (("o__r-1", "stored36"), ("o__r-2", "built337")):
        with np.load(Path(sr.scores_dir(str(root), RUN_ID)) / f"{iid}.npz") as d:
            assert np.array_equal(d["dense_L2"], _scores(iid, part)["dense_L2"])
    rec = sr.read_record(str(root), RUN_ID)
    assert rec is not None
    manifest = fs.read_manifest(str(next((tmp_path / "retained_k").iterdir())))
    assert rec["model_sha256"] == manifest["sha256"]
    assert rec["config_hash"] == manifest["config_hash"]
    assert rec["complete"] and rec["instances"] == 3 and rec["missing"] == []
    assert rec["follows_dev_analysis"] == "E-RQ2-DEV-1" and rec["set"] == "exec377"
    assert rec["files"] == {
        i: sr.sha256_file(str(Path(sr.scores_dir(str(root), RUN_ID)) / f"{i}.npz")) for i in IDS
    }
    assert rec["scores_sha256"] == sr.digest(rec["files"])
    # the scoring record of the last part names the hash of the record file
    last = rows[-1]["retained_scores"]
    assert last["record_sha256"] == sr.sha256_file(
        str(Path(sr.model_dir(str(root), RUN_ID)) / sr.RECORD_NAME)
    )
    assert last["scores_sha256"] == rec["scores_sha256"] and last["complete"] is True
    assert rows[0]["retained_scores"]["complete"] is False  # one part is not the whole set
    assert not sr.verify(str(root), RUN_ID, IDS, model_sha256=manifest["sha256"])


def test_the_first_part_wins_and_a_file_without_the_key_is_not_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fakes(monkeypatch, {"stored36": ["o__r-1"], "built337": ["o__r-1", "o__r-2"]})
    root = tmp_path / "scores"
    _score(tmp_path, "k", retain_scores=str(root), subset_ids=IDS)
    with np.load(Path(sr.scores_dir(str(root), RUN_ID)) / "o__r-1.npz") as d:
        assert np.array_equal(d["dense_L2"], _scores("o__r-1", "stored36")["dense_L2"])
    part = json.loads(
        (Path(sr.model_dir(str(root), RUN_ID)) / "parts" / "built337.json").read_text()
    )
    assert part["already"] == ["o__r-1"] and part["copied"] == 1
    rec = sr.read_record(str(root), RUN_ID)
    assert rec is not None and rec["missing"] == ["o__r-3"] and not rec["complete"]
    assert sr.verify(str(root), RUN_ID, IDS)  # an incomplete record is not usable

    src = tmp_path / "src"
    src.mkdir()
    np.savez_compressed(src / "o__r-3.npz", other=np.zeros(2))
    got = sr.retain_part(
        str(src),
        IDS,
        scores_root=str(root),
        run_id=RUN_ID,
        part="x",
        model_sha256="m",
        config_hash="c",
        follows="E-RQ2-DEV-1",
        dev_record_sha256="d",
        commit="c",
    )
    assert got["part_instances"] == 0 and not got["complete"]
    assert not (Path(sr.scores_dir(str(root), RUN_ID)) / "o__r-3.npz").exists()


def test_only_the_executable_377_is_retained_and_it_needs_the_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fakes(monkeypatch, {"eight": ["o__r-1"]})
    root = tmp_path / "scores"
    _, _, rows = _score(
        tmp_path, "eight", set_name="eight", retain_scores=str(root), subset_ids=IDS
    )
    assert rows and all("retained_scores" not in r for r in rows)
    assert not root.exists()  # the eight repositories are not kept
    with pytest.raises(fs.FinalSetsRefused, match="executable ids"):
        _score(tmp_path, "noids", retain_scores=str(root))
    assert not root.exists()


def test_a_damaged_file_or_another_checkpoint_is_not_usable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fakes(monkeypatch, PARTS)
    root = tmp_path / "scores"
    _score(tmp_path, "k", retain_scores=str(root), subset_ids=IDS)
    rec = sr.read_record(str(root), RUN_ID)
    assert rec is not None
    sha = rec["model_sha256"]
    assert sr.usable_models(str(root), [(RUN_ID, sha), ("other_u100_s100", sha)], IDS) == {
        RUN_ID: sr.scores_dir(str(root), RUN_ID)
    }
    assert sr.usable_models(str(root), [(RUN_ID, "0" * 64)], IDS) == {}
    assert sr.usable_models(None, [(RUN_ID, sha)], IDS) == {}
    assert sr.usable_models(str(tmp_path / "none"), [(RUN_ID, sha)], IDS) == {}
    victim = Path(sr.scores_dir(str(root), RUN_ID)) / "o__r-2.npz"
    victim.write_bytes(b"damaged")
    assert any("differs" in p for p in sr.verify(str(root), RUN_ID, IDS, model_sha256=sha))
    assert sr.usable_models(str(root), [(RUN_ID, sha)], IDS) == {}
    assert sr.verify(str(root), "never_scored", IDS) == ["no scores record"]


def test_the_scores_root_is_not_mistaken_for_a_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ril.training import retention

    _install_fakes(monkeypatch, PARTS)
    out, root, _ = _score(tmp_path, "k", subset_ids=IDS, retain_scores=str(tmp_path / "x"))
    inside = sr.default_scores_root(str(root))
    Path(inside, RUN_ID).mkdir(parents=True)
    Path(inside, RUN_ID, sr.RECORD_NAME).write_text("{}")
    assert [Path(f).name for f in retention.list_retained(str(root))] == [
        p.name for p in sorted(root.iterdir()) if (p / retention.MANIFEST_NAME).exists()
    ]
    assert sr.DEFAULT_SCORES_DIRNAME not in [
        Path(f).name for f in retention.list_retained(str(root))
    ]


def test_the_cli_keeps_scores_by_default_for_the_executable_377_and_the_guard_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import rq2_final_sets

    root = tmp_path / "retained"
    root.mkdir()
    retained_folder(root, "rq2f_mined_raw", 100)
    rec = str(tmp_path / "dev_record.json")
    fs.write_dev_analysis_record(rec, "E-RQ2-DEV-1", [RUN_ID], "ab" * 32)
    subset = tmp_path / "subset.json"
    subset.write_text(json.dumps({"executable": [{"instance_id": i} for i in reversed(IDS)]}))
    seen: list[dict[str, Any]] = []

    def fake_evaluate(folder: str, name: str, **kw: Any) -> list[dict[str, Any]]:
        seen.append({"set": name, **kw})
        return []

    monkeypatch.setattr(fs, "evaluate_retained", fake_evaluate)
    monkeypatch.setenv("RIL_COMMIT", "c0ffee")
    base = [
        "run", "--retained-root", str(root), "--dev-record", rec, "--out", str(tmp_path / "o"),
        "--home", "/h", "--work", str(tmp_path), "--subset", str(subset),
    ]  # fmt: skip
    # the guard comes first: no id, no scoring, and nothing is written for retention
    assert rq2_final_sets.main(base) == 3
    assert "give the id" in capsys.readouterr().err
    assert not seen and not (root / sr.DEFAULT_SCORES_DIRNAME).exists()
    follow = ["--follows-dev-analysis", "E-RQ2-DEV-1"]
    assert rq2_final_sets.main([*base, *follow]) == 0
    by_set = {s["set"]: s for s in seen}
    assert by_set["exec377"]["retain_scores"] == str(root / sr.DEFAULT_SCORES_DIRNAME)
    assert by_set["exec377"]["subset_ids"] == sorted(IDS)
    seen.clear()
    assert rq2_final_sets.main([*base, *follow, "--no-retain-scores"]) == 0
    assert all(s["retain_scores"] is None for s in seen)
    seen.clear()
    assert rq2_final_sets.main([*base, *follow, "--set", "eight"]) == 0
    assert all(s["retain_scores"] is None for s in seen)


def test_the_set_that_is_retained_is_the_executable_377() -> None:
    assert sr.SET_NAME == "exec377" and eval_sets.get(sr.SET_NAME).stage == eval_sets.FINAL
