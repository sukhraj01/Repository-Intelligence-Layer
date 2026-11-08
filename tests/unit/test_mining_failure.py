"""Content errors quarantine one pull request, infrastructure errors end the session (DEV-036).

Synthetic fixtures (the shapes of ``tests/unit/test_mining_pipeline.py``): a pass proves the code
against these, not against the live service.
"""

from __future__ import annotations

import errno
import subprocess
import urllib.error

import pytest

from ril.data_mining import miner, runner
from ril.data_mining.config import MiningConfig
from ril.data_mining.failure import corpus_error_reason, is_infrastructure_error
from ril.data_mining.github_api import ApiError, NotFound, TransportError
from ril.data_mining.miner import STATUS_QUARANTINED, mine_pr
from ril.data_mining.runner import (
    QuarantineRateExceeded,
    list_population,
    mine_selected,
    select_prs,
)
from ril.data_mining.snapshot import (
    GitSnapshots,
    MemorySnapshots,
    SnapshotError,
    SnapshotTimeout,
)
from ril.data_mining.store import MiningStore
from tests.unit.test_mining_pipeline import MODIFY, REPO, build_run, link, setup


@pytest.mark.parametrize(
    "exc",
    [
        ApiError(502, "bad gateway"),
        NotFound(404, "gone"),
        TransportError("name resolution"),
        urllib.error.URLError("unreachable"),
        ConnectionResetError(),
        TimeoutError(),
        subprocess.TimeoutExpired("git", 900),
        MemoryError(),
        OSError(errno.ENOSPC, "no space"),
        OSError(errno.EDQUOT, "quota"),
        OSError(errno.EIO, "io"),
    ],
)
def test_infrastructure_errors_are_told_apart_by_type(exc) -> None:
    assert is_infrastructure_error(exc)


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("bad id"),
        KeyError("x"),
        RecursionError(),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"),
        OSError(errno.ENAMETOOLONG, "name too long"),
        OSError(errno.EILSEQ, "illegal byte sequence"),
        SnapshotError("no such commit"),
    ],
)
def test_content_errors_are_not_infrastructure(exc) -> None:
    assert not is_infrastructure_error(exc)
    assert corpus_error_reason(exc) == f"corpus_error:{type(exc).__name__}"


def boom(exc: Exception):
    def raiser(*args, **kwargs):
        raise exc

    return raiser


def test_content_exception_while_parsing_quarantines_the_pull_request(monkeypatch) -> None:
    client, snaps, _ = setup(MODIFY)
    monkeypatch.setattr(miner, "parse_repository", boom(RecursionError("deep")))
    out = mine_pr(link(), client=client, snapshots=snaps, config=MiningConfig())
    assert out.status == STATUS_QUARANTINED
    assert out.reason == "corpus_error:RecursionError" and out.instance is None
    assert out.key == f"{REPO}#7"


def test_content_exception_while_mapping_quarantines_the_pull_request(monkeypatch) -> None:
    client, snaps, _ = setup(MODIFY)
    monkeypatch.setattr(miner, "map_change", boom(IndexError("odd hunk")))
    out = mine_pr(link(), client=client, snapshots=snaps, config=MiningConfig())
    assert out.status == STATUS_QUARANTINED and out.reason == "corpus_error:IndexError"


@pytest.mark.parametrize(
    "exc", [OSError(errno.ENOSPC, "no space"), TransportError("down"), ApiError(500, "x")]
)
def test_infrastructure_exception_propagates_from_mine_pr(monkeypatch, exc) -> None:
    client, snaps, _ = setup(MODIFY)
    monkeypatch.setattr(miner, "parse_repository", boom(exc))
    with pytest.raises(type(exc)):
        mine_pr(link(), client=client, snapshots=snaps, config=MiningConfig())


def test_snapshot_timeout_is_its_own_quarantine_reason() -> None:
    class Slow(MemorySnapshots):
        def materialize(self, repo, sha, dest):
            raise SnapshotTimeout("git fetch ran past 900 s")

    client, _, _ = setup(MODIFY)
    out = mine_pr(link(), client=client, snapshots=Slow({}), config=MiningConfig())
    assert out.status == STATUS_QUARANTINED and out.reason == "snapshot_timeout"


