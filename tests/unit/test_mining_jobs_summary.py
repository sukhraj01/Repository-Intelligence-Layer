"""Job layer, summary tables and the rank comparison (E-MINE-PILOT, M0 gate; synthetic inputs)."""

from __future__ import annotations

import json
import os

import pytest

from ril.data_mining import jobs
from ril.data_mining.config import MiningConfig
from ril.data_mining.github_api import ApiClient, ClientConfig
from ril.data_mining.pack import list_dirs
from ril.data_mining.population import select_population
from ril.data_mining.rank_compare import (
    MIN_DIRECTORIES,
    min_ranks,
    rank_sample,
    reading_rule,
    share_row,
    wilson,
)
from ril.data_mining.snapshot import MemorySnapshots
from tests.unit._mining_fixtures import (
    FakeClock,
    FakeTransport,
    compare_doc,
    graphql_page,
    issue_node,
    json_response,
    pr_node,
)
from tests.unit.test_mining_pipeline import MB, MODIFY, OLD, OTHER, REPO, tree_digest

POOL_NAMES = [f"acme__widgets-{n}" for n in (1, 2)] + ["zeta__other-3"]


def synthetic_client(prs: int = 4) -> tuple[ApiClient, MemorySnapshots, FakeTransport]:
    nodes = [pr_node(n, [issue_node(100 + n)]) for n in range(1, prs + 1)]
    tr = FakeTransport()
    tr.add("POST", "/graphql", lambda u, b: json_response(graphql_page(REPO, nodes)))
    tr.add(
        "GET",
        f"/repos/{REPO}/compare/",
        lambda u, b: json_response(compare_doc(MB, "h" * 40, MODIFY)),
    )
    client = ApiClient(tr, clock=FakeClock(), config=ClientConfig(retries=1, min_interval=0.0))
    return client, MemorySnapshots({(REPO, MB): {"m.py": OLD, "o.py": OTHER}}), tr


