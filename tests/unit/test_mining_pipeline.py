"""Per-PR pipeline, output contract, crash-and-resume, byte-identical rerun (E-MINE-PILOT, M0 gate).

All API responses are hand-built and synthetic; the snapshots are in memory.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable

import pytest

from ril.data_mining.config import CORPUS_KINDS_ALL, MiningConfig
from ril.data_mining.github_api import ApiClient, ClientConfig
from ril.data_mining.links import (
    PullRequest,
    issue_edited_after,
    multiplicity,
    parse_pr_page,
    regex_issue_refs,
)
from ril.data_mining.miner import (
    STATUS_MINED,
    STATUS_NO_POSITIVE,
    STATUS_NO_PYTHON,
    STATUS_QUARANTINED,
    classify_parse_failure,
    mine_pr,
)
from ril.data_mining.pack import list_dirs, local_fetch, pack_zip, write_listing
from ril.data_mining.runner import list_population, mine_selected, select_prs
from ril.data_mining.snapshot import MemorySnapshots
from ril.data_mining.store import MiningStore, stage_counts
from ril.training import pool_reader as reader
from tests.unit._mining_fixtures import (
    FakeClock,
    FakeTransport,
    compare_doc,
    file_entry,
    graphql_page,
    issue_node,
    json_response,
    make_patch,
    pr_node,
)

REPO = "acme/widgets"
BASE_SHA, HEAD_SHA = "b" * 40, "h" * 40
MB = "m" * 40  # merge base

OLD = """\
LIMIT = 3


def helper(x):
    return x + 1


class Widget:
    def area(self):
        return 2

    def perimeter(self):
        return 4
