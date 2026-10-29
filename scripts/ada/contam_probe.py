"""Contamination probe on the cluster: build the probe set, measure a shard, scan shards.

Why: whether functions of the Verified repositories occur in CoRNStack's python shards cannot be
answered from the schema (no repository field). Logic lives in ``ril.training.contamination`` and
``ril.training.contamination_index`` (unit-tested); this file does network, timing and bookkeeping.
Run it under the nodes' Python 3.10 (the parser needs it), CPU only, from the work directory.

  contam_probe.py build VERIFIED_REF.json CLONES.json OUT_PROBE.json OUT_STATS.json
  contam_probe.py measure URL MEGABYTES PROBE.json OUT.json [--negatives]
  contam_probe.py scan PROBE.json OUT_DIR URL_PREFIX FIRST LAST MEGABYTES [--negatives]
  contam_probe.py instances VERIFIED_REF.json CLONES.json OUT.json.gz MIN_NODES
  contam_probe.py tables CONFIG.yaml INSTANCES.json.gz SCAN_DIR PROBE_NODES.json OUT_JSON OUT_CSV
  contam_probe.py edited VERIFIED_REF.json CLONES.json PATCHES.json OUT.json.gz
  contam_probe.py edited-tables CONFIG.yaml INSTANCES.json.gz EDITED.json.gz SCAN_DIR OUT_JSON

``scan`` writes OUT_DIR/shard-NNNNN.json per shard and skips shards that already have one;
MEGABYTES 0 reads whole shards. Output holds counts and hashes only, never code text.
"""
# ruff: noqa  (standalone cluster tool; prints progress to stdout by design)

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ril.training import contamination as cm  # noqa: E402

CHUNK = 1 << 20
BATCH = 500


def open_stream(url: str, max_bytes: int):
    headers = {"Range": f"bytes=0-{max_bytes - 1}"} if max_bytes > 0 else {}
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=300)


def run_stream(url, max_bytes, probe, negatives, schema=False):
    """Stream, inflate and scan; return counts and a timing split (seconds)."""
    t_net = t_scan = 0.0
    nbytes = 0
    counts = cm.ScanCounts()
    hits = []
    schema_info = {"keys": {}, "negatives_per_row": [], "document_chars": [], "negative_chars": []}
    t_all = time.perf_counter()
    resp = open_stream(url, max_bytes)

    def chunks():
        nonlocal t_net, nbytes
        while True:
            t0 = time.perf_counter()
            b = resp.read(CHUNK)
            t_net += time.perf_counter() - t0
            if not b:
                return
            nbytes += len(b)
            yield b

    batch = []
    first = True
    for line in cm.gz_lines(chunks(), drop_partial=max_bytes > 0):
        batch.append(line)
        if len(batch) >= BATCH:
            if first and schema:
                for ln in batch[:200]:
                    try:
                        row = json.loads(ln)
                    except ValueError:
                        continue
                    for k, v in row.items():
                        d = schema_info["keys"].setdefault(k, {})
                        d[type(v).__name__] = d.get(type(v).__name__, 0) + 1
                    negs = row.get("negatives") or []
                    schema_info["negatives_per_row"].append(len(negs))
                    schema_info["document_chars"].append(len(row.get("document") or ""))
                    schema_info["negative_chars"].extend(len(x) for x in negs if isinstance(x, str))
                first = False
            t0 = time.perf_counter()
            c = cm.scan_lines(batch, probe, negatives=negatives, hits=hits)
            t_scan += time.perf_counter() - t0
            for k, v in c.as_dict().items():
                setattr(counts, k, getattr(counts, k) + v)
            batch = []
    if batch:
        t0 = time.perf_counter()
        c = cm.scan_lines(batch, probe, negatives=negatives, hits=hits)
        t_scan += time.perf_counter() - t0
        for k, v in c.as_dict().items():
            setattr(counts, k, getattr(counts, k) + v)
    total = time.perf_counter() - t_all
    return {
        "counts": counts.as_dict(),
        "compressed_bytes": nbytes,
        "seconds": {
            "total": round(total, 2),
            "network_read": round(t_net, 2),
            "scan_hash_json": round(t_scan, 2),
            "inflate_and_rest": round(total - t_net - t_scan, 2),
        },
        "hits": hits,
        "schema": schema_info,
    }


