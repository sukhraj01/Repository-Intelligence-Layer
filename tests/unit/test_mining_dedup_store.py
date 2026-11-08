"""The de-duplicated corpus store, the materialise step and the durable copy (D93, D94)."""

from __future__ import annotations

import os

import pytest

from ril.data_mining import cas, durable
from ril.data_mining.miner import MinedInstance
from ril.data_mining.store import LAYOUT_DEDUP, MiningStore


def _inst(repo: str, number: int, corpus: list[tuple[str, str]], positives: list[str]):
    dir_name = f"{repo.replace('/', '__')}-{number}"
    return MinedInstance(
        repo,
        number,
        dir_name,
        f"query {number}",
        "m" * 40,
        corpus,
        positives,
        {"repo": repo, "pr": number, "counters": {"positives": len(positives)}},
    )


def _instances() -> list[MinedInstance]:
    base = [(f"a.py/f{i}", f"def f{i}(): return {i}") for i in range(40)]
    changed = [*base[:30], ("a.py/f30", "def f30(): return 'new'"), *base[31:]]
    return [
        _inst("acme/widgets", 1, base, ["a.py/f3"]),
        _inst("acme/widgets", 2, changed, ["a.py/f30"]),
        _inst("acme/widgets", 7, [*changed, ("b.py/g", "def g(): pass")], ["b.py/g"]),
        _inst("other/lib", 4, base[:5], ["a.py/f1"]),  # same rows, other repository
        _inst("other/lib", 5, [], []),  # an empty corpus
    ]


def _write(root: str, layout: str) -> MiningStore:
    store = MiningStore(root, layout)
    for inst in _instances():
        store.write_instance(inst)
    return store


def test_materialised_directories_are_byte_identical_to_the_plain_layout(tmp_path) -> None:
    plain = _write(str(tmp_path / "plain"), "directories")
    dedup = _write(str(tmp_path / "dedup"), LAYOUT_DEDUP)
    out = str(tmp_path / "out")
    stats = cas.materialise(dedup.root, out)
    assert stats["materialised"] == 5 and stats["repositories"] == 2
    res = cas.compare_roots(plain.root, out)
    assert res["all_identical"] and res["compared"] == 5
    # a second run changes nothing and skips every directory
    assert cas.materialise(dedup.root, out)["skipped"] == 5


def test_rows_are_stored_once_per_repository(tmp_path) -> None:
    dedup = _write(str(tmp_path / "dedup"), LAYOUT_DEDUP)
    widgets = cas.RepoRows(dedup.root, "acme/widgets")
    # 40 rows of the first corpus, 1 changed row, 1 added row; "other/lib" keeps its own copy
    assert len(widgets.digests()) == 42
    assert len(cas.RepoRows(dedup.root, "other/lib").digests()) == 5
    assert not os.path.exists(os.path.join(dedup.pr_path("acme__widgets-1"), "corpus.jsonl.gz"))


def test_store_bytes_are_repeatable(tmp_path) -> None:
    a = _write(str(tmp_path / "a"), LAYOUT_DEDUP)
    b = _write(str(tmp_path / "b"), LAYOUT_DEDUP)
    res = cas.compare_roots(a.root, b.root)
    assert res["all_identical"]
    for repo in ("acme/widgets", "other/lib"):
        for name in (cas.ROWS_FILE, cas.DIGESTS_FILE, cas.SEGMENTS_FILE):
            pa = os.path.join(a.root, cas.CAS_DIR, cas.repo_dir_name(repo), name)
            pb = os.path.join(b.root, cas.CAS_DIR, cas.repo_dir_name(repo), name)
            assert open(pa, "rb").read() == open(pb, "rb").read()


