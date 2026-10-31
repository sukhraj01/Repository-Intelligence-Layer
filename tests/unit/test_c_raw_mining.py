"""Mechanical label completeness, transport recovery, leakage and cache compatibility."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ril.data_mining.github import (
    ISSUE_QUERY,
    Client,
    RecordedTransport,
    Response,
    digest,
    linked_issues,
)
from ril.data_mining.miner import (
    GitSnapshots,
    RecordedSnapshots,
    changed_lines,
    extract_example,
    historical_base,
    mine,
)
from ril.data_mining.ranks import ENCODER, dense_audit_scores, rank_audit
from ril.data_mining.recording import synthetic_recording
from ril.training.content_overlap import build_index
from ril.training.pool_reader import read_cache


def run_recording(tmp_path: Path, recording: dict, **kwargs: object) -> dict:
    return mine(
        recording["config"],
        tmp_path,
        Client(tmp_path / "api", RecordedTransport(recording)),
        RecordedSnapshots(recording),
        recording["held_out"],
        source_kind=recording["source_kind"],
        source_identity=digest(recording),
        **kwargs,
    )


def test_raw_labels_reader_compatibility_and_held_out_rules(tmp_path: Path) -> None:
    recording = synthetic_recording(5)
    result = run_recording(tmp_path, recording)
    assert result["repositories_selected"] == 5
    assert result["repositories_after_held_out"] == 2
    assert [r["repos_dropped"] for r in result["held_out_rule_counts"][:3]] == [1, 2, 3]
    assert result["rename_resolution"]["complete"]
    assert result["counts"] == {
        "merged_prs": 20,
        "no_linked_issue": 2,
        "linked_issues": 18,
        "linked_prs": 18,
        "parse_incomplete": 2,
        "no_overlapping_function": 2,
        "kept": 14,
        "positives": 16,
    }
    examples = read_cache(str(tmp_path / "pool.jsonl.gz"))
    assert len(examples) == 14
    assert all(ex.repo.startswith("synthetic/") for ex in examples)
    assert all("Synthetic issue" in ex.query for ex in examples)
    assert all(not ex.masked_ids for ex in examples)
    assert all(not set(ex.positive_ids) & set(ex.candidate_ids) for ex in examples)
    assert all(len(ex.ids) == 14 for ex in examples)
    assert result["content_overlap"]["status"].startswith("blocked")
    assert result["parse_failure_share"] == pytest.approx(2 / 18)
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert all("base_commit" in r for r in metadata if r["outcome"] == "kept")
    assert (
        len([r for r in metadata if r["outcome"] == "kept" and r["pr"] == 7][0]["positives"]) == 2
    )


def test_resume_does_not_reacquire_and_rejects_identity_changes(tmp_path: Path) -> None:
    recording = synthetic_recording(4, 7)
    first = run_recording(tmp_path, recording)
    examples = read_cache(str(tmp_path / "pool.jsonl.gz"))
    second = run_recording(tmp_path, recording)
    assert second["counts"] == first["counts"]
    assert second["api"]["api_calls"] == first["api"]["api_calls"]
    assert read_cache(str(tmp_path / "pool.jsonl.gz")) == examples
    recording["config"]["seed"] = 12
    with pytest.raises(ValueError, match="resume identity"):
        run_recording(tmp_path, recording)


def test_resume_after_interruption(tmp_path: Path) -> None:
    recording = synthetic_recording(4)
    replay = RecordedTransport(recording)
    calls = 0

    def transport(method: str, url: str, body: dict | None) -> Response:
        nonlocal calls
        calls += 1
        if calls == 15:
            raise KeyboardInterrupt
        return replay(method, url, body)

    with pytest.raises(KeyboardInterrupt):
        mine(
            recording["config"],
            tmp_path,
            Client(tmp_path / "api", transport),
            RecordedSnapshots(recording),
            recording["held_out"],
            source_kind=recording["source_kind"],
            source_identity=digest(recording),
        )
    result = run_recording(tmp_path, recording)
    assert result["counts"]["merged_prs"] == 10
    assert len(read_cache(str(tmp_path / "pool.jsonl.gz"))) == 7


def test_rate_reset_secondary_limit_pagination_and_cache(tmp_path: Path) -> None:
    clock = [100.0]
    calls = []

    def transport(method: str, url: str, body: dict | None) -> Response:
        calls.append(url)
        if len(calls) == 1:
            return Response(403, {}, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "225"})
        if len(calls) == 2:
            return Response(429, {}, {"Retry-After": "3"})
        if url.endswith("page=2"):
            return Response(200, [3], {})
        return Response(200, [1, 2], {"Link": '<https://api.github.com/list?page=2>; rel="next"'})

    sleeps = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    client = Client(tmp_path, transport, clock=lambda: clock[0], sleep=sleep)
    assert list(client.pages("/list")) == [1, 2, 3]
    assert max(sleeps) <= 60
    assert sum(sleeps) >= 129
    assert len(calls) == 4
    assert list(Client(tmp_path, transport).pages("/list")) == [1, 2, 3]
    assert len(calls) == 4
    with pytest.raises(ValueError, match="origin"):
        client.request("https://elsewhere.invalid/list")


def test_linked_issues_paginate_and_never_use_pr_body(tmp_path: Path) -> None:
    def transport(method: str, url: str, body: dict | None) -> Response:
        assert method == "POST" and body["query"] == ISSUE_QUERY
        second = body["variables"]["cursor"] == "next"
        return Response(
            200,
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "closingIssuesReferences": {
                                "nodes": [{"url": str(second), "title": "issue", "body": "text"}],
                                "pageInfo": {"hasNextPage": not second, "endCursor": "next"},
                            }
                        }
                    }
                }
            },
            {},
        )

    assert len(linked_issues(Client(tmp_path, transport), "owner/repo", 3)) == 2


@pytest.mark.parametrize(
    ("diff", "expected"),
    [
        ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -2 +2 @@\n-old\n+new", {2}),
        ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -2,0 +3 @@\n+new", {2, 3}),
        ("diff --git a/a.py b/new.py\n--- a/a.py\n+++ b/new.py\n@@ -2 +2 @@\n-old\n+new", {2}),
        (
            "diff --git a/a.py b/a.py\n--- a/a.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-one\n-two",
            {1, 2},
        ),
        ("diff --git a/a.py b/a.py\n--- /dev/null\n+++ b/a.py\n@@ -0,0 +1 @@\n+new", set()),
    ],
)
def test_diff_old_side_semantics(diff: str, expected: set[int]) -> None:
    assert changed_lines(diff).get("a.py", set()) == expected


def test_every_positive_including_tests_and_collision_ids(tmp_path: Path) -> None:
    (tmp_path / "test_a.py").write_text(
        "def same():\n    return 1\n\ndef same():\n    return 2\n"
        "\nclass C:\n    def m(self):\n        return 3\n"
    )
    diff = "diff --git a/test_a.py b/test_a.py\n--- a/test_a.py\n+++ b/test_a.py\n"
    diff += "@@ -1,9 +1 @@\n" + "\n".join("-x" for _ in range(9))
    ex, metadata = extract_example("own/pkg", 1, [{"title": "q", "body": "t"}], tmp_path, diff)
    assert ex is not None
    assert set(ex.positive_ids) == {"test_a.py/same", "test_a.py/same#2", "test_a.py/C/m"}
    assert not ex.candidate_ids
    assert len(metadata["positives"]) == 3


def test_content_overlap_is_reported_without_changing_selection(tmp_path: Path) -> None:
    recording = synthetic_recording(4)
    text = (
        "def changed():\n    long_value_one = 'informative copied statement one'\n"
        "    long_value_two = 'informative copied statement two'\n"
        "    return long_value_one + long_value_two\n"
    )
    for row in recording["snapshots"].values():
        if row["files"]["code.py"].startswith("def changed()"):
            row["files"]["code.py"] = row["files"]["code.py"].replace(
                "def changed():\n    return 1\n", text
            )
    index = build_index([text])
    result = run_recording(tmp_path, recording, overlap_index=index, overlap_identity="test-index")
    assert result["content_overlap"]["status"] == "computed"
    assert not result["content_overlap"]["applied_as_filter"]
    assert result["counts"]["kept"] == 7
    assert result["content_overlap"]["rows"][0]["units_covered"] > 0


def test_bm25_calls_existing_ranks_without_filtering(tmp_path: Path) -> None:
    recording = synthetic_recording(4)
    run_recording(tmp_path, recording)
    before = read_cache(str(tmp_path / "pool.jsonl.gz"))
    report = rank_audit(tmp_path)
    bm25, dense = report["comparison"][:2]
    assert bm25["teacher"] == "bm25" and bm25["share"] > 0
    assert dense["n"] == 0 and dense["share"] is None
    assert report["comparison"][4]["teacher"] == "swerankembed-small"
    assert read_cache(str(tmp_path / "pool.jsonl.gz")) == before
    assert len(json.loads((tmp_path / "ranks.json").read_text())) == sum(
        len(e.positive_ids) for e in before
    )


def test_full_scale_rejected_before_any_request(tmp_path: Path) -> None:
    recording = synthetic_recording(4)
    for key, value in [("repositories", 201), ("pull_requests", 2001)]:
        config = dict(recording["config"], **{key: value})
        with pytest.raises(ValueError, match="pilot limits"):
            mine(
                config,
                tmp_path,
                Client(tmp_path / "api", RecordedTransport(recording)),
                RecordedSnapshots(recording),
                recording["held_out"],
                source_kind="synthetic",
            )


def test_added_function_has_no_base_positive_and_bad_parse_is_quarantined(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def old():\n    return 1\n")
    # Addition after a blank line still anchors the old function's last line only if adjoining.
    diff = (
        "diff --git a/new.py b/new.py\n--- /dev/null\n+++ b/new.py\n"
        "@@ -0,0 +1,2 @@\n+def new():\n+    return 1"
    )
    ex, meta = extract_example("o/r", 1, [], tmp_path, diff)
    assert ex is None and meta["outcome"] == "no_overlapping_function"
    (tmp_path / "bad.py").write_text("def broken(:")
    ex, meta = extract_example("o/r", 1, [], tmp_path, diff)
    assert ex is None and meta["outcome"] == "parse_incomplete"
    assert meta["parse_errors"]


def test_historical_base_excludes_target_updates_after_upstream_sync(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(work), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "--quiet", "-b", "target")
    (work / "a.py").write_text("def edited():\n    return 1\n")
    git("add", "a.py")
    git("commit", "--quiet", "-m", "base")
    git("switch", "--quiet", "-c", "feature")
    (work / "a.py").write_text("def edited():\n    return 2\n")
    git("commit", "--quiet", "-am", "feature")
    git("switch", "--quiet", "target")
    (work / "upstream.py").write_text("def synced():\n    return 1\n")
    git("add", "upstream.py")
    git("commit", "--quiet", "-m", "upstream sync point")
    sync = git("rev-parse", "HEAD")
    git("switch", "--quiet", "feature")
    git("merge", "--quiet", "--no-edit", "target")
    head = git("rev-parse", "HEAD")
    git("switch", "--quiet", "target")
    (work / "unrelated.py").write_text("def unrelated():\n    return 1\n")
    git("add", "unrelated.py")
    git("commit", "--quiet", "-m", "later target advance")
    target = git("rev-parse", "HEAD")
    git("merge", "--quiet", "--no-edit", "--no-ff", "feature")
    merged = git("rev-parse", "HEAD")

    def transport(method: str, url: str, body: dict | None) -> Response:
        if "/git/commits/" in url:
            return Response(200, {"parents": [{"sha": target}, {"sha": head}]}, {})
        assert f"/compare/{target}...{head}" in url
        return Response(200, {"merge_base_commit": {"sha": git("merge-base", target, head)}}, {})

    base, metadata = historical_base(
        Client(tmp_path / "api", transport),
        "o/r",
        1,
        {"head": {"sha": head}, "base": {"sha": merged}, "merge_commit_sha": merged},
    )
    assert base == sync and metadata["target_before_merge"] == target
    cache = tmp_path / "git" / "o__r"
    subprocess.run(["git", "init", "--bare", "--quiet", str(cache)], check=True)
    subprocess.run(
        ["git", "--git-dir", str(cache), "fetch", "--quiet", str(work), head], check=True
    )
    scratch = tmp_path / "snapshot"
    scratch.mkdir()
    diff = GitSnapshots(tmp_path / "git").materialize("o/r", base, head, scratch)
    assert set(changed_lines(diff)) == {"a.py"}
    example, _ = extract_example("o/r", 1, [{"title": "issue"}], scratch, diff)
    assert example is not None and example.positive_ids == ("a.py/edited",)
    assert "upstream.py/synced" in example.candidate_ids
    assert "unrelated.py/unrelated" not in example.ids


def test_unsupported_squash_history_is_quarantined(tmp_path: Path) -> None:
    sha = "a" * 40
    client = Client(tmp_path, lambda *_: Response(200, {"parents": [{"sha": "b" * 40}]}, {}))
    base, metadata = historical_base(
        client, "o/r", 1, {"head": {"sha": sha}, "merge_commit_sha": "c" * 40}
    )
    assert base is None and "quarantined" in metadata["base_selection"]


def test_dense_cache_checks_identities_and_finite_values(tmp_path: Path) -> None:
    recording = synthetic_recording(4)
    provenance = run_recording(tmp_path, recording)
    examples = read_cache(str(tmp_path / "pool.jsonl.gz"))
    document = {
        "run_identity": provenance["run_identity"],
        "encoder": ENCODER,
        "instances": {
            ex.instance_id: {
                "ids": list(ex.ids),
                "query_sha256": digest(ex.query),
                "texts_sha256": digest(list(ex.positive_texts + ex.candidate_texts)),
                "scores": [0.0] * len(ex.ids),
            }
            for ex in examples
        },
    }
    scores = tmp_path / "scores.json"
    scores.write_text(json.dumps(document))
    assert rank_audit(tmp_path, dense_scores=scores)["comparison"][1]["share"] == 0.0
    row = document["instances"][examples[0].instance_id]
    row["scores"][0] = float("nan")
    scores.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="finite"):
        rank_audit(tmp_path, dense_scores=scores)
    row["scores"][0] = 0
    row["query_sha256"] = "wrong"
    scores.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="identity mismatch"):
        rank_audit(tmp_path, dense_scores=scores)


def test_dense_execution_requires_allocation_and_real_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    with pytest.raises(ValueError, match="Slurm"):
        dense_audit_scores(tmp_path)
    recording = synthetic_recording(3)
    run_recording(tmp_path, recording)
    assert rank_audit(tmp_path)["comparison"][0]["n"] == 0
    monkeypatch.setenv("RIL_CLUSTER", "1")
    monkeypatch.setenv("SLURM_JOB_ID", "17")
    monkeypatch.setenv("SLURM_JOB_GPUS", "0")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    with pytest.raises(ValueError, match="real pilot"):
        dense_audit_scores(tmp_path)
