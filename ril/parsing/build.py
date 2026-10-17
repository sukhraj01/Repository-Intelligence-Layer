"""Parse a checkout and build its graph, with the timings and artifacts of one build.

Implements ``specs/parse_one_repo.md`` (parse, graph build, deterministic artifacts). A build
reads one repository at one snapshot commit; the artifacts are written to
``<out>/<repo>@<commit>/`` as canonical JSONL so that a rebuild is byte-identical.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass

from ril.parsing.call_graph import (
    MAX_CANDIDATES,
    RESOLVER_NAME,
    RESOLVER_VERSION,
    GraphBuilder,
    apply_projections,
)
from ril.parsing.code_unit import CODEUNIT_SCHEMA_VERSION, units_to_jsonl
from ril.parsing.exploratory_edges import configures_edges, tests_edges
from ril.parsing.git_history import History, co_change_counts, read_history
from ril.parsing.repo_graph import REPO_GRAPH_SCHEMA_VERSION, RepoGraph
from ril.parsing.repository_parser import (
    PARSER_VERSION,
    ParsedRepository,
    ParseOptions,
    parse_repository,
)


@dataclass(frozen=True)
class BuildConfig:
    """Everything that decides the bytes of a build besides the repository content."""

    repo_id: str
    class_source: str = "full"  # Q28, provisional: ADR-013
    max_candidates: int = MAX_CANDIDATES
    with_history: bool = True
    seed: int = 0

    def config_hash(self) -> str:
        """SHA-256 of the canonical JSON of the config and the code versions."""
        payload = {
            **asdict(self),
            "parser": PARSER_VERSION,
            "resolver": f"{RESOLVER_NAME}/{RESOLVER_VERSION}",
            "repo_graph_schema": REPO_GRAPH_SCHEMA_VERSION,
            "codeunit_schema": CODEUNIT_SCHEMA_VERSION,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass
class BuildResult:
    """Outputs and timings of one build."""

    parsed: ParsedRepository
    graph: RepoGraph
    tests: RepoGraph | None
    configures: RepoGraph | None
    history: History | None
    commit: str
    seconds: dict[str, float]


def git_head(root: str) -> str:
    """The checked-out commit of ``root`` (full hash), or ``""`` outside a git checkout."""
    try:
        done = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def build_repository(root: str, config: BuildConfig, *, exploratory: bool = True) -> BuildResult:
    """Parse ``root`` and build its graph; time each stage.

    Stages timed separately: ``history`` (one pass over the commits reachable from the snapshot,
    the cost of D8), ``parse`` (phase one), ``graph_build`` (phase two: structure, imports and
    call sites) and ``exploratory`` (``tests`` and ``configures``).
    """
    commit = git_head(root)
    seconds: dict[str, float] = {}
    history: History | None = None
    if config.with_history and commit:
        t0 = time.perf_counter()
        history = read_history(root, commit)
        seconds["history"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    parsed = parse_repository(
        root,
        config.repo_id,
        last_modified=history.last_modified if history else None,
        options=ParseOptions(class_source=config.class_source),
    )
    seconds["parse"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    builder = GraphBuilder(parsed, config.max_candidates)
    graph = builder.build(commit, {"config_hash": config.config_hash()})
    apply_projections(parsed.units, graph)
    seconds["graph_build"] = time.perf_counter() - t0

    tests_graph = configures_graph = None
    if exploratory:
        t0 = time.perf_counter()
        meta = {**graph.meta, "family": "exploratory"}
        tests_graph = RepoGraph(meta=meta, nodes={}, edges=tests_edges(parsed, graph))
        configures_graph = RepoGraph(meta=meta, nodes={}, edges=configures_edges(parsed, builder))
        for g in (tests_graph, configures_graph):
            g.sort()
        seconds["exploratory"] = time.perf_counter() - t0
    return BuildResult(parsed, graph, tests_graph, configures_graph, history, commit, seconds)


def write_artifacts(result: BuildResult, out_dir: str) -> dict[str, str]:
    """Write units, nodes, edges and metadata as canonical bytes; return file name -> SHA-256."""
    os.makedirs(out_dir, exist_ok=True)
    files: dict[str, bytes] = {
        "units.jsonl": units_to_jsonl(result.parsed.units),
        "nodes.jsonl": result.graph.nodes_jsonl(),
        "edges.jsonl": result.graph.edges_jsonl(),
        "meta.json": result.graph.meta_json(),
    }
    if result.tests is not None:
        files["edges_tests_exploratory.jsonl"] = result.tests.edges_jsonl()
    if result.configures is not None:
        files["edges_configures_exploratory.jsonl"] = result.configures.edges_jsonl()
    digests: dict[str, str] = {}
    for name, data in sorted(files.items()):
        with open(os.path.join(out_dir, name), "wb") as handle:
            handle.write(data)
        digests[name] = hashlib.sha256(data).hexdigest()
    return digests


def co_change_summary(result: BuildResult) -> dict[str, object]:
    """Pair counts for N in {2, 3, 5} over the snapshot's Python files (counts only)."""
    if result.history is None:
        return {}
    return co_change_counts(result.history.commit_py_sets, set(result.parsed.files))
