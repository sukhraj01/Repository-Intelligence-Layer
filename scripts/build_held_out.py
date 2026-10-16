"""Build the held-out repository list, its report, the pool-filter reports and the audit tables.

Thin driver: reads the per-folder instance-id summaries produced on the cluster by
``scripts/ada/core_bench_instance_ids.py`` (merged into one JSON), the corpus and query statistics,
the Verified / Loc-Bench id exports and the pool repository counts, then calls ``ril.training``.
Implements ``specs/held_out_repos.md``. Deterministic: same inputs give the same bytes.

Usage: python -I scripts/build_held_out.py [--raw data/raw/core_bench] [--seed 0]
"""

# ruff: noqa: E501, T201

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ril.training.held_out import (  # noqa: E402
    build_held_out,
    canonical_json,
    canonical_repo,
    filter_repo_counts,
    sha256_hex,
)
from ril.training.held_out_build import (  # noqa: E402
    folder_evidence,
    merge_level,
    paired_n,
    pairwise_overlaps,
    repos_by_source,
)

VERIFIED_KEY = "princeton-nlp_SWE-bench_Verified/test-00000-of-00001.parquet"
LOC_KEYS = {
    "Loc-Bench_V1": "czlll_Loc-Bench_V1/test-00000-of-00001.parquet",
    "Loc-Bench_V0.2": "czlll_Loc-Bench_V0.2/test-00000-of-00001.parquet",
}
CARD = {
    "LEVEL-2": dict(
        repos=632,
        queries=5061,
        corpus=9377120,
        qrels=52712,
        rels_per_q=10.42,
        avg_q_len=1558.5,
        avg_c_len=1004.9,
    ),
    "LEVEL-3": dict(
        repos=97,
        queries=2580,
        corpus=2609581,
        qrels=106479,
        rels_per_q=41.27,
        avg_q_len=1074.4,
        avg_c_len=1154.8,
    ),
}
CARD_DS = {  # level, dataset -> (repos, queries, corpus, qrels) from the dataset card
    ("LEVEL-2", "SWE-bench_Verified"): (12, 432, 398397, 1173),
    ("LEVEL-2", "SWE-bench_Pro"): (10, 632, 586719, 8088),
    ("LEVEL-2", "SWE-bench-Live"): (209, 1623, 1229695, 14028),
    ("LEVEL-2", "SWE-Bench-plus-plus"): (319, 442, 5365829, 6197),
    ("LEVEL-2", "SWE-bench-plus"): (6, 207, 57320, 1483),
    ("LEVEL-2", "Multi-SWE-bench"): (35, 1449, 858042, 20384),
    ("LEVEL-2", "SWE-bench_Multilingual"): (41, 276, 881118, 1359),
    ("LEVEL-3", "SWE-bench_Verified"): (12, 302, 372258, 8928),
    ("LEVEL-3", "SWE-bench_Pro"): (10, 585, 509200, 14987),
    ("LEVEL-3", "Multi-SWE-bench"): (35, 1445, 857861, 77293),
    ("LEVEL-3", "SWE-bench_Multilingual"): (40, 248, 870262, 5271),
}


