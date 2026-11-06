# ruff: noqa  (standalone probe for a compute node; prints to stdout by design)
"""Part A probe 2: Verified census and gold-patch checks on instances of different repositories.
Stdlib plus pyarrow; swebench is read only for its per-repository install specifications."""

import json, os, re, subprocess, sys, time, resource, shlex

OUT = os.path.expanduser("~/ril_rq3/out")
WORK = "/tmp/ril_rq3_work"
os.makedirs(OUT, exist_ok=True)
os.makedirs(WORK, exist_ok=True)
CACHE = os.path.expanduser("~/ril_e/repo_cache")


def run(cmd, cwd=None, timeout=1800, env=None):
    """Run a shell command; return (exit, seconds, peak_rss_mb, output tail)."""
    t0 = time.time()
    p = subprocess.Popen(
        ["bash", "-c", cmd], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    try:
        out, _ = p.communicate(timeout=timeout)
        code = p.returncode
    except subprocess.TimeoutExpired:
        p.kill()
        out, _ = p.communicate()
        code = 124
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    return (
        code,
        round(time.time() - t0, 1),
        round(ru.ru_maxrss / 1024, 1),
        out.decode("utf-8", "replace"),
    )


import pyarrow.parquet as pq

rows = pq.read_table(os.path.expanduser("~/ril_rq3/data/verified.parquet")).to_pylist()
import importlib, pkgutil
import swebench
import swebench.harness.constants as _C


def _find_specs():
    """Locate the per-repository install specifications whatever the package version calls them."""
    mods = [_C] + [
        importlib.import_module(m.name)
        for m in pkgutil.walk_packages(_C.__path__, _C.__name__ + ".")
    ]
    for mod in mods:
        for name in dir(mod):
            v = getattr(mod, name)
            if (
                isinstance(v, dict)
                and "pallets/flask" in v
                and isinstance(v["pallets/flask"], dict)
            ):
                print("specs found at", mod.__name__, name)
                return v
    raise SystemExit("no specs dictionary found in swebench.harness.constants")


MAP_REPO_VERSION_TO_SPECS = _find_specs()
census = {"swebench_version": getattr(swebench, "__version__", "unknown"), "rows": len(rows)}


def f2p(r):
    return (
        json.loads(r["FAIL_TO_PASS"])
        if isinstance(r["FAIL_TO_PASS"], str)
        else list(r["FAIL_TO_PASS"])
    )


def has_spec(r):
    return (
        r["repo"] in MAP_REPO_VERSION_TO_SPECS
        and r["version"] in MAP_REPO_VERSION_TO_SPECS[r["repo"]]
    )


census["with_base_commit"] = sum(1 for r in rows if r["base_commit"])
census["with_fail_to_pass"] = sum(1 for r in rows if f2p(r))
census["with_test_patch"] = sum(1 for r in rows if r["test_patch"])
census["with_install_spec"] = sum(1 for r in rows if has_spec(r))
census["executable_all_four"] = sum(
    1 for r in rows if r["base_commit"] and f2p(r) and r["test_patch"] and has_spec(r)
)
per = {}
for r in rows:
    d = per.setdefault(
        r["repo"], {"n": 0, "executable": 0, "python": set(), "needs_pre_install": 0}
    )
    d["n"] += 1
    ok = r["base_commit"] and f2p(r) and r["test_patch"] and has_spec(r)
    d["executable"] += 1 if ok else 0
    if has_spec(r):
        sp = MAP_REPO_VERSION_TO_SPECS[r["repo"]][r["version"]]
        d["python"].add(sp.get("python", "?"))
        d["needs_pre_install"] += 1 if sp.get("pre_install") else 0
for d in per.values():
    d["python"] = sorted(d["python"])
census["per_repo"] = per
json.dump(census, open(f"{OUT}/a_verified_census.json", "w"), indent=1, sort_keys=True)
print(json.dumps(census, indent=1, sort_keys=True))


def vkey(r):
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.]", r["version"]))


cands = []
for repo in ["pallets/flask", "psf/requests", "mwaskom/seaborn", "pydata/xarray"]:
    rs = sorted(
        [r for r in rows if r["repo"] == repo and has_spec(r)],
        key=lambda r: (vkey(r), r["instance_id"]),
        reverse=True,
    )
    cands.append(rs[:2])