def cmd_build(ref, clones, out_probe, out_stats):
    from ril.training import contamination_index as ci

    verified = json.load(open(ref))
    by_repo = {}
    for iid, v in verified.items():
        by_repo.setdefault(v["repo"].lower(), set()).add(v["base_commit"])
    git_dirs = json.load(open(clones))
    git_dirs = {r.lower(): p for r, p in git_dirs.items()}
    t0 = time.time()
    probe, stats = ci.build_probe(git_dirs, {r: sorted(c) for r, c in by_repo.items()})
    open(out_probe, "w").write(probe.to_json())
    doc = {
        "version": cm.PROBE_VERSION,
        "seconds": round(time.time() - t0, 1),
        "repos": {r: len(c) for r, c in sorted(by_repo.items())},
        "snapshots": stats.snapshots,
        "blobs_seen": stats.blobs_seen,
        "blobs_parsed": stats.blobs_parsed,
        "blobs_unparseable": stats.blobs_unparseable,
        "blobs_skipped_by_rule": stats.blobs_skipped_by_rule,
        "functions": stats.functions,
        "distinct_text_hashes": len(probe.text),
        "distinct_ast_hashes": len(probe.ast),
        "per_repo": stats.per_repo,
    }
    json.dump(doc, open(out_stats, "w"), indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in doc.items() if k != "per_repo"}))


def load_probe(path):
    return cm.ProbeSet.from_json(open(path).read())


def cmd_measure(url, mb, probe_path, out, negatives):
    probe = load_probe(probe_path)
    res = run_stream(url, int(float(mb) * 1e6), probe, negatives, schema=True)
    res["url"] = url
    res["requested_megabytes"] = float(mb)
    res["negatives_scanned"] = negatives
    s = res["schema"]
    for key in ("negatives_per_row", "document_chars", "negative_chars"):
        v = sorted(s[key])
        s[key] = {
            "n": len(v),
            "median": v[len(v) // 2] if v else None,
            "p95": v[int(len(v) * 0.95)] if v else None,
            "max": v[-1] if v else None,
        }
    json.dump(res, open(out, "w"), indent=1, sort_keys=True)
    c = res["counts"]
    print(
        "rows", c["rows"], "bytes", res["compressed_bytes"], res["seconds"], "hits", c["any_hits"]
    )


def cmd_scan(probe_path, out_dir, prefix, first, last, mb, negatives):
    probe = load_probe(probe_path)
    os.makedirs(out_dir, exist_ok=True)
    for i in range(int(first), int(last) + 1):
        out = os.path.join(out_dir, "shard-%05d.json" % i)
        if os.path.exists(out):
            continue
        url = "%s/shard-%05d.jsonl.gz" % (prefix, i)
        for attempt in range(3):
            try:
                res = run_stream(url, int(float(mb) * 1e6), probe, negatives)
                break
            except Exception as exc:
                print("shard", i, "attempt", attempt, type(exc).__name__, exc, flush=True)
                time.sleep(10)
        else:
            continue
        res["url"] = url
        res["shard"] = i
        res["requested_megabytes"] = float(mb)
        res["negatives_scanned"] = negatives
        del res["schema"]
        json.dump(res, open(out + ".tmp", "w"), indent=1, sort_keys=True)
        os.replace(out + ".tmp", out)
        print(
            "shard",
            i,
            res["counts"]["rows"],
            res["seconds"],
            "hits",
            res["counts"]["any_hits"],
            flush=True,
        )


def cmd_instances(ref, clones, out, min_nodes):
    import gzip

    from ril.training import contamination_index as ci

    verified = json.load(open(ref))
    git_dirs = {r.lower(): p for r, p in json.load(open(clones)).items()}
    inst = {i: (v["repo"].lower(), v["base_commit"]) for i, v in verified.items()}
    t0 = time.time()
    res = ci.instance_hashes(git_dirs, inst, int(min_nodes))
    doc = {
        "min_nodes": int(min_nodes),
        "instances": {
            i: {"repo": inst[i][0], "base_commit": inst[i][1], "hashes": h} for i, h in res.items()
        },
    }
    with gzip.open(out + ".tmp", "wt") as f:
        json.dump(doc, f, sort_keys=True, separators=(",", ":"))
    os.replace(out + ".tmp", out)
    print(
        "instances",
        len(res),
        "functions",
        sum(len(h) for h in res.values()),
        "seconds",
        round(time.time() - t0, 1),
    )


def cmd_tables(config, inst_path, scan_dir, probe_nodes, out_json, out_csv):
    import csv
    import glob
    import gzip

    import yaml

    from ril.analysis import x4_tables as xt

    cfg = yaml.safe_load(open(config))
    shards = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(scan_dir, "shard-*.json")))]
    docs, check = xt.collect_hits(shards)
    doc = json.load(gzip.open(inst_path, "rt"))
    inst = {i: (v["repo"], v["hashes"]) for i, v in doc["instances"].items()}
    sizes = json.load(open(probe_nodes))["nodes"]
    floors = [cfg["size_floor"]["primary_nodes"]] + list(cfg["size_floor"]["sensitivity_nodes"])
    out = {
        "scan_version": xt.SCAN_VERSION,
        "config_hash": xt.config_hash(cfg),
        "check": check,
        "hit_documents_by_size": xt.size_profile(docs, sizes),
        "distinct_matched_hashes": len(docs),
        "per_floor": {},
    }
    csv_rows = []
    for fl in floors:
        rows = xt.repo_table(inst, docs, fl)
        out["per_floor"][str(fl)] = {"repos": rows}
        csv_rows += rows
    json.dump(out, open(out_json, "w"), indent=1, sort_keys=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(csv_rows[0]))
        w.writeheader()
        w.writerows(csv_rows)
    print(json.dumps(out["check"]))