def test_token_gate_refuses_without_a_token_and_never_prints_one(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(jobs.TokenMissing) as err:
        jobs.require_token()
    assert "GITHUB_TOKEN" in str(err.value)
    monkeypatch.setenv("GITHUB_TOKEN", "sentinel-token-value")
    assert jobs.require_token() == "sentinel-token-value"


def test_blocker_report_has_presence_but_no_value(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "sentinel-token-value")
    tr = FakeTransport()
    tr.add(
        "GET",
        "/rate_limit",
        lambda u, b: json_response({"resources": {"core": {"limit": 5000, "remaining": 4999}}}),
    )
    report = jobs.blocker_report(tr)
    assert report == {
        "token_present": True,
        "api_reachable": True,
        "core_limit": 5000,
        "core_remaining": 4999,
    }
    assert "sentinel-token-value" not in json.dumps(report)
    down = jobs.blocker_report(FakeTransport())  # 404 on /rate_limit
    assert down["api_reachable"] is False


def test_pilot_run_writes_provenance_summary_and_is_idempotent(tmp_path) -> None:
    client, snaps, tr = synthetic_client()
    cfg = MiningConfig(n_repos=1, max_prs=3)
    pop = select_population(POOL_NAMES, is_held_out=lambda r: False, seed=0, pool_size=10)
    kw = {
        "config": cfg,
        "out_root": str(tmp_path / "run"),
        "population": pop,
        "is_held_out": lambda r: False,
        "client": client,
        "snapshots": snaps,
        "created": "2026-11-02",
        "code_commit": "abc1234",
        "repos": [REPO],
    }
    first = jobs.run_pilot(**kw)
    assert first["attempted"] == 3 and first["outcomes"] == {"mined": 3}
    prov = json.load(open(tmp_path / "run" / "provenance.json"))
    assert prov["token"]["authenticated"] is False and "never recorded" in prov["token"]["scope"]
    assert prov["counts"]["prs_mined"] == 3 and prov["config_hash"] == cfg.config_hash()
    assert prov["api_budget"]["graphql_calls"] >= 1 and prov["created"] == "2026-11-02"
    assert prov["api_calls_logged"]["calls"] == 0  # this run has no event sink
    summary = json.load(open(tmp_path / "run" / "summary.json"))
    assert summary["yield"]["merged_prs"] == 4 and summary["yield"]["positives_total"] == 3
    assert summary["mined"]["positives_per_pr"]["median"] == 1.0
    assert summary["links"]["multiplicity"]["pairs"] == 4
    before, calls = tree_digest(str(tmp_path / "run")), len(tr.calls)
    again = jobs.run_pilot(**kw)
    assert again["attempted"] == 0 and again["skipped"] == 3
    assert len(tr.calls) == calls and tree_digest(str(tmp_path / "run")) == before
    assert len(list_dirs(str(tmp_path / "run"))) == 3


def test_selection_analysis_splits_kept_and_dropped(tmp_path) -> None:
    client, snaps, _ = synthetic_client()
    cfg = MiningConfig(n_repos=1, max_prs=4)
    names = ["acme__widgets-1", "acme__widgets-2"]
    pop = select_population(names, is_held_out=lambda r: False, seed=0, pool_size=10)
    jobs.run_pilot(
        config=cfg,
        out_root=str(tmp_path / "run"),
        population=pop,
        is_held_out=lambda r: False,
        client=client,
        snapshots=snaps,
        created="2026-11-02",
        code_commit="x",
        repos=[REPO],
    )
    sel = json.load(open(tmp_path / "run" / "summary.json"))["selection"]
    assert sel["summary"] == {
        "repos": 1,
        "linked_prs": 4,
        "kept_by_pool": 2,
        "kept_share": 0.5,
        "published_not_linked": 0,
    }
    assert sel["kept_by_pool"]["prs"] == 2 and sel["dropped_by_pool"]["prs"] == 2


def test_wilson_and_share_rows() -> None:
    lo, hi = wilson(15, 100)
    assert 0.09 < lo < 0.15 < hi < 0.24
    assert wilson(0, 0) == (0.0, 0.0)
    ranks = {f"a__b-{i}": (11 if i < 3 else 2) for i in range(10)}
    repo_of = {d: "a/b" if int(d.split("-")[1]) < 5 else "c/d" for d in ranks}
    row = share_row("bm25", 10, ranks, repo_of, seed=0)
    assert (row.directories, row.no_positive_in_top_k, row.share) == (10, 3, 0.3)
    assert row.wilson_low < 0.3 < row.wilson_high and row.cluster_low <= row.cluster_high
    assert share_row("bm25", 10, ranks, repo_of, seed=0) == row  # deterministic


def test_min_ranks_takes_the_best_positive() -> None:
    rows = [{"dir": "a__b-1", "ranks": [{"rank": 40}, {"rank": 7}]}, {"dir": "a__b-2", "ranks": []}]
    assert min_ranks(rows) == {"a__b-1": 7}


def test_reading_rule_below_and_above_the_minimum() -> None:
    small = reading_rule(40, 0.2)
    assert (
        small["reading"] == "too small to compare" and small["prs_needed_at_measured_yield"] == 500
    )
    assert reading_rule(MIN_DIRECTORIES, 0.5)["counts"] is True
    assert reading_rule(0, 0.0)["prs_needed_at_measured_yield"] is None


def test_rank_sample_covers_every_directory(tmp_path) -> None:
    client, snaps, _ = synthetic_client()
    cfg = MiningConfig(n_repos=1, max_prs=2)
    pop = select_population(POOL_NAMES, is_held_out=lambda r: False, seed=0, pool_size=10)
    root = str(tmp_path / "run")
    jobs.run_pilot(
        config=cfg,
        out_root=root,
        population=pop,
        is_held_out=lambda r: False,
        client=client,
        snapshots=snaps,
        created="2026-11-02",
        code_commit="x",
        repos=[REPO],
    )
    doc = rank_sample(root)
    assert len(doc["sample"]) == 2 and doc["listing_prefix"] == "train/python/"
    assert all(os.path.exists(os.path.join(root, "pr", r["dir"])) for r in doc["sample"])


def test_missing_repository_is_recorded_and_not_asked_again(tmp_path) -> None:
    from ril.data_mining.runner import list_population
    from ril.data_mining.store import MiningStore

    tr = FakeTransport()
    errors = {"errors": [{"type": "NOT_FOUND", "message": "Could not resolve to a Repository"}]}
    tr.add("POST", "/graphql", lambda u, b: json_response({"data": None, **errors}))
    client = ApiClient(tr, clock=FakeClock(), config=ClientConfig(retries=1, min_interval=0.0))
    store = MiningStore(str(tmp_path / "run"))
    listings, stats = list_population(client, [REPO], store, is_held_out=lambda r: False)
    assert listings == {} and stats.not_found == [REPO]
    calls = len(tr.calls)
    _, again = list_population(client, [REPO], store, is_held_out=lambda r: False)
    assert again.not_found == [REPO] and len(tr.calls) == calls


def test_agreement_job_against_the_run_packed_as_a_pool_and_handcheck_sample(tmp_path) -> None:
    from ril.data_mining import validation
    from ril.data_mining.pack import listing_of, local_fetch, pack_zip
    from ril.training.pool_ranks import group_members

    client, snaps, _ = synthetic_client()
    pop = select_population(POOL_NAMES, is_held_out=lambda r: False, seed=0, pool_size=10)
    root = str(tmp_path / "run")
    jobs.run_pilot(
        config=MiningConfig(n_repos=1, max_prs=3),
        out_root=root,
        population=pop,
        is_held_out=lambda r: False,
        client=client,
        snapshots=snaps,
        created="2026-11-02",
        code_commit="abc1234",
        repos=[REPO],
    )
    zip_path = str(tmp_path / "pool.zip")
    pack_zip(root, zip_path)
    doc = listing_of(zip_path, zip_path)
    members = group_members(doc["members"], "train/python/")
    out = validation.agreement_job(root, zip_path, members, fetch=local_fetch)
    assert out["mined_directories"] == 3 and out["also_in_pool"] == 3
    assert out["pool_fetch_errors"] == []
    assert out["table"]["prs_compared"] == 3
    assert (
        out["table"]["all"]["exact_share"] == 1.0
        and out["table"]["non_test"]["jaccard_mean"] == 1.0
    )
    assert out["rows"][0]["corpus_jaccard"] == 1.0
    empty = validation.agreement_job(root, zip_path, {}, fetch=local_fetch)
    assert empty["also_in_pool"] == 0 and empty["table"]["prs_compared"] == 0
    first = validation.handcheck_sample(root, 2, 0)
    assert first == validation.handcheck_sample(root, 2, 0) and len(first) == 2


def test_rank_glue_prepares_the_run_and_ranks_with_bm25_through_the_pool_tooling(tmp_path) -> None:
    from ril.data_mining import rank_jobs

    client, snaps, _ = synthetic_client()
    pop = select_population(POOL_NAMES, is_held_out=lambda r: False, seed=0, pool_size=10)
    root = str(tmp_path / "run")
    jobs.run_pilot(
        config=MiningConfig(n_repos=1, max_prs=3),
        out_root=root,
        population=pop,
        is_held_out=lambda r: False,
        client=client,
        snapshots=snaps,
        created="2026-11-02",
        code_commit="abc1234",
        repos=[REPO],
    )
    work = str(tmp_path / "work")
    assert rank_jobs.prepare(root, work)["directories"] == 3
    first = open(os.path.join(work, "mined.zip"), "rb").read()
    rank_jobs.prepare(root, work)
    assert open(os.path.join(work, "mined.zip"), "rb").read() == first
    ranks = str(tmp_path / "ranks_bm25.jsonl")
    res = rank_jobs.bm25(work, ranks)
    assert res["selected"] == 3 and res["written"] == 3
    assert rank_jobs.bm25(work, ranks)["written"] == 0  # resumable
    out = rank_jobs.tables(os.path.join(work, "sample.json"), [ranks], yield_per_pr=1.0)
    assert {r["k"] for r in out["rows"]} == {10, 20, 40}
    assert all(r["directories"] == 3 and r["teacher"] == "bm25" for r in out["rows"])
    assert out["reading"]["reading"] == "too small to compare"
    assert out["reading"]["prs_needed_at_measured_yield"] == 100


def test_listing_shards_write_only_their_repositories_and_no_mining_outputs(tmp_path) -> None:
    client, snaps, _ = synthetic_client()
    pop = select_population(POOL_NAMES, is_held_out=lambda r: False, seed=0, pool_size=10)
    root = str(tmp_path / "run")
    common = {
        "config": MiningConfig(n_repos=2, max_prs=3),
        "out_root": root,
        "population": pop,
        "is_held_out": lambda r: False,
        "client": client,
        "snapshots": snaps,
        "created": "2026-11-02",
        "code_commit": "abc1234",
        "repos": [REPO, "zeta/other"],
        "list_only": True,
    }
    res = jobs.run_pilot(shard=(0, 2), **common)
    assert res["listed"] == 1 and res["failed"] == {}
    assert sorted(os.listdir(os.path.join(root, "listing"))) == ["acme__widgets.json"]
    assert not os.path.exists(os.path.join(root, "pr")) and not os.path.exists(
        os.path.join(root, "summary.json")
    )
    res2 = jobs.run_pilot(shard=(1, 2), **common)
    assert res2["listed"] == 1
    assert len(os.listdir(os.path.join(root, "listing"))) == 2
    full = jobs.run_pilot(**{**common, "list_only": False})  # the mining session reuses both
    assert full["attempted"] == 3
    sessions = [json.loads(x) for x in open(os.path.join(root, "sessions.jsonl"))]
    assert sessions[-1]["listings_reused"] == 2 and sessions[-1]["listed_now"] == 0


def test_etag_store_can_be_switched_off(tmp_path) -> None:
    on = jobs.etag_store_for(str(tmp_path))
    off = jobs.etag_store_for(str(tmp_path), enabled=False)
    on.put("k" * 64, "e", b"x")
    off.put("j" * 64, "e", b"x")
    assert on.get("k" * 64) is not None and off.get("j" * 64) is None
    assert not os.path.exists(os.path.join(str(tmp_path), "etag", "jj"))


def test_command_line_accepts_the_run_options_the_job_script_passes() -> None:
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "scripts/mine_pilot.py", "run", "--help"],
        capture_output=True,
        check=True,
    ).stdout.decode()
    for flag in (
        "--list-only",
        "--shard",
        "--etag-cache",
        "--lookahead",
        "--stop-after",
        "--repos",
    ):
        assert flag in out