def test_convert_reproduces_the_plain_layout(tmp_path) -> None:
    plain = _write(str(tmp_path / "plain"), "directories")
    store = str(tmp_path / "store")
    assert cas.convert(plain.root, store)["converted"] == 5
    assert cas.convert(plain.root, store)["skipped"] == 5
    out = str(tmp_path / "out")
    cas.materialise(store, out, ["acme__widgets-2", "other__lib-4"])
    assert cas.instance_names(out) == ["acme__widgets-2", "other__lib-4"]
    for name in cas.instance_names(out):
        assert cas.directory_digest(os.path.join(out, "pr", name)) == cas.directory_digest(
            os.path.join(plain.root, "pr", name)
        )


def test_compare_roots_reports_a_changed_byte(tmp_path) -> None:
    a = _write(str(tmp_path / "a"), "directories")
    b = _write(str(tmp_path / "b"), "directories")
    with open(os.path.join(b.pr_path("acme__widgets-1"), "queries.jsonl"), "ab") as handle:
        handle.write(b" ")
    res = cas.compare_roots(a.root, b.root)
    assert not res["all_identical"] and res["different"] == ["acme__widgets-1"]


def test_an_unfinished_append_is_cut_back_and_the_rows_are_reused(tmp_path) -> None:
    root = str(tmp_path / "s")
    rows = cas.RepoRows(root, "acme/widgets")
    first = rows.add([b'{"_id":"a"}\n', b'{"_id":"b"}\n'])
    # a crash after the rows and digests were written, before the commit record
    with open(rows.rows_path, "ab") as handle:
        handle.write(b"partial")
    with open(rows.digests_path, "ab") as handle:
        handle.write(b"\0" * 20)
    reopened = cas.RepoRows(root, "acme/widgets")
    assert reopened.committed()[0] == 2
    again = reopened.add([b'{"_id":"b"}\n', b'{"_id":"c"}\n'])
    assert list(first) == [0, 1] and list(again) == [1, 2]
    assert reopened.load().line(2) == b'{"_id":"c"}\n'


def test_a_store_shorter_than_its_commit_record_is_an_error(tmp_path) -> None:
    root = str(tmp_path / "s")
    rows = cas.RepoRows(root, "acme/widgets")
    rows.add([b'{"_id":"a"}\n'])
    with open(rows.digests_path, "r+b") as handle:
        handle.truncate(5)
    with pytest.raises(cas.StoreError):
        cas.RepoRows(root, "acme/widgets").committed()


def test_a_slot_beyond_the_stored_rows_is_an_error(tmp_path) -> None:
    dedup = _write(str(tmp_path / "dedup"), LAYOUT_DEDUP)
    manifest = cas.encode_manifest(cas.array.array("I", [0, 999]))
    with open(os.path.join(dedup.pr_path("other__lib-4"), cas.MANIFEST), "wb") as handle:
        handle.write(manifest)
    with pytest.raises(cas.StoreError):
        cas.materialise(dedup.root, str(tmp_path / "out"), ["other__lib-4"])


def test_layouts_are_not_mixed_in_one_root(tmp_path) -> None:
    root = str(tmp_path / "r")
    MiningStore(root, LAYOUT_DEDUP).ensure_run("h", "2026-11-05")
    with pytest.raises(ValueError):
        MiningStore(root).ensure_run("h", "2026-11-05")
    with pytest.raises(ValueError):
        MiningStore(root, "tape")


def test_the_default_layout_keeps_the_run_record_unchanged(tmp_path) -> None:
    store = MiningStore(str(tmp_path / "r"))
    assert store.ensure_run("h", "2026-11-05") == {"created": "2026-11-05", "config_hash": "h"}


# ---- durable copy


def _record_all(store: MiningStore) -> None:
    from ril.data_mining.miner import STATUS_MINED, Outcome

    for inst in _instances():
        store.record(Outcome(f"{inst.repo}#{inst.pr}", STATUS_MINED, "", None, {}))


