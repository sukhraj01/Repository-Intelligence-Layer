# ruff: noqa  (standalone probe for a compute node; prints to stdout by design)
"""Environment census of Verified under the install specifications, plus a flask retry with pytest pinned below 8."""

import collections, importlib, json, os, pkgutil, re, shlex, subprocess, sys, time
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
envs = collections.OrderedDict()
py = collections.Counter()
pre = collections.Counter()
preset = set()
for r in rows:
    s = specs[r["repo"]][r["version"]]
    envs.setdefault((r["repo"], r["version"]), 0)
    envs[(r["repo"], r["version"])] += 1
    py[s.get("python", "?")] += 1
    if s.get("pre_install"):
        pre[r["repo"]] += 1
        for c in s["pre_install"]:
            preset.add(c if len(c) < 200 else c[:200])
out = {
    "instances": len(rows),
    "distinct_environments": len(envs),
    "instances_by_spec_python": dict(py),
    "instances_with_pre_install_by_repo": dict(pre),
    "pre_install_commands_distinct": sorted(preset)[:25],
    "has_eval_commands_or_other_keys": sorted(
        {k for r in rows for k in specs[r["repo"]][r["version"]].keys()}
    ),
}
ul = subprocess.run(
    "uv python list --only-downloads 2>&1 | head -60", shell=True, capture_output=True, text=True
).stdout
out["uv_downloadable_cpython_minor_versions"] = sorted(
    {m.group(1) for m in re.finditer(r"cpython-(3\.\d+)\.", ul)}
)
json.dump(out, open(os.path.expanduser("~/ril_rq3/out/a_env_census.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
# flask retry: spec packages, then pytest pinned below 8 (diagnosis of the failure of the first check)
r = next(x for x in rows if x["instance_id"] == "pallets__flask-5014")
s = specs[r["repo"]][r["version"]]
d = "/tmp/ril_rq3_work/flask_retry"
os.makedirs(d, exist_ok=True)


def sh(c, t=1200):
    t0 = time.time()
    p = subprocess.run(["bash", "-c", c], capture_output=True, text=True, timeout=t)
    return p.returncode, round(time.time() - t0, 1), (p.stdout + p.stderr)[-500:]


print(
    "spec pip_packages:",
    s.get("pip_packages"),
    "install:",
    s.get("install"),
    "test_cmd:",
    s.get("test_cmd"),
)
if not os.path.exists(d + "/repo/.git"):
    print(
        sh(
            f"git clone -q ~/ril_e/repo_cache/pallets__flask.git {d}/repo && git -C {d}/repo checkout -q {r['base_commit']}"
        )[:2]
    )
print(sh(f"uv venv --seed --python 3.11 {d}/venv")[:2])
act = f"source {d}/venv/bin/activate && cd {d}/repo && "
pk = s.get("pip_packages", [])
pk = pk.split() if isinstance(pk, str) else pk
print(
    sh(
        act + "python -m pip install -q " + " ".join(shlex.quote(p) for p in pk) + " 'pytest<8'",
        2400,
    )[:2]
)
print(sh(act + s.get("install", "python -m pip install -e ."), 2400)[:2])
open(d + "/t.patch", "w").write(r["test_patch"])
open(d + "/g.patch", "w").write(r["patch"])
print(sh(f"cd {d}/repo && git apply {d}/t.patch")[:2])
files = sorted(set(re.findall(r"^diff --git a/(\S+) b/", r["test_patch"], re.M)))
f2p = (
    json.loads(r["FAIL_TO_PASS"]) if isinstance(r["FAIL_TO_PASS"], str) else list(r["FAIL_TO_PASS"])
)
for tag, pre in (("before_gold", ""), ("after_gold", f"cd {d}/repo && git apply {d}/g.patch && ")):
    c, t, o = sh(pre + act + "pytest -rA " + " ".join(files))
    ok = [i for i in f2p if re.search(r"^PASSED " + re.escape(i), o, re.M)]
    print("flask_retry", tag, "exit", c, "seconds", t, "f2p", len(ok), "of", len(f2p))
    print(o[-250:])
