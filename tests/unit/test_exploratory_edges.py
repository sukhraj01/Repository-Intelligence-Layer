"""Unit tests for ril.parsing.exploratory_edges and ril.parsing.git_history."""

import subprocess
from pathlib import Path

from ril.parsing.build import BuildConfig, build_repository
from ril.parsing.git_history import co_change_counts, format_utc


def test_tests_edges_by_body_call_and_name_convention(mini_repo: Path) -> None:
    result = build_repository(str(mini_repo), BuildConfig(repo_id="acme/mini", with_history=False))
    assert result.tests is not None
    edges = {(e.src, e.dst, e.derivation) for e in result.tests.edges}
    assert (
        "tests/test_core.py::test_run",
        "pkg/core.py::Engine.run",
        "tests:body-invokes+name",
    ) in edges
    assert (
        "tests/test_core.py::test_helper",
        "pkg/core.py::helper",
        "tests:body-invokes+name",
    ) in edges
    # test_run -> Engine.run also by body call; name-convention finds ``run`` only if unique
    assert all(not dst.startswith("tests/") for _, dst, _ in edges)


def test_configures_edges_from_entry_point(mini_repo: Path) -> None:
    result = build_repository(str(mini_repo), BuildConfig(repo_id="acme/mini", with_history=False))
    assert result.configures is not None
    found = {(e.src, e.dst, e.derivation) for e in result.configures.edges}
    assert ("setup.cfg", "pkg/core.py::helper", "configures:entry-point") in found


def test_co_change_counts_threshold_and_cap() -> None:
    sets = [("a.py", "b.py"), ("a.py", "b.py"), ("a.py", "b.py", "c.py"), ("a.py", "x.py")]
    out = co_change_counts(
        sets, {"a.py", "b.py", "c.py"}, thresholds=(2, 3), max_files_per_commit=3
    )
    assert out["pairs_with_support_at_least"] == {"2": 1, "3": 1}
    assert out["pairs_any_support"] == 3
    capped = co_change_counts(
        sets, {"a.py", "b.py", "c.py"}, thresholds=(2,), max_files_per_commit=2
    )
    assert capped["commits_skipped_too_large"] == 1
    assert capped["pairs_with_support_at_least"] == {"2": 1}


def test_format_utc_is_the_d8_spelling() -> None:
    assert format_utc(0) == "1970-01-01T00:00:00Z"


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
        check=True,
        capture_output=True,
    )


def test_history_only_reads_ancestors_of_the_snapshot(mini_repo: Path) -> None:
    _git(mini_repo, "init", "-q")
    _git(mini_repo, "add", "pkg/util.py", "pkg/core.py")
    _git(mini_repo, "commit", "-q", "-m", "one", "--date=2020-01-01T00:00:00Z")
    snapshot = subprocess.run(
        ["git", "-C", str(mini_repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    (mini_repo / "pkg/util.py").write_text("def fmt(x):\n    return 1\n", encoding="utf-8")
    _git(mini_repo, "add", "pkg/util.py")
    _git(mini_repo, "commit", "-q", "-m", "later")
    _git(mini_repo, "checkout", "-q", snapshot)
    result = build_repository(str(mini_repo), BuildConfig(repo_id="acme/mini"))
    assert result.commit == snapshot
    assert result.history is not None and result.history.n_commits == 1
    mod = result.parsed.unit_by_id()["pkg/util.py::fmt"]
    assert mod.last_modified.endswith("Z") and len(mod.last_modified) == 20


def test_inspection_summaries() -> None:
    from ril.evaluation.edge_samples import summarize_labels, weighted_estimates, wilson

    rows = [
        {"repo": "r", "stratum": "resolved", "label": "correct", "truth": "in_repo"},
        {"repo": "r", "stratum": "resolved", "label": "correct", "truth": "in_repo"},
        {"repo": "r", "stratum": "ambiguous", "label": "incorrect", "truth": "external"},
        {"repo": "r", "stratum": "ambiguous", "label": "correct", "truth": "in_repo"},
        {"repo": "r", "stratum": "external", "label": "correct", "truth": "external"},
        {"repo": "r", "stratum": "unresolved", "label": "incorrect", "truth": "in_repo"},
    ]
    summary = summarize_labels(rows)
    assert summary["resolved"]["precision"] == 1.0 and summary["ambiguous"]["precision"] == 0.5
    lo, hi = wilson(1, 2)
    assert 0 < lo < 0.5 < hi < 1
    pops = {
        ("r", "resolved"): 100,
        ("r", "ambiguous"): 40,
        ("r", "external"): 200,
        ("r", "unresolved"): 10,
    }
    est = weighted_estimates(rows, pops, seed=0, n_boot=50)
    assert est["recall_resolved_over_in_repo_sites"]["estimate"] > 0.5
    assert (
        est["in_repo_share_of_sites"]["boot95_low"] <= est["in_repo_share_of_sites"]["boot95_high"]
    )