def test_copy_run_is_complete_ordered_and_idempotent(tmp_path) -> None:
    local = _write(str(tmp_path / "local"), LAYOUT_DEDUP)
    local.ensure_run("h", "2026-11-05")
    _record_all(local)
    dst = str(tmp_path / "durable")
    first = durable.copy_run(local.root, dst)
    assert first.directories == 5 and first.appended_bytes > 0
    assert cas.compare_roots(local.root, dst)["all_identical"]
    for rel in ("state.jsonl", "run.json"):
        assert (
            open(os.path.join(dst, rel), "rb").read()
            == open(os.path.join(local.root, rel), "rb").read()
        )
    second = durable.copy_run(local.root, dst)
    assert second.appended_bytes == 0 and second.directories == 0 and second.files == 0


def test_copy_run_appends_only_the_new_tail(tmp_path) -> None:
    local = MiningStore(str(tmp_path / "local"), LAYOUT_DEDUP)
    insts = _instances()
    local.write_instance(insts[0])
    dst = str(tmp_path / "durable")
    durable.copy_run(local.root, dst)
    local.write_instance(insts[1])
    stats = durable.copy_run(local.root, dst)
    assert stats.directories == 1 and 0 < stats.appended_bytes < 2000
    out = str(tmp_path / "out")
    cas.materialise(dst, out)
    assert cas.instance_names(out) == ["acme__widgets-1", "acme__widgets-2"]


def test_copy_run_refuses_to_overwrite_a_diverged_destination(tmp_path) -> None:
    a = _write(str(tmp_path / "a"), LAYOUT_DEDUP)
    b = MiningStore(str(tmp_path / "b"), LAYOUT_DEDUP)
    b.write_instance(_inst("acme/widgets", 9, [("z.py/z", "other text")], ["z.py/z"]))
    dst = str(tmp_path / "durable")
    durable.copy_run(b.root, dst)
    with pytest.raises(durable.DivergedError):
        durable.copy_run(a.root, dst)  # same repository, different first rows
    longer = str(tmp_path / "longer")
    durable.copy_run(a.root, longer)
    with pytest.raises(durable.DivergedError):
        durable.copy_run(b.root, longer)  # the destination has more than the source


def test_restore_rebuilds_a_lost_node_and_leaves_a_live_one(tmp_path) -> None:
    local = _write(str(tmp_path / "local"), LAYOUT_DEDUP)
    local.ensure_run("h", "2026-11-05")
    _record_all(local)
    dst = str(tmp_path / "durable")
    durable.copy_run(local.root, dst)
    fresh = str(tmp_path / "fresh")
    stats = durable.restore(dst, fresh)
    assert stats is not None and stats.directories == 5
    assert MiningStore(fresh, LAYOUT_DEDUP).load_state() == local.load_state()
    assert durable.restore(dst, fresh) is None  # a root with run.json is the live one
    assert durable.restore(str(tmp_path / "none"), str(tmp_path / "x")) is None


def test_syncer_pushes_on_count_and_on_time(tmp_path) -> None:
    local = MiningStore(str(tmp_path / "local"), LAYOUT_DEDUP)
    clock = [0.0]
    sync = durable.Syncer(
        local.root, str(tmp_path / "d"), every=3, seconds=100.0, clock=lambda: clock[0]
    )
    local.write_instance(_instances()[0])
    sync.tick()
    sync.tick()
    assert sync.passes == []
    sync.tick()
    assert len(sync.passes) == 1
    sync.tick()
    clock[0] = 150.0
    sync.tick()
    assert len(sync.passes) == 2
    with pytest.raises(ValueError):
        durable.Syncer(local.root, "x", every=0, seconds=1.0)


# ---- through the run


