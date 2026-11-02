"""Corner cases of the mined set: compare pagination, id collisions, file bytes, provenance."""

from __future__ import annotations

import json

from ril.data_mining.config import CORPUS_KINDS_ALL
from ril.data_mining.github_api import ApiClient, ClientConfig
from ril.data_mining.links import parse_pr_page
from ril.data_mining.miner import (
    MinedInstance,
    build_corpus,
    dir_name,
    fetch_comparison,
    primary_issue,
)
from ril.data_mining.pack import listing_of, pack_zip
from ril.data_mining.population import rename_report
from ril.data_mining.rank_compare import cluster_bootstrap
from ril.data_mining.store import MiningStore, instance_files, write_provenance
from tests.unit._mining_fixtures import (
    FakeClock,
    FakeTransport,
    compare_doc,
    file_entry,
    graphql_page,
    issue_node,
    json_response,
    pr_node,
    units_of,
)

PATCH = "@@ -1 +1 @@\n-a\n+b"


def test_compare_is_read_page_by_page_until_a_short_page() -> None:
    pages = {
        "1": [file_entry(f"a{i}.py", "modified", PATCH) for i in range(100)],
        "2": [file_entry(f"b{i}.py", "modified", PATCH) for i in range(100)],
        "3": [file_entry(f"c{i}.py", "modified", PATCH) for i in range(100)],
    }
    tr = FakeTransport()

    def route(url: str, body):
        page = url.split("page=")[1].split("&")[0]
        return json_response(compare_doc("m" * 40, "h" * 40, pages[page]))

    tr.add("GET", "/repos/acme/widgets/compare/", route)
    client = ApiClient(tr, clock=FakeClock(), config=ClientConfig(retries=1, min_interval=0.0))
    prs, _, _ = parse_pr_page(
        graphql_page("acme/widgets", [pr_node(3, [issue_node(1)])])["data"], "acme/widgets"
    )
    comp = fetch_comparison(client, prs[0])
    assert comp.files_listed == 300 and comp.truncated and len(tr.calls) == 3
    assert comp.merge_base == "m" * 40


def test_repeated_pool_ids_keep_the_first_unit_and_are_counted(tmp_path) -> None:
    src = "if True:\n    def f():\n        return 1\nelse:\n    def f():\n        return 2\n"
    units = units_of(tmp_path, {"m.py": src})
    rows, first, collisions = build_corpus(units, ("function", "method"))
    assert [pid for pid, _ in rows] == ["m.py/f"] and collisions == 1
    assert "return 1" in rows[0][1] and first["m.py/f"].start_line == 2
    every, _, _ = build_corpus(units, CORPUS_KINDS_ALL)
    assert "m.py/<module>" in [pid for pid, _ in every]


def test_primary_issue_prefers_the_same_repository_then_the_lowest_number() -> None:
    nodes = [
        issue_node(5, repo="other/place"),
        issue_node(9, repo="acme/widgets"),
        issue_node(7, repo="acme/widgets"),
    ]
    prs, _, _ = parse_pr_page(
        graphql_page("acme/widgets", [pr_node(1, nodes)])["data"], "acme/widgets"
    )
    assert primary_issue(prs[0]).number == 7
    assert dir_name("Acme/Widgets", 12) == "Acme__Widgets-12"


def test_instance_files_follow_the_pool_layout() -> None:
    inst = MinedInstance(
        repo="acme/widgets",
        pr=3,
        dir_name="acme__widgets-3",
        query="title\n\nbody",
        base_commit="m" * 40,
        corpus=[("a.py/f", "a.py/f\ndef f(): pass")],
        qrels=["a.py/f"],
        meta={"repo": "acme/widgets", "pr": 3},
    )
    files = instance_files(inst)
    assert set(files) == {"corpus.jsonl", "queries.jsonl", "qrels/test.tsv", "pr_meta.json"}
    row = json.loads(files["corpus.jsonl"])
    assert row == {"_id": "a.py/f", "title": "", "text": "a.py/f\ndef f(): pass", "metadata": {}}
    assert (
        files["qrels/test.tsv"].decode()
        == "query-id\tcorpus-id\tscore\nacme__widgets-3\ta.py/f\t1\n"
    )
    q = json.loads(files["queries.jsonl"])
    assert q["metadata"] == {"repo": "acme/widgets", "base_commit": "m" * 40}


def test_listing_has_local_header_offsets_for_every_member(tmp_path) -> None:
    store = MiningStore(str(tmp_path / "run"))
    inst = MinedInstance(
        "acme/widgets",
        3,
        "acme__widgets-3",
        "q",
        "m" * 40,
        [("a.py/f", "t")],
        ["a.py/f"],
        {"repo": "acme/widgets", "pr": 3, "counters": {"positives": 1}},
    )
    store.write_instance(inst)
    zip_path = str(tmp_path / "z.zip")
    pack_zip(store.root, zip_path)
    doc = listing_of(zip_path, "u")
    names = [m["name"] for m in doc["members"]]
    assert names == [
        f"train/python/acme__widgets-3/{n}"
        for n in ("corpus.jsonl", "queries.jsonl", "qrels/test.tsv")
    ]
    assert all(isinstance(m["offset"], int) for m in doc["members"])


def test_rename_report_and_cluster_bootstrap_are_deterministic() -> None:
    assert dict(rename_report({"a/b": "a/b", "c/d": "e/f", "G/H": "g/h"})) == {
        "same": 2,
        "renamed": 1,
    }
    flags = {f"d{i}": i % 3 == 0 for i in range(30)}
    repo_of = {d: f"r{int(d[1:]) % 5}" for d in flags}
    assert cluster_bootstrap(flags, repo_of, 0) == cluster_bootstrap(flags, repo_of, 0)
    assert cluster_bootstrap({}, {}, 0) == (0.0, 0.0)


def test_provenance_names_the_source_and_never_a_token(tmp_path) -> None:
    store = MiningStore(str(tmp_path / "run"))
    write_provenance(
        store,
        config={"seed": 0},
        config_hash="h",
        created="2026-11-02",
        authenticated=True,
        counts={"merged_prs": 1},
        budget={"calls": 2},
        population={"repos_selected": 1},
        code_commit="abc",
    )
    doc = json.load(open(tmp_path / "run" / "provenance.json"))
    assert (
        doc["token"]["authenticated"] is True and "value is never recorded" in doc["token"]["scope"]
    )
    assert any("compare" in e for e in doc["endpoints"]) and doc["created"] == "2026-11-02"