def test_git_timeout_becomes_snapshot_timeout_without_a_retry(tmp_path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def hang(cmd, **kwargs):
        calls.append(cmd)
        if "fetch" in cmd:
            raise subprocess.TimeoutExpired(cmd, 900)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", hang)
    snaps = GitSnapshots(str(tmp_path / "w"), remote="file:///nowhere")
    with pytest.raises(SnapshotTimeout):
        snaps.materialize(REPO, "a" * 40, str(tmp_path / "d"))
    assert sum("fetch" in c for c in calls) == 1


def run_state(tmp_path, n_prs: int):
    client, snaps, _, store = build_run(tmp_path, n_prs=n_prs)
    cfg = MiningConfig(max_prs=n_prs)
    listings, _ = list_population(client, [REPO], store, is_held_out=lambda r: False)
    return client, snaps, store, cfg, select_prs(listings, cfg)


def test_unexpected_compare_exception_in_the_window_quarantines(tmp_path, monkeypatch) -> None:
    client, snaps, store, cfg, selected = run_state(tmp_path, 3)
    monkeypatch.setattr(runner, "compare_for", boom(AttributeError("odd json")))
    session = mine_selected(
        selected, client=client, snapshots=snaps, store=store, config=cfg, lookahead=2
    )
    assert session.outcomes == {STATUS_QUARANTINED: 3}
    reasons = {row["reason"] for row in store.load_state().values()}
    assert reasons == {"corpus_error:AttributeError"}


def test_quarantine_rate_above_the_limit_stops_the_session_after_the_row(
    tmp_path, monkeypatch
) -> None:
    client, snaps, store, cfg, selected = run_state(tmp_path, 8)
    monkeypatch.setattr(miner, "parse_repository", boom(RuntimeError("bug")))
    with pytest.raises(QuarantineRateExceeded, match="corpus_error:RuntimeError"):
        mine_selected(
            selected,
            client=client,
            snapshots=snaps,
            store=store,
            config=cfg,
            quarantine_window=4,
            quarantine_max_share=0.5,
        )
    assert len(store.load_state()) == 4  # the window is full at the fourth, which is recorded


def test_quarantine_rate_at_the_limit_does_not_stop_the_session(tmp_path, monkeypatch) -> None:
    client, snaps, store, cfg, selected = run_state(tmp_path, 8)
    real = miner.parse_repository
    seen = {"n": 0}

    def alternate(*args, **kwargs):
        seen["n"] += 1
        if seen["n"] % 2:
            raise RuntimeError("bug")
        return real(*args, **kwargs)

    monkeypatch.setattr(miner, "parse_repository", alternate)
    session = mine_selected(
        selected,
        client=client,
        snapshots=snaps,
        store=store,
        config=cfg,
        quarantine_window=4,
        quarantine_max_share=0.5,  # exactly half is allowed, more is not
    )
    assert session.attempted == 8


def test_infrastructure_error_ends_the_session_and_resumption_mines_each_pr_once(
    tmp_path, monkeypatch
) -> None:
    client, snaps, store, cfg, selected = run_state(tmp_path, 6)
    real = miner.parse_repository
    seen = {"n": 0}

    def flaky(*args, **kwargs):
        seen["n"] += 1
        if seen["n"] == 4:
            raise OSError(errno.ENOSPC, "no space")
        return real(*args, **kwargs)

    monkeypatch.setattr(miner, "parse_repository", flaky)
    with pytest.raises(OSError):
        mine_selected(selected, client=client, snapshots=snaps, store=store, config=cfg)
    assert len(store.load_state()) == 3
    resumed = MiningStore(str(tmp_path / "run"))
    second = mine_selected(selected, client=client, snapshots=snaps, store=resumed, config=cfg)
    assert second.skipped == 3 and second.attempted == 3
    assert len(resumed.load_state()) == 6
    # three before the failure, the failed one again, then the two that were never reached
    assert len(snaps.calls) == 3 + 1 + 3
