"""Tests for the checkpoint inventory: neutral paths, node-local runs marked gone, a listed
checkpoint marked retained, curve steps, and no login names or home paths in the output."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ril.analysis import checkpoint_inventory as ci


def _run(root: Path, exp: str, h8: str, ckpt: str, with_rows: bool = True) -> None:
    d = root / exp / f"2026-01-01_{h8}"
    d.mkdir(parents=True)
    (d / "results.json").write_text(
        json.dumps({"training": {"checkpoint_root": ckpt, "seed": 3, "updates_this_process": 100}})
    )
    if with_rows:
        (d / "query_rows.csv").write_text("instance\n")


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "rq2"
    scripts = tmp_path / "scripts" / "ada"
    scripts.mkdir(parents=True)
    (scripts / "t5_runs.sbatch").write_text('CK=/tmp/x\nrm -rf "$CK"\n')
    (scripts / "t1_validate.sbatch").write_text("echo no cleanup\n")
    _run(root, "t5a_raw", "aaaaaaaa", "/tmp/ril_t5_50356/ckpt/t5a_raw/aaaaaaaa")
    _run(root, "t1_validate_cre", "bbbbbbbb", "/tmp/ril_t1_1/ckpt/x", with_rows=False)
    _run(
        root,
        "t1_validate_tiny",
        "cccccccc",
        "/home2/someone/ril_t1/work/ckpt/t1_validate_tiny/cccccccc",
    )
    listing = tmp_path / "listing.json"
    listing.write_text(
        json.dumps(
            {
                "retained": [
                    {"config_hash8": "cccccccc", "step": 19, "bytes": 10, "path": "<home>/a"},
                    {"config_hash8": "cccccccc", "step": "final", "bytes": 5, "path": "<home>/b"},
                ],
                "disk": {"df_available_kb": 1},
            }
        )
    )
    return root, listing, tmp_path


def test_neutral_replaces_home_and_job_ids() -> None:
    assert ci.neutral("/home2/someone/ril_t1/work") == "<home>/ril_t1/work"
    assert ci.neutral("/tmp/ril_t5_50356/ckpt") == "/tmp/ril_t5_<job>/ckpt"


def test_classification(tmp_path: Path) -> None:
    root, listing, base = _setup(tmp_path)
    rows = {r["run_id"]: r for r in ci.build(str(root), str(listing), str(base))}
    assert rows["t5a_raw"]["storage"] == "node-local, gone" and rows["t5a_raw"]["retained"] == "no"
    assert rows["t5a_raw"]["checkpoint_root_pattern"] == "/tmp/ril_t5_<job>/ckpt/t5a_raw/aaaaaaaa"
    assert rows["t1_validate_cre"]["storage"] == "node-local, gone (presumed)"
    assert rows["t1_validate_cre"]["eval_outputs_in_repo"] == "no"
    tiny = rows["t1_validate_tiny"]
    assert tiny["retained"] == "yes" and tiny["retained_bytes"] == 15
    assert tiny["step_or_updates"] == "final;19"


def test_no_login_names_in_output(tmp_path: Path) -> None:
    root, listing, base = _setup(tmp_path)
    rows = ci.build(str(root), str(listing), str(base))
    out = tmp_path / "inv.csv"
    ci.write(rows, str(out))
    text = out.read_text()
    assert "someone" not in text and "/home2" not in text
    assert list(csv.DictReader(out.open()))[0].keys() == set(ci.FIELDS)
    s = ci.summarise(rows, str(listing))
    assert s["retained_runs"] == ["t1_validate_tiny"] and s["retained_bytes"] == 15
