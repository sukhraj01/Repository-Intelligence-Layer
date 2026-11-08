"""Inventory of CORE-Bench repositories as candidate evaluation repositories (E-EVAL-REPOS).

Implements ``docs/experiments/B.md`` E-EVAL-REPOS (D75, ``docs/RQ2_PROTOCOL.md`` O8). It builds one
row per repository from files that already exist (per-folder instance ids and corpus statistics,
the held-out list, the stored unit records and dense stores) and one survey JSON produced on the
cluster (``scripts/ada/eval_repo_survey.py``). It chooses nothing: no column ranks or selects.

Counts are measured where the source says so; everything marked ``estimated`` is a ratio applied to
the folder's corpus size and carries its method in the ``units_basis`` column. Nothing here reads
dataset text.
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from ril.training.held_out import repo_from_instance_id

Record = dict[str, Any]

ENCODE_RATE_ASSUMED = 178.0
"""Texts per second given in the task brief; no run log with this value was found."""
ENCODE_RATE_MEASURED = 229.0
"""Unit texts per second of the dev evaluation (``docs/COMPUTE.md``, 590k texts in 43 minutes)."""
STORED_GPU_HOURS_PER_REPO = 0.06
"""Protocol figure per repository per checkpoint (``docs/RQ2_PROTOCOL.md`` section 5)."""
PYTHON_SHARE_PYTHON = 0.5
PYTHON_SHARE_MIXED = 0.1
MIN_SAMPLED_CODE_CHUNKS = 20

COLUMNS = (
    "repository",
    "datasets",
    "set_group",
    "l2_folders",
    "l3_folders",
    "folder_shared_with_other_repos",
    "l2_queries",
    "l3_queries",
    "l2_queries_by_folder",
    "l3_queries_by_folder",
    "l2_positive_rows",
    "l3_positive_rows",
    "l2_corpus_chunks_in_folder",
    "language_class",
    "python_share_of_sampled_code_chunks",
    "sampled_code_chunks",
    "unit_records_instances",
    "dense_store_instances",
    "units_basis",
    "units_per_snapshot",
    "distinct_unit_texts",
    "distinct_unit_texts_low",
    "distinct_unit_texts_high",
    "snapshots",
    "python_files_at_head",
    "files_estimate",
    "held_out_listed",
    "in_published_pool_listing",
    "in_training_population",
    "in_mining_population",
    "leaks_if_evaluated",
    "parse_seconds",
    "parse_basis",
    "encode_gpu_hours_at_178",
    "encode_gpu_hours_at_229",
    "encode_gpu_hours_stored_figure",
)


def split_key(key: str) -> tuple[str, str, str]:
    """``LEVEL-2/<dataset>/<folder>`` -> (level, dataset, folder)."""
    level, dataset, folder = key.split("/", 2)
    return level, dataset, folder


def folder_repo_queries(
    ids_all: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Per original folder key, per repository: query ids and positive rows.

    The repository of a query is read from its instance id (``repo_from_instance_id``), so a folder
    that holds several repositories is split exactly. Rewrite folders are skipped.
    """
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for key, doc in ids_all.items():
        if not key.startswith(("LEVEL-2/", "LEVEL-3/")):
            continue
        per_q = doc.get("qrels_query_ids", {})
        repos: dict[str, dict[str, Any]] = {}
        for qid in doc.get("queries_ids", []):
            repo = repo_from_instance_id(str(qid))
            if repo is None:
                raise ValueError(f"unreadable instance id {qid!r} in {key}")
            slot = repos.setdefault(repo, {"queries": set(), "positives": 0})
            slot["queries"].add(str(qid))
            slot["positives"] += int(per_q.get(qid, 0))
        out[key] = repos
    return out


