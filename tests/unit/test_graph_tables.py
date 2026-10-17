"""Unit tests for ril.analysis.graph_tables (tables of the first build)."""

from ril.analysis.graph_tables import extrapolation_rows, rule_rows, status_rows


def _stats() -> dict[str, dict[str, object]]:
    return {
        "local/flask": {
            "commit": "abcdef0123456789",
            "config_hash": "f" * 64,
            "edges_by_type_and_status": {"invoke": {"resolved": 3, "ambiguous": 1, "external": 5}},
            "invoke_by_rule": {"name:function": {"resolved": 3}},
            "import_by_rule": {"import:external": {"external": 2}},
        }
    }


def test_status_rows_list_every_status_even_when_zero() -> None:
    rows = status_rows(_stats())  # type: ignore[arg-type]
    by_status = {r["status"]: r["count"] for r in rows}
    assert by_status == {"resolved": 3, "ambiguous": 1, "unresolved": 0, "external": 5}
    assert all(r["machine"] == "local" and r["repo"] == "flask" for r in rows)


def test_rule_rows_cover_invoke_and_import() -> None:
    rows = rule_rows(_stats())  # type: ignore[arg-type]
    assert {(r["family"], r["rule"], r["count"]) for r in rows} == {
        ("invoke", "name:function", 3),
        ("import", "import:external", 2),
    }


def test_extrapolation_is_exact_for_a_linear_quantity() -> None:
    def build(units: int, seconds: float) -> dict[str, object]:
        return {
            "units": units,
            "edges": units * 2,
            "peak_rss_mb": 10 + units / 100,
            "artifact_bytes": units * 1000,
            "seconds": {"parse": seconds, "graph_build": seconds, "history": seconds},
        }

    summary = {
        "repos": {
            k: {"build": build(u, u / 10)}
            for k, u in (("flask", 1000), ("requests", 500), ("django", 10000))
        }
    }
    rows = extrapolation_rows(summary, {"flask": 1000, "requests": 500, "django": 10000}, "local")
    parse = [r for r in rows if r["quantity"] == "parse_s" and r["fit_basis"] == "units"][0]
    assert parse["predicted_from_the_two_small_repos"] == 1000.0 == parse["measured_django"]
    assert parse["measured_over_predicted"] == 1.0
