"""The thin command line of the driver: held-out draw, cost, power, analyse, model check."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "rq3_driver.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rq3_driver_script", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_subset(path: Path) -> list[str]:
    rows = [
        {"instance_id": f"{r}-{i}", "repo": r, "env_policy": "latest"}
        for r, n in (("a/a", 30), ("b/b", 20), ("c/c", 3))
        for i in range(n)
    ]
    path.write_text(json.dumps({"executable": rows}))
    return [r["instance_id"] for r in rows]


def test_heldout_is_written_and_reproducible(tmp_path: Path) -> None:
    mod = load()
    write_subset(tmp_path / "s.json")
    for name in ("h1.json", "h2.json"):
        assert (
            mod.main(["heldout", str(tmp_path / "s.json"), str(tmp_path / name), "--n", "10"]) == 0
        )
    assert (tmp_path / "h1.json").read_bytes() == (tmp_path / "h2.json").read_bytes()
    held = json.loads((tmp_path / "h1.json").read_text())
    assert len(held["instances"]) == 10 and held["seed"] == 0


def test_cost_reads_the_pilot_row_and_writes_the_cap(tmp_path: Path) -> None:
    mod = load()
    header = (
        "arm,calls_per_unit,calls_per_unit_hi,"
        "input_tokens_per_unit_mean,output_tokens_per_unit_mean"
    )
    (tmp_path / "pilot.csv").write_text(f"{header}\nall,1.4,1.5,12000,900\nbm25,1,1,1,1\n")
    assert mod.main(["cost", str(tmp_path / "o"), "--pilot-cost", str(tmp_path / "pilot.csv")]) == 0
    rows = list(csv.DictReader((tmp_path / "o" / "rq3_cost_model.csv").open()))
    assert {r["model"] for r in rows} >= {"gemini-3.5-flash-lite"}
    assert (
        float(
            json.loads((tmp_path / "o" / "rq3_cost_graded_check_cap.json").read_text())[
                "recommended_cap_usd"
            ]
        )
        >= 1
    )


def test_run_refuses_to_start_without_a_cap() -> None:
    import pytest

    mod = load()
    with pytest.raises(SystemExit) as exc:
        mod.main(
            [
                "run",
                "i",
                "l",
                "o",
                "--arm",
                "rrf",
                "--run-index",
                "0",
                "--instances",
                "x",
                "--model",
                "m",
                "--specs",
                "s",
                "--work-root",
                "w",
                "--cache-root",
                "c",
                "--mirror-dir",
                "m",
                "--subset",
                "s",
            ]
        )
    assert exc.value.code == 2


def test_analyse_and_model_check_on_stored_rows(tmp_path: Path) -> None:
    mod = load()
    ids = write_subset(tmp_path / "s.json")
    assert (
        mod.main(["heldout", str(tmp_path / "s.json"), str(tmp_path / "h.json"), "--n", "10"]) == 0
    )
    held = {r["instance_id"] for r in json.loads((tmp_path / "h.json").read_text())["instances"]}
    run = tmp_path / "res"
    run.mkdir()
    lines = []
    for k, iid in enumerate(ids):
        for arm, ok in (("raw", k % 3 == 0), ("dense", k % 6 == 0)):
            outcome = "resolved" if ok else "executed_unresolved"
            lines.append(
                {
                    "instance_id": iid,
                    "arm": arm,
                    "run": 0,
                    "outcome": outcome,
                    "outcome_tolerant": outcome,
                    "resolved": ok,
                    "resolved_tolerant": ok,
                    "cost_usd": 0.01,
                    "thought_tokens": 0,
                }
            )
    (run / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in lines))
    out = tmp_path / "tables"
    argv = [
        "analyse",
        str(tmp_path / "a.json"),
        str(run),
        "--subset",
        str(tmp_path / "s.json"),
        "--heldout",
        str(tmp_path / "h.json"),
        "--arms",
        "raw",
        "dense",
        "--primary",
        "raw",
        "dense",
        "--runs",
        "0",
        "--out-dir",
        str(out),
    ]
    assert mod.main(argv) == 0
    arms = list(csv.DictReader((out / "rq3_results_arms.csv").open()))
    assert {r["instances"] for r in arms if r["reading"] == "exact"} == {str(len(ids) - len(held))}
    assert (
        mod.main(
            [
                "model-check",
                str(tmp_path / "m.json"),
                f"gemini-3.5-flash-lite={run}",
                f"gemini-3.6-flash={run}",
            ]
        )
        == 0
    )
    chosen = json.loads((tmp_path / "m.json").read_text())
    assert chosen["chosen"] == "gemini-3.5-flash-lite" and chosen["floor_met"]
