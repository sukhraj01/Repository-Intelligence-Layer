# ruff: noqa  (standalone probe for a compute node; prints to stdout by design)
import collections, csv, importlib, os, pkgutil
import pyarrow.parquet as pq
import swebench.harness.constants as C

rows = pq.read_table(os.path.expanduser("~/ril_rq3/data/verified.parquet")).to_pylist()
specs = None
for m in [C] + [
    importlib.import_module(x.name) for x in pkgutil.walk_packages(C.__path__, C.__name__ + ".")
]:
    for n in dir(m):
        v = getattr(m, n)
        if isinstance(v, dict) and "pallets/flask" in v and isinstance(v["pallets/flask"], dict):
            specs = v
cnt = collections.Counter()
per = collections.defaultdict(lambda: collections.Counter())
pre_kinds = collections.Counter()
out = os.path.expanduser("~/ril_rq3/out/a_env_table.csv")
with open(out, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["repo", "version", "instances", "python", "has_pre_install", "pre_install_has_apt"])
    seen = collections.Counter()
    meta = {}
    for r in rows:
        s = specs[r["repo"]][r["version"]]
        k = (r["repo"], r["version"])
        seen[k] += 1
        pre = s.get("pre_install") or []
        meta[k] = (s.get("python"), bool(pre), any("apt-get" in c for c in pre))
    for k in sorted(seen):
        w.writerow([k[0], k[1], seen[k], *meta[k]])
for k, n in seen.items():
    py, pre, apt = meta[k]
    minor = int(py.split(".")[1])
    cat = (
        ("python<3.8" if minor < 8 else "python>=3.8")
        + (" + pre_install" if pre else " + no pre_install")
        + (" (apt-get)" if apt else "")
    )
    cnt[cat] += n
for k, v in sorted(cnt.items()):
    print(v, k)