"""
NEW = OLD.replace("return 2", "return 3")
OTHER = "def other():\n    return 1\n"


def graphql_route(nodes: list[dict]) -> Callable:
    return lambda url, body: json_response(graphql_page(REPO, nodes))


def make_client(tr: FakeTransport) -> ApiClient:
    return ApiClient(tr, clock=FakeClock(), config=ClientConfig(retries=1, min_interval=0.0))


def link(number: int = 7, issues: list[dict] | None = None, **kw) -> PullRequest:
    nodes = [pr_node(number, issues if issues is not None else [issue_node(70)], **kw)]
    prs, _, _ = parse_pr_page(graphql_page(REPO, nodes)["data"], REPO)
    return prs[0]


def compare_route(files: list[dict]) -> Callable:
    return lambda url, body: json_response(compare_doc(MB, HEAD_SHA, files))


def setup(files: list[dict], tree: dict[str, str] | None = None):
    tr = FakeTransport()
    tr.add("GET", f"/repos/{REPO}/compare/", compare_route(files))
    snaps = MemorySnapshots(
        {(REPO, MB): tree if tree is not None else {"m.py": OLD, "o.py": OTHER}}
    )
    return make_client(tr), snaps, tr


def mine(pr: PullRequest, files: list[dict], tree=None, cfg: MiningConfig | None = None):
    client, snaps, _ = setup(files, tree)
    return mine_pr(pr, client=client, snapshots=snaps, config=cfg or MiningConfig())


MODIFY = [file_entry("m.py", "modified", make_patch(OLD, NEW))]


def test_mined_instance_has_positives_corpus_and_flags() -> None:
    out = mine(link(), MODIFY)
    assert out.status == STATUS_MINED and out.instance is not None
    inst = out.instance
    assert inst.dir_name == "acme__widgets-7" and inst.base_commit == MB
    assert inst.qrels == ["m.py/Widget/area"]
    ids = [pid for pid, _ in inst.corpus]
    assert "m.py/helper" in ids and "m.py/Widget/area" in ids and "o.py/other" in ids
    assert all(text.startswith(pid + "\n") for pid, text in inst.corpus)
    assert inst.query.startswith("Widget area is wrong\n\n")
    (pos,) = inst.meta["positives"]
    assert pos["unit_kind"] == "method" and pos["is_test"] is False and pos["in_corpus"] is True
    assert pos["removed_lines"] == 1 and pos["unit_lines"] == 2 and pos["unit_loc"] == 2
    assert out.counters["positives"] == 1 and out.counters["added_function_defs"] == 0


def test_class_and_module_positives_go_to_the_side_table_by_default() -> None:
    new = OLD.replace("LIMIT = 3", "LIMIT = 4")
    out = mine(link(), [file_entry("m.py", "modified", make_patch(OLD, new))])
    assert out.status == STATUS_NO_POSITIVE
    assert out.counters["positives_side_only"] == 1 and out.counters["positives"] == 0
    both = mine(
        link(),
        [file_entry("m.py", "modified", make_patch(OLD, new))],
        cfg=MiningConfig(corpus_kinds=CORPUS_KINDS_ALL),
    )
    assert both.status == STATUS_MINED and both.instance is not None
    assert both.instance.qrels == ["m.py/<module>"]


def test_no_python_change_is_a_yield_stage_not_an_instance() -> None:
    out = mine(link(), [file_entry("README.md", "modified", "@@ -1 +1 @@\n-a\n+b")])
    assert out.status == STATUS_NO_PYTHON and out.instance is None


def test_added_function_count_and_file_added() -> None:
    new_file = "def one():\n    return 1\n"
    files = [*MODIFY, file_entry("n.py", "added", make_patch("", new_file))]
    out = mine(link(), files)
    assert out.status == STATUS_MINED and out.counters["added_function_defs"] == 1


@pytest.mark.parametrize(
    ("files", "tree", "reason"),
    [
        ([file_entry("m.py", "modified", None, changes=5000)], None, "patch_missing"),
        (
            [file_entry(f"f{i}.py", "modified", "@@ -1 +1 @@\n-a\n+b") for i in range(300)],
            None,
            "diff_truncated",
        ),
        (MODIFY, {}, "snapshot_unavailable"),
        (MODIFY, {"m.py": "def broken(:\n"}, "changed_file_unparseable:syntax-other"),
        (MODIFY, {"o.py": OTHER}, "old_file_missing_at_base"),
        (
            [file_entry("m.py", "modified", make_patch(OLD, NEW.replace("3", "9")))],
            {"m.py": "print 'hello'\n"},
            "changed_file_unparseable:python2-print",
        ),
    ],
)
def test_quarantine_reasons(files, tree, reason) -> None:
    client, snaps, _ = setup(files, tree)
    if tree == {}:
        snaps = MemorySnapshots({})  # the base commit cannot be fetched
    out = mine_pr(link(), client=client, snapshots=snaps, config=MiningConfig())
    assert out.status == STATUS_QUARANTINED and out.reason == reason and out.instance is None


def test_compare_not_found_is_quarantined_not_raised() -> None:
    tr = FakeTransport()
    out = mine_pr(
        link(), client=make_client(tr), snapshots=MemorySnapshots({}), config=MiningConfig()
    )
    assert out.status == STATUS_QUARANTINED and out.reason == "compare_not_found"


def test_unrelated_unparseable_file_only_shrinks_the_corpus() -> None:
    out = mine(link(), MODIFY, {"m.py": OLD, "legacy.py": "print 'x'\n"})
    assert out.status == STATUS_MINED and out.counters["corpus_unparsed_files"] == 1
    assert out.instance is not None
    assert out.instance.meta["parse_failure_causes"] == {"python2-print": 1}


def test_changed_generated_file_is_counted_not_mapped() -> None:
    gen = "# @generated -- do not edit\ndef f():\n    return 1\n"
    files = [*MODIFY, file_entry("gen_pb2.py", "modified", make_patch(gen, gen.replace("1", "2")))]
    out = mine(link(), files, {"m.py": OLD, "gen_pb2.py": gen})
    assert out.status == STATUS_MINED and out.counters["changed_files_skipped"] == 1


def test_primary_issue_and_multiplicity_and_edit_flag() -> None:
    issues = [issue_node(90, edited="2024-03-01T00:00:00Z"), issue_node(12, edited=None)]
    pr = link(issues=issues, body="Fixes #12 and also closes #55")
    out = mine(pr, MODIFY)
    assert out.instance is not None
    meta = out.instance.meta
    assert [p["issue"] for p in meta["pairs"]] == [12, 90]
    assert [p["primary"] for p in meta["pairs"]] == [True, False]
    assert [p["edited_after_pr_created"] for p in meta["pairs"]] == [False, True]
    assert meta["regex_refs"] == [12, 55] and meta["regex_only_refs"] == [55]
    assert multiplicity([pr]) == {
        "pairs": 2,
        "prs_with_issue": 1,
        "prs_with_several_issues": 1,
        "issues": 2,
        "issues_with_several_prs": 0,
    }


def test_links_helpers() -> None:
    assert regex_issue_refs("fixes #3, Resolves other/x#4, close #5", "a/b") == (3, 5)
    pr = link(issues=[issue_node(1, edited="2024-01-15T00:00:00Z")], created="2024-01-10T00:00:00Z")
    assert issue_edited_after(pr.issues[0], pr.created_at)
    assert not issue_edited_after(issue_node_obj(None), pr.created_at)


def issue_node_obj(edited):
    prs, _, _ = parse_pr_page(
        graphql_page(REPO, [pr_node(1, [issue_node(1, edited=edited)])])["data"], REPO
    )
    return prs[0].issues[0]


def test_classify_parse_failure() -> None:
    assert (
        classify_parse_failure("SyntaxError: Missing parentheses in call to 'print'")
        == "python2-print"
    )
    assert (
        classify_parse_failure("TabError: inconsistent use of tabs and spaces in indentation")
        == "mixed-tabs-spaces"
    )
    assert classify_parse_failure("SyntaxError: invalid syntax") == "syntax-other"
    assert classify_parse_failure("UnicodeDecodeError: bad") == "UnicodeDecodeError"


# --------------------------------------------------------------------------- the run


def build_run(tmp_path, n_prs: int = 4):
    """A repository with ``n_prs`` linked PRs (two of them without a Python change) and a client."""
    nodes = []
    for n in range(1, n_prs + 1):
        nodes.append(pr_node(n, [issue_node(100 + n)], base=BASE_SHA, head=HEAD_SHA))
    nodes.append(pr_node(99, []))  # no linked issue
    tr = FakeTransport()
    tr.add("POST", "/graphql", graphql_route(nodes))

    def route(url: str, body):
        return json_response(compare_doc(MB, HEAD_SHA, MODIFY))

    tr.add("GET", f"/repos/{REPO}/compare/", route)
    snaps = MemorySnapshots({(REPO, MB): {"m.py": OLD, "o.py": OTHER}})
    return make_client(tr), snaps, tr, MiningStore(str(tmp_path / "run"))


LOGS = {"sessions.jsonl", "api_events.jsonl"}
"""Per-session logs: appended by every session by design, not outputs of the run."""


def tree_digest(root: str) -> str:
    h = hashlib.sha256()
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for f in sorted(files):
            if f in LOGS:
                continue
            p = os.path.join(base, f)
            h.update(os.path.relpath(p, root).encode())
            with open(p, "rb") as handle:
                h.update(handle.read())
    return h.hexdigest()


def test_run_lists_selects_mines_and_records(tmp_path) -> None:
    client, snaps, tr, store = build_run(tmp_path)
    cfg = MiningConfig(max_prs=3)
    listings, stats = list_population(client, [REPO], store, is_held_out=lambda r: False)
    assert stats.listed == 1 and len(listings[REPO]) == 5
    selected = select_prs(listings, cfg)
    assert len(selected) == 3 and all(p.issues for p in selected)
    summary = mine_selected(selected, client=client, snapshots=snaps, store=store, config=cfg)
    assert summary.attempted == 3 and summary.outcomes == {STATUS_MINED: 3}
    assert len(list_dirs(store.root)) == 3
    counts = stage_counts(listings, store.load_state())
    assert counts["merged_prs"] == 5 and counts["prs_with_closing_issue"] == 4
    assert counts["status"] == {STATUS_MINED: 3}


def test_selection_is_seeded_and_stable(tmp_path) -> None:
    client, _, _, store = build_run(tmp_path)
    listings, _ = list_population(client, [REPO], store, is_held_out=lambda r: False)
    a = [p.number for p in select_prs(listings, MiningConfig(max_prs=2, seed=0))]
    b = [p.number for p in select_prs(listings, MiningConfig(max_prs=2, seed=0))]
    c = [p.number for p in select_prs(listings, MiningConfig(max_prs=4, seed=0))]
    assert a == b == c[:2]


def test_rerun_makes_no_api_call_and_leaves_identical_bytes(tmp_path) -> None:
    client, snaps, tr, store = build_run(tmp_path)
    cfg = MiningConfig(max_prs=4)
    listings, _ = list_population(client, [REPO], store, is_held_out=lambda r: False)
    selected = select_prs(listings, cfg)
    mine_selected(selected, client=client, snapshots=snaps, store=store, config=cfg)
    before, calls = tree_digest(store.root), len(tr.calls)
    listings2, stats2 = list_population(client, [REPO], store, is_held_out=lambda r: False)
    summary = mine_selected(
        select_prs(listings2, cfg), client=client, snapshots=snaps, store=store, config=cfg
    )
    assert stats2.reused == 1 and summary.attempted == 0 and summary.skipped == 4
    assert len(tr.calls) == calls and tree_digest(store.root) == before


def test_crash_between_directory_and_state_row_is_adopted(tmp_path) -> None:
    client, snaps, tr, store = build_run(tmp_path)
    cfg = MiningConfig(max_prs=4)
    listings, _ = list_population(client, [REPO], store, is_held_out=lambda r: False)
    selected = select_prs(listings, cfg)
    seen: list[str] = []

    def crash(outcome) -> None:
        seen.append(outcome.key)
        if len(seen) == 2:
            raise RuntimeError("simulated crash after the directory, before the row")

    with pytest.raises(RuntimeError):
        mine_selected(
            selected, client=client, snapshots=snaps, store=store, config=cfg, on_outcome=crash
        )
    assert len(store.load_state()) == 1 and len(list_dirs(store.root)) == 2
    os.makedirs(store.pr_path("acme__widgets-5.tmp"))  # a half-written directory
    full = mine_selected(selected, client=client, snapshots=snaps, store=store, config=cfg)
    assert full.adopted == 1 and full.attempted == 2 and len(store.load_state()) == 4
    reference_client, reference_snaps, _, reference_store = build_run(tmp_path / "ref")
    ref_listings, _ = list_population(
        reference_client, [REPO], reference_store, is_held_out=lambda r: False
    )
    mine_selected(
        select_prs(ref_listings, cfg),
        client=reference_client,
        snapshots=reference_snaps,
        store=reference_store,
        config=cfg,
    )
    assert tree_digest(os.path.join(store.root, "pr")) == tree_digest(
        os.path.join(reference_store.root, "pr")
    )
    assert not any(d.endswith(".tmp") for d in os.listdir(os.path.join(store.root, "pr")))


def test_stop_after_then_resume_completes(tmp_path) -> None:
    client, snaps, _, store = build_run(tmp_path)
    cfg = MiningConfig(max_prs=4)
    listings, _ = list_population(client, [REPO], store, is_held_out=lambda r: False)
    selected = select_prs(listings, cfg)
    first = mine_selected(
        selected, client=client, snapshots=snaps, store=store, config=cfg, stop_after=2
    )
    assert first.attempted == 2 and first.stopped
    second = mine_selected(selected, client=client, snapshots=snaps, store=store, config=cfg)
    assert second.skipped == 2 and second.attempted == 2 and not second.stopped


def test_renamed_into_held_out_is_dropped_and_counted(tmp_path) -> None:
    tr = FakeTransport()
    tr.add(
        "POST",
        "/graphql",
        lambda u, b: json_response(
            graphql_page(REPO, [pr_node(1, [issue_node(1)])], current="big/django")
        ),
    )
    store = MiningStore(str(tmp_path / "run"))
    listings, stats = list_population(
        make_client(tr), [REPO], store, is_held_out=lambda r: r == "big/django"
    )
    assert (
        listings == {}
        and stats.renamed_into_held_out == [REPO]
        and stats.renamed == {REPO: "big/django"}
    )


def test_config_hash_changes_with_values_and_mismatched_root_is_refused(tmp_path) -> None:
    a, b = MiningConfig(), MiningConfig(max_prs=5)
    assert a.config_hash() == MiningConfig().config_hash() != b.config_hash()
    store = MiningStore(str(tmp_path / "r"))
    store.ensure_run(a.config_hash(), "2026-11-02")
    assert store.ensure_run(a.config_hash(), "2030-01-01")["created"] == "2026-11-02"
    with pytest.raises(ValueError):
        store.ensure_run(b.config_hash(), "2026-11-02")
    with pytest.raises(ValueError):
        MiningConfig.from_dict({"bogus": 1})


# --------------------------------------------------------------------------- the reader contract


def test_pool_reader_reads_the_output_unchanged(tmp_path) -> None:
    client, snaps, _, store = build_run(tmp_path)
    cfg = MiningConfig(max_prs=2)
    listings, _ = list_population(client, [REPO], store, is_held_out=lambda r: False)
    mine_selected(
        select_prs(listings, cfg), client=client, snapshots=snaps, store=store, config=cfg
    )
    zip_path = str(tmp_path / "mined.zip")
    assert pack_zip(store.root, zip_path) == 2
    assert pack_zip(store.root, str(tmp_path / "again.zip")) == 2
    with open(zip_path, "rb") as a, open(tmp_path / "again.zip", "rb") as b:
        assert a.read() == b.read()  # same run, same bytes
    listing = str(tmp_path / "listing.json")
    write_listing(zip_path, listing)
    url, members = reader.load_listing(listing)
    names = reader.select_instances(members, is_held_out=lambda r: False)
    stats = reader.ReaderStats()
    examples = list(reader.read_pool(url, members, names, fetch=local_fetch, stats=stats))
    assert stats.yielded == 2 and stats.fetch_errors == 0
    ex = examples[0]
    assert ex.repo == REPO and ex.positive_ids == ("m.py/Widget/area",)
    assert "m.py/helper" in ex.candidate_ids and "m.py/Widget/area" not in ex.candidate_ids
    assert ex.query.startswith("Widget area is wrong")
    assert ex.positive_texts[0] == "    def area(self):\n        return 2"
    row = json.loads(open(os.path.join(store.pr_path(ex.instance_id), "queries.jsonl")).readline())
    assert row["metadata"] == {"repo": REPO, "base_commit": MB}


def test_published_first_puts_pool_pull_requests_ahead_of_the_seeded_order(tmp_path) -> None:
    client, _, _, store = build_run(tmp_path)
    listings, _ = list_population(client, [REPO], store, is_held_out=lambda r: False)
    linked = sorted(p.number for p in listings[REPO] if p.issues)
    last_in_seed = [p.number for p in select_prs(listings, MiningConfig(max_prs=99))][-1]
    pool = {REPO: frozenset({last_in_seed})}
    off = [p.number for p in select_prs(listings, MiningConfig(max_prs=2), pool)]
    on_cfg = MiningConfig(max_prs=2, published_first=True)
    on = [p.number for p in select_prs(listings, on_cfg, pool)]
    assert last_in_seed not in off and on[0] == last_in_seed
    assert sorted(
        select_prs(listings, MiningConfig(max_prs=99), pool), key=lambda p: p.number
    ) == sorted(
        select_prs(listings, on_cfg.__class__(max_prs=99, published_first=True), pool),
        key=lambda p: p.number,
    )
    assert len(linked) >= 3


def test_lookahead_prefetches_in_order_and_leaves_the_outputs_unchanged(tmp_path) -> None:
    digests = []
    for name, look in (("seq", 1), ("ahead", 3)):
        client, snaps, _, store = build_run(tmp_path / name)
        cfg = MiningConfig(max_prs=4)
        listings, _ = list_population(client, [REPO], store, is_held_out=lambda r: False)
        selected = select_prs(listings, cfg)
        res = mine_selected(
            selected,
            client=client,
            snapshots=snaps,
            store=store,
            config=cfg,
            lookahead=look,
            stop_after=None,
        )
        assert res.attempted == 4 and snaps.closed
        assert len(snaps.prefetched) == 4  # every pull request here changes a Python file
        digests.append(tree_digest(store.root))
    assert digests[0] == digests[1]


def test_lookahead_respects_stop_after_and_resumes_in_order(tmp_path) -> None:
    client, snaps, _, store = build_run(tmp_path)
    cfg = MiningConfig(max_prs=4)
    listings, _ = list_population(client, [REPO], store, is_held_out=lambda r: False)
    selected = select_prs(listings, cfg)
    kw = {"client": client, "snapshots": snaps, "store": store, "config": cfg, "lookahead": 3}
    first = mine_selected(selected, stop_after=2, **kw)
    assert first.attempted == 2 and first.stopped and len(snaps.prefetched) == 2
    second = mine_selected(selected, **kw)
    assert second.skipped == 2 and second.attempted == 2 and not second.stopped
