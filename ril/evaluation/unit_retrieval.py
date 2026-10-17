"""BM25 over the code units of one snapshot, scored on the mapped positives (pilot E1/E2).

Implements the unit-level half of ``docs/EXPERIMENTS.md`` E-BM25-REPRO. For one benchmark instance
this module takes a checkout at the instance's base commit, the issue text per level and the
positive chunk texts per level, and

1. parses the snapshot into units (``ril.parsing.repository_parser``, decision D6: the module
   unit holds the lines outside every definition);
2. locates each positive chunk in the files and maps it to units (decision D7,
   ``ril.evaluation.chunk_mapping``);
3. builds two BM25 indexes over the unit sources, one with and one without the module units, and
   records the rank of every gold unit in each (filter-first: every unit is a candidate);
4. records, per positive, the label-noise readings of ``ril.evaluation.label_noise``.

Two gold readings are kept side by side because the metric definition for a chunk that spans
several units is an open question (Q39): ``units`` (the mapping of pilot M: the functions or
methods the span overlaps, else the classes, else the module unit) and ``units_all`` (every unit
the span overlaps, including a class and the module unit when residual lines are touched).

Records hold ids, paths, line numbers and ranks only; no chunk, issue or source text.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import time
from typing import Any

from ril.evaluation.chunk_mapping import (
    SpanMapping,
    load_snapshot,
    locate_chunk,
    map_span,
    positive_kind,
)
from ril.evaluation.core_bench import rank_positives
from ril.evaluation.label_noise import (
    LineKinds,
    classify_span,
    edited_lines,
    line_kinds,
    span_overlaps,
    unit_overlaps_edit,
)
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repository_parser import parse_repository
from ril.retrieval.bm25_index import BM25Index, BM25Params, tokenize

Record = dict[str, Any]
INDEX_VARIANTS = ("with_module", "without_module")
_NO_TRUNCATION = 10**9


def units_all_of(file_units: list[CodeUnit], mapping: SpanMapping) -> tuple[str, ...]:
    """Every unit the span overlaps: leaves, classes, and the module unit for residual lines."""
    module = next((u.id for u in file_units if u.unit_type == "module"), "")
    ids = list(mapping.leaf_ids) + list(mapping.class_ids)
    if mapping.overlaps_residual and module:
        ids.append(module)
    return tuple(ids)


def _ranks_in_index(
    index: BM25Index, positions: dict[str, int], query_tokens: list[str], unit_ids: set[str]
) -> dict[str, Record]:
    wanted = {uid: positions[uid] for uid in unit_ids if uid in positions}
    if not wanted:
        return {}
    scores = index.scores(query_tokens)
    by_pos = rank_positives(scores, None, sorted(wanted.values()), _NO_TRUNCATION)
    return {
        uid: {
            "rank": by_pos[p]["filter_first"],
            "lo": by_pos[p]["lo"],
            "hi": by_pos[p]["hi"],
            "score": by_pos[p]["score"],
        }
        for uid, p in wanted.items()
    }


def analyse_units(
    root: str,
    repo_id: str,
    instance: str,
    queries: dict[str, str],
    levels: dict[str, dict[str, str]],
    patch: str,
    *,
    params: BM25Params | None = None,
) -> Record:
    """Unit-level BM25 ranks and label readings of one instance.

    ``queries`` maps a level (``L2``, ``L3``) to the issue text; ``levels`` maps a level to
    ``{corpus id: chunk text}`` of the instance's positives; ``patch`` is the reference patch,
    used only to read the labels.
    """
    t0 = time.perf_counter()
    parsed = parse_repository(root, repo_id)
    files, skipped = load_snapshot(root)
    parsed_paths = set(parsed.files)
    by_file: dict[str, list[CodeUnit]] = {}
    for u in parsed.units:
        by_file.setdefault(u.file, []).append(u)
    unit_by_id = {u.id: u for u in parsed.units}
    edits = edited_lines(patch)

    kinds_cache: dict[str, LineKinds | None] = {}
    lines_cache: dict[str, list[str]] = {}

    def kinds_of(path: str) -> tuple[LineKinds | None, list[str]]:
        if path not in kinds_cache:
            lines_cache[path] = files[path].splitlines()
            kinds_cache[path] = line_kinds(files[path]) if path.endswith(".py") else None
        return kinds_cache[path], lines_cache[path]

    positives: list[Record] = []
    gold_union: dict[str, set[str]] = {lv: set() for lv in levels}
    for level in sorted(levels):
        for cid in sorted(levels[level]):
            res = locate_chunk(levels[level][cid], files)
            rec: Record = {
                "level": level,
                "corpus_id": cid,
                "status": res.status,
                "n_locations": res.n_locations,
                "reason": res.reason,
            }
            if res.status != "found":
                rec.update(kind="unmatched", units=[], units_all=[], noise_class="unmatched")
                positives.append(rec)
                continue
            loc = res.locations[0]
            rec["path"], rec["start_line"], rec["end_line"] = loc.path, loc.start_line, loc.end_line
            if loc.path.endswith(".py") and loc.path in parsed_paths:
                mapping = map_span(by_file.get(loc.path, []), loc.start_line, loc.end_line)
                all_ids = units_all_of(by_file.get(loc.path, []), mapping)
            else:
                mapping = SpanMapping("none", (), (), (), False, "", "")
                all_ids = ()
            rec["category"] = mapping.category
            rec["kind"] = positive_kind(loc.path, mapping, parsed_paths)
            rec["units"] = list(mapping.units)
            rec["units_all"] = list(all_ids)
            kinds, lines = kinds_of(loc.path)
            rec["noise_class"] = classify_span(loc.path, kinds, lines, loc.start_line, loc.end_line)
            rec["edit_overlap"] = (
                span_overlaps(edits[loc.path], loc.start_line, loc.end_line)
                if loc.path in edits
                else False
            )
            gold_union[level].update(mapping.units)
            gold_union[level].update(all_ids)
            positives.append(rec)

    # one document per unit; the module unit's text is its residual lines (Q29)
    all_units = sorted(parsed.units, key=lambda u: u.id)
    tokens = {u.id: tokenize(u.source) for u in all_units}
    indexes: dict[str, tuple[BM25Index, dict[str, int]]] = {}
    for variant in INDEX_VARIANTS:
        members = [u for u in all_units if variant == "with_module" or u.unit_type != "module"]
        indexes[variant] = (
            BM25Index((tokens[u.id] for u in members), params),
            {u.id: i for i, u in enumerate(members)},
        )

    unit_ranks: dict[str, dict[str, dict[str, Record]]] = {}
    for level in sorted(levels):
        q_tokens = tokenize(queries.get(level, ""))
        unit_ranks[level] = {
            v: _ranks_in_index(idx, pos, q_tokens, gold_union[level])
            for v, (idx, pos) in indexes.items()
        }

    unit_edit: dict[str, bool] = {}
    for level in gold_union:
        for uid in gold_union[level]:
            gold_unit = unit_by_id.get(uid)
            if gold_unit is not None and uid not in unit_edit:
                unit_edit[uid] = gold_unit.file in edits and unit_overlaps_edit(
                    gold_unit, edits[gold_unit.file], by_file[gold_unit.file]
                )
    return {
        "instance": instance,
        "repo_id": repo_id,
        "seconds": round(time.perf_counter() - t0, 3),
        "snapshot": {
            "text_files": len(files),
            "python_files_parsed": len(parsed.files),
            "units": len(parsed.units),
            "module_units": sum(1 for u in parsed.units if u.unit_type == "module"),
            "files_skipped_by_loader": dict(skipped),
        },
        "query_chars": {lv: len(t) for lv, t in queries.items()},
        "edited_files": sorted(edits),
        "positives": positives,
        "unit_ranks": unit_ranks,
        "unit_edit_overlap": unit_edit,
        "index_sizes": {v: idx.n_docs for v, (idx, _) in indexes.items()},
    }
