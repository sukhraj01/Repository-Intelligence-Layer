"""Measure parse, graph build and storage options for one or more repositories.

Implements the storage measurement and the ``parse`` / ``graph_build`` throughput rows of
``specs/parse_one_repo.md`` through the latency harness (``ril.bench.latency_harness``): rows are
appended to the latency and throughput logs with the hardware spec of the machine that ran them.
Each heavy step runs in its own process so that peak resident memory is the step's own.

Subcommands (all print one JSON object): ``build``, ``write``, ``query``, ``throughput``,
``update`` and ``all`` (the orchestrator).

Kept compatible with Python 3.10 apart from the harness it imports (the cluster run copies the
package and uses the interpreter of the node; ``datetime.UTC`` in the harness needs 3.11, so the
cluster job uses a 3.11 interpreter or the harness import is replaced there; see the job script).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import platform
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ril.bench import graph_storage as gs
from ril.bench.latency_harness import (
    LATENCY_COLUMNS,
    THROUGHPUT_COLUMNS,
    BenchConfig,
    LatencyStage,
    RegressionThreshold,
    StageRegistry,
    append_rows,
    capture_environment,
    run_latency,
    run_throughput,
)
from ril.parsing.build import BuildConfig, build_repository, write_artifacts
from ril.parsing.call_graph import GraphBuilder
from ril.parsing.repo_graph import Edge, RepoGraph
from ril.parsing.repository_parser import ParseOptions, parse_file, parse_repository, read_source

N_QUERIES = 200


def _bench_config(label: str, backend: str, seed: int) -> BenchConfig:
    return BenchConfig(
        seed=seed,
        query_set=f"graph-{label}-{backend}-v1",
        warmup_n=5,
        repeats=3,
        throughput_repeats=3,
        regression=RegressionThreshold(rel_threshold=0.5, abs_floor_ms=0.5),
    )


def load_graph(artifact_dir: str) -> RepoGraph:
    """Rebuild a :class:`RepoGraph` from ``nodes.jsonl``, ``edges.jsonl`` and ``meta.json``."""
    with open(os.path.join(artifact_dir, "meta.json"), encoding="utf-8") as handle:
        meta = json.load(handle)
    nodes: dict[str, tuple[str, str]] = {}
    with open(os.path.join(artifact_dir, "nodes.jsonl"), encoding="utf-8") as handle:
        for line in handle:
            d = json.loads(line)
            nodes[d["id"]] = (d["kind"], d["path"])
    edges: list[Edge] = []
    with open(os.path.join(artifact_dir, "edges.jsonl"), encoding="utf-8") as handle:
        for line in handle:
            edges.append(Edge.from_dict(json.loads(line)))
    return RepoGraph(meta=meta, nodes=nodes, edges=edges)


def _emit(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")


# --------------------------------------------------------------------------- subcommands


def cmd_build(args: argparse.Namespace) -> None:
    cfg = BuildConfig(repo_id=args.repo_id, seed=args.seed)
    t0 = time.perf_counter()
    result = build_repository(args.repo_dir, cfg)
    wall = time.perf_counter() - t0
    digests = write_artifacts(result, args.out)
    status = result.graph.status_table()
    _emit(
        {
            "wall_s": round(wall, 4),
            "seconds": {k: round(v, 4) for k, v in result.seconds.items()},
            "peak_rss_mb": round(gs.peak_rss_mb(), 1),
            "units": len(result.parsed.units),
            "files": len(result.parsed.files),
            "nodes": len(result.graph.nodes),
            "edges": len(result.graph.edges),
            "status": status,
            "commit": result.commit,
            "config_hash": cfg.config_hash(),
            "graph_sha256": result.graph.digest(),
            "artifact_sha256": digests,
            "artifact_bytes": gs.dir_size(args.out),
        }
    )


def cmd_write(args: argparse.Namespace) -> None:
    graph = load_graph(args.artifact_dir)
    import_s = gs.preimport(args.backend)
    if os.path.isdir(args.store_dir):
        shutil.rmtree(args.store_dir)
    _, seconds = gs.timed(lambda: gs.writer(args.backend)(graph, args.store_dir))
    _emit(
        {
            "backend": args.backend,
            "write_s": round(seconds, 4),
            "import_s": round(import_s, 4),
            "size_bytes": gs.dir_size(args.store_dir),
        }
    )


def cmd_query(args: argparse.Namespace) -> None:
    queries = Path(args.queries).read_text(encoding="utf-8").splitlines()
    import_s = gs.preimport(args.backend)
    before = gs.peak_rss_mb()
    store, load_s = gs.timed(lambda: gs.loader(args.backend)(args.store_dir))
    after_load = gs.peak_rss_mb()
    registry = StageRegistry()

    def make(hops: int) -> Any:
        return lambda q: store.expand(q.split("|"), hops)

    registry.latency["graph_expand_1hop"] = LatencyStage("graph_expand_1hop", make(1), store.reset)
    registry.latency["graph_expand_2hop"] = LatencyStage("graph_expand_2hop", make(2), store.reset)
    config = _bench_config(args.label, args.backend, args.seed)
    env = capture_environment(config.config_hash())
    rows = run_latency(registry, config, queries, env)
    sizes = {h: [len(store.expand(q.split("|"), h)) for q in queries] for h in (1, 2)}
    _emit(
        {
            "backend": args.backend,
            "load_s": round(load_s, 4),
            "import_s": round(import_s, 4),
            "rss_before_load_mb": round(before, 1),
            "peak_rss_after_load_mb": round(after_load, 1),
            "peak_rss_after_queries_mb": round(gs.peak_rss_mb(), 1),
            "result_size_mean": {str(h): round(sum(v) / len(v), 1) for h, v in sizes.items()},
            "result_size_max": {str(h): max(v) for h, v in sizes.items()},
            "rows": rows,
        }
    )


def cmd_throughput(args: argparse.Namespace) -> None:
    holder: dict[str, Any] = {}

    def parse_fn() -> int:
        parsed = parse_repository(args.repo_dir, args.repo_id)
        holder["parsed"] = parsed
        return len(parsed.units)

    def graph_fn() -> int:
        parsed = holder.get("parsed") or parse_repository(args.repo_dir, args.repo_id)
        GraphBuilder(parsed).build()
        return len(parsed.units)

    registry = StageRegistry()
    registry.register_throughput("parse", parse_fn)
    registry.register_throughput("graph_build", graph_fn)
    config = dataclasses.replace(
        _bench_config(args.label, "build", args.seed), query_set=f"graph-{args.label}-v1"
    )
    env = capture_environment(config.config_hash())
    rows = run_throughput(registry, config, env)
    _emit({"rows": rows})


def cmd_update(args: argparse.Namespace) -> None:
    """Incremental update of the sidecar option: re-parse and re-resolve one file, rewrite it."""
    parsed = parse_repository(args.repo_dir, args.repo_id)
    builder = GraphBuilder(parsed)
    graph = builder.build()
    side_dir = os.path.join(args.work, "sidecar_update")
    gs.write_sidecars(graph, side_dir)
    rng = random.Random(args.seed)
    files = sorted(parsed.files)
    sample = rng.sample(files, min(args.n_files, len(files)))
    times: list[float] = []
    for path in sample:
        t0 = time.perf_counter()
        text, raw = read_source(os.path.join(args.repo_dir, path))
        import ast

        tree = ast.parse(raw)
        fs_old = parsed.files[path]
        parse_file(
            repo_id=parsed.repo_id,
            path=path,
            text=text,
            tree=tree,
            module_name=fs_old.module_name,
            is_package=fs_old.is_package,
            last_modified="",
            options=ParseOptions(),
        )
        builder.edges = []
        builder.process_file(fs_old)
        payload = [e.to_dict() for e in sorted(builder.edges, key=Edge.sort_key)]
        with open(os.path.join(side_dir, gs._sidecar_name(path)), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()

    def pct(p: float) -> float:
        import math

        return round(times[max(0, math.ceil(p / 100 * len(times)) - 1)], 3)

    _emit({"n_files": len(times), "p50_ms": pct(50), "p95_ms": pct(95), "p99_ms": pct(99)})


def _run(args: list[str]) -> dict[str, Any]:
    done = subprocess.run(
        [sys.executable, "-m", "ril.bench.graph_measure", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(f"step failed: {args[:3]}\n{done.stderr[-2000:]}")
    return json.loads(done.stdout.strip().splitlines()[-1])  # type: ignore[no-any-return]


def cmd_all(args: argparse.Namespace) -> None:
    """Orchestrate every step for every repository and append the harness rows."""
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    log_dir = Path(args.log_dir)
    config = _bench_config("all", "all", args.seed)
    summary: dict[str, Any] = {
        "repos": {},
        "environment": capture_environment(config.config_hash()),
        "host": platform.node(),
    }
    for spec in args.repo:
        label, repo_dir, repo_id = spec.split("=", 2)
        rdir = work / label
        art = str(rdir / "artifacts")
        info: dict[str, Any] = {"repo_dir": repo_dir, "repo_id": repo_id}
        info["build"] = _run(["build", repo_dir, repo_id, art, "--seed", str(args.seed)])
        again = _run(["build", repo_dir, repo_id, art + "_rerun", "--seed", str(args.seed)])
        info["determinism"] = {
            "graph_sha256_equal": again["graph_sha256"] == info["build"]["graph_sha256"],
            "all_artifact_files_byte_identical": again["artifact_sha256"]
            == info["build"]["artifact_sha256"],
            "rerun_seconds": again["seconds"],
        }
        shutil.rmtree(art + "_rerun", ignore_errors=True)
        graph = load_graph(art)
        queries = gs.build_query_set(graph, N_QUERIES, args.seed)
        del graph  # child processes measure their own memory; do not keep this one's graph alive
        qfile = rdir / "queries.txt"
        qfile.write_text("\n".join(queries) + "\n", encoding="utf-8")
        info["query_set_sha256"] = __import__("hashlib").sha256(qfile.read_bytes()).hexdigest()
        thr = _run(["throughput", repo_dir, repo_id, label, "--seed", str(args.seed)])
        append_rows(log_dir / "throughput_log.csv", THROUGHPUT_COLUMNS, thr["rows"])
        info["throughput"] = [
            {k: r[k] for k in ("stage", "units", "seconds", "units_per_s")} for r in thr["rows"]
        ]
        info["backends"] = {}
        for backend in args.backends:
            store = str(rdir / "stores" / backend)
            w = _run(["write", art, backend, store])
            q = _run(["query", store, backend, str(qfile), label, "--seed", str(args.seed)])
            append_rows(log_dir / "latency_log.csv", LATENCY_COLUMNS, q.pop("rows"))
            info["backends"][backend] = {**w, **q}
        info["sidecar_update"] = _run(
            ["update", repo_dir, repo_id, str(rdir), "--seed", str(args.seed)]
        )
        summary["repos"][label] = info
        if not args.keep:
            shutil.rmtree(rdir / "stores", ignore_errors=True)
    Path(args.out).write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    _emit({"written": args.out})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("repo_dir")
    b.add_argument("repo_id")
    b.add_argument("out")
    b.add_argument("--seed", type=int, default=0)
    b.set_defaults(fn=cmd_build)

    w = sub.add_parser("write")
    w.add_argument("artifact_dir")
    w.add_argument("backend", choices=gs.BACKENDS)
    w.add_argument("store_dir")
    w.set_defaults(fn=cmd_write)

    q = sub.add_parser("query")
    q.add_argument("store_dir")
    q.add_argument("backend", choices=gs.BACKENDS)
    q.add_argument("queries")
    q.add_argument("label")
    q.add_argument("--seed", type=int, default=0)
    q.set_defaults(fn=cmd_query)

    t = sub.add_parser("throughput")
    t.add_argument("repo_dir")
    t.add_argument("repo_id")
    t.add_argument("label")
    t.add_argument("--seed", type=int, default=0)
    t.set_defaults(fn=cmd_throughput)

    u = sub.add_parser("update")
    u.add_argument("repo_dir")
    u.add_argument("repo_id")
    u.add_argument("work")
    u.add_argument("--seed", type=int, default=0)
    u.add_argument("--n-files", type=int, default=30)
    u.set_defaults(fn=cmd_update)

    a = sub.add_parser("all")
    a.add_argument("--repo", action="append", required=True, help="label=dir=owner/name")
    a.add_argument("--work", required=True)
    a.add_argument("--log-dir", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--backends", nargs="+", default=list(gs.BACKENDS))
    a.add_argument("--keep", action="store_true")
    a.set_defaults(fn=cmd_all)

    ns = ap.parse_args(argv)
    ns.fn(ns)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
