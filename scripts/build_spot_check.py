"""Draw the second-reader spot-check sheet and its answer key from the single-reader label tables.

Usage: python -I scripts/build_spot_check.py [--config configs/experiments/h_spot_check.yaml]
                                               [--seed N] [--out data/review]
Writes OUT/spot_check.md (claims and source context, no labels) and OUT/spot_check_key.json (the
first reader's labels). A thin wrapper around ``ril.evaluation.spot_check``.
"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ril.evaluation.spot_check import (  # noqa: E402
    draw,
    key_records,
    load_items,
    make_source_reader,
    render_sheet,
)


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 (fixed https host)
        data: bytes = resp.read()
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=ROOT / "configs/experiments/h_spot_check.yaml")
    ap.add_argument("--seed", type=int, default=None, help="overrides the config's seed")
    ap.add_argument("--out", type=Path, default=ROOT / "data/review")
    args = ap.parse_args()
    raw = args.config.read_bytes()
    cfg = yaml.safe_load(raw)
    seed = cfg["seed"] if args.seed is None else args.seed
    for label, spec in cfg["repos"].items():
        if "local" in spec:
            head = subprocess.run(
                ["git", "-C", str(ROOT / spec["local"]), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            if head != spec["commit"]:
                print(f"error: {label} checkout is at {head}, config says {spec['commit']}")
                return 1
    pools = load_items(ROOT / "results/tables")
    check = draw(pools, cfg["quotas"], seed)
    read = make_source_reader(cfg["repos"], ROOT, args.out / "src_cache", fetch=_fetch)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "spot_check.md").write_text(
        render_sheet(check, read, cfg["radius"]), encoding="utf-8"
    )
    key = key_records(check)
    key["config_sha256"] = hashlib.sha256(raw).hexdigest()
    (args.out / "spot_check_key.json").write_text(
        json.dumps(key, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{len(check.items)} items, seed {seed}, written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
