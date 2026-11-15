"""Retriever demonstration on one real issue: the stages of the retrieval layer, printed.

Implements ``docs/DEMO.md``. The demo takes one issue and one repository at its base commit and
runs the same library functions as the experiments, with the configuration recorded in
``configs/frozen/rq3_contexts.json``: repository parse and typed graph, BM25, the dense scores of
the untrained encoder over the flat exact index, reciprocal rank fusion, same-file expansion, and
context assembly under a token budget. It changes no stored result; the assembled context is
compared with the stored one of the same instance by SHA-256.

The instance is chosen by a fixed rule that does not look at any outcome: among the held-out
instances, the one whose repository snapshot has the fewest units, ties by identifier
(:func:`select_instance`). What the stages find for the reference patch's edited functions is
printed as it comes out, however poor it is.

Dense stage: the dense scores are the stored scores of the encoder (flat exact: one score per unit
of the snapshot), because encoding runs on the cluster; no model is loaded here. ``dense=None``
skips the stage and the demo then shows BM25 only (the stored context compared is the BM25 arm's).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import textwrap
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TextIO

import numpy as np

from ril.assembly.assemble import Assembled, UnitText, assemble, block_header, snapshot_of
from ril.assembly.config import AssemblyConfig
from ril.assembly.measure import snapshot_units
from ril.assembly.rq3_contexts import candidates_for as arm_candidates
from ril.assembly.rq3_contexts import default_arms
from ril.assembly.tokens import ApproxTokenizer
from ril.bench.fusion_measure import CAP, SEEDS
from ril.data_mining.diff import FileChange, parse_patch
from ril.data_mining.mapping import map_change
from ril.evaluation.e3_prepare import unit_graph_arrays
from ril.evaluation.s1_graph_role import same_file_by_score
from ril.evaluation.x2_eval import positions, rrf_scores
from ril.parsing.build import BuildConfig, build_repository
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repo_graph import CORE_EDGE_TYPES, STATUSES
from ril.retrieval.bm25_index import BM25Index, order_by_score, tokenize

DEMO_VERSION = "demo-retrieve/v1"
WIDTH = 100
SHOWN = 10
ISSUE_CHARS = 600
BUDGET = 8000
"""Token budget of the primary contexts (``docs/RQ3_PILOT.md``)."""

Arr = np.ndarray[Any, Any]
Pause = Callable[[], None]

STAGE_TITLES: tuple[str, ...] = (
    "1. Parse the repository and build the typed graph",
    "2. BM25 over the units",
    "3. Dense scores of the untrained encoder",
    "4. Rank fusion and same-file expansion",
    "5. Context assembly under the token budget",
    "6. Gold: the functions the reference patch edits",
)


@dataclass(frozen=True)
class DemoConfig:
    """The settings read from the frozen record (nothing is set here)."""

    rrf_k: int
    candidates: int
    max_unit_tokens: int
    budget: int = BUDGET
    encoder: str = ""
    encoder_revision: str = ""
    encoder_max_tokens: int = 0


@dataclass(frozen=True)
class DemoInputs:
    """Everything one demo run reads; the loader of real data builds it, a test builds a toy."""

    instance: str
    repo_id: str
    base_commit: str
    issue: str
    patch: str
    root: str
    dense: Arr | None = None
    stored_sha256: Mapping[str, str] | None = None
    """Context SHA-256 of the instance's stored contexts at the demo budget, by arm name."""
    stored_text: Mapping[str, str] | None = None
    """Stored context text by arm name, when the archive is at hand (compared byte by byte)."""
    chosen_by: str = ""


def frozen_config(record: Mapping[str, Any]) -> DemoConfig:
    """Settings of the frozen context record (``configs/frozen/rq3_contexts.json``)."""
    cfg = record["configuration"]
    enc = record.get("encoder", {})
    return DemoConfig(
        rrf_k=int(cfg["rrf_k"]),
        candidates=int(cfg["candidates"]),
        max_unit_tokens=int(record["assembly"]["max_unit_tokens"]),
        encoder=str(enc.get("model_name", "")),
        encoder_revision=str(enc.get("revision", "")),
        encoder_max_tokens=int(enc.get("max_tokens", 0)),
    )


