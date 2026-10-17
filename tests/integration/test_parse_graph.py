"""Integration: checkout, units, graph, projections, artifacts and the command-line wrapper."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ril.parsing.build import BuildConfig, build_repository, write_artifacts
from ril.parsing.code_unit import units_from_jsonl
from ril.parsing.repo_graph import STATUSES
from ril.parsing.report import build_stats, invoke_shares, select_units

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_artifacts_round_trip_and_units_validate(mini_repo: Path, tmp_path: Path) -> None:
    result = build_repository(str(mini_repo), BuildConfig(repo_id="acme/mini", with_history=False))
    write_artifacts(result, str(tmp_path))
    units = units_from_jsonl((tmp_path / "units.jsonl").read_bytes())
    assert [u.id for u in units] == [u.id for u in result.parsed.units]
    ids = {u.id for u in units}
    for u in units:
        u.validate()
        assert set(u.calls) <= ids and set(u.called_by) <= ids
    meta = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert meta["repo_graph_schema_version"] == "v0-draft"
    assert meta["codeunit_schema_version"] == "v1"
    assert meta["n_units"] == len(units)


def test_statistics_report_every_status_and_the_unparseable_file(mini_repo: Path) -> None:
    result = build_repository(str(mini_repo), BuildConfig(repo_id="acme/mini", with_history=False))
    stats = build_stats(result)
    assert stats["files_unparseable"] == 1
    table = stats["edges_by_type_and_status"]
    assert set(table["invoke"]) == set(STATUSES)  # type: ignore[call-overload]
    shares = invoke_shares(table["invoke"])  # type: ignore[call-overload,index]
    assert 0 < shares["resolved_over_all_sites"] <= shares["resolved_over_non_external"] <= 1
    assert len(select_units(result.parsed.units, seed=3)) == 10 or len(result.parsed.units) < 10


def test_command_line_wrapper_prints_units_and_statistics(mini_repo: Path) -> None:
    out = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "parse_repo.py"),
            str(mini_repo),
            "--repo-id",
            "acme/mini",
            "--seed",
            "0",
            "--no-history",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "== ten CodeUnits (seed 0) ==" in out
    assert "== statistics ==" in out
    assert '"edges_by_type_and_status"' in out


@pytest.mark.skipif(
    not (REPO_ROOT / "data/raw/repos/pallets__flask/.git").exists(), reason="flask checkout absent"
)
def test_real_repository_graph_is_byte_identical_on_rerun(tmp_path: Path) -> None:
    root = str(REPO_ROOT / "data/raw/repos/pallets__flask")
    cfg = BuildConfig(repo_id="pallets/flask", with_history=False)
    a = write_artifacts(build_repository(root, cfg), str(tmp_path / "a"))
    b = write_artifacts(build_repository(root, cfg), str(tmp_path / "b"))
    assert a == b