def test_median_difference_interval_is_clustered_deterministic_and_handles_empty_groups() -> None:
    from ril.data_mining.summary import median_difference_interval

    kept = {f"r{i}": [10.0 + i % 3, 11.0] for i in range(12)}
    dropped = {f"r{i}": [2.0 + i % 2, 3.0] for i in range(12)}
    a = median_difference_interval(kept, dropped)
    assert a == median_difference_interval(kept, dropped)
    assert a["difference"] > 6 and a["excludes_zero"] is True and a["interval"][0] > 0
    same = median_difference_interval(kept, kept)
    assert same["difference"] == 0 and same["excludes_zero"] is False
    empty = median_difference_interval({}, dropped)
    assert empty["difference"] is None and empty["excludes_zero"] is None and empty["kept_n"] == 0


def test_report_renders_tables_and_measures_unit_costs_of_a_run(tmp_path) -> None:
    from ril.data_mining import report

    client, snaps, _ = synthetic_client()
    pop = select_population(POOL_NAMES, is_held_out=lambda r: False, seed=0, pool_size=10)
    root = str(tmp_path / "run")
    jobs.run_pilot(
        config=MiningConfig(n_repos=1, max_prs=3),
        out_root=root,
        population=pop,
        is_held_out=lambda r: False,
        client=client,
        snapshots=snaps,
        created="2026-11-02",
        code_commit="abc1234",
        repos=[REPO],
    )
    text = report.render(json.load(open(os.path.join(root, "summary.json"))))
    for heading in (
        "### Yield",
        "### Parse failures",
        "### Links",
        "### Selection by the published pool",
        "### Test-file positives",
    ):
        assert heading in text
    assert "prs_mined | 3" in text.replace("  ", " ")
    disk = report.disk_use(root)
    assert disk["mined_dirs"] == 3 and disk["pr_files"] == 12 and disk["bytes_per_mined_pr"] > 0
    secs = report.session_seconds(root)
    assert secs["listing"] >= 0 and secs["mining"] >= 0
    assert report.api_totals(root)["calls"] == 0  # no event sink in this run


