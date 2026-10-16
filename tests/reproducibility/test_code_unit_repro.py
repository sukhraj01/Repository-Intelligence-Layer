"""Same units serialize to identical bytes, however they were built (specs/code_unit.md)."""

from ril.parsing.code_unit import CodeUnit, units_from_jsonl, units_to_jsonl


def _unit(i: int) -> CodeUnit:
    return CodeUnit(
        id=f"m.py::f{i}", repo_id="o/n", language="python", file="m.py", start_line=i,
        end_line=i + 1, unit_type="function", name=f"f{i}", qualified_name=f"f{i}",
        signature=f"def f{i}()", docstring=None if i % 2 else "dé", source="x = 1\n",
        calls=["b", "a"], called_by=[], tests=[], configs=[], is_test=False, loc=1,
        last_modified="",
    )  # fmt: skip


def test_serialization_is_byte_identical_across_calls() -> None:
    units = [_unit(i) for i in range(50)]
    assert units_to_jsonl(units) == units_to_jsonl(units)


def test_serialization_survives_round_trip_byte_for_byte() -> None:
    blob = units_to_jsonl([_unit(i) for i in range(20)])
    assert units_to_jsonl(units_from_jsonl(blob)) == blob
