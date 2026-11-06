"""The resumable mining run: list, select, mine, record (designs D60, D64, D66).

Implements ``docs/experiments/B.md`` E-MINE-PILOT. Order of work: for each repository of the
population, list its merged pull requests with their closing issues (stored once); take the
linked ones; select the pull requests to mine as a seeded sample; mine each (skipping every one
that already has a state row) and record the outcome right after its directory is in place.
A run twice from the same state does no API call and rewrites nothing.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ril.data_mining.config import MiningConfig
from ril.data_mining.diff import Comparison
from ril.data_mining.github_api import ApiClient, ApiError, NotFound
from ril.data_mining.links import PR_PAGE_QUERY, PullRequest, parse_pr_page
from ril.data_mining.miner import STATUS_MINED, Outcome, compare_for, mine_pr, needs_snapshot
from ril.data_mining.snapshot import SnapshotProvider
from ril.data_mining.store import MiningStore
from ril.training import pool_ranks as pr_tools
from ril.util.log import get_logger

log = get_logger("data_mining.runner")
MAX_PAGES_PER_REPO = 2000
"""Safety bound on listing pages of one repository (50 pull requests each)."""


@dataclass
class ListingStats:
    """What listing the population found and skipped."""

    listed: int = 0
    reused: int = 0
    not_found: list[str] = field(default_factory=list)
    renamed: dict[str, str] = field(default_factory=dict)
    renamed_into_held_out: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


def list_repository(
    client: ApiClient, repo: str, store: MiningStore
) -> tuple[list[PullRequest], Mapping[str, Any]]:
    """All merged pull requests of ``repo`` with their closing issues, stored under the run root."""
    owner, _, name = repo.partition("/")
    cursor: str | None = None
    prs: list[PullRequest] = []
    info: Mapping[str, Any] = {}
    for _ in range(MAX_PAGES_PER_REPO):
        data = client.graphql(PR_PAGE_QUERY, {"owner": owner, "name": name, "cursor": cursor})
        page, cursor, info = parse_pr_page(data, repo)
        prs.extend(page)
        if cursor is None:
            break
    else:
        raise ApiError(0, f"{repo}: more than {MAX_PAGES_PER_REPO} listing pages")
    store.save_listing(repo, prs, info)
    return prs, info


def list_population(
    client: ApiClient,
    repos: Sequence[str],
    store: MiningStore,
    *,
    is_held_out: Callable[[str], bool],
    after_listed: Callable[[], None] | None = None,
) -> tuple[dict[str, list[PullRequest]], ListingStats]:
    """Listings of every repository (stored ones reused). A repository that has been renamed into
    the held-out list is dropped and counted (D65). ``after_listed`` runs after each repository
    listed from the API, so a long listing job can push what it has (a failure loses no finished
    listing)."""
    out: dict[str, list[PullRequest]] = {}
    stats = ListingStats()
    for repo in repos:
        if store.has_listing(repo):
            header, prs = store.load_listing(repo)
            stats.reused += 1
            if header.get("missing"):
                stats.not_found.append(repo)
                continue
        else:
            try:
                prs, info = list_repository(client, repo, store)
            except NotFound as exc:
                store.save_tombstone(repo, str(exc.status))
                stats.not_found.append(repo)
                continue
            except ApiError as exc:
                stats.failed[repo] = str(exc)[:120]
                continue
            header = {"current_name": str(info.get("nameWithOwner") or repo).lower()}
            stats.listed += 1
            if after_listed is not None:
                after_listed()
        current = str(header["current_name"])
        if current != repo.lower():
            stats.renamed[repo] = current
            if is_held_out(current):
                stats.renamed_into_held_out.append(repo)
                continue
        out[repo] = prs
    return out, stats


def select_prs(
    listings: Mapping[str, Sequence[PullRequest]],
    config: MiningConfig,
    published: Mapping[str, frozenset[int]] | None = None,
) -> list[PullRequest]:
    """The linked pull requests to mine: a seeded order, the first ``max_prs``.

    With ``config.published_first`` (validation stage only) the linked pull requests that the
    published pool holds come first, in the same seeded order, so the agreement with the pool is
    measured on all of them; the rest of the budget is the seeded sample.

    The order key is ``sha256("<seed>:<repo>#<number>")``, stable across machines. A pull request
    appears once however many issues it closes (the pair multiplicity is reported separately).
    """
    linked = [p for repo in sorted(listings) for p in listings[repo] if p.issues]
    held = published or {}

    def order(p: PullRequest) -> tuple[int, str]:
        first = config.published_first and p.number in held.get(p.repo, frozenset())
        return (0 if first else 1, pr_tools.seeded_key(config.seed, p.key))

    return sorted(linked, key=order)[: config.max_prs]


@dataclass
class RunSummary:
    """Result of one session of :func:`mine_selected`."""

    attempted: int = 0
    skipped: int = 0
    adopted: int = 0
    outcomes: dict[str, int] = field(default_factory=dict)
    stopped: bool = False


def mine_selected(
    selected: Iterable[PullRequest],
    *,
    client: ApiClient,
    snapshots: SnapshotProvider,
    store: MiningStore,
    config: MiningConfig,
    on_outcome: Callable[[Outcome], None] | None = None,
    stop_after: int | None = None,
    lookahead: int = 1,
    after_record: Callable[[], None] | None = None,
) -> RunSummary:
    """Mine the selected pull requests that have no state row; record each right away.

    ``stop_after`` ends the session after that many pull requests (a bounded session or a test of
    resumption). A crash between the directory rename and the state row is repaired on the next
    session by adopting the complete directory. With ``lookahead`` above 1 the compare calls of
    the next pull requests are made ahead and their base commits are fetched in the background
    while the current one is parsed; pull requests are still mined and recorded in the selected
    order, so the outputs do not depend on ``lookahead``. ``after_record`` is called after each
    state row (the copy of the run root to a durable area, ``durable.Syncer.tick``).
    """
    summary = RunSummary()
    store.clean_partial()
    state = store.load_state()
    for adopted in store.adopt_unrecorded(state):
        store.record(adopted)
        state[adopted.key] = adopted.row()
        summary.adopted += 1
    pending: Iterator[PullRequest] = iter(selected)
    window: deque[tuple[PullRequest, Comparison | Outcome]] = deque()
    exhausted = False
    planned = 0

    def refill() -> None:
        nonlocal exhausted, planned
        while not exhausted and len(window) < max(1, lookahead):
            if stop_after is not None and planned >= stop_after:
                return
            nxt = next(pending, None)
            if nxt is None:
                exhausted = True
                return
            if nxt.key in state:
                summary.skipped += 1
                continue
            planned += 1
            fetched = compare_for(nxt, client)
            if isinstance(fetched, Comparison) and needs_snapshot(fetched):
                snapshots.prefetch(nxt.repo, fetched.merge_base)
            window.append((nxt, fetched))

    try:
        refill()
        while window:
            pr, fetched = window.popleft()
            outcome = mine_pr(
                pr, client=client, snapshots=snapshots, config=config, comparison=fetched
            )
            if outcome.status == STATUS_MINED and outcome.instance is not None:
                store.write_instance(outcome.instance)
            if on_outcome is not None:
                on_outcome(outcome)  # test hook: may raise to simulate a crash before the row
            store.record(outcome)
            state[pr.key] = outcome.row()
            if after_record is not None:
                after_record()
            summary.attempted += 1
            summary.outcomes[outcome.status] = summary.outcomes.get(outcome.status, 0) + 1
            refill()
        if not exhausted:  # the session was bounded: count what is already done, note the rest
            for rest in pending:
                if rest.key in state:
                    summary.skipped += 1
                    continue
                summary.stopped = True
                break
    finally:
        snapshots.close()
    return summary
