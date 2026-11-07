"""End-to-end check of the converter on gold-derived edits (D110, E-RQ3-PATCHAPPLY).

The draw is seeded and stratified over repositories: every repository with at least
``MIN_REPO_SIZE`` executable instances gets one instance, the remaining places go to instances
drawn uniformly (so by repository size) from the rest. ``derive_all`` turns each drawn instance's
gold patch into edit blocks (``gold_edits``), converts them with the exact reading, and records
whether the converted patch yields the same tree as the gold patch before any test is run.
"""

from __future__ import annotations

import random
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ril.agent.providers.patch_convert import Reading, convert_reply, git_reader
from ril.evaluation.executor.spec import InstanceSpec
from ril.evaluation.gold_edits import derive_edits, render_reply, tree_after

MIN_REPO_SIZE = 5
CLONE_ATTEMPTS = 3

Row = dict[str, Any]


def draw_instances(executable: Sequence[Mapping[str, Any]], n: int, seed: int) -> list[Row]:
    """``n`` instances: one per repository of at least ``MIN_REPO_SIZE``, the rest by size."""
    by_repo: dict[str, list[str]] = {}
    policy = {str(r["instance_id"]): str(r.get("env_policy", "latest")) for r in executable}
    for r in executable:
        by_repo.setdefault(str(r["repo"]), []).append(str(r["instance_id"]))
    rng = random.Random(seed)
    picked: list[Row] = []
    taken: set[str] = set()
    big = sorted(r for r, ids in by_repo.items() if len(ids) >= MIN_REPO_SIZE)
    if n < len(big):
        raise ValueError("n is smaller than the number of repositories that must be represented")
    for repo in big:
        iid = rng.choice(sorted(by_repo[repo]))
        picked.append({"instance_id": iid, "repo": repo, "stratum": "repository_minimum"})
        taken.add(iid)
    rest = sorted((iid, repo) for repo, ids in by_repo.items() for iid in ids if iid not in taken)
    for iid, repo in rng.sample(rest, n - len(picked)):
        picked.append({"instance_id": iid, "repo": repo, "stratum": "by_size"})
    for r in picked:
        r["env_policy"] = policy[r["instance_id"]]
    picked.sort(key=lambda r: (r["repo"], r["instance_id"]))
    return picked


def ensure_bare(repo: str, commit: str, mirror_dir: Path, sources: Sequence[str]) -> Path | None:
    """Bare mirror of ``repo`` under ``mirror_dir`` holding ``commit``; ``None`` if unobtainable.

    ``sources`` are tried in order (a local mirror first, then the public remote).
    """
    dest = mirror_dir / (repo.replace("/", "__") + ".git")
    mirror_dir.mkdir(parents=True, exist_ok=True)
    for src in sources:
        for _ in range(CLONE_ATTEMPTS):
            if not dest.exists():
                done = subprocess.run(
                    ["git", "-c", "http.version=HTTP/1.1", "clone", "-q", "--bare", src, str(dest)],
                    capture_output=True,
                    check=False,
                )
                if done.returncode != 0:
                    shutil.rmtree(dest, ignore_errors=True)
                    continue
            have = subprocess.run(
                ["git", "-C", str(dest), "cat-file", "-e", f"{commit}^{{commit}}"],
                capture_output=True,
                check=False,
            )
            if have.returncode == 0:
                return dest
            subprocess.run(
                ["git", "-C", str(dest), "fetch", "-q", src, commit],
                capture_output=True,
                check=False,
            )
            have = subprocess.run(
                ["git", "-C", str(dest), "cat-file", "-e", f"{commit}^{{commit}}"],
                capture_output=True,
                check=False,
            )
            if have.returncode == 0:
                return dest
            break
    return None


def derive_all(
    specs: Sequence[InstanceSpec],
    gold: Mapping[str, str],
    mirror_dir: Path,
    local_mirrors: Path | None,
    scratch: Path,
    reading: Reading = "exact",
) -> tuple[list[Row], dict[str, str]]:
    """``(table rows, {instance: converted patch})`` for the drawn instances."""
    rows: list[Row] = []
    patches: dict[str, str] = {}
    scratch.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        t0 = time.perf_counter()
        row: Row = {"instance_id": spec.instance_id, "repo": spec.repo, "outcome": "", "detail": ""}
        sources = []
        if local_mirrors is not None:
            local = local_mirrors / (spec.repo.replace("/", "__") + ".git")
            if local.exists():
                sources.append(str(local))
        sources.append(f"https://github.com/{spec.repo}.git")
        mirror = ensure_bare(spec.repo, spec.base_commit, mirror_dir, sources)
        if mirror is None:
            rows.append({**row, "outcome": "mirror_unavailable"})
            continue
        read = git_reader(str(mirror), spec.base_commit)
        derived = derive_edits(gold[spec.instance_id], read)
        row["n_hunks"] = derived.n_hunks
        if derived.limit:
            rows.append({**row, "outcome": "derivation_limit", "detail": derived.limit})
            continue
        row["n_blocks"] = len(derived.edits)
        conv = convert_reply(render_reply(derived.edits), read, reading)
        if conv.failure is not None or not conv.diff:
            detail = conv.failure.kind if conv.failure else "empty_diff"
            rows.append({**row, "outcome": "conversion_failed", "detail": detail})
            continue
        gold_tree = tree_after(str(mirror), spec.base_commit, gold[spec.instance_id], str(scratch))
        new_tree = tree_after(str(mirror), spec.base_commit, conv.diff, str(scratch))
        row.update(
            outcome="converted",
            diff_chars=len(conv.diff),
            tree_equals_gold=bool(gold_tree) and gold_tree == new_tree,
            convert_ms=round((time.perf_counter() - t0) * 1000, 1),
        )
        rows.append(row)
        patches[spec.instance_id] = conv.diff
    return rows, patches
