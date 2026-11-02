"""Job entry points of the mined set: blocker check, pilot run, packing (designs D60, D66).

Implements ``docs/experiments/B.md`` E-MINE-PILOT. The scripts under ``scripts/`` only parse
arguments and call these functions.

**No live run without a token.** :func:`require_token` raises :class:`TokenMissing` when the
environment holds no ``GITHUB_TOKEN``; there is no flag that skips it. Unauthenticated calls allow
60 requests an hour, which cannot hold a pilot, and running slower on that quota would be a
different experiment than the one specified.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from typing import Any

from ril.data_mining.config import MiningConfig
from ril.data_mining.github_api import (
    ApiClient,
    ApiError,
    ClientConfig,
    EtagStore,
    Transport,
    UrllibTransport,
    token_from_env,
    token_present,
)
from ril.data_mining.population import Population, first_repos, select_population
from ril.data_mining.runner import list_population, mine_selected, select_prs
from ril.data_mining.snapshot import SnapshotProvider
from ril.data_mining.store import MiningStore, dumps, write_provenance
from ril.data_mining.summary import build_summary, yield_table
from ril.training import pool_ranks as pr_tools


class TokenMissing(RuntimeError):
    """The live run needs ``GITHUB_TOKEN`` and the environment has none."""


def require_token() -> str:
    """The token, or :class:`TokenMissing` (the message never contains a value)."""
    token = token_from_env()
    if token is None:
        raise TokenMissing(
            "GITHUB_TOKEN is not set: the live run is blocked (decision D2: the engineer provides "
            "a read-only token on Ada); nothing was fetched"
        )
    return token


def blocker_report(transport: Transport | None = None) -> dict[str, Any]:
    """Token presence (never the value) and the unauthenticated rate-limit probe, as a record."""
    client = ApiClient(
        transport or UrllibTransport(timeout=20.0),
        token=token_from_env(),
        config=ClientConfig(retries=1, min_interval=0.0),
    )
    report: dict[str, Any] = {"token_present": token_present()}
    try:
        doc = client.get_json("/rate_limit")
        core = (doc.get("resources") or {}).get("core") or {}
        report["api_reachable"] = True
        report["core_limit"] = core.get("limit")
        report["core_remaining"] = core.get("remaining")
    except (ApiError, OSError) as exc:
        report["api_reachable"] = False
        report["error"] = type(exc).__name__
    return report


def pool_directory_names(listing_path: str) -> list[str]:
    """Directory names of the published pool from a zip listing with member offsets."""
    with open(listing_path, encoding="utf-8") as handle:
        doc = json.load(handle)
    groups = pr_tools.group_members(doc["members"], "train/python/")
    return sorted(groups)


def population_from_listing(
    listing_path: str, is_held_out: Callable[[str], bool], config: MiningConfig
) -> Population:
    """The D60 population: the pool's first ``pool_size`` directories after the held-out filter."""
    return select_population(
        pool_directory_names(listing_path),
        is_held_out=is_held_out,
        seed=config.seed,
        pool_size=config.pool_size,
    )


def run_pilot(
    *,
    config: MiningConfig,
    out_root: str,
    population: Population,
    is_held_out: Callable[[str], bool],
    client: ApiClient,
    snapshots: SnapshotProvider,
    created: str,
    code_commit: str,
    stop_after: int | None = None,
    repos: list[str] | None = None,
) -> dict[str, Any]:
    """List, select and mine (resumable), then write the summary and ``provenance.json``.

    ``repos`` overrides the population's first ``n_repos`` (stage M1 validates on five).
    """
    store = MiningStore(out_root)
    store.ensure_run(config.config_hash(), created)
    budget_before = client.budget.to_dict()
    names = repos if repos is not None else first_repos(population, config.n_repos)
    listings, stats = list_population(client, names, store, is_held_out=is_held_out)
    selected = select_prs(listings, config, population.published)
    session = mine_selected(
        selected,
        client=client,
        snapshots=snapshots,
        store=store,
        config=config,
        stop_after=stop_after,
    )
    budget = store.add_budget(budget_delta(budget_before, client.budget.to_dict()))
    summary = build_summary(store, listings, population)
    summary["listing"] = {
        "not_found": sorted(stats.not_found),
        "renamed": dict(sorted(stats.renamed.items())),
        "renamed_into_held_out": sorted(stats.renamed_into_held_out),
    }
    summary["selected_prs"] = len(selected)
    write_provenance(
        store,
        config=config.to_dict(),
        config_hash=config.config_hash(),
        created=created,
        authenticated=client.authenticated,
        counts=yield_table(store, listings),
        budget=budget,
        population=population.counts,
        code_commit=code_commit,
    )
    store.log_session(
        {
            "listed_now": stats.listed,
            "listings_reused": stats.reused,
            "listing_failed": dict(sorted(stats.failed.items())),
            "attempted": session.attempted,
            "skipped": session.skipped,
            "adopted": session.adopted,
            "outcomes": dict(sorted(session.outcomes.items())),
            "stopped": session.stopped,
            "api": budget_delta(budget_before, client.budget.to_dict()),
        }
    )
    path = os.path.join(out_root, "summary.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(dumps(summary) + "\n")
    os.replace(tmp, path)
    return {
        "attempted": session.attempted,
        "skipped": session.skipped,
        "adopted": session.adopted,
        "outcomes": session.outcomes,
        "stopped": session.stopped,
        "summary": path,
    }


def budget_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Counters added between two readings of one client's budget (a client may serve several
    sessions in one process; the run root counts each call once)."""
    out: dict[str, Any] = {}
    for key, value in after.items():
        if key == "by_endpoint":
            prev = before.get("by_endpoint") or {}
            out[key] = {
                ep: n - int(prev.get(ep, 0))
                for ep, n in value.items()
                if n - int(prev.get(ep, 0)) != 0
            }
        else:
            out[key] = value - before.get(key, 0)
    return out


def jsonl_sink(path: str) -> Callable[[dict[str, Any]], None]:
    """Event sink appending one JSON line per API call and sleep (the rate-limit budget log)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def write(event: dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(dumps(event) + "\n")

    return write


def etag_store_for(out_root: str) -> EtagStore:
    """The conditional-request store of a run root (under ``etag/``)."""
    return EtagStore(os.path.join(out_root, "etag"))


def summarize_budget(budget: Mapping[str, Any]) -> str:
    """One line of the cumulative API budget for logs."""
    return (
        f"calls={budget.get('calls', 0)} rest={budget.get('rest_calls', 0)} "
        f"graphql={budget.get('graphql_calls', 0)} 304={budget.get('not_modified', 0)} "
        f"retries={budget.get('retries', 0)} slept_s={budget.get('slept_seconds', 0)}"
    )
