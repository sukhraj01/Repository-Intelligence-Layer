"""PR-mined set: thin command line over ``ril.data_mining.jobs`` (E-MINE-PILOT).

Subcommands (logic in ``ril/``):
  check                       token presence (never the value) and the API rate-limit probe
  run CONFIG OUT --listing L --held-out H [--rename-cache R] --work W [--repos N] [--stop-after N]
                              list, select, mine (resumable); refuses to start without GITHUB_TOKEN
  pack OUT ZIP                zip + member listing in the layout the pool reader streams
  rank-sample OUT SAMPLE      selection file covering every mined directory (for the rank tooling)
  agreement OUT JSON --listing L
                              mined positives against the pool's, for pull requests in both
  scale SUMMARY COSTS --listing-seconds S --free-bytes B --targets REPOS:PRS ...
                              extrapolated API calls, wall time and disk from a measured pilot
  report OUT MD               tables of a finished run (summary.json) and its measured unit costs
  rank-prepare OUT WORK       zip, listing and selection file of the run for the rank tooling
  rank-bm25 WORK RANKS        BM25 ranks (CPU);  rank-dense WORK RANKS LOG --teachers T ...  (GPU)
  rank-tables WORK JSON --ranks R ... --yield-per-pr Y   shares with no positive in the top K
  rank-reproduce OLD --new R ...   exact comparison of rank rows with an earlier rank file
  handcheck OUT MD --n N --seed S
                              markdown for a human to read: issue title, hunks, mined positives
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.data_mining.readings import NON_TEST, READINGS, UNRESTRICTED  # noqa: E402 - needs the path set above


def _commit() -> str:
    given = os.environ.get("RIL_COMMIT", "").strip()
    if given and given != "none":
        return given
    done = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, check=False)
    return done.stdout.decode().strip() or "unknown"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    r = sub.add_parser("run")
    r.add_argument("config")
    r.add_argument("out")
    r.add_argument("--listing", required=True)
    r.add_argument("--held-out", required=True)
    r.add_argument("--rename-cache")
    r.add_argument("--work", required=True)
    r.add_argument("--repos", type=int)
    r.add_argument("--stop-after", type=int)
    r.add_argument("--list-only", action="store_true", help="write the listing files only")
    r.add_argument("--shard", type=int, nargs=2, metavar=("I", "N"), help="every N-th repository")
    r.add_argument("--etag-cache", action="store_true", help="keep conditional-request responses")
    r.add_argument(
        "--lookahead", type=int, default=1, help="base commits fetched ahead (speed only)"
    )
    r.add_argument("--created", required=True, help="date of the first session, YYYY-MM-DD")
    r.add_argument(
        "--store-layout",
        choices=("directories", "dedup"),
        default="directories",
        help="dedup: rows once per repository plus a manifest per pull request (D93)",
    )
    r.add_argument("--durable", help="durable copy of the run root (restored from, pushed to)")
    r.add_argument("--sync-every", type=int, default=25, help="outcomes between pushes")
    r.add_argument("--sync-seconds", type=float, default=600.0, help="seconds between pushes")
    k = sub.add_parser("pack")
    k.add_argument("out")
    k.add_argument("zip")
    k.add_argument("--reading", choices=READINGS, default=UNRESTRICTED)
    s = sub.add_parser("rank-sample")
    s.add_argument("out")
    s.add_argument("sample")
    g = sub.add_parser("agreement")
    g.add_argument("out")
    g.add_argument("json")
    g.add_argument("--listing", required=True)
    h = sub.add_parser("handcheck")
    h.add_argument("out")
    h.add_argument("md")
    h.add_argument("--n", type=int, default=20)
    h.add_argument("--seed", type=int, default=0)
    pr_ = sub.add_parser("report")
    pr_.add_argument("out")
    pr_.add_argument("md")
    yl = sub.add_parser("yield", help="yield and gate G2 from state.jsonl (no directory opened)")
    yl.add_argument("state", help="state.jsonl of a store or run root")
    yl.add_argument("--target-attempted", type=int)
    rpt = sub.add_parser("repeat")
    rpt.add_argument("reference")
    rpt.add_argument("out")
    rpt.add_argument("config")
    rpt.add_argument("--listing", required=True)
    rpt.add_argument("--held-out", required=True)
    rpt.add_argument("--rename-cache")
    rpt.add_argument("--work", required=True)
    rpt.add_argument("--repos", type=int, required=True, help="the first N repositories")
    rpt.add_argument("--lookahead", type=int, default=1)
    sc2 = sub.add_parser("store-convert", help="build a de-duplicated store from a run root")
    sc2.add_argument("src")
    sc2.add_argument("dst")
    mt = sub.add_parser("materialise", help="rebuild the directory layout from a store")
    mt.add_argument("store")
    mt.add_argument("out")
    mt.add_argument("--names", help="file with one directory name per line (default: all)")
    cp = sub.add_parser("compare-roots", help="checksum comparison of two run roots")
    cp.add_argument("a")
    cp.add_argument("b")
    cp.add_argument("json")
    dd = sub.add_parser("dedup-measure")
    dd.add_argument("out")
    dd.add_argument("json")
    sc = sub.add_parser("scale")
    sc.add_argument("summary")
    sc.add_argument("costs")
    sc.add_argument("--listing-seconds", type=float, required=True)
    sc.add_argument("--free-bytes", type=float, required=True)
    sc.add_argument("--targets", nargs="+", required=True, help="REPOS:LINKED_PRS pairs")
    rp = sub.add_parser("rank-prepare")
    rp.add_argument("out")
    rp.add_argument("work")
    rp.add_argument("--limit", type=int, help="first N directories of the seeded order")
    rp.add_argument("--drop-tests", action="store_true", help="alias of --reading non_test")
    rp.add_argument(
        "--reading", choices=READINGS, help="view over the run root (default: unrestricted)"
    )
    rp.add_argument(
        "--only-from", help="selection file (sample.json): prepare exactly its directories"
    )
    rb = sub.add_parser("rank-bm25")
    rb.add_argument("work")
    rb.add_argument("ranks")
    rb.add_argument("--form", default="code")
    rd = sub.add_parser("rank-dense")
    rd.add_argument("work")
    rd.add_argument("ranks")
    rd.add_argument("log")
    rd.add_argument("--teachers", nargs="+", required=True)
    rd.add_argument("--cut", type=int, default=1024)
    rd.add_argument("--form", default="code")
    re_ = sub.add_parser("rank-estimate")
    re_.add_argument("out")
    re_.add_argument("--limit", type=int, help="estimate for the first N directories (pool-like)")
    re_.add_argument("--texts-per-second", type=float, required=True)
    rt = sub.add_parser("rank-tables")
    rt.add_argument("work")
    rt.add_argument("json")
    rt.add_argument("--ranks", nargs="+", required=True)
    rt.add_argument("--yield-per-pr", type=float, required=True)
    rr = sub.add_parser("rank-reproduce")
    rr.add_argument("old")
    rr.add_argument("--new", nargs="+", required=True)
    a = p.parse_args(argv)

    from ril.data_mining import jobs

    if a.cmd == "check":
        sys.stdout.write(json.dumps(jobs.blocker_report(), indent=1, sort_keys=True) + "\n")
        return 0
    if a.cmd == "pack":
        from ril.data_mining.pack import pack_zip, write_listing

        n = pack_zip(a.out, a.zip, reading=a.reading)
        write_listing(a.zip, a.zip + ".listing.json")
        sys.stdout.write(json.dumps({"instances": n, "zip": a.zip}) + "\n")
        return 0
    if a.cmd == "rank-sample":
        from ril.data_mining.rank_compare import rank_sample

        doc = rank_sample(a.out)
        Path(a.sample).write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")
        sys.stdout.write(json.dumps({"directories": len(doc["sample"])}) + "\n")
        return 0

    if a.cmd == "repeat":
        import yaml

        from ril.data_mining.config import MiningConfig
        from ril.data_mining.github_api import (
            ApiClient,
            ClientConfig,
            UrllibTransport,
            token_from_env,
        )
        from ril.data_mining.repeat import repeat
        from ril.data_mining.snapshot import GitSnapshots
        from ril.training.pool_rank_jobs import held_out_predicate

        try:
            jobs.require_token()
        except jobs.TokenMissing as exc:
            sys.stderr.write(f"BLOCKED: {exc}\n")
            return 3
        cfg = MiningConfig.from_dict(yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
        pop = jobs.population_from_listing(
            a.listing, held_out_predicate(a.held_out, a.rename_cache), cfg
        )
        client = ApiClient(
            UrllibTransport(),
            token=token_from_env(),
            etags=jobs.etag_store_for(a.out, enabled=False),
            config=ClientConfig(),
        )
        res = repeat(
            a.reference,
            a.out,
            repos=list(pop.repos[: a.repos]),
            config=cfg,
            client=client,
            snapshots=GitSnapshots(a.work, workers=max(1, a.lookahead)),
            lookahead=a.lookahead,
        )
        sys.stdout.write(json.dumps(res, indent=1, sort_keys=True) + "\n")
        return 0
    if a.cmd in ("store-convert", "materialise", "compare-roots"):
        from ril.data_mining import cas

        if a.cmd == "store-convert":
            doc = cas.convert(a.src, a.dst)
            doc["bytes"] = cas.store_bytes(a.dst)
        elif a.cmd == "materialise":
            names = Path(a.names).read_text(encoding="utf-8").split() if a.names else None
            doc = cas.materialise(a.store, a.out, names)
        else:
            doc = cas.compare_roots(a.a, a.b)
            Path(a.json).write_text(
                json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
            )
        import resource

        doc["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
        sys.stdout.write(json.dumps(doc, sort_keys=True) + "\n")
        return 0 if doc.get("all_identical", True) else 1
    if a.cmd == "dedup-measure":
        from ril.data_mining import dedup

        doc = dedup.measure(a.out)
        Path(a.json).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        sys.stdout.write(json.dumps({k: v for k, v in doc.items() if k != "per_repository"}) + "\n")
        return 0
    if a.cmd == "scale":
        from ril.data_mining import report
        from ril.data_mining.scale import extrapolate

        summary = json.loads(Path(a.summary).read_text(encoding="utf-8"))
        costs = json.loads(Path(a.costs).read_text(encoding="utf-8"))
        unit = report.scale_inputs(summary, costs, a.listing_seconds)
        rows = []
        for target in a.targets:
            repos, _, prs = target.partition(":")
            rows.append(
                extrapolate(
                    unit,
                    repos=int(repos),
                    linked_prs=int(prs),
                    available_bytes=a.free_bytes,
                    available_files=1e12,
                )
            )
        sys.stdout.write(json.dumps({"unit": unit, "rows": rows}, indent=1, sort_keys=True) + "\n")
        return 0
    if a.cmd == "yield":
        from ril.data_mining import state_yield

        res_y = state_yield.yield_report(
            state_yield.read_state(a.state), target_attempted=a.target_attempted
        )
        sys.stdout.write(json.dumps(res_y, indent=1, sort_keys=True) + "\n")
        return 0
    if a.cmd == "report":
        from ril.data_mining import report

        doc = json.loads((Path(a.out) / "summary.json").read_text(encoding="utf-8"))
        costs = {
            "api": report.api_totals(a.out),
            "seconds": report.session_seconds(a.out),
            "disk": report.disk_use(a.out),
        }
        Path(a.md).write_text(report.render(doc), encoding="utf-8")
        Path(a.md).with_suffix(".costs.json").write_text(
            json.dumps(costs, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        sys.stdout.write(json.dumps(costs, sort_keys=True) + "\n")
        return 0
    if a.cmd.startswith("rank-"):
        from ril.data_mining import rank_jobs

        if a.cmd == "rank-prepare":
            if a.drop_tests and a.reading not in (None, NON_TEST):
                raise SystemExit("--drop-tests means --reading non_test; give only one")
            only = None
            if a.only_from:
                only = [r["dir"] for r in json.loads(Path(a.only_from).read_text())["sample"]]
            reading = NON_TEST if a.drop_tests else (a.reading or UNRESTRICTED)
            res = rank_jobs.prepare(a.out, a.work, reading, a.limit, only)
        elif a.cmd == "rank-bm25":
            res = rank_jobs.bm25(a.work, a.ranks, form=a.form)
        elif a.cmd == "rank-dense":
            res = rank_jobs.dense(
                a.work, a.ranks, a.log, teachers=a.teachers, cut=a.cut, form=a.form
            )
        elif a.cmd == "rank-estimate":
            res = rank_jobs.estimate(a.out, a.texts_per_second, limit=a.limit)
        elif a.cmd == "rank-reproduce":
            res = rank_jobs.reproduces(a.new, a.old)
            sys.stdout.write(json.dumps(res, sort_keys=True) + "\n")
            return 0 if res["exact"] else 4
        else:
            res = rank_jobs.tables(f"{a.work}/sample.json", a.ranks, yield_per_pr=a.yield_per_pr)
            Path(a.json).write_text(
                json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8"
            )
        sys.stdout.write(json.dumps(res if a.cmd != "rank-tables" else {"written": a.json}) + "\n")
        return 0
    if a.cmd == "agreement":
        from ril.data_mining import validation

        url, members = validation.pool_members_for(a.listing)
        validation.write_json(a.json, validation.agreement_job(a.out, url, members))
        sys.stdout.write(json.dumps({"written": a.json}) + "\n")
        return 0
    if a.cmd == "handcheck":
        from ril.data_mining import validation
        from ril.data_mining.github_api import (
            ApiClient,
            ClientConfig,
            UrllibTransport,
            token_from_env,
        )

        try:
            jobs.require_token()
        except jobs.TokenMissing as exc:
            sys.stderr.write(f"BLOCKED: {exc}\n")
            return 3
        client = ApiClient(
            UrllibTransport(),
            token=token_from_env(),
            etags=jobs.etag_store_for(a.out),
            config=ClientConfig(),
            sink=jobs.jsonl_sink(str(Path(a.out) / "api_events.jsonl")),
        )
        text, chosen = validation.handcheck_file(a.out, client, a.n, a.seed)
        Path(a.md).write_text(text, encoding="utf-8")
        sys.stdout.write(json.dumps({"written": a.md, "prs": len(chosen)}) + "\n")
        return 0

    import yaml

    from ril.data_mining.config import MiningConfig
    from ril.data_mining.github_api import ApiClient, ClientConfig, UrllibTransport, token_from_env
    from ril.data_mining.runner import QuarantineRateExceeded
    from ril.data_mining.snapshot import GitSnapshots
    from ril.training.pool_rank_jobs import held_out_predicate

    try:
        jobs.require_token()
    except jobs.TokenMissing as exc:
        sys.stderr.write(f"BLOCKED: {exc}\n")
        return 3
    config = MiningConfig.from_dict(yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
    is_held_out = held_out_predicate(a.held_out, a.rename_cache)
    population = jobs.population_from_listing(a.listing, is_held_out, config)
    events = f"api_events_shard{a.shard[0]}of{a.shard[1]}.jsonl" if a.shard else "api_events.jsonl"
    client = ApiClient(
        UrllibTransport(),
        token=token_from_env(),
        etags=jobs.etag_store_for(a.out, enabled=a.etag_cache),
        config=ClientConfig(),
        sink=jobs.jsonl_sink(str(Path(a.out) / events)),
    )
    repos = None
    if a.repos is not None:
        repos = list(population.repos[: a.repos])
    try:
        res = jobs.run_pilot(
            config=config,
            out_root=a.out,
            population=population,
            is_held_out=is_held_out,
            client=client,
            snapshots=GitSnapshots(a.work, workers=max(1, a.lookahead)),
            lookahead=a.lookahead,
            list_only=a.list_only,
            shard=tuple(a.shard) if a.shard else None,
            created=a.created,
            code_commit=_commit(),
            stop_after=a.stop_after,
            repos=repos,
            store_layout=a.store_layout,
            durable_root=a.durable,
            sync_every=a.sync_every,
            sync_seconds=a.sync_seconds,
        )
    except jobs.ListingIncomplete as exc:
        sys.stderr.write(f"LISTING INCOMPLETE: {exc}\n")
        return 4
    except QuarantineRateExceeded as exc:
        sys.stderr.write(f"QUARANTINE RATE EXCEEDED: {exc}\n")
        return 5
    sys.stdout.write(json.dumps(res, indent=1, sort_keys=True) + "\n")
    if a.list_only and res.get("failed"):  # a listing job that left a repository out must fail
        sys.stderr.write(f"LISTING INCOMPLETE: {sorted(res['failed'])[:5]}\n")
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
