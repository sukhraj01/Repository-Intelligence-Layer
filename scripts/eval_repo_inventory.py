"""Evaluation-repository inventory (E-EVAL-REPOS): thin command line over the analysis module.

--survey SURVEY.json [--raw data/raw/core_bench] [--out results/tables/eval_repo_inventory.csv]

Deterministic (no randomness; ``--seed`` is accepted and recorded for the log). Chooses nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--survey", required=True)
    p.add_argument("--raw", default=str(ROOT / "data/raw/core_bench"))
    p.add_argument("--dev-config", default=str(ROOT / "configs/experiments/e1_bm25_dev3.yaml"))
    p.add_argument("--held-out", default=str(ROOT / "data/held_out/held_out_repos.json"))
    p.add_argument("--rename-cache", default=str(ROOT / "data/held_out/rename_cache.json"))
    p.add_argument("--out", default=str(ROOT / "results/tables/eval_repo_inventory.csv"))
    p.add_argument("--log", default=None)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--hardware", default="", help="where the survey job ran (for the log)")
    p.add_argument("--commit", default="", help="code commit (for the log)")
    a = p.parse_args(argv)

    import yaml

    from ril.analysis import eval_repo_inventory as inv
    from ril.training.pool_rank_jobs import held_out_predicate
    from ril.training.rename_resolution import alias_map, load_cache

    raw = Path(a.raw)
    ids_all = json.loads((raw / "ids_all.json").read_text(encoding="utf-8"))
    stats = json.loads((raw / "corpus_stats_all.json").read_text(encoding="utf-8"))
    survey = json.loads(Path(a.survey).read_text(encoding="utf-8"))
    corpus_rows = {
        k[: -len("/corpus.jsonl")]: int(v["rows"])
        for k, v in stats.items()
        if k.startswith("LEVEL-2/") and k.endswith("/corpus.jsonl")
    }
    cfg = yaml.safe_load(Path(a.dev_config).read_text(encoding="utf-8"))
    folder_sets: dict[str, str] = {}
    store_folders: dict[str, str] = {}
    for f in cfg["folders"]:
        for lv in f["levels"]:
            folder_sets[f"LEVEL-{lv[-1]}/{f['dataset']}/{f['folder']}"] = str(f["role"])
        if f.get("units"):
            store_folders[str(f["repo"])] = f"LEVEL-2/{f['dataset']}/{f['folder']}"
    rename = Path(a.rename_cache)
    aliases = alias_map(load_cache(rename)) if rename.exists() else {}
    pred = held_out_predicate(a.held_out, a.rename_cache)
    rows = inv.build_rows(
        folder_queries=inv.folder_repo_queries(ids_all),
        corpus_rows=corpus_rows,
        folder_sets=folder_sets,
        store_folders=store_folders,
        survey=survey,
        is_held_out=pred,
        resolve=lambda r: aliases.get(r, r),
    )
    inv.write_csv(rows, a.out)
    points = inv.calibration_points(store_folders, corpus_rows, survey.get("stores", {}))
    loo = inv.leave_one_out(points)
    summary = inv.summarise(rows)
    config = {
        "survey_version": survey.get("survey_version"),
        "thresholds": {
            "python_share_python": inv.PYTHON_SHARE_PYTHON,
            "python_share_mixed": inv.PYTHON_SHARE_MIXED,
            "min_sampled_code_chunks": inv.MIN_SAMPLED_CODE_CHUNKS,
        },
        "encode_rate_assumed": inv.ENCODE_RATE_ASSUMED,
        "encode_rate_measured": inv.ENCODE_RATE_MEASURED,
        "stored_gpu_hours_per_repo": inv.STORED_GPU_HOURS_PER_REPO,
        "dev_config_sha256": _sha(Path(a.dev_config)),
        "input_sha256": {
            "ids_all": _sha(raw / "ids_all.json"),
            "corpus_stats_all": _sha(raw / "corpus_stats_all.json"),
            "survey": _sha(Path(a.survey)),
            "held_out": _sha(Path(a.held_out)),
            "rename_cache": _sha(rename) if rename.exists() else None,
        },
    }
    log = {
        "experiment": "E-EVAL-REPOS",
        "seed": a.seed,
        "commit": a.commit,
        "hardware_of_survey_job": a.hardware,
        "config_hash": hashlib.sha256(
            json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "config": config,
        "summary": summary,
        "calibration_points": points,
        "leave_one_out_relative_error": loo,
        "output_sha256": _sha(Path(a.out)),
    }
    if a.log:
        Path(a.log).write_text(json.dumps(log, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps(summary, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
