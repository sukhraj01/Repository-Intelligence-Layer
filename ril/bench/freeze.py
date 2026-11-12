"""Configuration freeze records, one per consumer, and the check that none of them changed.

Implements ``docs/ROADMAP.md`` "Before week 6 - freeze" and ``configs/frozen/README.md``
(E-FREEZE-AND-LATENCY). The retrieval settings differ between consumers (the RRF ``k`` is 60 in the
RQ2 evaluation and 100 in the RQ3 contexts and the dev selection; the truncation and the budgets
differ too), so each consumer's setting is frozen as its own named record and nothing is unified:
unifying would invalidate the registered RQ2 hashes and the contexts already built. A record is
*read* from the consumer's stored configuration files, never typed, and holds:

* the sources (path and SHA-256 of every stored configuration it was read from) and the hash the
  consumer itself stores or computes for its configuration (``training.config_io.config_hash`` for
  the RQ2 runs, the file hash stored beside the RQ3 contexts, the hash in the ladder's run record);
* the configuration as the consumer uses it, the encoder and BM25 variants with their versions, the
  resolver version, the assembly rule and the budgets, whether any expansion or prior is on;
* the measured sensitivity of the setting that differs between consumers (read from the stored dev
  table, never recomputed here);
* a latency snapshot: the stored rows (host, commit, configuration hash, p50, p95, p99) of the
  stages of the consumer's path, copied in, with the stages that have no row listed.

``write_records`` writes ``configs/frozen/*.json`` and ``MANIFEST.json`` (SHA-256 of every record)
and, for the setting that no final run consumes, ``configs/records/*.json`` (provenance, outside the
manifest and outside ``verify``; ruling of 2026-11-12);
``verify`` returns the problems found: a record that differs from the manifest, a consumer file that
no longer hashes to what the record says, a latency row that is no longer in the log. A consumer
whose stored configuration cannot be located is listed in the record (``not_found``), not guessed.
Nothing here changes a consumer's code or configuration.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import os
import subprocess
from typing import Any

import yaml

from ril.analysis.rq1_ladder import pick_latency
from ril.assembly.config import ASSEMBLY_VERSION, DEFAULT_MAX_UNIT_TOKENS
from ril.parsing.call_graph import RESOLVER_NAME, RESOLVER_VERSION
from ril.parsing.code_unit import CODEUNIT_SCHEMA_VERSION
from ril.parsing.repository_parser import PARSER_VERSION
from ril.retrieval.bm25_index import STOPWORDS_EN, BM25Params
from ril.retrieval.dense_encoder import ENCODERS
from ril.training.config_io import TRAINING_VERSION, config_hash, load_train_config
from ril.training.rq2_plan import cell_table_digest

RECORD_VERSION = "freeze-record/v1"
FROZEN_DIR = "configs/frozen"
RECORDS_DIR = "configs/records"
MANIFEST = "MANIFEST.json"
LATENCY_LOG = "results/latency/latency_log.csv"
SENSITIVITY_TABLE = "results/tables/x2_first_dev.csv"
RQ2_DIR = "configs/experiments/rq2_final"
LAUNCH_COMMIT = "c2a8db6"
LAUNCH_CELL_TABLE_SHA256 = "f441e76574a90bf199ee5d634a64fd41904a76505dad044e33f06ce9e1f16f90"
RQ3_BUILD_MANIFEST_SHA256 = "9784f5ae1ca4f5bf014afb1691a0f94ccbc0f0d183fbc198f5f5875ef2fb0fb7"
"""Facts the ruling of 2026-11-12 cites: the commit the RQ2 runs were submitted from, the digest of
the registered cell table, and the SHA-256 of the manifest of the built RQ3 contexts."""
RQ3_CONFIG = "configs/experiments/rq3_contexts_v1.yaml"
RQ3_HASH_FILE = "results/rq3_contexts/config_hash_63792.txt"
LADDER_CONFIG = "configs/experiments/rq1_ladder_cre.yaml"
LADDER_RECORD = "results/logs/rq1_ladder_run_files_2026-11-09.json"
Record = dict[str, Any]

# stage -> query set, host prefix, per consumer; the dense query encoder is measured per truncation
_STAGE_ROWS: dict[str, tuple[str, str]] = {
    "bm25": ("retrieval-{scale}-v1", "Sukhraj.local"),
    "rrf_fusion": ("fusion-{scale}-v1", "Sukhraj.local"),
    "same_file_expansion": ("fusion-{scale}-v1", "Sukhraj.local"),
    "recency_prior": ("fusion-{scale}-v1", "Sukhraj.local"),
    "assemble": ("assembly-{scale}-b8000-v1", "Sukhraj.local"),
}
_DENSE_ROWS = {
    "django": "dsearch-coderankembed-django-torch-v1",
    "flask": "dsearch-coderankembed-dev-torch-v1",
}
"""Dense search rows: the django scale (35,860 units) and the dev median snapshot (5,195 units),
the smaller scale of the ladder's latency table; BM25, fusion and assembly rows at that scale are
flask (974 units)."""
_SCALES = {"django": 35860, "flask": 974}


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _read_yaml(path: str) -> Record:
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected a mapping")
    return doc


def _source(root: str, rel: str) -> Record:
    return {"path": rel, "sha256": sha256_file(os.path.join(root, rel))}


def _git_head(root: str) -> str:
    done = subprocess.run(
        ["git", "-C", root, "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    return done.stdout.strip() or "unknown"


# --------------------------------------------------------------------------- shared parts


def encoder_record(name: str, max_tokens: int) -> Record:
    spec = ENCODERS[name]
    return {
        "name": spec.name,
        "model_name": spec.model_id.partition("/")[2],
        "revision": spec.revision,
        "max_tokens": max_tokens,
        "query_template": spec.query_template,
    }


def bm25_record() -> Record:
    p = BM25Params()
    return {
        "variant": "reference form (Lucene-variant scoring, stemmed, stop list)",
        "k1": p.k1,
        "b": p.b,
        "stop_words": len(STOPWORDS_EN),
        "provisional": ["ADR-004"],
        "unit_level_variants": "none frozen (D119 dev run: E-FREEZE-AND-LATENCY)",
    }


def parsing_record() -> Record:
    return {
        "resolver": f"{RESOLVER_NAME}/{RESOLVER_VERSION}",
        "resolver_note": "D117: becomes v0.1 at the next cache rebuild, none forced",
        "parser": PARSER_VERSION,
        "codeunit_schema": CODEUNIT_SCHEMA_VERSION,
        "unit_granularity": "function, method, class, one residual module unit per file (D6)",
    }


def _sensitivity(root: str) -> Record:
    """Dev values of RRF k 60 and 100 at 512 and 1,024 tokens, read from the stored table."""
    rows: list[Record] = []
    with open(os.path.join(root, SENSITIVITY_TABLE), encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out: dict[str, Record] = {}
    for tokens in (512, 1024):
        for k in (60, 100):
            name = f"rrf|coderankembed__t{tokens}|k{k}"
            cell: Record = {}
            for level, metric in (("L2", "ndcg10"), ("L3", "recall100")):
                hit = [
                    r
                    for r in rows
                    if r["group"] == "dev"
                    and r["level"] == level
                    and r["reading"] == "units_all_nomod"
                    and r["metric"] == metric
                    and r["name"] == name
                    and r["against"] == "bm25"
                ]
                if not hit:
                    raise ValueError(f"{SENSITIVITY_TABLE}: no dev row for {name} {level} {metric}")
                cell[f"{level}_{metric}"] = float(hit[0]["value"])
                cell[f"{level}_queries"] = int(hit[0]["queries"])
            out[f"t{tokens}_k{k}"] = cell
    spread = max(
        abs(out[f"t{t}_k60"][m] - out[f"t{t}_k100"][m])
        for t in (512, 1024)
        for m in ("L2_ndcg10", "L3_recall100")
    )
    return {
        "source": _source(root, SENSITIVITY_TABLE),
        "reading": "dev, units_all_nomod, CodeRankEmbed, RRF with BM25 (E-DENSE-FUSION)",
        "values": out,
        "largest_k60_vs_k100_difference_points": round(spread, 4),
    }


def latency_snapshot(root: str, stages: list[str], query_encode: tuple[str, str]) -> Record:
    """Stored latency rows of ``stages`` at both index sizes; missing rows are listed.

    ``query_encode`` is (query-set id, host prefix) of the encoder row for the truncation.
    """
    with open(os.path.join(root, LATENCY_LOG), encoding="utf-8", newline="") as fh:
        log = list(csv.DictReader(fh))
    rows: list[Record] = []
    missing: list[Record] = []
    for scale, units in _SCALES.items():
        for stage in ["query_encode", *stages]:
            if stage == "query_encode":
                qset, host = query_encode
            elif stage == "dense_search":
                qset, host = _DENSE_ROWS[scale], "gnode044"
            else:
                qset, host = _STAGE_ROWS[stage]
                qset = qset.format(scale=scale)
            hit = pick_latency(log, {"stage": stage, "query_set_id": qset, "host": host})
            if hit is None:
                missing.append({"scale": scale, "stage": stage, "query_set_id": qset, "host": host})
                continue
            rows.append({"scale": scale, "index_units": units, **hit})
    return {
        "source": LATENCY_LOG,
        "kind": "stored rows copied in; stages are timed on different hosts and are not additive",
        "rows": rows,
        "not_measured": missing,
    }


# --------------------------------------------------------------------------- consumers


def build_rq2_evaluation(root: str) -> Record:
    """The RQ2 evaluation: dense alone and RRF(BM25, dense) at k 60, dev role, 512 tokens."""
    not_found: list[str] = []
    tmpl_paths = {
        "injected": f"{RQ2_DIR}/_template_injected.yaml",
        "mined": f"{RQ2_DIR}/_template_mined.yaml",
    }
    for name, rel in list(tmpl_paths.items()):
        if not os.path.exists(os.path.join(root, rel)):
            not_found.append(rel)
            del tmpl_paths[name]
    if not tmpl_paths:
        return {"consumer": "rq2_evaluation", "not_found": not_found}
    templates = {n: _read_yaml(os.path.join(root, rel)) for n, rel in tmpl_paths.items()}
    runs = sorted(
        p
        for p in glob.glob(os.path.join(root, RQ2_DIR, "*_u100_s*.yaml"))
        if not os.path.basename(p).startswith("_")
    )
    hashes: dict[str, str] = {}
    evaluations: list[str] = []
    for p in runs:
        cfg = load_train_config(p)
        hashes[os.path.relpath(p, root)] = config_hash(cfg)
        evaluations.append(json.dumps(cfg["evaluation"], sort_keys=True))
    ref = templates.get("injected") or next(iter(templates.values()))
    ev = ref["evaluation"]
    held = {k: ref[k] for k in ("model", "batch", "negatives", "loss", "optimizer", "budget")}
    max_tokens = int(ref["model"]["max_tokens"])
    return {
        "consumer": "rq2_evaluation",
        "record_version": RECORD_VERSION,
        "description": (
            "Checkpoint evaluation of the RQ2 final runs (ril.evaluation.checkpoint_eval on the "
            "X2 machinery): dense alone and RRF(BM25, dense), dev role, flat exact index, no "
            "expansion and no recency prior, query-time encoding at the training truncation."
        ),
        "sources": [_source(root, rel) for rel in tmpl_paths.values()],
        "consumer_hashes": {
            "kind": "training.config_io.config_hash of each rendered run configuration",
            "training_version": TRAINING_VERSION,
            "runs": hashes,
            "cell_table_digest": cell_table_digest(),
            "evaluation_section_identical_in_all_runs": len(set(evaluations)) == 1,
        },
        "configuration": {
            "evaluation": ev,
            "rrf_k": ev["rrf_k"],
            "roles": ev["roles"],
            "held_identical_training_sections": held,
            "index": "flat exact (no approximate index)",
            "fusion": "reciprocal rank fusion over whole rankings (rank-based, not a score sum)",
            "expansion": "off",
            "recency_prior": "off",
        },
        "encoder": encoder_record(str(ref["model"]["encoder"]), max_tokens),
        "bm25": bm25_record(),
        "parsing": parsing_record(),
        "assembly": "not part of the RQ2 evaluation (retrieval metrics only)",
        "budgets": "none (rank metrics: nDCG@10, Recall@100)",
        "provisional_in_consumer": list(ref.get("provisional", [])),
        "sensitivity": _sensitivity(root),
        "latency": latency_snapshot(
            root,
            ["bm25", "dense_search", "rrf_fusion"],
            ("qenc-coderankembed-t512-v1", "gnode044"),
        ),
        "not_found": not_found,
    }


def build_rq3_contexts(root: str) -> Record:
    """The RQ3 contexts: stored scores of the untrained encoder at 512 tokens, RRF k 100."""
    not_found = [
        p for p in (RQ3_CONFIG, RQ3_HASH_FILE) if not os.path.exists(os.path.join(root, p))
    ]
    if not_found:
        return {"consumer": "rq3_contexts", "not_found": not_found}
    cfg = _read_yaml(os.path.join(root, RQ3_CONFIG))
    stored = open(os.path.join(root, RQ3_HASH_FILE), encoding="utf-8").read().split()[0]
    asm = cfg["assembly"]
    return {
        "consumer": "rq3_contexts",
        "record_version": RECORD_VERSION,
        "description": (
            "Retrieved contexts of the executable instances (E-RQ3-CONTEXTS, D108): BM25, the "
            "untrained base encoder alone and RRF over both, assembled by the stage of ADR-014."
        ),
        "sources": [_source(root, RQ3_CONFIG), _source(root, RQ3_HASH_FILE)],
        "consumer_hashes": {
            "kind": "SHA-256 of the configuration file, stored beside the built contexts",
            "stored": stored,
            "equals_file_hash": stored == sha256_file(os.path.join(root, RQ3_CONFIG)),
        },
        "configuration": {
            "arms": cfg["arms"],
            "dense_key": cfg["dense_key"],
            "rrf_k": asm["rrf_k"],
            "candidates": asm["candidates"],
            "query_level": asm["query_level"],
            "index": "flat exact (stored scores of every unit of the snapshot)",
            "fusion": "reciprocal rank fusion over whole rankings (rank-based, not a score sum)",
            "expansion": "off",
            "recency_prior": "off",
        },
        "encoder": encoder_record("coderankembed", 512),
        "bm25": bm25_record(),
        "parsing": parsing_record(),
        "assembly": {
            "version": ASSEMBLY_VERSION,
            "rule": "first fit in rank order, blocks ordered by file and line (D102, ADR-014)",
            "max_unit_tokens": asm["max_unit_tokens"],
            "max_unit_tokens_default_in_code": DEFAULT_MAX_UNIT_TOKENS,
            "tokenizer": asm["tokenizer"],
            "class_units": "header form (D103); the index keeps the full form (D25)",
        },
        "budgets": asm["budgets"],
        "provisional_in_consumer": ["D102", "D103", "ADR-006", "ADR-014 (Proposed)"],
        "sensitivity": _sensitivity(root),
        "latency": latency_snapshot(
            root,
            ["bm25", "dense_search", "rrf_fusion", "assemble"],
            ("qenc-coderankembed-t512-v1", "gnode044"),
        ),
        "not_found": [],
    }


def build_dev_selection(root: str) -> Record:
    """The dev selection and the RQ1 ladder: CodeRankEmbed at 1,024 tokens, RRF k 100."""
    not_found = [
        p for p in (LADDER_CONFIG, LADDER_RECORD) if not os.path.exists(os.path.join(root, p))
    ]
    if not_found:
        return {"consumer": "rq1_dev_selection", "not_found": not_found}
    cfg = _read_yaml(os.path.join(root, LADDER_CONFIG))
    run = json.load(open(os.path.join(root, LADDER_RECORD), encoding="utf-8"))
    stored = str(run["configs"]["cre"])
    g = cfg["graph"]
    return {
        "consumer": "rq1_dev_selection",
        "record_version": RECORD_VERSION,
        "description": (
            "Dev selection of E-DENSE-FUSION and the RQ1 ladder on the development set "
            "(E-RQ1-LADDER): CodeRankEmbed at 1,024 tokens, RRF k 100. Expansion and the recency "
            "prior are ladder rungs read against controls, not part of the retrieval setting."
        ),
        "sources": [_source(root, LADDER_CONFIG), _source(root, LADDER_RECORD)],
        "consumer_hashes": {
            "kind": "SHA-256 of the configuration file, stored in the ladder's run record",
            "stored": stored,
            "equals_file_hash": stored == sha256_file(os.path.join(root, LADDER_CONFIG)),
            "evaluation_hashes": run["cre"]["eval_hashes"],
            "cache_hashes": run["cre"]["cache_hashes"],
        },
        "configuration": {
            "rrf_k": g["k"],
            "first_stage_variant": g["variant"],
            "index": "flat exact (stored scores of every unit of the snapshot)",
            "fusion": "reciprocal rank fusion over whole rankings (rank-based, not a score sum)",
            "expansion": "off in every frozen setting; same-file expansion by score stays an "
            "unfrozen candidate (Q30)",
            "recency_prior": "off in every frozen setting",
            "ladder_cell": {k: g[k] for k in ("seeds", "gamma", "hops", "weight", "cap")},
        },
        "encoder": encoder_record("coderankembed", 1024),
        "bm25": bm25_record(),
        "parsing": parsing_record(),
        "assembly": "not part of the ladder (retrieval metrics only)",
        "budgets": "none (rank metrics)",
        "provisional_in_consumer": ["ADR-004", "ADR-006"],
        "sensitivity": _sensitivity(root),
        "latency": latency_snapshot(
            root,
            ["bm25", "dense_search", "rrf_fusion"],
            ("qenc-coderankembed-t1024-v1", "gnode044"),
        ),
        "not_found": [],
    }


BUILDERS = {"rq2_evaluation": build_rq2_evaluation, "rq3_contexts": build_rq3_contexts}
"""Frozen records: a registered or built artefact depends on each of them."""
RECORD_BUILDERS = {"rq1_dev_selection": build_dev_selection}
"""Provenance records (``configs/records/``): settings recorded, no final run consumes them."""


# --------------------------------------------------------------------------- write and verify


def _dump(path: str, doc: Record) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")


def _cross_sensitivity(docs: dict[str, Record]) -> None:
    """Add to each record the stored dev difference between its setting and the other consumers'.

    The setting of a consumer is (truncation, RRF k) as the record states them; the values are the
    stored ones of the sensitivity table, so the numbers stay next to the setting they qualify.
    """
    settings = {
        n: (int(d["encoder"]["max_tokens"]), int(d["configuration"]["rrf_k"]))
        for n, d in docs.items()
        if "encoder" in d
    }
    for name, doc in docs.items():
        if name not in settings:
            continue
        vals = doc["sensitivity"]["values"]
        mine = vals[f"t{settings[name][0]}_k{settings[name][1]}"]
        pairs = []
        for other, (tok, k) in sorted(settings.items()):
            if other == name:
                continue
            theirs = vals[f"t{tok}_k{k}"]
            pairs.append(
                {
                    "other_consumer": other,
                    "other_setting": {"max_tokens": tok, "rrf_k": k},
                    "L2_ndcg10_points": round(theirs["L2_ndcg10"] - mine["L2_ndcg10"], 4),
                    "L3_recall100_points": round(theirs["L3_recall100"] - mine["L3_recall100"], 4),
                }
            )
        doc["sensitivity"]["own_setting"] = {
            "max_tokens": settings[name][0],
            "rrf_k": settings[name][1],
        }
        doc["sensitivity"]["difference_to_other_consumers"] = pairs
        doc["sensitivity"]["largest_difference_to_other_consumers_points"] = max(
            (max(abs(p["L2_ndcg10_points"]), abs(p["L3_recall100_points"])) for p in pairs),
            default=0.0,
        )


def apply_status(name: str, doc: Record) -> None:
    """Replace the consumer's provisional labels by the status the ruling of 2026-11-12 gives.

    ``rq2_evaluation``: frozen at launch (the 45 runs were submitted on it). ``rq3_contexts``:
    frozen (the contexts of the executable subset are built on it). ``rq1_dev_selection``: a
    record kept for provenance, not a frozen configuration. The ADR and decision labels the
    consumer carried before are kept under a name that does not say "provisional".
    """
    labels = doc.pop("provisional_in_consumer", [])
    doc["labels_in_consumer_before_ruling"] = labels
    if isinstance(doc.get("bm25"), dict) and "provisional" in doc["bm25"]:
        doc["bm25"]["labels_before_ruling"] = doc["bm25"].pop("provisional")
    if name == "rq2_evaluation":
        doc["status"] = {
            "state": "frozen at launch",
            "launch_commit": LAUNCH_COMMIT,
            "cell_table_sha256": LAUNCH_CELL_TABLE_SHA256,
            "runs": 45,
            "ruling": "2026-11-12; a change needs a new decision and invalidates the run hashes",
        }
    elif name == "rq3_contexts":
        doc["status"] = {
            "state": "frozen",
            "built_contexts": "E-RQ3-CONTEXTS (job 63792, 377 instances, 2,262 contexts)",
            "configuration_sha256": doc["consumer_hashes"]["stored"],
            "context_manifest_sha256": RQ3_BUILD_MANIFEST_SHA256,
            "ruling": "2026-11-12; a change after this date invalidates the RQ3 pilot and the "
            "built contexts and needs a new decision",
        }
    else:
        doc["status"] = {
            "state": "recorded for provenance, not a frozen configuration",
            "reason": "the setting the RQ1 development selected on dev; no final run consumes it",
            "ruling": "2026-11-12",
        }


def write_records(root: str, date: str) -> list[str]:
    """Write every record and the manifest; refuses to overwrite a record that already exists."""
    out_dir = os.path.join(root, FROZEN_DIR)
    os.makedirs(out_dir, exist_ok=True)
    commit = _git_head(root)
    written: list[str] = []
    manifest: Record = {"record_version": RECORD_VERSION, "date": date, "code_commit": commit}
    files: dict[str, str] = {}
    docs = {name: build(root) for name, build in {**BUILDERS, **RECORD_BUILDERS}.items()}
    _cross_sensitivity(docs)
    rec_dir = os.path.join(root, RECORDS_DIR)
    os.makedirs(rec_dir, exist_ok=True)
    for name, doc in docs.items():
        frozen = name in BUILDERS
        path = os.path.join(out_dir if frozen else rec_dir, f"{name}.json")
        if os.path.exists(path):
            raise FileExistsError(f"{path} exists; a record is never rewritten")
        apply_status(name, doc)
        doc["frozen_on" if frozen else "recorded_on"] = date
        doc["code_commit"] = commit
        _dump(path, doc)
        if frozen:
            files[f"{name}.json"] = sha256_file(path)
        written.append(path)
    manifest["files"] = files
    mpath = os.path.join(out_dir, MANIFEST)
    if os.path.exists(mpath):
        raise FileExistsError(f"{mpath} exists; a frozen record is never rewritten")
    _dump(mpath, manifest)
    written.append(mpath)
    return written


def verify(root: str) -> list[str]:
    """Problems found; an empty list means every record and every consumer file is as frozen."""
    problems: list[str] = []
    out_dir = os.path.join(root, FROZEN_DIR)
    mpath = os.path.join(out_dir, MANIFEST)
    if not os.path.exists(mpath):
        return [f"{FROZEN_DIR}/{MANIFEST} is missing"]
    manifest = json.load(open(mpath, encoding="utf-8"))
    on_disk = {os.path.basename(p) for p in glob.glob(os.path.join(out_dir, "*.json"))} - {MANIFEST}
    for extra in sorted(on_disk - set(manifest["files"])):
        problems.append(f"{extra} is in {FROZEN_DIR} but not in the manifest")
    for name, want in sorted(manifest["files"].items()):
        path = os.path.join(out_dir, name)
        if not os.path.exists(path):
            problems.append(f"{name} is in the manifest but missing")
            continue
        if sha256_file(path) != want:
            problems.append(f"{name} changed after the freeze")
            continue
        doc = json.load(open(path, encoding="utf-8"))
        for src in doc.get("sources", []):
            sp = os.path.join(root, src["path"])
            if not os.path.exists(sp):
                problems.append(f"{name}: source {src['path']} is missing")
            elif sha256_file(sp) != src["sha256"]:
                problems.append(f"{name}: source {src['path']} changed since the freeze")
        problems += _verify_latency(root, name, doc)
        problems += _verify_run_hashes(root, name, doc)
    return problems


def _verify_latency(root: str, name: str, doc: Record) -> list[str]:
    lat = doc.get("latency")
    if not lat:
        return []
    with open(os.path.join(root, LATENCY_LOG), encoding="utf-8", newline="") as fh:
        log = list(csv.DictReader(fh))
    out = []
    for row in lat["rows"]:
        found = any(
            r["timestamp_utc"] == row["timestamp_utc"]
            and r["stage"] == row["stage"]
            and r["query_set_id"] == row["query_set_id"]
            and r["host"] == row["host"]
            and r["cache_state"] == row["cache_state"]
            and float(r["p50_ms"]) == float(row["p50_ms"])
            for r in log
        )
        if not found:
            out.append(
                f"{name}: latency row {row['stage']} {row['query_set_id']} is not in the log"
            )
    return out


def _verify_run_hashes(root: str, name: str, doc: Record) -> list[str]:
    hashes = doc.get("consumer_hashes", {})
    out: list[str] = []
    for rel, want in hashes.get("runs", {}).items():
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            out.append(f"{name}: run configuration {rel} is missing")
        elif config_hash(load_train_config(path)) != want:
            out.append(f"{name}: run configuration {rel} no longer hashes to the recorded value")
    if "cell_table_digest" in hashes and hashes["cell_table_digest"] != cell_table_digest():
        out.append(f"{name}: the RQ2 cell table digest changed")
    return out