def select_instance(unit_counts: Mapping[str, int]) -> tuple[str, int]:
    """The instance with the fewest units, ties by identifier (a rule that sees no outcome)."""
    if not unit_counts:
        raise ValueError("no instances to choose from")
    count, name = min((n, i) for i, n in unit_counts.items())
    return name, count


# --------------------------------------------------------------------------- output helpers


class Out:
    """Writer with the demo's layout: at most ``WIDTH`` columns, colour on headings and gold."""

    def __init__(self, stream: TextIO, color: bool = False) -> None:
        self.stream = stream
        self.color = color

    def line(self, text: str = "") -> None:
        self.stream.write(_clip(text) + "\n")
        self.stream.flush()

    def heading(self, text: str, seconds: float | None) -> None:
        tail = "" if seconds is None else f"  [{_secs(seconds)}]"
        plain = _clip(f"== {text}{tail}")
        self.stream.write((f"\033[1;36m{plain}\033[0m" if self.color else plain) + "\n")
        self.stream.flush()

    def gold(self, text: str) -> str:
        return f"\033[1;33m{text}\033[0m" if self.color else text


def _clip(text: str) -> str:
    return text if len(text) <= WIDTH else text[: WIDTH - 3] + "..."


def _cell(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "~"


def _cell_tail(text: str, width: int) -> str:
    """Clip from the left so that the end of a ``path:line`` stays visible."""
    return text if len(text) <= width else "~" + text[-(width - 1) :]


def _secs(seconds: float) -> str:
    return f"{seconds:.2f} s" if seconds >= 0.1 else f"{seconds * 1000:.1f} ms"


def _where(u: CodeUnit) -> str:
    return f"{u.file}:{u.start_line}"


# --------------------------------------------------------------------------- stages


@dataclass
class Parsed:
    units: list[CodeUnit]
    seconds: float
    files: int
    by_type: dict[str, int]
    edges: dict[str, dict[str, int]]


def parse_stage(inputs: DemoInputs) -> Parsed:
    """Parse and build the typed graph as the instance caches were built (class form full)."""
    t0 = time.perf_counter()
    result = build_repository(
        inputs.root, BuildConfig(repo_id=inputs.repo_id, with_history=False, seed=0)
    )
    units, _, _, _ = unit_graph_arrays(result)
    by_type = Counter(u.unit_type for u in units)
    return Parsed(
        units,
        time.perf_counter() - t0,
        len(result.parsed.files),
        dict(by_type),
        result.graph.status_table(),
    )


def _top(
    scores: Arr, units: Sequence[CodeUnit], n: int = SHOWN
) -> list[tuple[int, float, CodeUnit]]:
    order = order_by_score(scores)[:n]
    return [(r + 1, float(scores[int(i)]), units[int(i)]) for r, i in enumerate(order)]


def _rank_table(out: Out, rows: Sequence[tuple[int, float, CodeUnit]], fmt: str = "{:.3f}") -> None:
    out.line(f"   {'rank':>4}  {'score':>8}  {'file:line':<38} qualified name")
    for rank, score, u in rows:
        out.line(
            f"   {rank:>4}  {fmt.format(score):>8}  {_cell_tail(_where(u), 38):<38} "
            f"{_cell(u.qualified_name, 40)}"
        )


def signal_of(unit_index: int, tops: Mapping[str, set[int]], fallback: str) -> str:
    """Signals whose printed top list holds the unit, joined by ``+``; ``fallback`` if none."""
    names = [name for name, members in tops.items() if unit_index in members]
    return "+".join(names) if names else fallback


def expanded_list(
    order: Arr, file_of_unit: Arr, seeds: int, cap: int
) -> tuple[list[int], set[int]]:
    """Seeds, then same-file units best score first, then the rest (the E-GRAPH-ROLE list form).

    Returns the list and the set of units that came from the seeds' files.
    """
    seed_units = [int(u) for u in order[:seeds]]
    expansion = same_file_by_score(file_of_unit, order, seed_units, cap)
    seed_files = {int(file_of_unit[s]) for s in seed_units}
    infile = {u for u in expansion if int(file_of_unit[u]) in seed_files}
    front = seed_units + expansion
    taken = set(front)
    return front + [int(u) for u in order if int(u) not in taken], infile


def edited_units(patch: str, units: Sequence[CodeUnit]) -> list[tuple[CodeUnit, str]]:
    """Base-commit units the patch edits (the miner's mapping, D63), with a note per unit.

    Only Python files are mapped. A unit is a function, method or class; the ``module`` unit
    holds the lines no definition covers.
    """
    by_file: dict[str, list[CodeUnit]] = {}
    for u in units:
        by_file.setdefault(u.file, []).append(u)
    found: list[tuple[CodeUnit, str]] = []
    for path, text in _file_patches(patch):
        if not path.endswith(".py") or path not in by_file:
            continue
        change = FileChange(path, path, "modified", True, parse_patch(text), False)
        for hit in map_change(by_file[path], change).hits:
            found.append((hit.unit, f"{hit.removed_lines} removed, {hit.inserted_lines} added"))
    return found


def _file_patches(patch: str) -> list[tuple[str, str]]:
    """``(old path, hunk text)`` of every file of a unified diff."""
    out: list[tuple[str, list[str]]] = []
    for line in patch.split("\n"):
        if line.startswith("diff --git "):
            path = line.split(" b/", 1)[0].removeprefix("diff --git a/")
            out.append((path, []))
        elif out and (line.startswith("@@") or out[-1][1]):
            out[-1][1].append(line)
    return [(p, "\n".join(ls).rstrip("\n")) for p, ls in out if ls]


@dataclass
class Report:
    """What a run found, for the tests and the transcript header."""

    instance: str
    units: int
    stage_seconds: dict[str, float]
    identity: str
    """``identical``, ``different`` or ``no stored context``."""
    context_sha256: str
    included: int
    skipped: dict[str, int]
    total_tokens: int
    gold: list[dict[str, Any]]


def _identity(inputs: DemoInputs, arm: str, assembled: Assembled, out: Out, budget: int) -> str:
    sha = assembled.manifest.context_sha256
    out.line(f"   check against the stored context (arm {arm}, budget {budget}):")
    verdicts: list[str] = []
    if inputs.stored_sha256 is not None and arm in inputs.stored_sha256:
        ok = inputs.stored_sha256[arm] == sha
        verdicts.append("identical" if ok else "different")
        out.line(f"     SHA-256 equals the stored record: {'yes' if ok else 'NO'} ({sha[:16]}...)")
    if inputs.stored_text is not None and arm in inputs.stored_text:
        ok = inputs.stored_text[arm].encode("utf-8") == assembled.context.encode("utf-8")
        verdicts.append("identical" if ok else "different")
        out.line(f"     bytes equal the stored file: {'yes' if ok else 'NO'}")
    if not verdicts:
        out.line("     no stored context exists for this instance and arm; nothing to compare")
        return "no stored context"
    return "identical" if all(v == "identical" for v in verdicts) else "different"


def run_demo(
    inputs: DemoInputs,
    cfg: DemoConfig,
    stream: TextIO,
    *,
    pause: Pause | None = None,
    color: bool = False,
    unit_total_note: str = "",
) -> Report:
    """Run the six stages, print each with its wall time, and return what was found."""
    out = Out(stream, color)
    seconds: dict[str, float] = {}

    def wait() -> None:
        if pause is not None:
            pause()

    out.line(f"instance  {inputs.instance}")
    out.line(f"repo      {inputs.repo_id}")
    out.line(f"commit    {inputs.base_commit}")
    if inputs.chosen_by:
        out.line(f"chosen    {inputs.chosen_by}{unit_total_note}")
    out.line("issue text (first 600 characters):")
    for raw in inputs.issue[:ISSUE_CHARS].splitlines() or [""]:
        for piece in textwrap.wrap(raw, WIDTH - 6) or [""]:
            out.line(f"   {piece}" if piece else "")
    out.line()

    # 1. parse and typed graph
    wait()
    parsed = parse_stage(inputs)
    seconds["parse"] = parsed.seconds
    units = parsed.units
    n = len(units)
    out.heading(STAGE_TITLES[0], parsed.seconds)
    t = parsed.by_type
    out.line(
        f"   {parsed.files} files, {n} units: {t.get('function', 0)} functions, "
        f"{t.get('method', 0)} methods, {t.get('class', 0)} classes, "
        f"{t.get('module', 0)} module remainders"
    )
    out.line(f"   {'edge type':<10}" + "".join(f"{s:>12}" for s in STATUSES) + f"{'total':>10}")
    for etype in CORE_EDGE_TYPES:
        erow = parsed.edges.get(etype, {})
        out.line(
            f"   {etype:<10}"
            + "".join(f"{erow.get(s, 0):>12}" for s in STATUSES)
            + f"{sum(erow.get(s, 0) for s in STATUSES):>10}"
        )
    out.line()

    # 2. BM25
    wait()
    t0 = time.perf_counter()
    index = BM25Index(tokenize(u.source) for u in units)
    t_index = time.perf_counter() - t0
    t1 = time.perf_counter()
    bm25 = index.scores(tokenize(inputs.issue))
    seconds["bm25"] = time.perf_counter() - t0
    t_query = time.perf_counter() - t1
    out.heading(STAGE_TITLES[1], seconds["bm25"])
    out.line(f"   index build {t_index:.2f} s, one query {t_query * 1000:.1f} ms; top {SHOWN}:")
    _rank_table(out, _top(bm25, units), "{:.2f}")
    out.line()

    # 3. dense
    wait()
    dense = inputs.dense
    if dense is None:
        out.heading(STAGE_TITLES[2] + " (skipped: --no-dense)", None)
        out.line(
            "   the dense stage is off; fusion below is not available, BM25 is the first stage"
        )
    else:
        if len(dense) != n:
            raise ValueError(f"dense scores for {len(dense)} units, snapshot has {n}")
        t0 = time.perf_counter()
        dense_top = _top(dense, units)
        seconds["dense"] = time.perf_counter() - t0
        out.heading(STAGE_TITLES[2], seconds["dense"])
        out.line(
            f"   {cfg.encoder} (revision {cfg.encoder_revision[:7]}, {cfg.encoder_max_tokens} "
            "tokens), not trained;"
        )
        out.line(f"   flat exact scores of all {n} units, stored (encoded on the cluster GPU);")
        out.line(
            "   no model is loaded on this machine. Device here: none (a table lookup). Top 10:"
        )
        _rank_table(out, dense_top, "{:.3f}")
    out.line()

    # 4. fusion and same-file expansion
    wait()
    file_idx = {f: i for i, f in enumerate(sorted({u.file for u in units}))}
    file_of_unit = np.asarray([file_idx[u.file] for u in units], dtype=np.int32)
    t0 = time.perf_counter()
    if dense is None:
        first_stage = np.asarray(bm25, dtype=np.float64)
        stage_name = "BM25 only"
    else:
        first_stage = rrf_scores([positions(bm25), positions(dense)], cfg.rrf_k)
        stage_name = f"reciprocal rank fusion, k = {cfg.rrf_k}"
    order = order_by_score(first_stage)
    expanded, in_files = expanded_list(order, file_of_unit, SEEDS, CAP)
    seconds["fusion"] = time.perf_counter() - t0
    tops: dict[str, set[int]] = {"bm25": {int(i) for i in order_by_score(bm25)[:SHOWN]}}
    if dense is not None:
        tops["dense"] = {int(i) for i in order_by_score(dense)[:SHOWN]}
    out.heading(STAGE_TITLES[3], seconds["fusion"])
    out.line(f"   {stage_name}, then same-file expansion of the top {SEEDS} (up to {CAP} units).")
    out.line("   signal: the lists whose printed top 10 hold the unit; 'fusion' = neither alone.")
    out.line(f"   {'rank':>4}  {'signal':<12} {'file:line':<38} qualified name")
    for r, i in enumerate(expanded[:SHOWN], start=1):
        u = units[i]
        sig = "same-file" if (r > SEEDS and i in in_files) else signal_of(i, tops, "fusion")
        out.line(
            f"   {r:>4}  {sig:<12} {_cell_tail(_where(u), 38):<38} {_cell(u.qualified_name, 40)}"
        )
    out.line(
        "   ranks 1 to 5 are the fused top five (seeds); 6 to 10 are the best same-file units."
    )
    out.line("   Expansion is off in the frozen configuration: the context below is built from the")
    out.line("   fused list without it, the same list the experiments assembled.")
    out.line()

    # 5. assembly (the frozen path: arm list, no expansion)
    wait()
    t0 = time.perf_counter()
    header_units: list[UnitText] = snapshot_units(inputs.root, inputs.repo_id)
    ids = [u.unit_id for u in header_units]
    if ids != [u.id for u in units]:
        raise ValueError("unit order of the two parses differs; the stored scores would not align")
    arm = next(a for a in default_arms(cfg.rrf_k) if a.name == ("bm25" if dense is None else "rrf"))
    cands = arm_candidates(arm, bm25, dense, ids, cfg.candidates)
    tok = ApproxTokenizer()
    snap = snapshot_of(header_units)
    assembled = assemble(cands, snap, AssemblyConfig(cfg.budget, cfg.max_unit_tokens), tok)
    seconds["assembly"] = time.perf_counter() - t0
    m = assembled.manifest
    skipped = Counter(s.reason for s in m.skipped)
    out.heading(STAGE_TITLES[4], seconds["assembly"])
    out.line(
        f"   budget {cfg.budget} tokens, unit cap {cfg.max_unit_tokens}, tokenizer {m.tokenizer}; "
        f"{len(cands)} candidates"
    )
    out.line(
        f"   included {len(m.entries)} units, skipped {len(m.skipped)}"
        + (f" ({', '.join(f'{k} {v}' for k, v in sorted(skipped.items()))})" if skipped else "")
    )
    out.line(f"   total {m.total_tokens} tokens of {cfg.budget}; first three block headers:")
    for e in m.entries[:3]:
        out.line(f"     {block_header(snap[e.unit_id], e.rank)}")
    identity = _identity(inputs, arm.name, assembled, out, cfg.budget)
    out.line()

    # 6. gold
    wait()
    t0 = time.perf_counter()
    gold = edited_units(inputs.patch, units)
    pos_of = {
        "bm25": positions(bm25),
        "dense": positions(dense) if dense is not None else None,
        "fusion": positions(first_stage) if dense is not None else None,
    }
    exp_rank = {u: r for r, u in enumerate(expanded, start=1)}
    included = {e.unit_id: e for e in m.entries}
    index_of = {u.id: i for i, u in enumerate(units)}
    rows: list[dict[str, Any]] = []
    for u, note in gold:
        i = index_of[u.id]
        row: dict[str, Any] = {
            "unit": u.id,
            "bm25": int(pos_of["bm25"][i]) + 1,  # type: ignore[index]
            "dense": None if pos_of["dense"] is None else int(pos_of["dense"][i]) + 1,
            "fusion": None if pos_of["fusion"] is None else int(pos_of["fusion"][i]) + 1,
            "expanded": exp_rank[i],
            "in_context": u.id in included,
            "truncated": bool(u.id in included and included[u.id].truncated),
            "note": note,
        }
        rows.append(row)
    seconds["gold"] = time.perf_counter() - t0
    out.heading(STAGE_TITLES[5], seconds["gold"])
    if not rows:
        out.line("   the reference patch edits no function of a parsed Python file")
    for row in rows:
        out.line(out.gold(f"   * {row['unit']}") + f"   ({row['note']})")
        cells = [("BM25", row["bm25"]), ("dense", row["dense"]), ("fused", row["fusion"])]
        out.line(
            "     rank in:  "
            + "   ".join(f"{k} {v if v is not None else '-'}" for k, v in cells)
            + f"   with same-file expansion {row['expanded']}"
        )
        cut = " (cut at the unit cap)" if row["truncated"] else ""
        out.line(
            "     in the assembled context: "
            + out.gold("yes" if row["in_context"] else "no")
            + (cut if row["in_context"] else "")
        )
    if any(u.unit_type == "class" and note.startswith("0 removed") for u, note in gold):
        out.line(
            "   (a class with added lines only: the mapping gives lines added after a method's"
        )
        out.line("   last line to the class that holds the method)")
    for text in _reading(rows, dense is not None).split("\n"):
        out.line(text)
    out.line()
    out.line(
        "This is one illustrative instance chosen by a fixed rule (fewest units among the 50 "
        "held-out"
    )
    out.line("instances), not a measurement.")
    return Report(
        inputs.instance,
        n,
        seconds,
        identity,
        m.context_sha256,
        len(m.entries),
        dict(skipped),
        m.total_tokens,
        rows,
    )


def _reading(rows: Sequence[Mapping[str, Any]], has_dense: bool) -> str:
    """Where the best gold unit ranks in each list, and which lists hold it in their top 10."""
    if not rows:
        return "   no gold function to rank."
    names = {"bm25": "BM25", "dense": "dense", "fusion": "fused"}
    lists = ["bm25", *(["dense", "fusion"] if has_dense else [])]
    best = {k: min(int(r[k]) for r in rows) for k in lists}
    inside = [names[k] for k in lists if best[k] <= SHOWN] or ["none"]
    outside = [names[k] for k in lists if best[k] > SHOWN] or ["none"]
    return (
        "   best gold rank: " + ", ".join(f"{names[k]} {best[k]}" for k in lists) + "\n"
        f"   inside the top {SHOWN} in: {', '.join(inside)}; outside it in: {', '.join(outside)}"
    )


# --------------------------------------------------------------------------- real inputs


def context_sha_by_arm(csv_path: str, instance: str, budget: int) -> dict[str, str]:
    """Stored context SHA-256 of one instance by arm, from the tracked contexts table."""
    import csv

    found: dict[str, str] = {}
    with open(csv_path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["instance"] == instance and int(row["budget"]) == budget:
                found[row["arm"]] = row["context_sha256"]
    return found


def stored_text_from_archive(archive: str, instance: str, budget: int) -> dict[str, str]:
    """Stored context text by arm from the archive (``contexts_b<budget>/<arm>/<id>.txt``)."""
    import tarfile

    found: dict[str, str] = {}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            parts = member.name.split("/")
            if (
                len(parts) == 3
                and parts[0] == f"contexts_b{budget}"
                and parts[2] == f"{instance}.txt"
            ):
                handle = tar.extractfile(member)
                if handle is not None:
                    found[parts[1]] = handle.read().decode("utf-8")
    return found


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_frozen(path: str) -> DemoConfig:
    with open(path, encoding="utf-8") as handle:
        return frozen_config(json.load(handle))


VERIFIED_TABLE = "hf_meta/princeton-nlp_SWE-bench_Verified/data/test-00000-of-00001.parquet"
DENSE_DIR = "x2/dense/coderankembed__t512"
CACHE_DIR = "e3/e3_cache"
UNIT_COUNTS_TABLE = "results/rq3_units/instances.csv"


def unit_counts(ids: Sequence[str], counts_csv: str, cache_dir: str) -> dict[str, int]:
    """Units per instance from the stored unit records: the table first, the instance caches next.

    Raises when an instance has neither, so that the selection rule never runs on a partial set.
    """
    import csv
    import os

    from ril.evaluation.e3_prepare import read_cache

    counts: dict[str, int] = {}
    if os.path.exists(counts_csv):
        with open(counts_csv, encoding="utf-8", newline="") as handle:
            counts = {r["instance"]: int(r["units"]) for r in csv.DictReader(handle)}
    out: dict[str, int] = {}
    for iid in ids:
        if iid in counts:
            out[iid] = counts[iid]
            continue
        path = os.path.join(cache_dir, f"{iid}.npz")
        if not os.path.exists(path):
            raise FileNotFoundError(f"no stored unit record for {iid}: {counts_csv} or {path}")
        out[iid] = int(read_cache(path)[1]["units"])
    return out


def checkout_archive(repo_git_dir: str, commit: str, dest: str) -> None:
    """Export ``commit`` of a clone into the empty directory ``dest`` (the clone is not touched)."""
    import subprocess
    import tarfile

    done = subprocess.run(
        ["git", "-C", repo_git_dir, "archive", commit],
        capture_output=True,
        check=False,
        timeout=300,
    )
    if done.returncode != 0:
        raise RuntimeError(f"git archive {commit} failed: {done.stderr.decode()[:200]}")
    import io

    with tarfile.open(fileobj=io.BytesIO(done.stdout)) as tar:
        tar.extractall(dest, filter="data")


def verified_row(table_path: str, instance: str) -> dict[str, Any]:
    """The row of one instance of the Verified table (issue text, base commit, reference patch)."""
    import pyarrow.parquet as pq

    columns = ["instance_id", "repo", "base_commit", "problem_statement", "patch"]
    for rec in pq.read_table(table_path, columns=columns).to_pylist():
        if rec["instance_id"] == instance:
            return dict(rec)
    raise KeyError(f"{instance} is not in {table_path}")


def stored_dense(path: str, n_units: int) -> Arr:
    """Stored flat-exact scores of the untrained encoder for the instance (key ``dense_L2``)."""
    with np.load(path, allow_pickle=False) as z:
        scores = np.asarray(z["dense_L2"])
    if len(scores) != n_units:
        raise ValueError(f"{path}: {len(scores)} scores for {n_units} units")
    return scores


def real_inputs(
    instance: str,
    *,
    checkout_dir: str,
    use_dense: bool,
    chosen_by: str,
    budget: int = BUDGET,
    archive: str | None = None,
    repo_dir: str | None = None,
) -> DemoInputs:
    """Inputs of one held-out instance from the stored data (paths from ``ril.config.paths``).

    The base commit is exported from the local clone into ``checkout_dir`` (empty directory);
    ``repo_dir`` is an existing checkout at the base commit to use instead.
    """
    import os

    from ril.config.paths import processed_dir, raw_dir, repo_root

    row = verified_row(str(raw_dir() / VERIFIED_TABLE), instance)
    repo_id = str(row["repo"])
    commit = str(row["base_commit"])
    root = repo_dir
    if root is None:
        clone = str(raw_dir() / "repos" / repo_id.replace("/", "__"))
        checkout_archive(clone, commit, checkout_dir)
        root = checkout_dir
    dense = None
    if use_dense:
        path = str(processed_dir() / DENSE_DIR / f"{instance}.npz")
        with np.load(path, allow_pickle=False) as z:
            dense = np.asarray(z["dense_L2"])
    table = str(repo_root() / "results" / "rq3_contexts" / "rq3_contexts_contexts.csv")
    sha = context_sha_by_arm(table, instance, budget) if os.path.exists(table) else None
    text = stored_text_from_archive(archive, instance, budget) if archive else None
    return DemoInputs(
        instance=instance,
        repo_id=repo_id,
        base_commit=commit,
        issue=str(row["problem_statement"]),
        patch=str(row["patch"]),
        root=root,
        dense=dense,
        stored_sha256=sha,
        stored_text=text,
        chosen_by=chosen_by,
    )


def environment_lines() -> list[str]:
    """Machine description for the transcript header (no host name, no user name)."""
    import os
    import platform

    mem = ""
    try:
        mem = f", {os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 2**30:.0f} GiB memory"
    except (ValueError, OSError, AttributeError):
        pass
    return [
        f"machine: {platform.platform()}, {platform.machine()}, {os.cpu_count()} CPUs{mem}",
        "device: CPU only; no accelerator is used (the dense stage reads stored scores)",
        f"python: {platform.python_version()}",
    ]


def transcript_text(report: Report, body: str, *, commit: str, mode: str, date: str) -> str:
    """The recorded transcript: header (code commit, machine, mode), the run, per-stage times."""
    head = [
        f"# retriever demo transcript ({DEMO_VERSION})",
        f"# code commit: {commit}",
        f"# recorded: {date}, mode: {mode}",
        *(f"# {line}" for line in environment_lines()),
        f"# instance: {report.instance}, stored-context check: {report.identity}",
        "",
    ]
    names = {
        "parse": "parse and typed graph",
        "bm25": "BM25",
        "dense": "dense (stored scores)",
        "fusion": "fusion and same-file expansion",
        "assembly": "context assembly",
        "gold": "gold lookup",
    }
    tail = ["", "# wall time per stage (seconds, from this run)"]
    tail += [f"#   {names[k]:<32}{v:.4f}" for k, v in report.stage_seconds.items() if k in names]
    tail.append(f"#   {'total of the stages':<32}{sum(report.stage_seconds.values()):.4f}")
    return "\n".join(head) + body.rstrip("\n") + "\n" + "\n".join(tail) + "\n"
