"""Unit tests for ril.training.content_overlap (specs/held_out_repos.md, content-overlap audit)."""

from ril.training.content_overlap import (
    audit_pool,
    audit_repo,
    build_index,
    informative_lines,
    line_hash,
    unit_coverage,
)

HELD = """\
def route(self, rule, **options):
    # a comment line that is long enough to count but must be ignored
    def decorator(f):
        endpoint = options.pop("endpoint", None)
        self.add_url_rule(rule, endpoint, f, **options)
        return f
    return decorator
"""


def test_informative_lines_drop_short_and_comment_lines() -> None:
    lines = informative_lines(HELD)
    assert "def decorator(f):" not in lines  # shorter than 25 characters
    assert all(not ln.startswith("#") for ln in lines)
    assert 'endpoint = options.pop("endpoint", None)' in lines


def test_whitespace_is_normalised() -> None:
    a = informative_lines("x = some_function_call(argument_one,   argument_two)")
    b = informative_lines("\tx = some_function_call(argument_one, argument_two)  ")
    assert a == b


def test_hash_is_stable_across_calls() -> None:
    assert line_hash("abc" * 10) == line_hash("abc" * 10)
    assert line_hash("abc" * 10) != line_hash("abd" * 10)


def test_positive_control_identical_unit_scores_fully() -> None:
    idx = build_index([HELD])
    n, hit = unit_coverage(HELD, idx)
    assert n >= 3 and hit == n


def test_unrelated_code_scores_zero() -> None:
    idx = build_index([HELD])
    other = "\n".join(
        f"value_{i} = compute_something_else(parameter_{i}, 'text')" for i in range(6)
    )
    assert unit_coverage(other, idx) == (6, 0)


def test_audit_repo_threshold_and_min_lines() -> None:
    idx = build_index([HELD])
    mostly = HELD + "\n# a trailing comment that is long enough to be counted if it were code\n"
    tiny = "return x_value_that_is_long_enough_to_count_here"
    r = audit_repo("o/n", [HELD, mostly, "pass", tiny], idx)
    assert r.units_scored == 2 and r.units_covered == 2  # tiny units are skipped, not scored
    partial = HELD + "\n".join(
        f"unrelated_statement_{i} = call_the_function(arg)" for i in range(10)
    )
    assert audit_repo("o/n", [partial], idx).units_covered == 0


def test_audit_pool_orders_by_share_then_name() -> None:
    idx = build_index([HELD])
    clean = "\n".join(
        f"value_{i} = compute_something_else(parameter_{i}, 'text')" for i in range(6)
    )
    rows = audit_pool({"b/clean": [clean], "a/copy": [HELD], "c/copy": [HELD]}, idx)
    assert [r.repo for r in rows] == ["a/copy", "c/copy", "b/clean"]
    assert rows[0].share == 1.0 and rows[-1].share == 0.0


def test_empty_repo_has_zero_share() -> None:
    assert audit_repo("o/n", [], set()).share == 0.0
