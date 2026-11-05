"""Write the build inputs of the D100 evaluation repositories.

--selection configs/experiments/eval_repos_v1.json  [--use-reserve REPO ...]
Writes configs/experiments/eval_repos_v1_build.yaml and a base-commit table (default
data/processed/eval_repos_v1_meta.json, untracked). ``--use-reserve`` replaces a failed primary
by the next unused reserve repository, in the recorded order (only after a technical failure
recorded before any result is read; the replacement is printed).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--selection", default=str(ROOT / "configs/experiments/eval_repos_v1.json"))
    p.add_argument("--inventory", default=str(ROOT / "results/tables/eval_repo_inventory.csv"))
    p.add_argument("--template", default=str(ROOT / "configs/experiments/e1_bm25_dev3.yaml"))
    p.add_argument("--ids-all", default=str(ROOT / "data/raw/core_bench/ids_all.json"))
    p.add_argument("--meta-dir", default=str(ROOT / "data/raw/hf_meta/dev"))
    p.add_argument(
        "--out-config", default=str(ROOT / "configs/experiments/eval_repos_v1_build.yaml")
    )
    p.add_argument("--out-meta", default=str(ROOT / "data/processed/eval_repos_v1_meta.json"))
    p.add_argument("--replace", action="append", default=[], help="failed primary repository")
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args(argv)

    import pyarrow.parquet as pq
    import yaml

    from ril.evaluation import eval_build_inputs as ebi

    sel = json.loads(Path(a.selection).read_text(encoding="utf-8"))
    repos = [e["repository"] for e in sel["evaluation"]]
    reserve = [e["repository"] for e in sel["reserve"]]
    for failed in a.replace:
        replacement = reserve.pop(0)
        repos[repos.index(failed)] = replacement
        sys.stdout.write(f"replaced {failed} by {replacement}\n")
    folders = ebi.folders_of(a.inventory, repos)
    template = yaml.safe_load(Path(a.template).read_text(encoding="utf-8"))
    cfg = ebi.build_config(template, folders)
    Path(a.out_config).write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    ids_all = json.loads(Path(a.ids_all).read_text(encoding="utf-8"))
    tables = {
        ds: [
            row
            for stem in stems
            for row in pq.read_table(
                Path(a.meta_dir) / f"{stem}.parquet",
                columns=["instance_id", "base_commit", "patch"],
            ).to_pylist()
        ]
        for ds, stems in ebi.PARQUET_OF_DATASET.items()
    }
    meta, missing = ebi.build_meta(folders, ids_all, tables)
    out = Path(a.out_meta)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(meta), encoding="utf-8")
    sys.stdout.write(
        json.dumps({"repositories": repos, "instances": len(meta), "missing": missing}) + "\n"
    )
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
