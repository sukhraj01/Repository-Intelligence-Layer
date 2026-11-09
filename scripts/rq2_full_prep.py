"""Full-store preparation: command line over ``ril.data_mining.full_prep`` and ``full_prep_run``.

Subcommands (logic in ``ril/``; E-RQ2-FULL-PREP):
  snapshot STORE DEST --limit N       byte copy of the first N final mined directories and their
                                      repositories' rows into a store at DEST (never overwrites)
  verify-snapshot DEST                re-hash a snapshot against its manifest
  run --store S --out O --scratch T --index I --held-out H --rename-cache R [options]
                                      the chain of stages (select ... check); resumable
  verify-materialised STORE VIEW NAMES_FILE
                                      materialised directories against the store (small files, rows)
  check RUN --held-out H --rename-cache R --readings ...
                                      counts, held-out and drop-list checks over a run's outputs
  cache-memory CACHE --variant plain|shared|equal
                                      resident memory after reading a whole example cache
  link RUN WORK [--reading R] [--allow-trial]
                                      links a run's cache, features, summary into a work dir
  progress STATE STORE                yield from the state log and the store's growth by quarter
  compare A B                         two output directories, byte for byte (timing fields aside)
  pilot-check RUN PILOT_RANKS PILOT_FEATURES --reading R
                                      ranks and features of the directories shared with the pilot
  project RUN STATE --full-state STATE --full-directories N
          [--probe-run RUN2 --trial-store S --full-store S]
                                      the run's stage costs projected to the whole store
Every subcommand prints a JSON document.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.data_mining import full_prep as fp  # noqa: E402 - needs the path set above
from ril.data_mining import full_prep_run as fr  # noqa: E402


def _config_defaults(path: str | None) -> dict[str, object]:
    if not path:
        return {}
    import yaml

    with open(path, encoding="utf-8") as handle:
        return dict(yaml.safe_load(handle))


def cmd_snapshot(a: argparse.Namespace) -> dict[str, object]:
    state = a.state or str(Path(a.store) / "state.jsonl")
    sel = fp.select_closed(state, a.store, a.limit)
    doc = fp.snapshot_store(a.store, state, a.dest, sel)
    return {k: v for k, v in doc.items() if k != "manifest"}


def cmd_run(a: argparse.Namespace) -> dict[str, object]:
    d = _config_defaults(a.config)
    cfg = fr.PrepConfig(
        store=a.store,
        out=a.out,
        scratch=a.scratch,
        index=a.index,
        held_out=a.held_out,
        rename_cache=a.rename_cache,
        python=a.python or sys.executable,
        repo_root=str(Path(__file__).resolve().parents[1]),
        state=a.state,
        limit=a.limit,
        names_file=a.names_file,
        shards=int(a.shards or d.get("shards", 1)),  # type: ignore[call-overload]
        readings=tuple(a.readings or d.get("readings", ("non_test",))),  # type: ignore[call-overload]
        stages=fr.main_stage_list(a.stages),
        k=int(d.get("k", 20)),  # type: ignore[call-overload]
        seed=int(d.get("seed", 0)),  # type: ignore[call-overload]
        drop_list=a.drop_list,
        drop_sha256=a.drop_sha256,
        guard_bytes=int(d.get("guard_bytes", 1 << 30)),  # type: ignore[call-overload]
        cache_bytes_per_directory=int(d.get("cache_bytes_per_directory", 0)),  # type: ignore[call-overload]
        clean_scratch=a.clean_scratch,
        force=a.force,
    )
    fr.Runner(cfg).run()
    return {"out": cfg.out, "stages": list(cfg.stages)}


def cmd_verify_materialised(a: argparse.Namespace) -> dict[str, object]:
    return fp.verify_materialised(a.store, a.view, fp.read_names(a.names))


def cmd_check(a: argparse.Namespace) -> dict[str, object]:
    return fr.check_run(a.run, a.held_out, a.rename_cache, a.readings)


def cmd_cache_memory(a: argparse.Namespace) -> dict[str, object]:
    return fr.cache_memory(a.cache, a.variant)


def cmd_link(a: argparse.Namespace) -> dict[str, object]:
    return fr.link_outputs(a.run, a.work, a.reading, allow_trial=a.allow_trial)


def cmd_progress(a: argparse.Namespace) -> dict[str, object]:
    from ril.data_mining import state_yield

    rows = fp.read_state_rows(a.state)
    cas_root = Path(a.store) / "cas"
    sizes = {
        d.name: sum(f.stat().st_size for f in d.iterdir() if f.is_file())
        for d in cas_root.iterdir()
        if d.is_dir()
    }
    return {
        "state_sha256": fp.sha256_file(a.state),
        "yield": state_yield.yield_report(rows, target_attempted=len(rows)),
        "store_bytes": {
            "cas": sum(sizes.values()),
            "pr": fp.tree_size(str(Path(a.store) / "pr")),
            "listing": fp.tree_size(str(Path(a.store) / "listing")),
        },
        "quarters": fp.quarter_table(rows, sizes),
    }


def cmd_compare(a: argparse.Namespace) -> dict[str, object]:
    return fp.compare_outputs(a.a, a.b)


def cmd_pilot(a: argparse.Namespace) -> dict[str, object]:
    return fr.compare_with_pilot(
        f"{a.run}/{a.reading}/ranks_bm25.jsonl",
        f"{a.run}/{a.reading}/features_mined.csv",
        a.pilot_ranks,
        a.pilot_features,
    )


def cmd_project(a: argparse.Namespace) -> dict[str, object]:
    rows = [
        json.loads(x) for x in Path(f"{a.run}/stages.jsonl").read_text().splitlines() if x.strip()
    ]
    trial_state = fp.read_state_rows(a.state)
    full_state = fp.read_state_rows(a.full_state)
    sel = json.loads(Path(f"{a.run}/selection.json").read_text())
    used = {n for n in fp.read_names(f"{a.run}/names.txt")}
    trial_units = [
        float((r.get("counters") or {}).get("corpus_units", 0))
        for r in trial_state
        if r.get("status") == "mined" and fp.dir_name_of_key(str(r["key"])) in used
    ]
    full_units = fp.corpus_units_of_mined(full_state)
    extra: dict[str, object] = {}
    if a.probe_run:
        probe_names = fp.read_names(f"{a.probe_run}/names_kept.txt")
        probe_set = set(probe_names)
        probe_units = [
            float((r.get("counters") or {}).get("corpus_units", 0))
            for r in full_state
            if r.get("status") == "mined" and fp.dir_name_of_key(str(r["key"])) in probe_set
        ]
        kept = fp.read_names(f"{a.run}/names_kept.txt")
        extra = {
            "probe_rows": [
                json.loads(x)
                for x in Path(f"{a.probe_run}/stages.jsonl").read_text().splitlines()
                if x.strip()
            ],
            "trial_x": (fp.cas_megabytes(a.trial_store, kept), sum(trial_units) / 1e6),
            "probe_x": (fp.cas_megabytes(a.full_store, probe_names), sum(probe_units) / 1e6),
            "full_x": (
                fp.cas_megabytes(a.full_store, fp.select_closed(a.full_state, a.full_store).names),
                sum(full_units) / 1e6,
            ),
        }
    return fp.project_chain(
        rows,
        trial_directories=int(sel["directories"]),
        full_directories=a.full_directories,
        trial_units=trial_units,
        full_units=full_units,
        exclude_steps=tuple(
            f"{sep}{r}{tail}"
            for r in ("pool_aligned", "unrestricted")
            if r != a.reading
            for sep, tail in (("_", ""), ("_", "_again"))
        ),
        **extra,  # type: ignore[arg-type]
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("store")
    s.add_argument("dest")
    s.add_argument("--limit", type=int)
    s.add_argument("--state")
    v = sub.add_parser("verify-snapshot")
    v.add_argument("dest")
    r = sub.add_parser("run")
    for k in ("store", "out", "scratch", "index", "held_out", "rename_cache"):
        r.add_argument(f"--{k.replace('_', '-')}", required=True)
    r.add_argument("--config")
    r.add_argument("--state")
    r.add_argument("--python")
    r.add_argument("--limit", type=int)
    r.add_argument("--names-file", help="a named subset instead of the first N (scale probes)")
    r.add_argument("--shards", type=int)
    r.add_argument("--readings", nargs="+")
    r.add_argument("--stages", default="all")
    r.add_argument("--drop-list")
    r.add_argument("--drop-sha256")
    r.add_argument("--clean-scratch", action="store_true")
    r.add_argument("--force", action="store_true")
    vm = sub.add_parser("verify-materialised")
    vm.add_argument("store")
    vm.add_argument("view")
    vm.add_argument("names")
    ck = sub.add_parser("check")
    ck.add_argument("run")
    ck.add_argument("--held-out", required=True)
    ck.add_argument("--rename-cache", required=True)
    ck.add_argument("--readings", nargs="+", required=True)
    cm = sub.add_parser("cache-memory")
    cm.add_argument("cache")
    cm.add_argument("--variant", choices=["plain", "shared", "equal"], required=True)
    ln = sub.add_parser("link")
    ln.add_argument("run")
    ln.add_argument("work")
    ln.add_argument("--reading", default="non_test")
    ln.add_argument("--allow-trial", action="store_true")
    pg = sub.add_parser("progress")
    pg.add_argument("state")
    pg.add_argument("store")
    c = sub.add_parser("compare")
    c.add_argument("a")
    c.add_argument("b")
    k = sub.add_parser("pilot-check")
    k.add_argument("run")
    k.add_argument("pilot_ranks")
    k.add_argument("pilot_features")
    k.add_argument("--reading", default="non_test")
    j = sub.add_parser("project")
    j.add_argument("run")
    j.add_argument("state", help="state.jsonl of the trial store")
    j.add_argument("--full-state", required=True)
    j.add_argument("--full-directories", type=int, required=True)
    j.add_argument("--reading", default="non_test", help="the reading whose steps are costed")
    j.add_argument("--probe-run", help="a run over a few large repositories (two-factor reading)")
    j.add_argument("--trial-store")
    j.add_argument("--full-store")
    a = p.parse_args(argv)
    if a.cmd == "verify-snapshot":
        out = fp.verify_snapshot(a.dest)
    else:
        out = {
            "verify-materialised": cmd_verify_materialised,
            "check": cmd_check,
            "link": cmd_link,
            "progress": cmd_progress,
            "cache-memory": cmd_cache_memory,
            "snapshot": cmd_snapshot,
            "run": cmd_run,
            "compare": cmd_compare,
            "pilot-check": cmd_pilot,
            "project": cmd_project,
        }[a.cmd](a)
    json.dump(out, sys.stdout, indent=1, sort_keys=True, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