def language_class(sample: Mapping[str, int] | None) -> tuple[str, float | None, int]:
    """(class, python share, sampled code chunks) of one folder's sample.

    ``python`` when at least half of the sampled code-like chunks have Python markers, ``mixed``
    from one tenth, ``non_python`` below that; ``unknown`` with fewer than 20 code-like chunks or
    no sample. A line-marker heuristic on six slices of the corpus file, not a language detector.
    """
    if not sample:
        return "unknown", None, 0
    py, other = int(sample.get("python", 0)), int(sample.get("other_code", 0))
    code = py + other
    if code < MIN_SAMPLED_CODE_CHUNKS:
        return "unknown", None, code
    share = py / code
    if share >= PYTHON_SHARE_PYTHON:
        return "python", share, code
    if share >= PYTHON_SHARE_MIXED:
        return "mixed", share, code
    return "non_python", share, code


def hours(texts: float, rate: float) -> float:
    """GPU-hours to encode ``texts`` at ``rate`` texts per second."""
    return texts / rate / 3600.0


def _median(values: Sequence[float]) -> float:
    return float(statistics.median(values))


def build_rows(
    *,
    folder_queries: Mapping[str, Mapping[str, Mapping[str, Any]]],
    corpus_rows: Mapping[str, int],
    folder_sets: Mapping[str, str],
    store_folders: Mapping[str, str],
    survey: Mapping[str, Any],
    is_held_out: Callable[[str], bool],
    resolve: Callable[[str], str],
) -> list[Record]:
    """One row per repository, sorted by repository name.

    ``folder_sets`` maps a folder key to ``dev`` / ``test`` (the experiment configuration's roles;
    absent = no role). ``store_folders`` maps a repository to the folder key its stored records
    were built from (their calibration against the folder's corpus size). ``survey`` is the
    cluster survey; ``resolve`` maps a repository name to its current name.
    """
    stores: Mapping[str, Any] = survey.get("stores", {})
    lang_by_key: Mapping[str, Any] = survey.get("language", {})
    clones: Mapping[str, Any] = survey.get("bare_clones", {})
    pop: Mapping[str, Any] = survey.get("population", {})
    raw_pool = {resolve(r) for r in pop.get("raw_pool_repos", {})} | set(
        pop.get("raw_pool_repos", {})
    )
    after_filter = set(pop.get("pool_after_filter_repos", {}))
    mining = set(pop.get("mining_population_repos", {}))

    per_repo: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "folders": {2: [], 3: []},
            "by_folder": {2: {}, 3: {}},
            "datasets": set(),
            "q": {2: set(), 3: set()},
            "pos": {2: 0, 3: 0},
            "shared": False,
            "chunks": 0.0,
            "lang_keys": [],
        }
    )
    for key, repos in sorted(folder_queries.items()):
        level, dataset, folder = split_key(key)
        lv = 2 if level == "LEVEL-2" else 3
        for repo, doc in repos.items():
            slot = per_repo[repo]
            slot["folders"][lv].append(f"{dataset}/{folder}")
            slot["by_folder"][lv][f"{dataset}/{folder}"] = len(doc["queries"])
            slot["datasets"].add(dataset)
            slot["q"][lv] |= doc["queries"]
            slot["pos"][lv] += int(doc["positives"])
            if len(repos) > 1:
                slot["shared"] = True
            if lv == 2:
                total_q = sum(len(d["queries"]) for d in repos.values())
                share = len(doc["queries"]) / total_q if total_q else 0.0
                slot["chunks"] += corpus_rows.get(key, 0) * share
                slot["lang_keys"].append(key)

    # calibration of corpus size against the stored records: measured ratios, taken on the folder
    # the records were built from
    points = calibration_points(store_folders, corpus_rows, stores)
    ratios_t = {r: p["texts"] / p["chunks"] for r, p in points.items()}
    ratios_u = {r: p["units"] / p["chunks"] for r, p in points.items()}
    sec_per_unit: list[float] = []
    units_per_file: list[float] = []
    for repo in points:
        st = stores[_store_name(repo, stores)]
        for u, sec in zip(st["units"], st["seconds"], strict=True):
            if u and sec:
                sec_per_unit.append(float(sec) / float(u))
        clone = clones.get(_store_name(repo, clones))
        if clone and clone.get("py_files_at_head"):
            units_per_file.append(points[repo]["units"] / float(clone["py_files_at_head"]))
    r_t = sorted(ratios_t.values())
    r_u = sorted(ratios_u.values())
    spu = _median(sec_per_unit) if sec_per_unit else 0.0
    upf = _median(units_per_file) if units_per_file else 0.0

    rows: list[Record] = []
    for repo in sorted(per_repo):
        slot = per_repo[repo]
        groups = {
            folder_sets.get(f"LEVEL-{lv}/{f}", "") for lv in (2, 3) for f in slot["folders"][lv]
        }
        group = (
            "dev"
            if "dev" in groups
            else "verified"
            if "SWE-bench_Verified" in slot["datasets"]
            else "other"
        )
        py_n = sum(int((lang_by_key.get(k) or {}).get("python", 0)) for k in slot["lang_keys"])
        ot_n = sum(int((lang_by_key.get(k) or {}).get("other_code", 0)) for k in slot["lang_keys"])
        if any(k in lang_by_key for k in slot["lang_keys"]):
            cls, py_share, code = language_class({"python": py_n, "other_code": ot_n})
        else:
            cls, py_share, code = "unknown", None, 0
        st = stores.get(_store_name(repo, stores))
        measured = bool(st and st.get("units"))
        n_snap = len(slot["q"][2] | slot["q"][3])
        chunks = float(slot["chunks"])
        clone = clones.get(_store_name(repo, clones)) or {}
        row: Record = {
            "repository": repo,
            "datasets": ";".join(sorted(slot["datasets"])),
            "set_group": group,
            "l2_folders": ";".join(sorted(slot["folders"][2])),
            "l3_folders": ";".join(sorted(slot["folders"][3])),
            "folder_shared_with_other_repos": int(slot["shared"]),
            "l2_queries": len(slot["q"][2]),
            "l3_queries": len(slot["q"][3]),
            "l2_queries_by_folder": ";".join(
                f"{k}={v}" for k, v in sorted(slot["by_folder"][2].items())
            ),
            "l3_queries_by_folder": ";".join(
                f"{k}={v}" for k, v in sorted(slot["by_folder"][3].items())
            ),
            "l2_positive_rows": slot["pos"][2],
            "l3_positive_rows": slot["pos"][3],
            "l2_corpus_chunks_in_folder": round(chunks),
            "language_class": cls,
            "python_share_of_sampled_code_chunks": None if py_share is None else round(py_share, 3),
            "sampled_code_chunks": code,
            "unit_records_instances": int(st["unit_records"]) if st else 0,
            "dense_store_instances": int(st["dense"]) if st else 0,
            "python_files_at_head": clone.get("py_files_at_head"),
            "held_out_listed": int(is_held_out(repo)),
            "in_published_pool_listing": int(repo in raw_pool or resolve(repo) in raw_pool),
            "in_training_population": int(repo in after_filter or resolve(repo) in after_filter),
            "in_mining_population": int(repo in mining or resolve(repo) in mining),
        }
        row["leaks_if_evaluated"] = int(
            row["in_training_population"] or row["in_mining_population"]
        )
        if measured:
            assert st is not None
            row.update(
                units_basis="measured: stored unit records",
                units_per_snapshot=round(_median(st["units"])),
                distinct_unit_texts=int(st["distinct_unit_texts"]),
                distinct_unit_texts_low=None,
                distinct_unit_texts_high=None,
                snapshots=len(st["units"]),
            )
            parse_s = float(sum(st["seconds"]))
            row["parse_seconds"] = round(parse_s, 1)
            row["parse_basis"] = "measured: sum of stored per-snapshot prep seconds"
            texts = float(st["distinct_unit_texts"])
        elif r_t and chunks:
            texts = _median(r_t) * chunks
            row.update(
                units_basis=(
                    f"estimated: median of {len(r_t)} measured ratios (distinct unit texts per "
                    "L2 corpus chunk) times the folder's chunks; low/high = min/max ratio"
                ),
                units_per_snapshot=round(_median(r_u) * chunks),
                distinct_unit_texts=round(texts),
                distinct_unit_texts_low=round(r_t[0] * chunks),
                distinct_unit_texts_high=round(r_t[-1] * chunks),
                snapshots=n_snap,
            )
            parse_s = n_snap * _median(r_u) * chunks * spu
            row["parse_seconds"] = round(parse_s, 1)
            row["parse_basis"] = (
                "estimated: snapshots x estimated units per snapshot x median measured "
                "prep seconds per unit (includes checkout)"
            )
        else:
            texts = 0.0
            row.update(
                units_basis="none: no corpus size or no calibration",
                units_per_snapshot=None,
                distinct_unit_texts=None,
                distinct_unit_texts_low=None,
                distinct_unit_texts_high=None,
                snapshots=n_snap,
                parse_seconds=None,
                parse_basis="",
            )
        if clone.get("py_files_at_head"):
            row["files_estimate"] = int(clone["py_files_at_head"])
        elif upf and row.get("units_per_snapshot"):
            row["files_estimate"] = round(float(row["units_per_snapshot"]) / upf)
        else:
            row["files_estimate"] = None
        row["encode_gpu_hours_at_178"] = (
            round(hours(texts, ENCODE_RATE_ASSUMED), 4) if texts else None
        )
        row["encode_gpu_hours_at_229"] = (
            round(hours(texts, ENCODE_RATE_MEASURED), 4) if texts else None
        )
        row["encode_gpu_hours_stored_figure"] = STORED_GPU_HOURS_PER_REPO
        rows.append(row)
    return rows


