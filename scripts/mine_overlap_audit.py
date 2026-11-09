"""Content-overlap audit of the mined corpora: command line over ``ril.data_mining.overlap_audit``.

Subcommands (logic in ``ril/``; E-OVERLAP-AUDIT, decision D105):
  index OUT --probe P ... --texts T ...
                      held-out index (syntax-tree hashes and line hashes) from stored probe sets
                      and unit-text stores; read-only on its inputs
  audit STORE INDEX OUT [--names-file F] [--seed N]
                      one JSON line per directory of a de-duplicated store, the summary at every
                      floor, the hand-reading sample and run.json; never writes into STORE
  merge OUT SHARD_DIR ... --index INDEX --store STORE
                      records of shard audits (audit with --names-file) joined in the order of an
                      unsharded audit; the summary and run.json as audit writes them
  apply OUT [--floor N] [--share S] [--positives non_test|all] [--drop-flagged]
                      lists of directories to drop and to flag under a rule, from OUT/records.jsonl;
                      never deletes or rewrites a store
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.data_mining import full_prep  # noqa: E402
from ril.data_mining import overlap_audit as oa  # noqa: E402 - needs the path set above
from ril.util.machine import hardware  # noqa: E402


def _commit() -> str:
    given = os.environ.get("RIL_COMMIT", "").strip()
    if given and given != "none":
        return given
    done = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, check=False)
    return done.stdout.decode().strip() or "unknown"


def _write_json(path: Path, doc: object) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1, sort_keys=True)
        handle.write("\n")


def _read_records(out: Path) -> list[dict[str, object]]:
    with open(out / "records.jsonl", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def cmd_index(args: argparse.Namespace) -> int:
    texts = [str(p) for d in args.texts for p in sorted(Path(d).glob("*.jsonl"))]
    t0 = time.perf_counter()
    index = oa.build_held_out_index(args.probe, texts)
    manifest = oa.save_index(index, args.out)
    manifest["seconds"] = round(time.perf_counter() - t0, 1)
    manifest["commit"] = _commit()
    manifest["hardware"] = hardware()
    _write_json(Path(args.out) / "manifest.json", manifest)
    sys.stdout.write(
        json.dumps({k: v for k, v in manifest.items() if k not in ("sources", "repositories_ast")})
        + "\n"
    )
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    index = oa.load_index(args.index)
    with open(Path(args.index) / "manifest.json", encoding="utf-8") as handle:
        manifest = json.load(handle)
    names = None
    if args.names_file:
        names = [x.strip() for x in Path(args.names_file).read_text().splitlines() if x.strip()]
    floors = tuple(args.floors)
    primary = oa.Rule(floor=args.floor, corpus_share=args.share)
    t0 = time.perf_counter()
    records = []
    path = out / "records.jsonl"
    with open(path, "w", encoding="utf-8") as handle:
        for rec in oa.audit_store(args.store, index, floors, names):
            records.append(rec)
            handle.write(json.dumps(rec, sort_keys=True) + "\n")
    seconds = time.perf_counter() - t0
    _finish(out, args.index, manifest, records, floors, primary, args.seed, args.store, seconds)
    sys.stdout.write(f"audited {len(records)} directories in {seconds:.1f} s\n")
    return 0


def _finish(
    out: Path,
    index_dir: str,
    manifest: dict[str, object],
    records: list[dict[str, object]],
    floors: tuple[int, ...],
    primary: oa.Rule,
    seed: int,
    store: str,
    seconds: float,
) -> None:
    """Summary, hand-reading sample and run.json of a set of records (shared by audit and merge)."""
    path = out / "records.jsonl"
    summary = oa.summarise(records, floors, primary)
    _write_json(out / "summary.json", summary)
    sample = oa.sample_matches(records, primary, seed=seed)
    with open(out / "match_sample.tsv", "w", encoding="utf-8") as handle:
        cols = ["directory", "mined_repo", "positive_id", "nodes", "heldout_repos"]
        handle.write("\t".join(cols) + "\n")
        for row in sample:
            handle.write("\t".join(str(row[c]) for c in cols) + "\n")
    _write_json(
        out / "run.json",
        {
            "version": oa.AUDIT_VERSION,
            "config_hash": oa.config_hash(manifest, floors, primary),
            "floors": list(floors),
            "primary_floor": primary.floor,
            "corpus_flag_share": primary.corpus_share,
            "seed": seed,
            "commit": _commit(),
            "hardware": hardware(),
            "store": os.path.abspath(store),
            "index_manifest_sha256": hashlib.sha256(
                (Path(index_dir) / "manifest.json").read_bytes()
            ).hexdigest(),
            "directories": len(records),
            "seconds": round(seconds, 1),
            "records_sha256": oa.file_sha256(str(path)),
        },
    )


def cmd_merge(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(Path(args.index) / "manifest.json", encoding="utf-8") as handle:
        manifest = json.load(handle)
    runs = []
    for d in args.shards:
        with open(Path(d) / "run.json", encoding="utf-8") as handle:
            runs.append(json.load(handle))
    if len({r["config_hash"] for r in runs}) != 1:
        raise SystemExit("the shards were audited under different configurations")
    records = full_prep.merge_audit_records(args.shards)
    with open(out / "records.jsonl", "w", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(rec, sort_keys=True) + "\n")
    floors = tuple(runs[0]["floors"])
    primary = oa.Rule(floor=runs[0]["primary_floor"], corpus_share=runs[0]["corpus_flag_share"])
    seconds = sum(float(r["seconds"]) for r in runs)
    _finish(out, args.index, manifest, records, floors, primary, args.seed, args.store, seconds)
    sys.stdout.write(f"merged {len(records)} directories of {len(args.shards)} shards\n")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    out = Path(args.out)
    rule = oa.Rule(args.floor, args.share, args.positives, args.drop_flagged)
    result = oa.apply_rule(_read_records(out), rule)
    tag = f"f{rule.floor}_{rule.positives}{'_dropflagged' if rule.drop_flagged else ''}"
    (out / f"drop_{tag}.txt").write_text(
        "".join(f"{n}\n" for n in result.pop("dropped_directories"))
    )
    (out / f"flag_{tag}.txt").write_text(
        "".join(f"{n}\n" for n in result.pop("flagged_directories"))
    )
    _write_json(out / f"apply_{tag}.json", result)
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("index")
    i.add_argument("out")
    i.add_argument("--probe", nargs="*", default=[], help="ProbeSet JSON files")
    i.add_argument("--texts", nargs="*", default=[], help="directories of unit-text stores")
    i.add_argument(
        "--seed", type=int, default=0, help="unused (deterministic); kept for the contract"
    )
    a = sub.add_parser("audit")
    a.add_argument("store")
    a.add_argument("index")
    a.add_argument("out")
    a.add_argument("--names-file")
    a.add_argument("--floor", type=int, default=oa.FLOOR)
    a.add_argument("--floors", type=int, nargs="+", default=list(oa.SENSITIVITY_FLOORS))
    a.add_argument("--share", type=float, default=oa.CORPUS_FLAG_SHARE)
    a.add_argument("--seed", type=int, default=0, help="order of the hand-reading sample")
    m = sub.add_parser("merge")
    m.add_argument("out")
    m.add_argument("shards", nargs="+")
    m.add_argument("--index", required=True)
    m.add_argument("--store", required=True)
    m.add_argument("--seed", type=int, default=0)
    b = sub.add_parser("apply")
    b.add_argument("out")
    b.add_argument("--floor", type=int, default=oa.FLOOR)
    b.add_argument("--share", type=float, default=oa.CORPUS_FLAG_SHARE)
    b.add_argument("--positives", choices=oa.POSITIVES_READINGS, default="non_test")
    b.add_argument("--drop-flagged", action="store_true")
    b.add_argument(
        "--seed", type=int, default=0, help="unused (deterministic); kept for the contract"
    )
    args = p.parse_args(argv)
    return {"index": cmd_index, "audit": cmd_audit, "merge": cmd_merge, "apply": cmd_apply}[
        args.cmd
    ](args)


if __name__ == "__main__":
    raise SystemExit(main())
