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


def test_canonical_bytes_are_pinned_for_schema_v1() -> None:
    """A golden line: any change to key order, separators or escaping changes these bytes."""
    u = CodeUnit(
        id="pkg/m.py::C.f#2", repo_id="o/n", language="python", file="pkg/m.py", start_line=3,
        end_line=4, unit_type="method", name="f", qualified_name="C.f", signature="def f(self)",
        docstring=None, source="def f(self):\n    return '日本'\n", calls=["pkg/m.py::g"],
        called_by=[], tests=[], configs=["setup.cfg"], is_test=False, loc=2,
        last_modified="2026-10-17T10:00:00Z",
    )  # fmt: skip
    expected = (
        '{"called_by":[],"calls":["pkg/m.py::g"],"configs":["setup.cfg"],"docstring":null,'
        '"end_line":4,"file":"pkg/m.py","id":"pkg/m.py::C.f#2","is_test":false,'
        '"language":"python","last_modified":"2026-10-17T10:00:00Z","loc":2,"name":"f",'
        '"qualified_name":"C.f","repo_id":"o/n","signature":"def f(self)",'
        '"source":"def f(self):\\n    return \'日本\'\\n","start_line":3,"tests":[],'
        '"unit_type":"method"}\n'
    ).encode()
    assert units_to_jsonl([u]) == expected