def _store_name(repo: str, table: Mapping[str, Any]) -> str:
    """Key of ``repo`` (``owner/name``) in a table keyed ``owner__name``, or ``""``.

    Exact match only: a looser rule would attach ``ansible/ansible-lint`` to ``ansible/ansible``.
    """
    owner, _, name = repo.partition("/")
    cand = f"{owner}__{name}"
    return cand if cand in table else ""


def calibration_points(
    store_folders: Mapping[str, str],
    corpus_rows: Mapping[str, int],
    stores: Mapping[str, Any],
) -> dict[str, dict[str, float]]:
    """Per repository with stored records: the stored folder's corpus chunks and what was measured.

    Keys: ``chunks`` (L2 corpus rows of the folder the records were built from), ``texts``
    (distinct unit texts), ``units`` (median units per snapshot).
    """
    out: dict[str, dict[str, float]] = {}
    for repo, key in sorted(store_folders.items()):
        st = stores.get(_store_name(repo, stores))
        chunks = float(corpus_rows.get(key, 0))
        if st and st.get("units") and chunks:
            out[repo] = {
                "chunks": chunks,
                "texts": float(st["distinct_unit_texts"]),
                "units": _median(st["units"]),
            }
    return out


def leave_one_out(points: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    """Relative error of the median-ratio estimate of distinct unit texts, one repository left out.

    ``(estimate - measured) / measured`` where the estimate is the median of the other
    repositories' texts-per-chunk ratio times the left-out repository's chunks.
    """
    out: dict[str, float] = {}
    for repo, pt in points.items():
        others = [q["texts"] / q["chunks"] for r, q in points.items() if r != repo]
        if others:
            out[repo] = (_median(others) * pt["chunks"] - pt["texts"]) / pt["texts"]
    return out


def write_csv(rows: Iterable[Mapping[str, Any]], path: str) -> None:
    """Write the inventory with the fixed column order; empty cells for missing values."""
    with open(path, "w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=list(COLUMNS), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r[c]) for c in COLUMNS})


def summarise(rows: Sequence[Mapping[str, Any]]) -> Record:
    """Counts of repositories by group, language class and leakage, for the entry."""
    out: Record = {"repositories": len(rows)}
    for col in ("set_group", "language_class"):
        c: dict[str, int] = defaultdict(int)
        for r in rows:
            c[str(r[col])] += 1
        out[col] = dict(sorted(c.items()))
    out["leaking"] = sum(int(r["leaks_if_evaluated"]) for r in rows)
    out["held_out_listed"] = sum(int(r["held_out_listed"]) for r in rows)
    out["with_l3"] = sum(1 for r in rows if int(r["l3_queries"]) > 0)
    return out