def test_rank_estimate_counts_distinct_texts_per_repository_and_outside_tests(tmp_path) -> None:
    from ril.data_mining import rank_jobs

    client, snaps, _ = synthetic_client()
    pop = select_population(POOL_NAMES, is_held_out=lambda r: False, seed=0, pool_size=10)
    root = str(tmp_path / "run")
    jobs.run_pilot(
        config=MiningConfig(n_repos=1, max_prs=3),
        out_root=root,
        population=pop,
        is_held_out=lambda r: False,
        client=client,
        snapshots=snaps,
        created="2026-11-02",
        code_commit="abc1234",
        repos=[REPO],
    )
    est = rank_jobs.estimate(root, 100.0, teachers=2)
    assert est["directories"] == 3 and est["repositories"] == 1
    assert est["corpus_rows"]["all"] == 3 * est["distinct_texts"]["all"]  # same snapshot, three PRs
    assert est["distinct_texts"]["non_test"] <= est["distinct_texts"]["all"]
    expect = round(2 * est["distinct_texts"]["all"] / 100.0 / 3600, 3)
    assert est["gpu_hours"]["all"] == expect


def test_every_subcommand_the_job_scripts_call_accepts_its_flags() -> None:
    import subprocess
    import sys

    wanted = {
        "rank-prepare": ("--drop-tests", "--limit"),
        "rank-estimate": ("--limit", "--texts-per-second"),
        "rank-dense": ("--teachers", "--cut", "--form"),
        "rank-bm25": ("--form",),
        "rank-tables": ("--ranks", "--yield-per-pr"),
        "agreement": ("--listing",),
        "handcheck": ("--n", "--seed"),
        "report": (),
        "pack": (),
    }
    for cmd, flags in wanted.items():
        out = subprocess.run(
            [sys.executable, "scripts/mine_pilot.py", cmd, "--help"],
            capture_output=True,
            check=True,
        ).stdout.decode()
        for flag in flags:
            assert flag in out, (cmd, flag)
