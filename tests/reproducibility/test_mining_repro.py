"""Same inputs, same seed, same bytes for the mined set (E-MINE-PILOT)."""

from __future__ import annotations

from ril.data_mining import jobs
from ril.data_mining.config import MiningConfig
from ril.data_mining.pack import pack_zip
from ril.data_mining.population import select_population
from tests.unit.test_mining_jobs_summary import POOL_NAMES, synthetic_client
from tests.unit.test_mining_pipeline import REPO, tree_digest


def run_once(root: str) -> None:
    client, snaps, _ = synthetic_client(prs=6)
    pop = select_population(POOL_NAMES, is_held_out=lambda r: False, seed=0, pool_size=10)
    jobs.run_pilot(
        config=MiningConfig(n_repos=1, max_prs=4),
        out_root=root,
        population=pop,
        is_held_out=lambda r: False,
        client=client,
        snapshots=snaps,
        created="2026-11-02",
        code_commit="abc1234",
        repos=[REPO],
    )


def test_two_fresh_runs_have_identical_outputs_and_zip(tmp_path) -> None:
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    run_once(a)
    run_once(b)
    assert tree_digest(a) == tree_digest(b)
    pack_zip(a, str(tmp_path / "a.zip"))
    pack_zip(b, str(tmp_path / "b.zip"))
    assert (tmp_path / "a.zip").read_bytes() == (tmp_path / "b.zip").read_bytes()


def test_selection_does_not_depend_on_listing_order(tmp_path) -> None:
    from ril.data_mining.runner import select_prs

    client, _, _ = synthetic_client(prs=6)
    from ril.data_mining.store import MiningStore

    store = MiningStore(str(tmp_path / "r"))
    from ril.data_mining.runner import list_population

    listings, _ = list_population(client, [REPO], store, is_held_out=lambda r: False)
    forward = [p.number for p in select_prs(listings, MiningConfig(max_prs=3))]
    reversed_listing = {r: list(reversed(v)) for r, v in listings.items()}
    backward = [p.number for p in select_prs(reversed_listing, MiningConfig(max_prs=3))]
    assert forward == backward
