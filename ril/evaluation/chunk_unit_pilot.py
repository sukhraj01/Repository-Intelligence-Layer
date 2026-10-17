"""Pilot M: chunk-to-unit mapping and graph reach, per benchmark instance (exploratory).

Implements the evaluation-side mapping of decision D7 and the reach study E-GRAPH-REACH
(``docs/EXPERIMENTS.md``). For each instance the caller supplies a checkout at the instance's
base commit and the positive chunk texts of the levels it appears in; this module

1. builds the units and the graph of the snapshot (``ril.parsing.build``), plus the exploratory
   ``co_change`` edges;
2. locates every positive chunk in the snapshot files and maps its span to units
   (``ril.evaluation.chunk_mapping``);
3. for the instances present at both levels, measures how far the units of the new L3
   positives lie from the units of the L2 positives, per edge subset, next to three random
   controls (``ril.evaluation.graph_reach``).

Chunk text never leaves this module: records hold ids, paths, line numbers, tiers and unit ids.
Licence note: CORE-Bench is non-commercial share-alike, so only counts and derived tables are
committed.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
from collections import Counter
from collections.abc import Iterable
from typing import Any

from ril.evaluation.chunk_mapping import (
    Location,
    SpanMapping,
    load_snapshot,
    locate_chunk,
    map_span,
    positive_kind,
    prefix_span,
    wave1_style_category,
)
from ril.evaluation.graph_reach import (
    CO_CHANGE_SUPPORTS,
    CONTROLS,
    DEFAULT_DRAWS,
    SUBSET_NAMES,
    SUBSETS,
    adjacency,
    control_pools,
    control_shares,
    distances,
    draw_pool,
    draw_sets,
    edge_pairs,
    min_distance,
    observed_shares,
    stable_rng,
    unit_kind,
)
from ril.parsing.build import BuildConfig, BuildResult, build_repository
from ril.parsing.call_graph import RESOLVER_NAME, RESOLVER_VERSION
from ril.parsing.code_unit import CODEUNIT_SCHEMA_VERSION, CodeUnit
from ril.parsing.exploratory_edges import co_change_edges
from ril.parsing.repo_graph import REPO_GRAPH_SCHEMA_VERSION, Edge
from ril.parsing.repository_parser import PARSER_VERSION

PILOT_VERSION = "pilot-m/v1"
PREFIX_CHARS = 200
"""The first label sample matched only this many leading characters of a long chunk."""
MAX_LISTED_LOCATIONS = 10

Record = dict[str, Any]


def config_hash(seed: int, draws: int) -> str:
    """SHA-256 of everything besides the data that decides the output of the pilot."""
    payload = {
        "pilot": PILOT_VERSION,
        "seed": seed,
        "draws": draws,
        "prefix_chars": PREFIX_CHARS,
        "subsets": list(SUBSET_NAMES),
        "controls": list(CONTROLS),
        "co_change_supports": list(CO_CHANGE_SUPPORTS),
        "parser": PARSER_VERSION,
        "resolver": f"{RESOLVER_NAME}/{RESOLVER_VERSION}",
        "repo_graph_schema": REPO_GRAPH_SCHEMA_VERSION,
        "codeunit_schema": CODEUNIT_SCHEMA_VERSION,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def hardware() -> dict[str, Any]:
    """Machine description recorded with every run."""
    info: dict[str, Any] = {
        "host": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpus_visible": os.cpu_count(),
    }
    try:
        with open("/proc/meminfo", encoding="ascii") as handle:
            info["mem_total_kb"] = int(handle.readline().split()[1])
    except (OSError, ValueError, IndexError):
        info["mem_total_kb"] = None
    return info


# --------------------------------------------------------------------------- git


def _git(args: list[str], cwd: str | None = None, timeout: int = 600) -> str:
    done = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, timeout=timeout
    )
    return done.stdout.strip()


def checkout_commit(bare_dir: str, work_dir: str, commit: str) -> str:
    """Check out ``commit`` in a working clone of ``bare_dir``; return ``ok`` or a reason.

    The clone is created on first use and reused (idempotent). A commit missing from the cache
    is fetched from the cache's origin once.
    """
    try:
        if not os.path.isdir(os.path.join(work_dir, ".git")):
            _git(["clone", "-q", "--no-checkout", bare_dir, work_dir])
        for attempt in (0, 1):
            try:
                _git(["checkout", "-q", "-f", commit], cwd=work_dir)
                break
            except subprocess.CalledProcessError:
                if attempt == 1:
                    return "base_commit_not_available"
                _git(["--git-dir", bare_dir, "fetch", "-q", "origin", commit])
                _git(["fetch", "-q", bare_dir, commit], cwd=work_dir)
        _git(["clean", "-fdxq"], cwd=work_dir)
        head = _git(["rev-parse", "HEAD"], cwd=work_dir)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        return f"git_error:{type(exc).__name__}"
    return "ok" if head == commit else "checkout_mismatch"


# --------------------------------------------------------------------------- input files


def read_qrels(path: str) -> dict[str, list[str]]:
    """``{query id: [positive corpus ids]}`` from a ``qrels.jsonl`` (rows with a positive score)."""
    out: dict[str, list[str]] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if float(row.get("score", 1)) > 0:
                out.setdefault(row["query_id"], []).append(row["corpus_id"])
    return {q: sorted(ids) for q, ids in sorted(out.items())}


def read_corpus_texts(path: str, wanted: set[str]) -> dict[str, str]:
    """Text of the wanted corpus ids, streamed from a ``corpus.jsonl`` (nothing else is kept)."""
    out: dict[str, str] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["_id"] in wanted:
                out[row["_id"]] = row["text"]
    return out


# --------------------------------------------------------------------------- one instance


def _units_by_file(units: Iterable[CodeUnit]) -> dict[str, list[CodeUnit]]:
    out: dict[str, list[CodeUnit]] = {}
    for u in units:
        out.setdefault(u.file, []).append(u)
    return out


def _views(files: dict[str, str], by_file: dict[str, list[CodeUnit]], loc: Location) -> Record:
    """Categories of one location under four readings (frozen units or the first sample's rule;
    whole chunk span or only its first 200 characters)."""
    if not loc.path.endswith(".py"):
        na = "non_python"
        return {"d6_full": na, "d6_prefix": na, "wave1_full": na, "wave1_prefix": na}
    text = files[loc.path]
    p_start, p_end = prefix_span(loc, text, PREFIX_CHARS)
    units = by_file.get(loc.path, [])
    return {
        "d6_full": map_span(units, loc.start_line, loc.end_line).category,
        "d6_prefix": map_span(units, p_start, p_end).category,
        "wave1_full": wave1_style_category(text, loc.start_line, loc.end_line),
        "wave1_prefix": wave1_style_category(text, p_start, p_end),
    }


def _map_positive(
    level: str,
    corpus_id: str,
    text: str,
    files: dict[str, str],
    by_file: dict[str, list[CodeUnit]],
    parsed_paths: set[str],
) -> tuple[Record, SpanMapping | None]:
    """Locate one positive chunk and map it; return its record and its span mapping."""
    res = locate_chunk(text, files)
    rec: Record = {
        "level": level,
        "corpus_id": corpus_id,
        "chars": len(text),
        "status": res.status,
        "tier": res.tier,
        "reason": res.reason,
        "n_locations": res.n_locations,
        "n_files": len({loc.path for loc in res.locations}),
        "locations": [
            [loc.path, loc.start_line, loc.end_line] for loc in res.locations[:MAX_LISTED_LOCATIONS]
        ],
    }
    if res.status != "found":
        rec.update(
            kind="unmatched",
            category="none",
            units=[],
            primary_id="",
            primary_type="",
            overlaps_residual=False,
            views={},
        )
        return rec, None
    first = res.locations[0]
    rec["path"] = first.path
    if first.path.endswith(".py") and first.path in parsed_paths:
        mapping = map_span(by_file.get(first.path, []), first.start_line, first.end_line)
    else:
        mapping = SpanMapping("none", (), (), (), False, "", "")
    rec["category"] = mapping.category
    rec["units"] = list(mapping.units)
    rec["primary_id"] = mapping.primary_id
    rec["primary_type"] = mapping.primary_type
    rec["overlaps_residual"] = mapping.overlaps_residual
    rec["kind"] = positive_kind(first.path, mapping, parsed_paths)
    rec["views"] = _views(files, by_file, first)
    return rec, mapping


def analyse_instance(
    root: str,
    repo_id: str,
    instance: str,
    levels: dict[str, dict[str, str]],
    *,
    seed: int,
    draws: int = DEFAULT_DRAWS,
) -> Record:
    """Map the positives of ``instance`` and, when L2 and L3 are both given, measure reach.

    ``levels`` maps a level name (``L2``, ``L3``) to ``{corpus id: chunk text}`` of the positives
    of this instance. ``root`` is a checkout at the instance's base commit.
    """
    has_git = os.path.isdir(os.path.join(root, ".git"))
    cfg = BuildConfig(repo_id=repo_id, with_history=has_git, seed=seed)
    t0 = time.perf_counter()
    result: BuildResult = build_repository(root, cfg)
    build_seconds = time.perf_counter() - t0
    files, skipped = load_snapshot(root)
    parsed = result.parsed
    by_file = _units_by_file(parsed.units)
    parsed_paths = set(parsed.files)

    positives: list[Record] = []
    mappings: dict[tuple[str, str], SpanMapping | None] = {}
    for level in sorted(levels):
        for cid in sorted(levels[level]):
            rec, mapping = _map_positive(
                level, cid, levels[level][cid], files, by_file, parsed_paths
            )
            rec["text_sha256_16"] = hashlib.sha256(levels[level][cid].encode("utf-8")).hexdigest()[
                :16
            ]
            positives.append(rec)
            mappings[(level, cid)] = mapping

    out: Record = {
        "instance": instance,
        "repo_id": repo_id,
        "config_hash": config_hash(seed, draws),
        "build_config_hash": cfg.config_hash(),
        "commit": result.commit,
        "build_seconds": round(build_seconds, 3),
        "snapshot": {
            "text_files": len(files),
            "python_files_parsed": len(parsed.files),
            "files_skipped_by_loader": dict(skipped),
            "units": len(parsed.units),
            "units_by_type": dict(Counter(u.unit_type for u in parsed.units)),
        },
        "positives": positives,
    }
    if "L2" in levels and "L3" in levels:
        out["reach"] = _reach(result, positives, seed, draws, instance)
    return out


# --------------------------------------------------------------------------- reach


def _all_edges(result: BuildResult) -> tuple[dict[str, list[tuple[str, str]]], Record]:
    edges: list[Edge] = list(result.graph.edges)
    for g in (result.tests, result.configures):
        if g is not None:
            edges += g.edges
    co: dict[int, list[Edge]] = {}
    if result.history is not None:
        for n in CO_CHANGE_SUPPORTS:
            co[n] = co_change_edges(result.parsed, result.history.commit_py_sets, n)
    pairs = edge_pairs(edges, co)
    counts = {fam: len(v) for fam, v in sorted(pairs.items())}
    return pairs, {
        "resolved_edges_by_family": counts,
        "history_commits": (result.history.n_commits if result.history else 0),
    }


def _reach(
    result: BuildResult, positives: list[Record], seed: int, draws: int, instance: str
) -> Record:
    parsed = result.parsed
    units_by_id = {u.id: u for u in parsed.units}
    pairs, edge_info = _all_edges(result)

    l2_units: set[str] = set()
    l2_hashes: set[str] = set()
    for rec in positives:
        if rec["level"] == "L2":
            l2_units.update(rec["units"])
            l2_hashes.add(rec["text_sha256_16"])
    info: Record = {"l2_units": len(l2_units), **edge_info, "positives": {}}
    if not l2_units:
        info["status"] = "no_l2_units"
        return info
    info["status"] = "ok"

    dists = {s.name: distances(adjacency(pairs, s), l2_units) for s in SUBSETS}
    touched: dict[str, set[str]] = {
        fam: {n for pair in ps for n in pair} for fam, ps in sorted(pairs.items())
    }
    all_ids = set(units_by_id)
    info["incident_base_rate"] = {
        fam: round(len(nodes & all_ids) / len(all_ids), 4) for fam, nodes in touched.items()
    }
    pools = control_pools(parsed.units, l2_units)
    per_positive: dict[str, Record] = {}
    for rec in positives:
        if rec["level"] != "L3":
            continue
        entry: Record = {"same_text_as_l2": rec["text_sha256_16"] in l2_hashes}
        units = list(rec["units"])
        kind = rec["kind"]
        if kind == "non_python_config":
            units = [rec["path"]]  # a configuration file is a node of the `configures` family
        if not units:
            entry["status"] = "no_graph_node"
        elif kind != "non_python_config" and set(units) & l2_units:
            entry["status"] = "covered_by_l2"
        else:
            entry["status"] = "ok"
            entry["k"] = len(units)
            entry["incident"] = {fam: bool(set(units) & nodes) for fam, nodes in touched.items()}
            entry["reach"] = {}
            sets_by_control: dict[str, list[tuple[str, ...]]] = {}
            if kind != "non_python_config":
                files_of = {units_by_id[u].file for u in units if u in units_by_id}
                primary_kind = unit_kind(units_by_id[rec["primary_id"]])
                for control in CONTROLS:
                    pool = draw_pool(control, pools, files_of, primary_kind)
                    rng = stable_rng(seed, instance, rec["corpus_id"], control)
                    sets_by_control[control] = draw_sets(pool, len(units), draws, rng)
            for s in SUBSET_NAMES:
                d = min_distance(dists[s], units)
                entry["reach"][s] = {
                    "d": d,
                    "obs": observed_shares(d),
                    "ctrl": {
                        c: control_shares(sets_by_control[c], dists[s])
                        if c in sets_by_control
                        else None
                        for c in CONTROLS
                    },
                }
        per_positive[rec["corpus_id"]] = entry
    info["positives"] = per_positive
    return info


# --------------------------------------------------------------------------- summaries


def match_summary(positives: Iterable[Record]) -> Record:
    """Counts of match status, tier, failure reason and span category for a set of positives."""
    recs = list(positives)
    return {
        "positives": len(recs),
        "status": dict(Counter(r["status"] for r in recs)),
        "found_unique": sum(1 for r in recs if r["status"] == "found" and r["n_locations"] == 1),
        "found_several_locations": sum(
            1 for r in recs if r["status"] == "found" and r["n_locations"] > 1
        ),
        "tier": dict(Counter(r["tier"] for r in recs if r["status"] == "found")),
        "failure_reason": dict(Counter(r["reason"] for r in recs if r["status"] != "found")),
        "category": dict(Counter(r["category"] for r in recs)),
        "kind": dict(Counter(r["kind"] for r in recs)),
    }


# --------------------------------------------------------------------------- the run


def read_base_commits(parquet_path: str) -> dict[str, str]:
    """``{instance id: base commit}`` from the SWE-bench Verified parquet (needs pyarrow)."""
    import pyarrow.parquet as pq

    table = pq.read_table(parquet_path, columns=["instance_id", "base_commit"]).to_pydict()
    return dict(zip(table["instance_id"], table["base_commit"], strict=True))


def _dump(path: str, obj: object) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    os.replace(tmp, path)


def run_pilot(
    *,
    data_root: str,
    repos: list[str],
    base_commits: dict[str, str],
    cache_dir: str,
    work_dir: str,
    out_dir: str,
    seed: int,
    draws: int = DEFAULT_DRAWS,
    force: bool = False,
) -> Record:
    """Run the pilot for the given ``owner__name`` folders; resumable per instance.

    ``data_root`` holds ``data/LEVEL-2|3/SWE-bench_Verified/<repo>/{corpus,qrels}.jsonl``;
    ``cache_dir`` holds bare clones ``<repo>.git``; ``work_dir`` receives working clones. A
    finished instance (same config hash) is read back from ``out_dir/instances`` and not redone.
    """
    chash = config_hash(seed, draws)
    inst_dir = os.path.join(out_dir, "instances")
    os.makedirs(inst_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)
    instances: list[Record] = []
    failures: list[Record] = []
    for repo in repos:
        folders = {
            lv: os.path.join(data_root, "data", f"LEVEL-{n}", "SWE-bench_Verified", repo)
            for lv, n in (("L2", 2), ("L3", 3))
        }
        qrels = {
            lv: read_qrels(os.path.join(f, "qrels.jsonl"))
            for lv, f in folders.items()
            if os.path.isdir(f)
        }
        texts: dict[str, dict[str, str]] = {}
        for lv, q in qrels.items():
            wanted = {cid for ids in q.values() for cid in ids}
            texts[lv] = read_corpus_texts(os.path.join(folders[lv], "corpus.jsonl"), wanted)
        for instance in sorted({i for q in qrels.values() for i in q}):
            cache_file = os.path.join(inst_dir, f"{instance}.json")
            if not force and os.path.exists(cache_file):
                with open(cache_file, encoding="utf-8") as handle:
                    cached = json.load(handle)
                if cached.get("config_hash") == chash:
                    instances.append(cached)
                    continue
            commit = base_commits.get(instance, "")
            if not commit:
                failures.append({"instance": instance, "reason": "no_base_commit_in_metadata"})
                continue
            status = checkout_commit(
                os.path.join(cache_dir, f"{repo}.git"), os.path.join(work_dir, repo), commit
            )
            if status != "ok":
                failures.append({"instance": instance, "reason": status, "base_commit": commit})
                continue
            levels = {
                lv: {cid: texts[lv][cid] for cid in q[instance] if cid in texts[lv]}
                for lv, q in qrels.items()
                if instance in q
            }
            rec = analyse_instance(
                os.path.join(work_dir, repo),
                repo.replace("__", "/", 1),
                instance,
                levels,
                seed=seed,
                draws=draws,
            )
            rec["base_commit"] = commit
            rec["missing_corpus_rows"] = {
                lv: sum(1 for cid in q[instance] if cid not in texts[lv])
                for lv, q in qrels.items()
                if instance in q
            }
            _dump(cache_file, rec)
            instances.append(rec)
    instances.sort(key=lambda r: r["instance"])
    doc: Record = {
        "pilot": PILOT_VERSION,
        "label": "exploratory pilot",
        "config_hash": chash,
        "seed": seed,
        "draws": draws,
        "repos": repos,
        "hardware": hardware(),
        "git": _git(["--version"]),
        "failures": failures,
        "instances": instances,
    }
    _dump(os.path.join(out_dir, "records.json"), doc)
    return doc
