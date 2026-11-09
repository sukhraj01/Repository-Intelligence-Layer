"""Evaluation-set selector and the sealed order of the final sets (no torch).

``ril.evaluation.eval_sets`` and ``ril.evaluation.final_sets``; implements D100 and D125.
"""

from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path

import pytest

from ril.evaluation import eval_sets as es
from ril.evaluation import final_sets as fs
from ril.training import retention

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def test_training_jobs_may_score_the_dev_set_only() -> None:
    assert es.for_training("dev").stage == es.TRAINING
    for name in ("eight", "verified377"):
        with pytest.raises(es.EvalSetRefused, match="final set"):
            es.for_training(name)
    with pytest.raises(es.EvalSetRefused, match="unknown"):
        es.get("nope")


def test_final_sets_carry_a_test_label_and_the_executable_377_has_three_parts() -> None:
    assert es.get("dev").deliberate_test is None and es.get("dev").roles == ("dev",)
    for name in ("eight", "verified377"):
        spec = es.get(name)
        assert spec.roles == ("test",) and spec.deliberate_test
    assert [p.part for p in es.get("verified377").parts] == ["stored36", "built337", "built_xarray"]
    assert [p.compressed_texts for p in es.get("verified377").parts] == [False, True, True]
    for spec in es.SETS.values():
        for p in spec.parts:
            assert (ROOT / p.e1_config).is_file(), p.e1_config


def test_resolve_puts_the_dev_cache_in_the_work_directory() -> None:
    (part,) = es.resolve(es.DEV, "/h", work="/h/ril_rq2f/work")
    assert part.e3_cache == "/h/ril_rq2f/work/e3_cache_dev5"
    assert part.prep == "/h/ril_x2/prep"
    parts = es.resolve(es.get("eight"), "/h")
    assert parts[0].prep == "/h/ril_eval/prep" and parts[0].e3_cache == "/h/ril_eval/e3_cache"


def test_train_cli_refuses_a_final_set_and_a_missing_home() -> None:
    import train

    base = ["run-batch", "c.yaml", "--cache", "x", "--results-root", "r", "--work-root", "w"]
    base += ["--date", "d", "--work", "w"]
    with pytest.raises(SystemExit):
        train.main([*base, "--eval-set", "eight", "--home", "/h"])
    with pytest.raises(SystemExit):
        train.main([*base, "--eval-set", "dev"])
    with pytest.raises(SystemExit):
        train.main(base)  # neither a set nor explicit roots


def _record(
    tmp_path: Path, aid: str = "E-RQ2-DEV-1", runs: tuple[str, ...] = ("mined_raw_u100_s100",)
) -> str:
    path = str(tmp_path / "dev_record.json")
    fs.write_dev_analysis_record(path, aid, runs, "ab" * 32)
    return path


def test_no_id_no_scoring(tmp_path: Path) -> None:
    path = _record(tmp_path)
    for bad in (None, "", "x", "bad id!"):
        with pytest.raises(fs.FinalSetsRefused, match="follows|dev analysis"):
            fs.load_dev_analysis_record(path, bad, ["mined_raw_u100_s100"])


def test_record_must_match_the_id_be_complete_and_cover_the_run(tmp_path: Path) -> None:
    path = _record(tmp_path)
    ok = fs.load_dev_analysis_record(path, "E-RQ2-DEV-1", ["mined_raw_u100_s100"])
    assert ok["status"] == "complete" and len(ok["record_sha256"]) == 64
    with pytest.raises(fs.FinalSetsRefused, match="not 'E-RQ2-DEV-2'"):
        fs.load_dev_analysis_record(path, "E-RQ2-DEV-2", ["mined_raw_u100_s100"])
    with pytest.raises(fs.FinalSetsRefused, match="not covered"):
        fs.load_dev_analysis_record(path, "E-RQ2-DEV-1", ["mined_sub_u100_s100"])
    with pytest.raises(fs.FinalSetsRefused, match="no dev-analysis record"):
        fs.load_dev_analysis_record(str(tmp_path / "none.json"), "E-RQ2-DEV-1", [])
    rec = json.loads(Path(path).read_text())
    rec["status"] = "running"
    Path(path).write_text(json.dumps(rec))
    with pytest.raises(fs.FinalSetsRefused, match="not marked complete"):
        fs.load_dev_analysis_record(path, "E-RQ2-DEV-1", ["mined_raw_u100_s100"])