results = []
good_repos = set()
for rs in cands:
    for r in rs:
        repo = r["repo"]
        if repo in good_repos or len(good_repos) >= 3:
            break
        iid = r["instance_id"]
        sp = MAP_REPO_VERSION_TO_SPECS[repo][r["version"]]
        res = {
            "instance": iid,
            "repo": repo,
            "version": r["version"],
            "spec_python": sp.get("python"),
            "steps": {},
        }
        d = f"{WORK}/{iid}"
        os.makedirs(d, exist_ok=True)
        bare = f"{CACHE}/{repo.replace('/', '__')}.git"
        steps = res["steps"]

        def step(name, cmd, **kw):
            c, s, m, o = run(cmd, **kw)
            steps[name] = {
                "exit": c,
                "seconds": s,
                "peak_rss_mb_cumulative_max": m,
                "tail": o[-600:],
            }
            return c

        if not os.path.exists(f"{d}/repo/.git"):
            if step(
                "clone",
                f"git clone -q {shlex.quote(bare)} {d}/repo && git -C {d}/repo checkout -q {r['base_commit']}",
            ):
                results.append(res)
                continue
        py = sp.get("python", "3.9")
        if step("venv", f"uv venv --seed --python {py} {d}/venv"):
            results.append(res)
            continue
        act = f"source {d}/venv/bin/activate && cd {d}/repo && "
        if sp.get("pre_install"):
            res["pre_install_skipped"] = sp["pre_install"]
        pkgs = sp.get("pip_packages", [])
        if isinstance(pkgs, str):
            pkgs = pkgs.split()
        if pkgs and step(
            "pip_packages",
            act + "python -m pip install -q " + " ".join(shlex.quote(p) for p in pkgs),
            timeout=2400,
        ):
            results.append(res)
            continue
        inst = sp.get("install", "python -m pip install -e .")
        if step("install", act + inst, timeout=2400):
            results.append(res)
            continue
        if step("pytest_installed", act + "python -m pip install -q pytest 2>&1 | tail -1"):
            pass
        open(f"{d}/test.patch", "w").write(r["test_patch"])
        open(f"{d}/gold.patch", "w").write(r["patch"])
        files = sorted(set(re.findall(r"^diff --git a/(\S+) b/", r["test_patch"], re.M)))
        tc = sp.get("test_cmd", "pytest -rA")
        ids = f2p(r)

        def tests(tag):
            code, s, m, o = run(
                act + f"{tc} " + " ".join(shlex.quote(f) for f in files) + " 2>&1", timeout=1800
            )
            passed = {
                m_.group(1).strip() for m_ in re.finditer(r"^PASSED (\S.*?)(?: - .*)?$", o, re.M)
            }
            failed = {
                m_.group(1).strip()
                for m_ in re.finditer(r"^(?:FAILED|ERROR) (\S.*?)(?: - .*)?$", o, re.M)
            }
            steps[f"tests_{tag}"] = {
                "exit": code,
                "seconds": s,
                "peak_rss_mb_cumulative_max": m,
                "n_passed": len(passed),
                "n_failed": len(failed),
                "f2p_total": len(ids),
                "f2p_passed": sum(1 for i in ids if i in passed),
                "f2p_missing_from_output": [i for i in ids if i not in passed and i not in failed][
                    :5
                ],
                "tail": o[-400:],
            }
            open(f"{OUT}/{iid}_{tag}.log", "w").write(o[-200000:])

        if step("apply_test_patch", f"cd {d}/repo && git apply {d}/test.patch"):
            results.append(res)
            continue
        tests("before_gold")
        if step("apply_gold_patch", f"cd {d}/repo && git apply {d}/gold.patch"):
            results.append(res)
            continue
        tests("after_gold")
        a = steps["tests_after_gold"]
        res["resolved_by_gold"] = a["f2p_passed"] == a["f2p_total"] and a["f2p_total"] > 0
        results.append(res)
        if res["resolved_by_gold"]:
            good_repos.add(repo)
json.dump(results, open(f"{OUT}/a_gold_checks.json", "w"), indent=1)
for r in results:
    print(
        r["instance"],
        r["repo"],
        "spec_python",
        r["spec_python"],
        "resolved_by_gold",
        r.get("resolved_by_gold"),
        {k: (v.get("exit"), v.get("seconds")) for k, v in r["steps"].items()},
    )
