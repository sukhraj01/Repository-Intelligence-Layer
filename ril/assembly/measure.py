"""Gold in the assembled context, by budget and first stage (E-ASSEMBLY; exploratory).

Implements ``docs/experiments/B.md`` E-ASSEMBLY and ``specs/assembly.md`` ("Measurement"). Inputs
are those of ``ril.evaluation.s1_graph_role``: the pilot-E3 cache (BM25 scores, file of each unit,
gold unit indices under four readings) and one dense score file per instance for the stored
reciprocal-rank-fusion first stage. The cache holds no unit text, so each instance is checked out
at its base commit and rebuilt (class units in header form, no history; ids and unit order are
those of the cache, which a count check enforces). For each level, first stage and budget the
ranked list is assembled with ``ril.assembly.assemble`` and the gold units and files are looked up
in the manifest.

Nothing is tuned here: the unit cap, the candidate list length and the budget grid are stated in
the configuration before any run. The assembly itself is deterministic, so ``seed`` is recorded
only.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np

from ril.assembly.assemble import Candidate, UnitText, assemble, snapshot_of
from ril.assembly.config import AssemblyConfig
from ril.assembly.gold import gold_in_context
from ril.assembly.tokens import ApproxTokenizer, Tokenizer
from ril.evaluation.e3_prepare import READINGS, read_cache
from ril.evaluation.x2_eval import positions, rrf_scores
from ril.retrieval.bm25_index import order_by_score

MEASURE_VERSION = "assembly-gold/v1"
FIRST_STAGES = ("bm25", "rrf")
Record = dict[str, Any]
Arr = np.ndarray[Any, Any]


@dataclass(frozen=True)
class MeasureSpec:
    """One stated setting; the budgets are the measurement grid."""

    budgets: tuple[int, ...]
    max_unit_tokens: int
    candidates: int
    first_stages: tuple[str, ...]
    dense_variant: str
    rrf_k: int
    readings: tuple[str, ...]
    caps: tuple[int, ...] = ()
    """Unit caps to compare (E-ASSEMBLY-CAP); empty means the single ``max_unit_tokens``."""

    @property
    def unit_caps(self) -> tuple[int, ...]:
        return self.caps or (self.max_unit_tokens,)


def spec_from_config(cfg: Record) -> tuple[MeasureSpec, tuple[str, ...]]:
    """Validated specification and roles; test instances need a confirm specification."""
    roles = tuple(cfg["roles"])
    if "test" in roles and not cfg.get("confirm", False):
        raise ValueError("test instances may only be evaluated by a confirm specification")
    a = cfg["assembly"]
    stages = tuple(a["first_stages"])
    readings = tuple(a["readings"])
    if not set(stages) <= set(FIRST_STAGES):
        raise ValueError(f"first stages must be among {FIRST_STAGES}")
    if not set(readings) <= set(READINGS):
        raise ValueError(f"readings must be among {READINGS}")
    if cfg.get("tokenizer", "approx") != "approx":
        raise ValueError("the measurement counts with the approximate tokenizer")
    return (
        MeasureSpec(
            budgets=tuple(int(b) for b in a["budgets"]),
            max_unit_tokens=int(a["max_unit_tokens"]),
            candidates=int(a["candidates"]),
            first_stages=stages,
            dense_variant=str(a["dense_variant"]),
            rrf_k=int(a["rrf_k"]),
            readings=readings,
            caps=tuple(int(c) for c in a.get("max_unit_tokens_grid", ())),
        ),
        roles,
    )


def measure_hash(cfg: Record, prepare_hash: str) -> str:
    """SHA-256 over the evaluation configuration, the cache's hash and the assembly version."""
    from ril.assembly.config import ASSEMBLY_VERSION

    payload = {
        "version": MEASURE_VERSION,
        "assembly": ASSEMBLY_VERSION,
        "config": cfg,
        "prepare": prepare_hash,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- one level


def first_stage_scores(stage: str, bm25: Arr, dense: Arr | None, rrf_k: int) -> Arr:
    """Scores of a first stage over the snapshot (``rrf`` is the rank fusion of BM25 and dense)."""
    if stage == "bm25":
        return np.asarray(bm25, dtype=np.float64)
    if stage == "rrf":
        if dense is None:
            raise ValueError("rrf needs dense scores")
        return rrf_scores([positions(bm25), positions(dense)], rrf_k)
    raise ValueError(f"unknown first stage {stage!r}")


def candidates_of(
    stage: str, scores: Arr, unit_ids: list[str], n_top: int, with_dense: bool
) -> list[Candidate]:
    """The ``n_top`` best units in rank order (ties by lower index, as everywhere else)."""
    order = order_by_score(scores)[:n_top]
    produced = ("bm25", "dense") if stage == "rrf" and with_dense else (stage,)
    return [Candidate(unit_ids[int(i)], float(scores[int(i)]), produced) for i in order]


def measure_level(
    meta: Record,
    level: str,
    arrays: dict[str, Arr],
    dense: Arr | None,
    units: list[UnitText],
    sp: MeasureSpec,
    tok: Tokenizer,
) -> list[Record]:
    """Rows of one (instance, level): first stage x budget x reading."""
    ids = [u.unit_id for u in units]
    snap = snapshot_of(units)
    file_of = {u.unit_id: u.file for u in units}
    golds = {r: [ids[int(i)] for i in arrays[f"gold_{level}_{r}"]] for r in sp.readings}
    rows: list[Record] = []
    for stage in sp.first_stages:
        if stage == "rrf" and dense is None:
            continue
        scores = first_stage_scores(stage, arrays[f"scores_{level}"], dense, sp.rrf_k)
        cands = candidates_of(stage, scores, ids, sp.candidates, stage == "rrf")
        for cap, budget in product(sp.unit_caps, sp.budgets):
            cfg = AssemblyConfig(budget=budget, max_unit_tokens=cap)
            out = assemble(cands, snap, cfg, tok)
            m = out.manifest
            for reading in sp.readings:
                gold_units = golds[reading]
                gold_files = sorted({file_of[u] for u in gold_units})
                g = gold_in_context(m, gold_units, gold_files)
                rows.append(
                    {
                        "instance": meta["instance"],
                        "level": level,
                        "role": meta["role"],
                        "dataset": meta["dataset"],
                        "folder": meta["folder"],
                        "repo_id": meta["repo_id"],
                        "first_stage": stage,
                        "budget": budget,
                        "max_unit_tokens": cap,
                        "reading": reading,
                        "n_gold_units": g.n_units,
                        "units_in": g.units_in,
                        "units_intact": g.units_intact,
                        "n_gold_files": g.n_files,
                        "files_in": g.files_in,
                        "tokens": m.total_tokens,
                        "n_included": len(m.entries),
                        "n_truncated": sum(1 for e in m.entries if e.truncated),
                        "n_skipped_fit": sum(1 for s in m.skipped if s.reason == "does_not_fit"),
                        "context_sha256": m.context_sha256,
                    }
                )
    return rows


# --------------------------------------------------------------------------- the cluster run


def snapshot_units(root: str, repo_id: str) -> list[UnitText]:
    """Units of the checked-out snapshot in cache order (sorted id), class units in header form."""
    from ril.assembly.snapshot import unit_text_of
    from ril.parsing.build import BuildConfig, build_repository

    result = build_repository(
        root, BuildConfig(repo_id=repo_id, class_source="header", with_history=False, seed=0)
    )
    return [unit_text_of(u) for u in sorted(result.parsed.units, key=lambda u: u.id)]


def run_measure(
    cfg: Record,
    cache_dir: str,
    dense_root: str,
    repo_cache: str,
    work_dir: str,
    out_dir: str,
    *,
    only: str | None = None,
    limit: int | None = None,
) -> Record:
    """Measure every cached instance of the roles; one JSON file per instance, resumable."""
    from ril.evaluation.chunk_unit_pilot import checkout_commit

    sp, roles = spec_from_config(cfg)
    tok = ApproxTokenizer()
    counts: Record = {
        "measured": 0,
        "reused": 0,
        "skipped_role": 0,
        "no_dense": 0,
        "failed": 0,
    }
    failures: list[Record] = []
    os.makedirs(os.path.join(out_dir, "instances"), exist_ok=True)
    done = 0
    for name in sorted(os.listdir(cache_dir)):
        if not name.endswith(".npz") or (only and only not in name):
            continue
        arrays, meta = read_cache(os.path.join(cache_dir, name))
        if meta["role"] not in roles:
            counts["skipped_role"] += 1
            continue
        ehash = measure_hash(cfg, str(meta["config_hash"]))
        out = os.path.join(out_dir, "instances", name.replace(".npz", ".json"))
        if os.path.exists(out):
            with open(out, encoding="utf-8") as handle:
                if json.load(handle).get("measure_hash") == ehash:
                    counts["reused"] += 1
                    continue
        if limit is not None and done >= limit:
            break
        dense_path = os.path.join(dense_root, sp.dense_variant, name)
        dense_all: dict[str, Arr] = {}
        if os.path.exists(dense_path):
            with np.load(dense_path, allow_pickle=False) as dz:
                dense_all = {k: dz[k] for k in dz.files if k.startswith("dense_")}
        else:
            counts["no_dense"] += 1
        t0 = time.perf_counter()
        repo_dir = str(meta["repo_id"]).replace("/", "__")
        work = os.path.join(work_dir, repo_dir)
        status = checkout_commit(
            os.path.join(repo_cache, f"{repo_dir}.git"), work, str(meta["base_commit"])
        )
        if status != "ok":
            counts["failed"] += 1
            failures.append({"instance": meta["instance"], "reason": status})
            continue
        units = snapshot_units(work, str(meta["repo_id"]))
        if len(units) != int(meta["units"]):
            counts["failed"] += 1
            failures.append(
                {
                    "instance": meta["instance"],
                    "reason": f"unit_count {len(units)} != cache {meta['units']}",
                }
            )
            continue
        rows: list[Record] = []
        for level in meta["levels"]:
            if not any(len(arrays[f"gold_{level}_{r}"]) for r in sp.readings):
                continue
            d = dense_all.get(f"dense_{level}")
            if d is not None and len(d) != len(units):
                raise ValueError(
                    f"{meta['instance']}: dense has {len(d)} units, cache {len(units)}"
                )
            rows += measure_level(meta, level, arrays, d, units, sp, tok)
        with open(out + ".tmp", "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "measure_hash": ehash,
                    "instance": meta["instance"],
                    "units": len(units),
                    "has_dense": bool(dense_all),
                    "seconds": round(time.perf_counter() - t0, 3),
                    "rows": rows,
                },
                handle,
                sort_keys=True,
            )
        os.replace(out + ".tmp", out)
        counts["measured"] += 1
        done += 1
    counts["failures"] = failures
    return counts
