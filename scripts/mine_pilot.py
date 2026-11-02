"""PR-mined set: thin command line over ``ril.data_mining.jobs`` (E-MINE-PILOT).

Subcommands (logic in ``ril/``):
  check                       token presence (never the value) and the API rate-limit probe
  run CONFIG OUT --listing L --held-out H [--rename-cache R] --work W [--repos N] [--stop-after N]
                              list, select, mine (resumable); refuses to start without GITHUB_TOKEN
  pack OUT ZIP                zip + member listing in the layout the pool reader streams
  rank-sample OUT SAMPLE      selection file covering every mined directory (for the rank tooling)
  agreement OUT JSON --listing L
                              mined positives against the pool's, for pull requests in both
  report OUT MD               tables of a finished run (summary.json) and its measured unit costs
  rank-prepare OUT WORK       zip, listing and selection file of the run for the rank tooling
  rank-bm25 WORK RANKS        BM25 ranks (CPU);  rank-dense WORK RANKS LOG --teachers T ...  (GPU)
  rank-tables WORK JSON --ranks R ... --yield-per-pr Y   shares with no positive in the top K
  handcheck OUT MD --n N --seed S
                              markdown for a human to read: issue title, hunks, mined positives
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _commit() -> str:
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
    k = sub.add_parser("pack")
    k.add_argument("out")
    k.add_argument("zip")
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
    rp = sub.add_parser("rank-prepare")
    rp.add_argument("out")
    rp.add_argument("work")
    rp.add_argument(
        "--drop-tests", action="store_true", help="pool-like reading (no test functions)"
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
    a = p.parse_args(argv)

    from ril.data_mining import jobs

    if a.cmd == "check":
        sys.stdout.write(json.dumps(jobs.blocker_report(), indent=1, sort_keys=True) + "\n")
        return 0
    if a.cmd == "pack":
        from ril.data_mining.pack import pack_zip, write_listing

        n = pack_zip(a.out, a.zip)
        write_listing(a.zip, a.zip + ".listing.json")
        sys.stdout.write(json.dumps({"instances": n, "zip": a.zip}) + "\n")
        return 0
    if a.cmd == "rank-sample":
        from ril.data_mining.rank_compare import rank_sample

        doc = rank_sample(a.out)
        Path(a.sample).write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")
        sys.stdout.write(json.dumps({"directories": len(doc["sample"])}) + "\n")
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
            res = rank_jobs.prepare(a.out, a.work, a.drop_tests, a.limit)
        elif a.cmd == "rank-bm25":
            res = rank_jobs.bm25(a.work, a.ranks, form=a.form)
        elif a.cmd == "rank-dense":
            res = rank_jobs.dense(
                a.work, a.ranks, a.log, teachers=a.teachers, cut=a.cut, form=a.form
            )
        elif a.cmd == "rank-estimate":
            res = rank_jobs.estimate(a.out, a.texts_per_second, limit=a.limit)
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
    )
    sys.stdout.write(json.dumps(res, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