def _retained(tmp_path: Path, cell: str = "rq2f_mined_raw", seed: int = 100) -> str:
    folder = tmp_path / f"{cell}__s{seed}__abcd1234"
    (folder / "model").mkdir(parents=True)
    (folder / "model" / "weights.bin").write_bytes(b"w" * 10)
    files = retention.tree_files(str(folder / "model"))
    manifest = {
        "version": retention.MANIFEST_VERSION,
        "cell": cell,
        "seed": seed,
        "updates": 100,
        "config_hash": "c" * 64,
        "sha256": retention.tree_digest(files),
        "bytes": 10,
        "files": files,
    }
    retention.write_manifest(str(folder), manifest)
    return str(folder)


def test_run_id_and_plan_of_a_retained_folder(tmp_path: Path) -> None:
    folder = _retained(tmp_path)
    m = fs.read_manifest(folder)
    assert fs.retained_run_id(m) == "mined_raw_u100_s100"
    entries = fs.plan([folder], ["eight", "verified377"], str(tmp_path / "out"))
    assert [(e["set"], e["part"]) for e in entries] == [
        ("eight", "eight"),
        ("verified377", "stored36"),
        ("verified377", "built337"),
        ("verified377", "built_xarray"),
    ]
    assert all(e["run_id"] == "mined_raw_u100_s100" for e in entries)


def test_evaluate_refuses_without_scoring_when_the_order_or_the_model_is_wrong(
    tmp_path: Path,
) -> None:
    folder = _retained(tmp_path)
    rec = fs.load_dev_analysis_record(_record(tmp_path), "E-RQ2-DEV-1", ["mined_raw_u100_s100"])
    kw = dict(
        out_root=str(tmp_path / "o"),
        home="/h",
        work=str(tmp_path),
        follows="E-RQ2-DEV-1",
        commit="c",
    )
    with pytest.raises(fs.FinalSetsRefused, match="training-stage"):
        fs.evaluate_retained(folder, "dev", record=rec, **kw)
    with pytest.raises(fs.FinalSetsRefused, match="not covered"):
        fs.evaluate_retained(folder, "eight", record={**rec, "runs": []}, **kw)
    (Path(folder) / "model" / "weights.bin").write_bytes(b"tampered")
    with pytest.raises(fs.FinalSetsRefused, match="manifest"):
        fs.evaluate_retained(folder, "eight", record=rec, **kw)


def test_reader_returns_rows_only_for_the_followed_id(tmp_path: Path) -> None:
    folder = _retained(tmp_path)
    m = fs.read_manifest(folder)
    spec = es.get("eight")
    row = fs.index_row(
        run_id="mined_raw_u100_s100",
        folder=folder,
        manifest=m,
        spec=spec,
        part="eight",
        follows="E-RQ2-DEV-1",
        record_sha256="r" * 64,
        commit="c",
        result_dir="d",
        queries=224,
        seconds=1.0,
    )
    idx = tmp_path / fs.INDEX_NAME
    idx.write_text(json.dumps(row) + "\n")
    assert fs.read_final_sets(str(idx), "E-RQ2-DEV-1")[0]["queries"] == 224
    with pytest.raises(fs.FinalSetsRefused, match="not 'E-RQ2-DEV-9'"):
        fs.read_final_sets(str(idx), "E-RQ2-DEV-9")
    with pytest.raises(fs.FinalSetsRefused, match="dev-analysis entry"):
        fs.read_final_sets(str(idx), None)
    assert row["follows_dev_analysis"] == "E-RQ2-DEV-1" and row["roles"] == ["test"]


def test_unpack_prep_links_stores_and_unpacks_texts(tmp_path: Path) -> None:
    prep = tmp_path / "prep"
    (prep / "texts_units_gz").mkdir(parents=True)
    (prep / "queries").mkdir()
    with gzip.open(prep / "texts_units_gz" / "units__a.jsonl.gz", "wb") as h:
        h.write(b'{"h": "1"}\n')
    out = fs.unpack_prep(str(prep), str(tmp_path / "node"))
    assert (Path(out) / "texts_units" / "units__a.jsonl").read_text() == '{"h": "1"}\n'
    assert os.path.islink(Path(out) / "queries")
    fs.unpack_prep(str(prep), out)  # idempotent


def test_cli_run_refuses_without_an_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import rq2_final_sets

    folder = _retained(tmp_path)
    root = str(Path(folder).parent)
    rec = _record(tmp_path)
    args = [
        "run",
        "--retained-root",
        root,
        "--dev-record",
        rec,
        "--out",
        str(tmp_path / "o"),
        "--home",
        "/h",
        "--work",
        str(tmp_path),
    ]
    assert rq2_final_sets.main(args) == 3
    assert "give the id" in capsys.readouterr().err
    assert rq2_final_sets.main([*args, "--follows-dev-analysis", "E-RQ2-DEV-7"]) == 3
    assert rq2_final_sets.main(["plan", "--retained-root", root, "--out", str(tmp_path / "o")]) == 0