RUNS = [
    dict(
        run_id="s4-core-bench-instance-ids",
        where="ada gnode002, u22/low, 4 CPU, job 24595",
        seconds=1175,
        result="1,458 folders (L2, L3, Rewrite L2/L3): query ids and qrels rows; 6,065,040,177 B of queries.jsonl and "
        "35,094,386 B of qrels.jsonl streamed, only ids and counts kept",
    ),
    dict(
        run_id="s4-core-bench-corpus-stats",
        where="ada gnode002, u22/low, 4 CPU, job 24596",
        seconds=1017,
        result="729 L2/L3 corpus.jsonl streamed (13,801,911,834 B): 11,986,701 rows, mean chars, longest chunk",
    ),
    dict(
        run_id="s4-core-bench-query-stats",
        where="ada gnode002, u22/low, 4 CPU, jobs 24605 and 24606",
        seconds=314,
        result="729 L2/L3 queries.jsonl: mean query chars, candidate-list sizes; 3 folders retried after DNS errors",
    ),
    dict(
        run_id="s4-pool-repo-counts",
        where="ada gnode002, u22/low, job 24604 (24597 and 24602 failed: venv built on the "
        "login node's python 3.9 does not run on the nodes' python 3.10)",
        seconds=77,
        result="CodeSearchNet python 457,461 rows / 13,590 repositories; gangiswag candidate 24,285 instance dirs / 2,448 repositories",
    ),
    dict(
        run_id="s4-label-quality",
        where="ada login node, seed 0",
        seconds=None,
        result="30 sampled L2 Verified instances over six repositories, 53 positives classified (numbers only)",
    ),
    dict(
        run_id="s4-github-name-check",
        where="ada login node, unauthenticated GitHub API",
        seconds=None,
        result="same-name-other-owner pool repositories looked up; stopped by the 60 requests per hour limit",
    ),
    dict(
        run_id="s4-held-out-list",
        where="local, scripts/build_held_out.py",
        seconds=None,
        result="605 repositories, sha256 recorded in data/held_out/held_out_repos.sha256",
    ),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def md_table(header: list[str], rows: list[list[object]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def fmt(n: float | int | None, nd: int = 0) -> str:
    if n is None:
        return "n/a"
    return f"{n:,.{nd}f}" if nd else f"{int(n):,}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "data/raw/core_bench"))
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    raw = Path(args.raw)
    ids_all = json.loads((raw / "ids_all.json").read_text())
    corpus_all = json.loads((raw / "corpus_stats_all.json").read_text())
    qstats_path = raw / "query_stats_all.json"
    qstats = json.loads(qstats_path.read_text()) if qstats_path.exists() else {}
    meta = json.loads((raw / "meta_ids.json").read_text())
    label_q = json.loads((raw / "label_quality_sample.json").read_text())
    pools = {
        "codesearchnet_python": json.loads((raw / "pool_csn_repos.json").read_text()),
        "gangiswag_train_data_python": json.loads((raw / "pool_gangiswag_repos.json").read_text()),
    }
    fork_checks: dict[str, dict] = {}
    for p in sorted((raw / "work").glob("fork_check_*.json")):
        fork_checks.update(json.loads(p.read_text())["checked"])

    # --- evidence per folder -------------------------------------------------------------
    evidence = [
        folder_evidence(*key.split("/", 2), doc["queries_ids"])
        for key, doc in sorted(ids_all.items())
    ]
    by_source = repos_by_source(evidence)
    l2, l3 = merge_level(by_source, "LEVEL-2"), merge_level(by_source, "LEVEL-3")
    verified_pairs = meta[VERIFIED_KEY]["pairs"]
    verified_repos = {canonical_repo(r) for r, _ in verified_pairs}
    verified_ids = [i for _, i in verified_pairs]
    unresolved = [
        {
            "level": e.level,
            "dataset": e.dataset,
            "folder": e.folder,
            "unreadable_ids": len(e.unresolved_ids),
        }
        for e in evidence
        if e.unresolved_ids or not e.repos
    ]

    sources: dict[str, set[str]] = {"Verified": verified_repos}
    for key, repos in by_source.items():
        level, ds = key.split(":", 1)
        if level in ("LEVEL-2", "LEVEL-3"):
            sources[f"{'L2' if level.endswith('2') else 'L3'}:{ds}"] = repos
    rewrite_extra = 0
    for key, repos in by_source.items():
        level, ds = key.split(":", 1)
        if level.startswith("Rewrite"):
            base = by_source.get(f"{level[len('Rewrite-') :]}:{ds}", set())
            extra = repos - base
            rewrite_extra += len(extra)
            if extra:  # only recorded when a rewrite folder names a repository the original lacks
                sources[f"RW-{'L2' if level.endswith('2') else 'L3'}:{ds}"] = extra
    held = build_held_out(sources)
    held["unresolved_folders"] = unresolved
    held["source_labels"] = (
        "L2:<dataset> / L3:<dataset> = CORE-Bench folders; Verified = SWE-bench Verified metadata; "
        "RW-* only if a Rewrite folder names a repository its original lacks"
    )
    held["fork_rule"] = "not applied: exact canonical names only (open question)"
    held["loc_bench"] = "not included (open question)"
    body = canonical_json(held)
    out = ROOT / "data/held_out"
    (out / "held_out_repos.json").write_bytes(body)
    digest = sha256_hex(body)
    write(out / "held_out_repos.sha256", f"{digest}  held_out_repos.json\n")
    held_set = set(held["repos"])  # type: ignore[arg-type]

    # --- tables: folders, source counts, overlaps ------------------------------------------
    folder_rows = []
    for e in evidence:
        doc = ids_all[f"{e.level}/{e.dataset}/{e.folder}"]
        folder_rows.append(
            [
                e.level,
                e.dataset,
                e.folder,
                e.n_queries,
                doc.get("qrels_rows", 0),
                ";".join(e.repos),
                int(e.folder_has_owner_separator),
                int(e.folder_matches_repo),
                len(e.repos),
            ]
        )
    write_csv(
        ROOT / "data/processed/core_bench/folder_repos.csv",
        [
            "level",
            "dataset",
            "folder",
            "queries",
            "qrels_rows",
            "repositories",
            "folder_has_double_underscore",
            "folder_equals_repository",
            "n_repositories",
        ],
        folder_rows,
    )
    src_rows = []
    for key in sorted(by_source):
        level, ds = key.split(":", 1)
        fl = [e for e in evidence if e.level == level and e.dataset == ds]
        src_rows.append(
            [
                level,
                ds,
                len(fl),
                len(by_source[key]),
                sum(1 for e in fl if not e.folder_has_owner_separator),
                sum(1 for e in fl if len(e.repos) > 1),
                sum(1 for e in fl if not e.folder_matches_repo),
            ]
        )
    write_csv(
        ROOT / "results/tables/held_out_source_counts.csv",
        [
            "level",
            "dataset",
            "folders",
            "distinct_repositories",
            "folders_without_double_underscore",
            "folders_holding_more_than_one_repository",
            "folders_not_equal_to_repository",
        ],
        src_rows,
    )
    named = {"L2": l2, "L3": l3, "Verified": verified_repos}
    pw = pairwise_overlaps(named)
    l2ds = {k.split(":", 1)[1]: v for k, v in by_source.items() if k.startswith("LEVEL-2:")}
    l3ds = {k.split(":", 1)[1]: v for k, v in by_source.items() if k.startswith("LEVEL-3:")}
    pw_ds = pairwise_overlaps(
        {f"L2:{k}": v for k, v in l2ds.items()}
        | {f"L3:{k}": v for k, v in l3ds.items()}
        | {"Verified": verified_repos}
    )
    write_csv(
        ROOT / "results/tables/held_out_pairwise_overlaps.csv",
        ["pair", "shared_repositories"],
        [[k, v] for k, v in pw_ds.items()],
    )

    # --- Loc-Bench, reported separately ------------------------------------------------
    loc = {}
    for name, key in LOC_KEYS.items():
        r = {canonical_repo(a) for a, _ in meta[key]["pairs"]}
        loc[name] = dict(
            repos=r,
            rows=meta[key]["rows"],
            in_held=len(r & held_set),
            not_in_held=sorted(r - held_set),
        )
    write(
        ROOT / "data/processed/core_bench/reference_loc_bench_repos.json",
        json.dumps(
            {
                "note": "reference only, not part of the held-out list (open question)",
                **{
                    k: {
                        "rows": v["rows"],
                        "repositories": len(v["repos"]),
                        "in_held_out_list": v["in_held"],
                        "repositories_not_in_held_out_list": v["not_in_held"],
                    }
                    for k, v in loc.items()
                },
            },
            indent=1,
            sort_keys=True,
        )
        + "\n",
    )

    # --- paired n ---------------------------------------------------------------------------
    ids_by = defaultdict(set)
    for key, doc in ids_all.items():
        lvl, ds, _ = key.split("/", 2)
        ids_by[(lvl, ds)].update(doc["queries_ids"])
    pn = paired_n(
        ids_by[("LEVEL-2", "SWE-bench_Verified")],
        ids_by[("LEVEL-3", "SWE-bench_Verified")],
        verified_ids,
    )
    all_l2 = set().union(*[v for (lv, _), v in ids_by.items() if lv == "LEVEL-2"])
    all_l3 = set().union(*[v for (lv, _), v in ids_by.items() if lv == "LEVEL-3"])
    per_repo_paired = defaultdict(lambda: [0, 0, 0, 0])
    from ril.training.held_out import repo_from_instance_id

    a, b = ids_by[("LEVEL-2", "SWE-bench_Verified")], ids_by[("LEVEL-3", "SWE-bench_Verified")]
    for i in verified_ids:
        r = repo_from_instance_id(i) or "?"
        per_repo_paired[r][0] += 1
        per_repo_paired[r][1] += i in a
        per_repo_paired[r][2] += i in b
        per_repo_paired[r][3] += i in a and i in b
    pn_doc = {
        "verified_rows": len(verified_ids),
        "l2_verified": pn.l2_verified,
        "l3_verified": pn.l3_verified,
        "l2_and_l3_verified": pn.l2_and_l3_verified,
        "l2_ids_not_in_verified_metadata": pn.l2_not_in_verified_metadata,
        "l3_ids_not_in_verified_metadata": pn.l3_not_in_verified_metadata,
        "l3_verified_not_in_l2_verified": len(b - a),
        "all_datasets_distinct_ids": {
            "L2": len(all_l2),
            "L3": len(all_l3),
            "L2_and_L3": len(all_l2 & all_l3),
        },
        "all_datasets_rows": {
            "L2": sum(
                len(d["queries_ids"]) for k, d in ids_all.items() if k.startswith("LEVEL-2/")
            ),
            "L3": sum(
                len(d["queries_ids"]) for k, d in ids_all.items() if k.startswith("LEVEL-3/")
            ),
        },
        "per_repository_verified": {
            r: dict(zip(["verified", "l2", "l3", "l2_and_l3"], v, strict=True))
            for r, v in sorted(per_repo_paired.items())
        },
        "l3_ids_in_l2_by_dataset": {
            ds: [
                len(ids_by[("LEVEL-3", ds)]),
                len(ids_by[("LEVEL-3", ds)] & ids_by[("LEVEL-2", ds)]),
            ]
            for (lv, ds) in sorted(ids_by)
            if lv == "LEVEL-3"
        },
    }
    write(
        ROOT / "results/tables/paired_n.json", json.dumps(pn_doc, indent=1, sort_keys=True) + "\n"
    )

    # --- card vs measured ----------------------------------------------------------------
    def level_totals(level: str) -> dict[str, float]:
        docs = {k: d for k, d in ids_all.items() if k.startswith(level + "/")}
        cstats = {
            k: v
            for k, v in corpus_all.items()
            if k.startswith("data/" + level + "/") or k.startswith(level + "/")
        }
        qs = {k: v for k, v in qstats.items() if f"/{level}/" in k}
        return dict(
            folders=len(docs),
            queries=sum(d["queries_rows"] for d in docs.values()),
            qrels=sum(d.get("qrels_rows", 0) for d in docs.values()),
            corpus=sum(v["rows"] for v in cstats.values()),
            chars=sum(v["chars"] for v in cstats.values()),
            q_chars=sum(v["text_chars"] for v in qs.values()),
            q_n=sum(v["queries"] for v in qs.values()),
        )

    cvm: list[list[object]] = []
    totals = {lv: level_totals(lv) for lv in ("LEVEL-2", "LEVEL-3")}
    for lv, tag in (("LEVEL-2", "L2"), ("LEVEL-3", "L3")):
        c, t = CARD[lv], totals[lv]
        distinct = len(l2) if lv == "LEVEL-2" else len(l3)
        cvm += [
            [
                tag,
                "ALL",
                "repos (folders)",
                fmt(c["repos"]),
                "same as card",
                fmt(t["folders"]),
                "folders counted in listing and queries files",
            ],
            [
                tag,
                "ALL",
                "distinct canonical repositories",
                "not stated",
                "not stated",
                fmt(distinct),
                "from instance ids; case-folded owner/name",
            ],
            [
                tag,
                "ALL",
                "queries",
                fmt(c["queries"]),
                "same as card",
                fmt(t["queries"]),
                "rows of queries.jsonl",
            ],
            [
                tag,
                "ALL",
                "corpus chunks",
                fmt(c["corpus"]),
                "same as card",
                fmt(t["corpus"]),
                "rows of corpus.jsonl",
            ],
            [
                tag,
                "ALL",
                "qrels",
                fmt(c["qrels"]),
                "same as card",
                fmt(t["qrels"]),
                "rows of qrels.jsonl",
            ],
            [
                tag,
                "ALL",
                "rels per query",
                fmt(c["rels_per_q"], 2),
                "same as card",
                fmt(t["qrels"] / t["queries"], 2),
                "qrels rows / query rows",
            ],
            [
                tag,
                "ALL",
                "mean chunk length (chars)",
                fmt(c["avg_c_len"], 1),
                "about 1,005 (L2) / 1,155 (L3), unit unstated",
                fmt(t["chars"] / t["corpus"], 1) if t["corpus"] else "n/a",
                "mean len(text) over all chunks; unit of the card figure is not stated",
            ],
            [
                tag,
                "ALL",
                "mean query length (chars)",
                fmt(c["avg_q_len"], 1),
                "not stated",
                fmt(t["q_chars"] / t["q_n"], 1) if t["q_n"] else "n/a",
                "mean len(text) over queries; unit of the card figure is not stated",
            ],
        ]
    for (lv, ds), (rp, qu, co, qr) in CARD_DS.items():
        docs = {k: d for k, d in ids_all.items() if k.startswith(f"{lv}/{ds}/")}
        cs = [v for k, v in corpus_all.items() if f"{lv}/{ds}/" in k]
        cvm.append(
            [
                lv.replace("LEVEL-", "L"),
                ds,
                "repos / queries / chunks / qrels (card)",
                f"{rp} / {qu} / {fmt(co)} / {fmt(qr)}",
                "same as card",
                f"{len(docs)} folders ({len(by_source[lv + ':' + ds])} distinct repos) / "
                f"{fmt(sum(d['queries_rows'] for d in docs.values()))} / {fmt(sum(v['rows'] for v in cs))} / "
                f"{fmt(sum(d.get('qrels_rows', 0) for d in docs.values()))}",
                "measured from the files",
            ]
        )
    rw_no_qrels = [
        k for k, d in ids_all.items() if k.startswith("Rewrite-") and "qrels_rows" not in d
    ]
    rw_fewer = [
        (k, ids_all[k[len("Rewrite-") :]]["qrels_rows"] - d["qrels_rows"])
        for k, d in ids_all.items()
        if k.startswith("Rewrite-")
        and "qrels_rows" in d
        and d["qrels_rows"] != ids_all[k[len("Rewrite-") :]]["qrels_rows"]
    ]
    rw_ids_differ = sum(
        1
        for k, d in ids_all.items()
        if k.startswith("Rewrite-")
        and set(d["queries_ids"]) != set(ids_all[k[len("Rewrite-") :]]["queries_ids"])
    )
    rw_note = (
        f"{len(rw_no_qrels)} Rewrite folders (SWE-bench_Multilingual) hold no qrels file; {len(rw_fewer)} other folders "
        f"hold fewer qrels rows than their original ({sum(x[1] for x in rw_fewer)} rows in all); query id sets are identical "
        f"in all folders ({rw_ids_differ} differ)"
    )
    cvm += [
        [
            "Verified",
            "SWE-bench Verified",
            "rows / distinct repos",
            "500 / 12",
            "same as card",
            f"{len(verified_ids)} / {len(verified_repos)}",
            "parquet metadata",
        ],
        [
            "L2/L3",
            "Rewrite",
            "qrels rows vs original (L2 / L3)",
            "share qrels with originals",
            "same as card",
            f"{fmt(sum(d.get('qrels_rows', 0) for k, d in ids_all.items() if k.startswith('Rewrite-LEVEL-2/')))} vs "
            f"{fmt(totals['LEVEL-2']['qrels'])} (L2); "
            f"{fmt(sum(d.get('qrels_rows', 0) for k, d in ids_all.items() if k.startswith('Rewrite-LEVEL-3/')))} vs "
            f"{fmt(totals['LEVEL-3']['qrels'])} (L3)",
            rw_note,
        ],
        [
            "SFT",
            "paper",
            "repos / queries",
            "n/a",
            "628 / 53,301",
            "not measurable",
            "SFT data is not in the package; paper_reported",
        ],
        [
            "L2",
            "BM25",
            "nDCG@10 / Recall@100",
            "13.0 / 38.8",
            "same as card",
            "not run in this project",
            "to be measured when the evaluation loader exists",
        ],
    ]
    write_csv(
        ROOT / "results/tables/core_bench_card_vs_measured.csv",
        ["level", "scope", "statistic", "card", "paper", "measured", "note"],
        cvm,
    )

    # --- pool filtering ---------------------------------------------------------------------
    loc_union = set().union(*[v["repos"] for v in loc.values()])
    pool_rows = []
    all_proxy: set[str] = set()
    pool_docs = {}
    for pname, p in pools.items():
        counts = p["repos"]
        kept, rep = filter_repo_counts(counts, held_set)
        kept_loc, rep_loc = filter_repo_counts(counts, held_set | loc_union)
        names_held = {r.split("/", 1)[1] for r in held_set}
        proxy = sorted(r for r in kept if r.split("/", 1)[1] in names_held)
        all_proxy |= set(proxy)
        checked = {r: fork_checks[r] for r in proxy if r in fork_checks}
        renamed_into_held = sorted(
            r
            for r, v in checked.items()
            if v.get("status") == 200
            and canonical_repo(v["full_name"]) != r
            and canonical_repo(v["full_name"]) in held_set
        )
        forks_of_held = sorted(
            r
            for r, v in checked.items()
            if v.get("fork")
            and (
                canonical_repo(v.get("source") or "-/-") in held_set
                or canonical_repo(v.get("parent") or "-/-") in held_set
            )
        )
        extra_inst = sum(kept[r] for r in renamed_into_held)
        write(
            ROOT / "data/processed/pools" / f"{pname}_repos.json",
            json.dumps(
                {
                    "pool": pname,
                    "held_out_sha256": digest,
                    "rule": "exact canonical names only",
                    "instances": rep.instances_after,
                    "repositories": dict(kept),
                },
                indent=0,
                sort_keys=True,
            )
            + "\n",
        )
        pool_docs[pname] = dict(
            before=(rep.instances_before, rep.repos_before),
            after=(rep.instances_after, rep.repos_after),
            dropped_repos=len(rep.dropped_repos),
            top=rep.top_dropped(15),
            with_loc=(rep_loc.instances_after, rep_loc.repos_after),
            proxy=len(proxy),
            proxy_inst=sum(kept[r] for r in proxy),
            checked=len(checked),
            renamed=renamed_into_held,
            extra_inst=extra_inst,
            forks=forks_of_held,
            unchecked=len(proxy) - len(checked),
            not_found=sorted(r for r, v in checked.items() if v.get("status") == 404),
            rename_after=(
                rep.instances_after - extra_inst,
                rep.repos_after - len(renamed_into_held),
            ),
            n_dropped_instances=rep.instances_before - rep.instances_after,
        )
        pool_rows.append(
            [
                pname,
                rep.instances_before,
                rep.repos_before,
                rep.instances_after,
                rep.repos_after,
                f"{rep.instances_surviving_pct:.2f}",
                f"{rep.repos_surviving_pct:.2f}",
                len(rep.dropped_repos),
                rep_loc.instances_after,
                rep_loc.repos_after,
                len(proxy),
                len(checked),
                len(renamed_into_held),
                len(forks_of_held),
            ]
        )
    write_csv(
        ROOT / "results/tables/pool_filter_summary.csv",
        [
            "pool",
            "instances_before",
            "repos_before",
            "instances_after_exact",
            "repos_after_exact",
            "pct_instances_surviving",
            "pct_repos_surviving",
            "repos_dropped",
            "instances_after_if_loc_bench_added",
            "repos_after_if_loc_bench_added",
            "same_name_other_owner_candidates",
            "candidates_checked_on_github",
            "checked_renamed_into_held_out",
            "checked_forks_of_held_out",
        ],
        pool_rows,
    )

    write(
        ROOT / "results/tables/github_name_check.json",
        json.dumps(
            {
                "what": "same-name-other-owner pool repositories looked up on the GitHub API (name, fork, root)",
                "checked": {r: fork_checks[r] for r in sorted(all_proxy) if r in fork_checks},
                "not_checked_rate_limit": sorted(r for r in all_proxy if r not in fork_checks),
            },
            indent=1,
            sort_keys=True,
        )
        + "\n",
    )
    descr = {
        "codesearchnet_python": (
            "CodeSearchNet python (train, validation, test parquet files)",
            "rows are functions (comment-code pairs); `repository_name` identifies the repository",
        ),
        "gangiswag_train_data_python": (
            "`gangiswag/train_data` train.zip, python folders (CANDIDATE, provisional; Open question Q7, not chosen as the pool)",
            "rows are instance directories `train/python/<owner>__<name>-<PR>/`; repository names are read from directory names in the zip central directory, nothing else was fetched",
        ),
    }
    for pname, d in pool_docs.items():
        lines = [
            f"# Pool filter report: {pname}\n",
            f"Pool: {descr[pname][0]}. Unit counted: {descr[pname][1]}.\n",
            "Held-out list: `held_out_repos.json` (exact canonical names, no fork rule, no Loc-Bench). "
            "This is a measurement of survival, not a choice of training pool.\n",
            md_table(
                ["", "instances", "repositories"],
                [
                    ["before", fmt(d["before"][0]), fmt(d["before"][1])],
                    ["after (exact-name filter)", fmt(d["after"][0]), fmt(d["after"][1])],
                    [
                        "surviving",
                        f"{100 * d['after'][0] / d['before'][0]:.2f} %",
                        f"{100 * d['after'][1] / d['before'][1]:.2f} %",
                    ],
                ],
            ),
            f"\nHeld-out repositories present in the pool: {d['dropped_repos']}.\n\nTop dropped repositories (by instances):\n",
            md_table(["repository", "instances"], [[r, fmt(n)] for r, n in d["top"]]),
            "\n## Sensitivity to the two open rules (both reported, neither chosen)\n",
            md_table(
                ["rule", "instances after", "repositories after"],
                [
                    ["exact names only (above)", fmt(d["after"][0]), fmt(d["after"][1])],
                    [
                        "exact names + Loc-Bench repositories (open question)",
                        fmt(d["with_loc"][0]),
                        fmt(d["with_loc"][1]),
                    ],
                    [
                        f"exact names + current-name resolution of {d['checked']} same-name candidates checked on GitHub",
                        fmt(d["rename_after"][0]),
                        fmt(d["rename_after"][1]),
                    ],
                ],
            ),
            f"\nFork / near-duplicate evidence: {d['proxy']} surviving pool repositories ({fmt(d['proxy_inst'])} instances) share a repository name with a held-out repository under a different owner. "
            f"{d['checked']} of them were looked up through the unauthenticated GitHub API (60 requests per hour); {d['unchecked']} were not checked. "
            f"Among the checked: {len(d['renamed'])} resolve to a held-out repository under its current name (a rename or ownership transfer, so the exact-name filter lets them through): {', '.join(d['renamed']) or 'none'}; "
            f"{len(d['forks'])} are forks whose fork-network root or parent is held out; {len(d['not_found'])} no longer exist. "
            "Renamed repositories whose name part differs, and forks with other names, cannot be found this way: this is a lower bound.\n",
        ]
        write(out / f"pool_filter_report_{pname}.md", "\n".join(lines))
    write(
        out / "pool_filter_report_cornstack_python.md",
        "# Pool filter report: CoRNStack python (`cornstack-python-v1`)\n\n"
        "Cannot be repo-filtered: no repository identifier. The row schema has `query`, `document`, "
        "`document_rank`, `document_score`, `metadata`, `negatives`, `negative_scores`; none holds a "
        "repository name, path or URL (schema read from the first 200 rows of shard 0).\n",
    )
    write(
        out / "pool_filter_report_sweloc.md",
        "# Pool filter report: SweLoc\n\nNo dataset named SweLoc is published, so there is nothing to filter. "
        "The one undocumented candidate (`gangiswag/train_data`) is reported in "
        "`pool_filter_report_gangiswag_train_data_python.md` as a provisional candidate only.\n",
    )

    # --- report.md -------------------------------------------------------------------------
    nm2 = sum(1 for e in evidence if e.level == "LEVEL-2" and not e.folder_matches_repo)
    nm3 = sum(1 for e in evidence if e.level == "LEVEL-3" and not e.folder_matches_repo)
    nodouble2 = sum(
        1 for e in evidence if e.level == "LEVEL-2" and not e.folder_has_owner_separator
    )
    nodouble3 = sum(
        1 for e in evidence if e.level == "LEVEL-3" and not e.folder_has_owner_separator
    )
    multi2 = [e for e in evidence if e.level == "LEVEL-2" and len(e.repos) > 1]
    multi3 = [e for e in evidence if e.level == "LEVEL-3" and len(e.repos) > 1]
    folders_by_case = defaultdict(list)
    for e in evidence:
        if e.level in ("LEVEL-2", "LEVEL-3"):
            folders_by_case[(e.level, e.dataset, e.folder.casefold())].append(e.folder)
    case_groups = sorted(
        (k[0], k[1], tuple(sorted(v))) for k, v in folders_by_case.items() if len(v) > 1
    )
    rpt = [
        "# Held-out repository list\n",
        f"Contract: `specs/held_out_repos.md`. List: `held_out_repos.json` (sha256 `{digest}`, file `held_out_repos.sha256`).\n",
        "## Form and method\n",
        "- Canonical form: `owner/name`, case-folded (`Owner/Repo`, `owner__repo` and `owner/repo` are one entry).\n"
        "- CORE-Bench folder names are truncated and are not repository names, so the repository of a folder is read from the instance ids in its `queries.jsonl` (`owner__name-<PR>`; the Pro split `instance_owner__name-<hash>`). "
        "Every one of the 1,458 folders resolved; unresolved folders: "
        + (str(len(unresolved)) if unresolved else "none")
        + ". Nothing was guessed from a folder name.\n"
        "- Union held out: all L2 datasets, all L3 datasets, the Rewrite variants (same repositories, checked below) and SWE-bench Verified metadata.\n"
        "- Not applied: any fork or near-duplicate rule, and Loc-Bench (both are open questions; counts under each are below).\n",
        f"## Result\n\n**{held['n_repos']} distinct repositories held out.**\n",
        md_table(
            [
                "source",
                "folders",
                "distinct repositories",
                "folders without `__`",
                "folders holding more than one repository",
            ],
            [
                [f"{r[0]} {r[1]}", r[2], r[3], r[4], r[5]]
                for r in src_rows
                if not r[0].startswith("Rewrite")
            ]
            + [["Verified (metadata)", "-", len(verified_repos), "-", "-"]],
        ),
        "\nRewrite variants: the repository set of every Rewrite dataset equals that of its original (checked per dataset; "
        f"repositories added by Rewrite folders: {rewrite_extra}).\n",
        md_table(
            [
                "level",
                "folders",
                "distinct repositories",
                "folders whose name is not the repository",
                "folders without `__`",
                "folders holding several repositories",
            ],
            [
                ["L2", totals["LEVEL-2"]["folders"], len(l2), nm2, nodouble2, len(multi2)],
                ["L3", totals["LEVEL-3"]["folders"], len(l3), nm3, nodouble3, len(multi3)],
            ],
        ),
        f"\nThe card's 632 and 97 are folder counts. Distinct repositories are {len(l2)} (L2) and {len(l3)} (L3). "
        f"{len(multi2)} L2 folders hold more than one repository (a truncated name such as `open` or `python` is shared by several owners). "
        f"Folders of one dataset whose names differ only by letter case (they would collide on a case-insensitive file system): {len(case_groups)} groups ("
        + "; ".join(f"{g[0]} {g[1]}: {' / '.join(g[2])}" for g in case_groups)
        + "). Each pair holds the same repository.\n",
        "## Pairwise overlaps (distinct repositories)\n",
        md_table(["pair", "shared"], [[k, v] for k, v in pw.items()]),
        f"\nL2 union L3 union Verified = {len(l2 | l3 | verified_repos)}. L3 is wholly inside L2 ({len(l3 & l2)} of {len(l3)}), and the 12 Verified repositories are inside both. "
        "The per-dataset overlap matrix is `results/tables/held_out_pairwise_overlaps.csv`.\n",
        "## Loc-Bench (reported separately, not in the list)\n",
        md_table(
            ["version", "rows", "repositories", "already in the list", "not in the list"],
            [
                [k, v["rows"], len(v["repos"]), v["in_held"], len(v["not_in_held"])]
                for k, v in loc.items()
            ],
        ),
        "\nWhether Loc-Bench repositories are held out of training is ADR-005 and is not decided here.\n",
        "## Paired analysis n (instance ids)\n",
        md_table(
            ["quantity", "n"],
            [
                [
                    "L2 SWE-bench_Verified queries that are SWE-bench Verified instances",
                    pn.l2_verified,
                ],
                [
                    "L3 SWE-bench_Verified queries that are SWE-bench Verified instances",
                    pn.l3_verified,
                ],
                ["in both L2 and L3 Verified", pn.l2_and_l3_verified],
                [
                    "L2/L3 Verified query ids absent from the Verified metadata",
                    pn.l2_not_in_verified_metadata + pn.l3_not_in_verified_metadata,
                ],
            ],
        )
        + "\nDetails per repository: `results/tables/paired_n.json`.\n",
        "## Fork and near-duplicate counts\n",
        "See the pool reports below. The held-out list itself is exact names only. "
        "Measured on candidate pools: repositories that were renamed or transferred since the pool was built still carry their old name and pass an exact-name filter.\n",
        "## Pool reports\n",
        md_table(
            ["pool", "instances before", "after", "repos before", "after"],
            [[r[0], fmt(r[1]), fmt(r[3]), fmt(r[2]), fmt(r[4])] for r in pool_rows],
        )
        + "\nFiles: `pool_filter_report_<pool>.md` (CodeSearchNet python, the gangiswag candidate), `pool_filter_report_cornstack_python.md` (cannot be filtered), `pool_filter_report_sweloc.md` (does not exist).\n",
    ]
    write(out / "report.md", "\n".join(rpt))

    # --- run log -----------------------------------------------------------------------------
    inputs = {
        p.name: sha(p)[:12]
        for p in sorted(raw.glob("*.json"))
        if p.name
        in (
            "ids_all.json",
            "corpus_stats_all.json",
            "query_stats_all.json",
            "meta_ids.json",
            "manifest.json",
            "pool_csn_repos.json",
            "pool_gangiswag_repos.json",
        )
    }
    scripts = {
        s: sha(ROOT / s)[:12]
        for s in (
            "scripts/build_held_out.py",
            "ril/training/held_out.py",
            "ril/training/held_out_build.py",
            "scripts/ada/core_bench_instance_ids.py",
            "scripts/ada/core_bench_corpus_stats.py",
            "scripts/ada/core_bench_query_stats.py",
            "scripts/ada/pool_repo_counts.py",
            "scripts/ada/label_quality_sample.py",
            "scripts/ada/github_repo_check.py",
            "scripts/ada/export_meta_ids.py",
        )
        if (ROOT / s).exists()
    }
    cfg_hash = sha256_hex(
        canonical_json({"inputs": inputs, "scripts": scripts, "seed": args.seed})
    )[:12]
    cand = {}
    for lv in ("LEVEL-2", "LEVEL-3"):
        vals = [v for k, v in qstats.items() if f"/{lv}/" in k]
        n_q = sum(v["queries"] for v in vals)
        cand[lv] = dict(
            queries=n_q,
            mean_candidates_per_query=round(sum(v["cand_sum"] for v in vals) / n_q, 1)
            if n_q
            else None,
            min=min((v["cand_min"] for v in vals), default=None),
            max=max((v["cand_max"] for v in vals), default=None),
        )
    write(
        ROOT / "results/tables/label_quality_sample.json",
        json.dumps(label_q, indent=1, sort_keys=True) + "\n",
    )
    summary = dict(
        candidate_list_sizes=cand,
        held_out_repos=held["n_repos"],
        held_out_sha256=digest,
        config_hash=cfg_hash,
        l2_folders=totals["LEVEL-2"]["folders"],
        l3_folders=totals["LEVEL-3"]["folders"],
        l2_distinct=len(l2),
        l3_distinct=len(l3),
        verified=len(verified_repos),
        l2_l3_overlap=len(l2 & l3),
        paired=pn_doc["l2_verified"],
        totals=totals,
        pools={
            name: {
                **{k: v for k, v in d.items() if k not in ("top", "renamed", "forks", "not_found")},
                "renamed_into_held_out": len(d["renamed"]),
                "forks_of_held_out": len(d["forks"]),
                "no_longer_exist": len(d["not_found"]),
            }
            for name, d in pool_docs.items()
        },
        loc_bench={
            k: dict(rows=v["rows"], repos=len(v["repos"]), in_held=v["in_held"])
            for k, v in loc.items()
        },
        label_quality=dict(
            seed=label_q["seed"], n=label_q["n_sample"], classes=label_q["class_counts"]
        ),
        folders_multi_repo=dict(L2=len(multi2), L3=len(multi3)),
        folders_not_equal_repo=dict(L2=nm2, L3=nm3),
        folders_without_dunder=dict(L2=nodouble2, L3=nodouble3),
        case_groups=[list(g[2]) for g in case_groups],
        rewrite_extra_repos=rewrite_extra,
        rewrite_note=rw_note,
        unresolved=len(unresolved),
    )
    log = dict(
        session="2026-10-17-04 ground-truth-b",
        date="2026-10-17",
        seed=args.seed,
        seed_note="no randomness except the label-quality sample (seed 0, run on the cluster)",
        hardware=dict(
            local="Apple macOS 24.6 (Darwin), 8 GB class box, no GPU; aggregation only",
            ada="ada-gw1 login (Xeon Gold 5215, python 3.9) and gnode002 via u22/low; CPU only",
        ),
        runs=RUNS,
        input_sha256_prefix=inputs,
        script_sha256_prefix=scripts,
        summary=summary,
    )
    write(
        ROOT / "results/logs/s4_ground_truth_b_2026-10-17.json",
        json.dumps(log, indent=1, sort_keys=True, default=list) + "\n",
    )
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "held_out_repos",
                    "held_out_sha256",
                    "config_hash",
                    "l2_distinct",
                    "l3_distinct",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