def cmd_edited(ref, clones, patches, out):
    import gzip

    from ril.evaluation import contamination_edited as ce

    verified = json.load(open(ref))
    pat = json.load(open(patches))
    git_dirs = {r.lower(): p for r, p in json.load(open(clones)).items()}
    inst = {i: (v["repo"].lower(), v["base_commit"], pat[i]) for i, v in verified.items()}
    t0 = time.time()
    res = ce.edited_for_instances(git_dirs, inst)
    doc = {"version": ce.EDITED_VERSION, "instances": res}
    with gzip.open(out + ".tmp", "wt") as f:
        json.dump(doc, f, sort_keys=True, separators=(",", ":"))
    os.replace(out + ".tmp", out)
    print("instances", len(res), "seconds", round(time.time() - t0, 1))


def cmd_edited_tables(config, inst_path, edited_path, scan_dir, out_json):
    import glob
    import gzip

    import yaml

    from ril.analysis import x4_tables as xt
    from ril.analysis import x5_tables as x5

    cfg = yaml.safe_load(open(config))
    shards = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(scan_dir, "shard-*.json")))]
    docs, check = xt.collect_hits(shards)
    doc = json.load(gzip.open(inst_path, "rt"))
    inst = {i: (v["repo"], v["hashes"]) for i, v in doc["instances"].items()}
    edited = json.load(gzip.open(edited_path, "rt"))["instances"]
    floors = [cfg["size_floor"]["primary_nodes"]] + list(cfg["size_floor"]["sensitivity_nodes"])
    out = {
        "scan_check": check,
        "config_hash": xt.config_hash(cfg),
        "diagnostics": x5.diagnostics(edited),
        "per_floor": {str(f): x5.floor_table(edited, inst, docs, f) for f in floors},
    }
    json.dump(out, open(out_json, "w"), indent=1, sort_keys=True)
    print(json.dumps(out["diagnostics"]))


def main():
    args = [a for a in sys.argv[1:] if a != "--negatives"]
    neg = "--negatives" in sys.argv
    cmd = args[0]
    if cmd == "build":
        cmd_build(*args[1:5])
    elif cmd == "measure":
        cmd_measure(*args[1:5], neg)
    elif cmd == "scan":
        cmd_scan(*args[1:7], neg)
    elif cmd == "instances":
        cmd_instances(*args[1:5])
    elif cmd == "tables":
        cmd_tables(*args[1:7])
    elif cmd == "edited":
        cmd_edited(*args[1:5])
    elif cmd == "edited-tables":
        cmd_edited_tables(*args[1:6])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
