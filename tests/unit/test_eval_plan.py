"""Plan-only evaluation-set check: stores found, counted and missing ones reported."""

from __future__ import annotations

from pathlib import Path

import yaml

from ril.evaluation.eval_plan import EvalSet, plan_sets


def _fixture(tmp: Path, with_texts: bool) -> EvalSet:
    cfg = {
        "folders": [
            {
                "role": "test",
                "dataset": "D",
                "folder": "f",
                "repo": "o/r",
                "levels": ["L2"],
                "units": True,
            }
        ],
        "bm25": {},
    }
    e1 = tmp / "e1.yaml"
    e1.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    prep = tmp / "prep"
    (prep / "texts_units").mkdir(parents=True)
    (prep / "queries").mkdir()
    (prep / "queries" / "L2__D__f.jsonl").write_text("{}\n{}\n", encoding="utf-8")
    if with_texts:
        (prep / "texts_units" / "o__r.s1.jsonl").write_text(
            '{"h": "a"}\n{"h": "b"}\n{"h": "a"}\n', encoding="utf-8"
        )
    (tmp / "cache").mkdir()
    return EvalSet("fixture", str(e1), str(prep), ("test",), str(tmp / "cache"))


def test_ready_set_is_counted(tmp_path: Path) -> None:
    plan = plan_sets([_fixture(tmp_path, True)])
    row = plan["sets"][0]
    assert (
        plan["ready"]
        and row["unit_texts"] == 2
        and row["unit_lines"] == 3
        and row["query_texts"] == 2
    )


def test_missing_texts_block_the_launch(tmp_path: Path) -> None:
    plan = plan_sets([_fixture(tmp_path, False)])
    assert not plan["ready"] and plan["sets"][0]["missing"] == ["unit texts of o__r"]


def test_missing_path_is_reported_not_raised(tmp_path: Path) -> None:
    plan = plan_sets(
        [
            EvalSet(
                "gone", str(tmp_path / "x.yaml"), str(tmp_path / "p"), ("dev",), str(tmp_path / "c")
            )
        ]
    )
    assert not plan["ready"] and len(plan["sets"][0]["missing"]) == 3
