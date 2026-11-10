"""The frozen configuration records do not change (E-FREEZE-AND-LATENCY).

The manifest digest is pinned here as well, so changing a record or the manifest needs a visible
edit of this test; ``ril.bench.freeze.verify`` also checks the sources, the run configurations and
the latency rows of every record.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ril.bench import freeze

ROOT = Path(__file__).resolve().parents[2]
PINNED_MANIFEST_SHA256 = "b2b48b4acb8b34732895ffb2f62ad8e559e92e376edb303de3d71caf58738829"
CONSUMERS = ("rq2_evaluation", "rq3_contexts", "rq1_dev_selection")


def test_frozen_files_are_as_recorded() -> None:
    assert freeze.sha256_file(str(ROOT / "configs/frozen/MANIFEST.json")) == PINNED_MANIFEST_SHA256
    assert freeze.verify(str(ROOT)) == []


def test_every_consumer_was_found_and_ties_to_its_stored_hash() -> None:
    for name in CONSUMERS:
        doc = json.loads((ROOT / f"configs/frozen/{name}.json").read_text(encoding="utf-8"))
        assert doc["not_found"] == [] and doc["sources"]
        hashes = doc["consumer_hashes"]
        if "equals_file_hash" in hashes:
            assert hashes["equals_file_hash"] is True
    rq2 = json.loads((ROOT / "configs/frozen/rq2_evaluation.json").read_text(encoding="utf-8"))
    assert len(rq2["consumer_hashes"]["runs"]) == 45
    assert rq2["consumer_hashes"]["evaluation_section_identical_in_all_runs"] is True
    assert rq2["configuration"]["rrf_k"] == 60
    assert rq2["configuration"]["expansion"] == "off"
    rq3 = json.loads((ROOT / "configs/frozen/rq3_contexts.json").read_text(encoding="utf-8"))
    assert rq3["configuration"]["rrf_k"] == 100
    assert rq3["assembly"]["version"] == "assembly/v1"


def test_latency_snapshot_lists_what_it_lacks() -> None:
    for name in CONSUMERS:
        doc = json.loads((ROOT / f"configs/frozen/{name}.json").read_text(encoding="utf-8"))
        lat = doc["latency"]
        assert lat["not_measured"] == []
        for row in lat["rows"]:
            assert row["p50_ms"] <= row["p95_ms"] <= row["p99_ms"]


@pytest.fixture
def copy_root(tmp_path: Path) -> Path:
    """A root with the frozen directory, every source it reads, the run configs and the log."""
    shutil.copytree(ROOT / "configs/frozen", tmp_path / "configs/frozen")
    shutil.copytree(
        ROOT / "configs/experiments/rq2_final", tmp_path / "configs/experiments/rq2_final"
    )
    rels = {freeze.LATENCY_LOG, freeze.SENSITIVITY_TABLE}
    for name in CONSUMERS:
        doc = json.loads((ROOT / f"configs/frozen/{name}.json").read_text(encoding="utf-8"))
        rels |= {s["path"] for s in doc["sources"]}
    for rel in rels:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    return tmp_path


def test_copy_verifies_clean(copy_root: Path) -> None:
    assert freeze.verify(str(copy_root)) == []


def test_changed_record_is_reported(copy_root: Path) -> None:
    path = copy_root / "configs/frozen/rq2_evaluation.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"rrf_k": 60', '"rrf_k": 61'))
    assert any(
        "rq2_evaluation.json changed after the freeze" in p for p in freeze.verify(str(copy_root))
    )


def test_changed_consumer_configuration_is_reported(copy_root: Path) -> None:
    path = copy_root / freeze.RQ3_CONFIG
    path.write_text(path.read_text(encoding="utf-8") + "# edited\n")
    assert any("changed since the freeze" in p for p in freeze.verify(str(copy_root)))


def test_changed_run_configuration_is_reported(copy_root: Path) -> None:
    path = next((copy_root / freeze.RQ2_DIR).glob("inj_raw_u100_s100.yaml"))
    path.write_text(path.read_text(encoding="utf-8").replace("rrf_k: 60", "rrf_k: 59"))
    assert any("no longer hashes" in p for p in freeze.verify(str(copy_root)))


def test_missing_latency_row_and_stray_file_are_reported(copy_root: Path) -> None:
    log = copy_root / freeze.LATENCY_LOG
    lines = [
        ln for ln in log.read_text(encoding="utf-8").splitlines() if "fusion-django-v1" not in ln
    ]
    log.write_text("\n".join(lines) + "\n")
    (copy_root / "configs/frozen/extra.json").write_text("{}")
    problems = freeze.verify(str(copy_root))
    assert any("not in the log" in p for p in problems)
    assert any("extra.json is in configs/frozen but not in the manifest" in p for p in problems)


def test_write_refuses_to_overwrite(copy_root: Path) -> None:
    with pytest.raises(FileExistsError):
        freeze.write_records(str(copy_root), "2026-11-10")
