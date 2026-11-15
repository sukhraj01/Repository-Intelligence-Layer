"""Failure breakdown of graded RQ3 attempts, efficiency numbers, django split (no model call).

  rq3_failure_breakdown.py presence --gold-files G.json --gold-units U.json --ids IDS.txt \\
        --untrained-tar T.tar.gz --trained NAME=ARM:DIR ... --oracle DIR --out presence.csv
      gold presence per (arm, instance) from the stored context manifests at 8,000 tokens
  rq3_failure_breakdown.py analyse --presence presence.csv --out-dir DIR
      every table of E-RQ3-FAILURE-BREAKDOWN from stored rows and the presence file

Thin wrapper; logic in ``ril/analysis/rq3_failure_breakdown.py``. Implements
``docs/experiments/B.md`` E-RQ3-FAILURE-BREAKDOWN.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import tarfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.analysis import rq3_failure_breakdown as fb  # noqa: E402
from ril.analysis.rq3_results import score_matrix  # noqa: E402
from ril.util.log import get_logger  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402

log = get_logger("rq3_failure_breakdown")
D = "results/rq3_driver"
M = "gemini-3.8-flash"
ROWS = {
    "rrf": f"{D}/untrained_runs/{M}/rrf_runs0-2/results.jsonl",
    "raw": f"{D}/trained_runs/{M}/tr_mined_raw_u100_s100_runs0-2/results/results.jsonl",
    "filter": f"{D}/trained_runs/{M}/tr_mined_filter_bm25_u100_s100_runs0-2/results/results.jsonl",
    "sub": f"{D}/trained_runs/{M}/tr_mined_sub_u100_s100_runs0-2/results/results.jsonl",
    "oracle": f"{D}/oracle_runs/{M}/oracle_runs0-1/results/results.jsonl",
    "floor1": f"{D}/floor_runs/{M}/floor_runs0-0/results/results.jsonl",
    "floor2": f"{D}/floor_runs/{M}/floor_stage2_runs0-0/results/results.jsonl",
}
ARM_NAME = {
    "rrf": "rrf",
    "raw": "tr_mined_raw_u100_s100",
    "filter": "tr_mined_filter_bm25_u100_s100",
    "sub": "tr_mined_sub_u100_s100",
    "oracle": "oracle",
    "floor": "floor",
}
REGISTERED = ("rrf", "raw", "filter", "sub")
RUNS = {
    "rrf": (0, 1, 2),
    "raw": (0, 1, 2),
    "filter": (0, 1, 2),
    "sub": (0, 1, 2),
    "oracle": (0, 1),
    "floor": (0,),
}


def _jsonl(path: str) -> list[dict[str, Any]]:
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _ids(path: str) -> list[str]:
    return [x.strip() for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def cmd_presence(a: argparse.Namespace) -> int:
    ids = _ids(a.ids)
    gold_files = json.loads(Path(a.gold_files).read_text(encoding="utf-8"))["instances"]
    gold_units = json.loads(Path(a.gold_units).read_text(encoding="utf-8"))["instances"]
    manifests: dict[str, dict[str, list[dict[str, Any]]]] = {}
    with tarfile.open(a.untrained_tar) as tf:
        got: dict[str, list[dict[str, Any]]] = {}
        for m in tf.getmembers():
            parts = m.name.split("/")
            if len(parts) == 3 and parts[1] == "rrf" and parts[2].endswith(".manifest.json"):
                fh = tf.extractfile(m)
                assert fh is not None
                got[parts[2][: -len(".manifest.json")]] = json.loads(fh.read())["entries"]
        manifests["rrf"] = got
    specs = [("oracle", "oracle", a.oracle)]
    for spec in a.trained:
        name, rest = spec.split("=", 1)
        arm, directory = rest.split(":", 1)
        specs.append((name, arm, directory))
    for name, arm, directory in specs:
        out: dict[str, list[dict[str, Any]]] = {}
        for iid in ids:
            doc = json.loads(gzip.open(Path(directory) / "instances" / f"{iid}.json.gz").read())
            out[iid] = doc["contexts"][f"{arm}|8000"]["manifest"]["entries"]
        manifests[name] = out
    rows: list[dict[str, Any]] = []
    for name, per in manifests.items():
        for iid in ids:
            gf = gold_files[iid]["modified"]
            gpy = [f for f in gf if f.endswith(".py")]
            gu = gold_units[iid]["units"]
            p = fb.presence(per[iid], gf, gu)
            ppy = fb.presence(per[iid], gpy, gu)
            rows.append(
                {
                    "arm": name,
                    "instance_id": iid,
                    "n_gold_files": p["n_gold_files"],
                    "files_in": p["files_in"],
                    "n_gold_files_py": ppy["n_gold_files"],
                    "files_in_py": ppy["files_in"],
                    "n_gold_units": p["n_gold_units"],
                    "units_in": p["units_in"],
                    "context_units": len(per[iid]),
                }
            )
    _write(Path(a.out), rows)
    log.info("wrote %d presence rows for %s", len(rows), sorted(manifests))
    return 0


def _read_presence(path: str) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {}
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(r["arm"], {})[r["instance_id"]] = r
    return out


def cmd_analyse(a: argparse.Namespace) -> int:
    ids = _ids(a.ids)
    heldout = json.loads(Path(a.subset).read_text(encoding="utf-8"))
    repo_of = {str(e["instance_id"]): str(e["repo"]) for e in heldout["executable"]}
    pres = _read_presence(a.presence)
    rows_by = {k: _jsonl(p) for k, p in ROWS.items()}
    floor = rows_by.pop("floor1") + rows_by.pop("floor2")
    rows_by["floor"] = floor
    all_rows = [r for v in rows_by.values() for r in v]
    out_dir = Path(a.out_dir)
    seed = a.seed
    summary: dict[str, Any] = {"seed": seed, "resamples": fb.RESAMPLES, "instances": len(ids)}

    att: dict[str, fb.Table] = {}
    for arm in ("rrf", "raw", "filter", "sub", "oracle"):
        att[arm] = fb.attempts(rows_by[arm], ARM_NAME[arm], ids, pres[arm])
    att["floor"] = fb.attempts(rows_by["floor"], "floor", ids, None)
    flat = [x for arm in att for x in att[arm]]
    for x in flat:
        x["arm"] = next(k for k, v in ARM_NAME.items() if v == x["arm"])
    _write(out_dir / "attempts.csv", flat)
    summary["attempts"] = {k: len(v) for k, v in att.items()}
    summary["exec_errors"] = sum(1 for x in flat if x["outcome_class"] == "exec_error")

    levels = {"file": "file_status", "file_py": "file_status_py", "unit": "unit_status"}
    tab_a: list[dict[str, Any]] = []
    tab_a_floor: list[dict[str, Any]] = []
    tab_b: list[dict[str, Any]] = []
    for arm in ("rrf", "raw", "filter", "sub", "oracle"):
        for lv, col in levels.items():
            for r in fb.failure_split(att[arm], col):
                tab_a.append({"arm": arm, "level": lv} | r)
            for r in fb.conditional_rates(att[arm], col, seed + 11):
                tab_b.append({"arm": arm, "level": lv} | r)
    # outcome classes of every arm (including the floor), no gold status
    for arm in ("rrf", "raw", "filter", "sub", "oracle", "floor"):
        n = len(att[arm])
        row: dict[str, Any] = {"arm": arm, "attempts": n}
        for c in fb.CLASSES:
            row[c] = sum(1 for x in att[arm] if x["outcome_class"] == c)
            row[c + "_share"] = row[c] / n
        tab_a_floor.append(row)
    _write(out_dir / "table_a_failures_by_gold_status.csv", tab_a)
    _write(out_dir / "table_a_outcome_classes.csv", tab_a_floor)
    _write(out_dir / "table_b_resolved_by_gold_status.csv", tab_b)

    tab_c: list[dict[str, Any]] = []
    for arm in ("raw", "filter", "sub"):
        for col in levels.values():
            for kind in ("all", "any"):
                tab_c.append(
                    {"arm": arm, "base": "rrf"} | fb.paired_counts(att["rrf"], att[arm], col, kind)
                )
    _write(out_dir / "table_c_paired_gold_counts.csv", tab_c)

    sc = score_matrix(all_rows, ids, list(ARM_NAME.values())[:4], (0, 1, 2), "exact")
    score = {
        arm: {i: float(sc.values[n, j]) for n, i in enumerate(ids)}
        for j, arm in enumerate(REGISTERED)
    }
    tab_d: list[dict[str, Any]] = []
    for arm in ("raw", "filter", "sub"):
        for col in levels.values():
            tab_d.append(
                {"arm": arm, "base": "rrf"}
                | fb.consistency_check(
                    att["rrf"], att[arm], score["rrf"], score[arm], col, seed + 21
                )
            )
    _write(out_dir / "table_d_consistency_check.csv", tab_d)

    eff = [
        fb.efficiency(rows_by[k], ARM_NAME[k], ids)
        for k in ("rrf", "raw", "filter", "sub", "oracle", "floor")
    ]
    for e, k in zip(eff, ("rrf", "raw", "filter", "sub", "oracle", "floor"), strict=True):
        e["arm"] = k
    _write(out_dir / "efficiency.csv", eff)

    floor_ids = sorted({x["instance_id"] for x in att["floor"]})
    sall = {
        k: score_matrix(all_rows, floor_ids, [ARM_NAME[k]], RUNS[k], "exact").values[:, 0]
        for k in ("rrf", "oracle", "floor")
    }
    gc = fb.gap_closed(sall["rrf"], sall["floor"], sall["oracle"], seed + 31)
    _write(out_dir / "gap_closed.csv", [gc])
    # same ratio with the oracle and untrained arms restricted to the floor's repeat 0 (matched k)
    m0 = {
        k: score_matrix(all_rows, floor_ids, [ARM_NAME[k]], (0,), "exact").values[:, 0]
        for k in ("rrf", "oracle", "floor")
    }
    gc0 = fb.gap_closed(m0["rrf"], m0["floor"], m0["oracle"], seed + 32)
    _write(out_dir / "gap_closed_matched_k.csv", [gc0])

    split = fb.repository_split(
        all_rows,
        ids,
        repo_of,
        ARM_NAME["rrf"],
        [ARM_NAME[k] for k in ("raw", "filter", "sub")],
        (0, 1, 2),
        seed + 41,
    )
    for s in split:
        s["arm"] = next(k for k, v in ARM_NAME.items() if v == s["arm"])
        s["base"] = "rrf"
    _write(out_dir / "django_split.csv", split)

    # counts that qualify the gold labels
    summary["django_instances"] = int(sum(1 for i in ids if repo_of[i] == "django/django"))
    summary["files_without_modified_gold"] = int(
        sum(1 for i in ids if int(pres["rrf"][i]["n_gold_files"]) == 0)
    )
    summary["instances_with_nonpython_gold_file"] = int(
        sum(
            1
            for i in ids
            if int(pres["rrf"][i]["n_gold_files"]) > int(pres["rrf"][i]["n_gold_files_py"])
        )
    )
    summary["without_gold_unit"] = int(
        sum(1 for i in ids if int(pres["rrf"][i]["n_gold_units"]) == 0)
    )
    summary["floor_instances"] = len(floor_ids)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    log.info("summary %s", json.dumps(summary, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("presence")
    p.add_argument("--gold-files", default="results/rq3_oracle/oracle_gold_files.json")
    p.add_argument("--gold-units", default="results/rq3_failure_breakdown/gold_units.json")
    p.add_argument("--ids", default=f"{D}/ids_confirmatory.txt")
    p.add_argument("--untrained-tar", required=True)
    p.add_argument("--trained", nargs="+", required=True, help="NAME=ARMKEY:DIR")
    p.add_argument("--oracle", required=True)
    p.add_argument("--out", default="results/rq3_failure_breakdown/context_gold_presence.csv")
    p.set_defaults(fn=cmd_presence)
    p = sub.add_parser("analyse")
    p.add_argument("--presence", default="results/rq3_failure_breakdown/context_gold_presence.csv")
    p.add_argument("--ids", default=f"{D}/ids_confirmatory.txt")
    p.add_argument("--subset", default="results/rq3_exec/executable_instances_v1.json")
    p.add_argument("--out-dir", default="results/rq3_failure_breakdown")
    p.set_defaults(fn=cmd_analyse)
    for sp in sub.choices.values():
        sp.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    set_seed(args.seed)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