def _run(tmp_path, name: str, layout: str, durable_root: str | None = None, stop_after=None):
    from ril.data_mining.config import MiningConfig
    from ril.data_mining.runner import list_population, mine_selected, select_prs
    from tests.unit.test_mining_pipeline import REPO, build_run

    client, snaps, _, _ = build_run(tmp_path / name)
    store = MiningStore(str(tmp_path / name / "run"), layout)
    cfg = MiningConfig(max_prs=3)
    store.ensure_run(cfg.config_hash(), "2026-11-05")
    listings, _ = list_population(client, [REPO], store, is_held_out=lambda r: False)
    syncer = (
        durable.Syncer(store.root, durable_root, every=1, seconds=1e9) if durable_root else None
    )
    mine_selected(
        select_prs(listings, cfg),
        client=client,
        snapshots=snaps,
        store=store,
        config=cfg,
        stop_after=stop_after,
        after_record=syncer.tick if syncer else None,
    )
    return store, syncer


def test_a_dedup_run_packs_to_the_same_archive_as_the_plain_run(tmp_path) -> None:
    from ril.data_mining.pack import pack_zip

    plain, _ = _run(tmp_path, "plain", "directories")
    dedup, _ = _run(tmp_path, "dedup", LAYOUT_DEDUP)
    out = str(tmp_path / "view")
    cas.materialise(dedup.root, out)
    assert cas.compare_roots(plain.root, out)["all_identical"]
    pack_zip(plain.root, str(tmp_path / "a.zip"))
    pack_zip(out, str(tmp_path / "b.zip"))
    assert open(tmp_path / "a.zip", "rb").read() == open(tmp_path / "b.zip", "rb").read()


def test_a_run_resumed_from_the_durable_copy_loses_nothing(tmp_path) -> None:
    dur = str(tmp_path / "durable")
    first, syncer = _run(tmp_path, "node1", LAYOUT_DEDUP, durable_root=dur, stop_after=2)
    assert syncer is not None and len(syncer.passes) == 2
    done = first.load_state()
    # node 1 is lost: a new root is restored from the durable area and the run continues
    restored = str(tmp_path / "node2" / "run")
    assert durable.restore(dur, restored) is not None
    assert MiningStore(restored, LAYOUT_DEDUP).load_state() == done
    reference, _ = _run(tmp_path, "ref", LAYOUT_DEDUP)
    out_a, out_b = str(tmp_path / "va"), str(tmp_path / "vb")
    cas.materialise(restored, out_a)
    assert cas.instance_names(out_a) == sorted(
        f"acme__widgets-{r['key'].split('#')[1]}" for r in done.values() if r["status"] == "mined"
    )
    cas.materialise(reference.root, out_b, cas.instance_names(out_a))
    assert cas.compare_roots(out_a, out_b)["all_identical"]


def test_reading_a_manifest_directory_without_materialising_says_so(tmp_path) -> None:
    from ril.data_mining.files import corpus_size, read_corpus

    dedup = _write(str(tmp_path / "dedup"), LAYOUT_DEDUP)
    with pytest.raises(FileNotFoundError, match="materialise"):
        read_corpus(dedup.pr_path("acme__widgets-1"))
    with pytest.raises(FileNotFoundError, match="materialise"):
        corpus_size(dedup.pr_path("acme__widgets-1"))


def test_pilot_job_in_the_dedup_layout_with_a_durable_copy_and_a_restore(tmp_path) -> None:
    import json

    from ril.data_mining import jobs
    from ril.data_mining.config import MiningConfig
    from ril.data_mining.population import select_population
    from tests.unit.test_mining_jobs_summary import POOL_NAMES, REPO, synthetic_client

    cfg = MiningConfig(n_repos=1, max_prs=3)
    pop = select_population(POOL_NAMES, is_held_out=lambda r: False, seed=0, pool_size=10)
    dur = str(tmp_path / "durable")

    def run(root: str, **extra):
        client, snaps, _ = synthetic_client()
        return jobs.run_pilot(
            config=cfg,
            out_root=root,
            population=pop,
            is_held_out=lambda r: False,
            client=client,
            snapshots=snaps,
            created="2026-11-05",
            code_commit="x",
            repos=[REPO],
            store_layout=LAYOUT_DEDUP,
            durable_root=dur,
            sync_every=1,
            **extra,
        )

    first = run(str(tmp_path / "node1"), stop_after=2)
    assert first["attempted"] == 2 and first["sync_passes"] >= 3  # two outcomes and the last push
    # the node is lost; the next job starts on an empty disk and finishes the run
    second = run(str(tmp_path / "node2"))
    assert second["restored"] is not None and second["restored"]["directories"] == 2
    assert second["attempted"] == 1 and second["skipped"] == 2
    final = json.load(open(os.path.join(dur, "run.json")))
    assert final["layout"] == LAYOUT_DEDUP
    assert len(cas.instance_names(dur)) == 3
    assert len(MiningStore(dur, LAYOUT_DEDUP).load_state()) == 3
    assert os.path.exists(os.path.join(dur, "summary.json"))
    # the same run in the plain layout gives the same materialised directories
    plain_client, plain_snaps, _ = synthetic_client()
    jobs.run_pilot(
        config=cfg,
        out_root=str(tmp_path / "plain"),
        population=pop,
        is_held_out=lambda r: False,
        client=plain_client,
        snapshots=plain_snaps,
        created="2026-11-05",
        code_commit="x",
        repos=[REPO],
    )
    out = str(tmp_path / "view")
    cas.materialise(dur, out)
    assert cas.compare_roots(str(tmp_path / "plain"), out)["all_identical"]


def test_manifest_roundtrip_row_block_and_store_bytes(tmp_path) -> None:
    slots = cas.array.array("I", [3, 0, 3, 7, 4_000_000_000])
    assert list(cas.decode_manifest(cas.encode_manifest(slots))) == list(slots)
    dedup = _write(str(tmp_path / "dedup"), LAYOUT_DEDUP)
    names = cas.instance_names(dedup.root)
    assert list(cas.read_manifest(dedup.pr_path(names[0]))) == list(range(40))
    block = cas.RepoRows(dedup.root, "acme/widgets").load()
    assert len(block) == 42 and block.line(0).endswith(b"\n")
    sizes = cas.store_bytes(dedup.root)
    assert sizes["total"] == sum(v for k, v in sizes.items() if k != "total") > 0
    assert sizes["rows"] > 0 and sizes["digests"] == (42 + 5) * 20
    stats = durable.copy_run(dedup.root, str(tmp_path / "d"))
    assert stats.to_dict()["directories"] == 5


def test_a_listing_job_that_fails_keeps_the_listings_it_finished(tmp_path, monkeypatch) -> None:
    import pytest

    from ril.data_mining import jobs, runner
    from ril.data_mining.config import MiningConfig
    from ril.data_mining.github_api import TransportError
    from ril.data_mining.population import select_population
    from tests.unit.test_mining_jobs_summary import POOL_NAMES, REPO, synthetic_client

    real = runner.list_repository

    def flaky(client, repo, store):
        if repo == "boom/later":
            raise TransportError("cut body")
        return real(client, repo, store)

    monkeypatch.setattr(runner, "list_repository", flaky)
    pop = select_population(POOL_NAMES, is_held_out=lambda r: False, seed=0, pool_size=10)
    dur = str(tmp_path / "durable")
    client, snaps, _ = synthetic_client()
    with pytest.raises(TransportError):
        jobs.run_pilot(
            config=MiningConfig(n_repos=2, max_prs=3),
            out_root=str(tmp_path / "node"),
            population=pop,
            is_held_out=lambda r: False,
            client=client,
            snapshots=snaps,
            created="2026-11-06",
            code_commit="x",
            repos=[REPO, "boom/later"],
            list_only=True,
            store_layout=LAYOUT_DEDUP,
            durable_root=dur,
        )
    assert MiningStore(dur, LAYOUT_DEDUP).has_listing(REPO)
