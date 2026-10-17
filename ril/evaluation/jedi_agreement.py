"""Agreement of a second static resolver (Jedi) on a stratified sample of call sites.

Implements recovery definition (c) of ``specs/parse_one_repo.md`` / ADR-012. For each sampled
``invoke`` edge, Jedi is asked to infer the definition at the callee name of the call site. The two
resolvers agree when:

* ``resolved``   Jedi's in-repository definitions are exactly {dst} (``exact``) or contain dst
                 (``overlap``);
* ``ambiguous``  Jedi's definitions are non-empty and inside the candidate set (``contained``) or
                 meet it (``overlap``);
* ``external``   Jedi finds no definition inside the repository;
* ``unresolved`` Jedi finds no definition inside the repository (both fail to recover the site);
                 otherwise the site is one Jedi recovers and this resolver did not.

Agreement of two resolvers is not accuracy: Jedi has its own failures (no installed
dependencies here, so third-party receivers are unknown to it). The sample, the rule and the
outcome of every site are listed in the results table.
"""

from __future__ import annotations

import ast
import os
import random
from collections import Counter
from dataclasses import dataclass
from typing import Any

from ril.evaluation.edge_recovery import UnitIndex
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repo_graph import Edge, RepoGraph


@dataclass(frozen=True)
class Site:
    """A sampled call site."""

    repo: str
    edge: Edge


def draw_sites(
    graphs: dict[str, RepoGraph],
    total: int,
    seed: int,
    statuses: tuple[str, ...] = ("resolved", "ambiguous", "unresolved", "external"),
) -> list[Site]:
    """Stratify by (repository, status): near-equal quotas, one seeded draw per stratum."""
    strata = [(repo, s) for repo in sorted(graphs) for s in statuses]
    base, extra = divmod(total, len(strata))
    sites: list[Site] = []
    for i, (repo, status) in enumerate(strata):
        quota = base + (1 if i < extra else 0)
        pool = [e for e in graphs[repo].edges if e.type == "invoke" and e.status == status]
        pool.sort(key=Edge.sort_key)
        rng = random.Random(f"{seed}:{repo}:{status}")
        picked = rng.sample(pool, min(quota, len(pool)))
        sites.extend(Site(repo, e) for e in sorted(picked, key=Edge.sort_key))
    return sites


def _callee_position(call: ast.AST) -> tuple[int, int] | None:
    func = call.func if isinstance(call, ast.Call) else call
    if (
        isinstance(func, ast.Attribute)
        and func.end_lineno is not None
        and func.end_col_offset is not None
    ):
        return func.end_lineno, func.end_col_offset - len(func.attr)
    if isinstance(func, ast.Name):
        return func.lineno, func.col_offset
    return None


def _find_call(tree: ast.AST, line: int, col: int, text: str) -> ast.AST | None:
    """The call (or decorator expression) at a site; the callee text disambiguates the calls
    that start at the same position (``f(x).g(y)`` starts the same way as ``f(x)``)."""
    exact: ast.AST | None = None
    loose: ast.AST | None = None
    other: ast.AST | None = None
    for node in ast.walk(tree):
        if getattr(node, "lineno", -1) != line or getattr(node, "col_offset", -1) != col:
            continue
        if isinstance(node, ast.Call):
            try:
                func_text = " ".join(ast.unparse(node.func).split())
            except (ValueError, RecursionError):
                continue
            if func_text == text and exact is None:
                exact = node
            elif func_text.startswith(text[:60]) and loose is None:
                loose = node
        elif isinstance(node, ast.Name | ast.Attribute) and other is None:
            other = node
    return exact or other or loose


@dataclass
class JediOutcome:
    """What Jedi inferred for one site."""

    units: tuple[str, ...]
    n_external: int
    n_total: int
    error: str = ""


def jedi_units_for(
    site: Site, root: str, idx: UnitIndex, project: Any, cache: dict[str, tuple[str, ast.AST]]
) -> JediOutcome:
    """Ask Jedi for the definitions at the callee name of one site."""
    import jedi  # local import: comparator, optional dependency

    path, line_s, col_s = site.edge.site.rsplit(":", 2)
    line, col = int(line_s), int(col_s)
    if path not in cache:
        with open(os.path.join(root, path), encoding="utf-8", errors="replace") as handle:
            code = handle.read()
        cache[path] = (code, ast.parse(code))
    code, tree = cache[path]
    node = _find_call(tree, line, col, site.edge.target_text)
    pos = _callee_position(node) if node is not None else None
    if pos is None:
        return JediOutcome((), 0, 0, "no-callee-position")
    lines = code.split("\n")
    pline, pcol = pos
    if pline - 1 < len(lines):
        pcol = len(lines[pline - 1].encode("utf-8")[:pcol].decode("utf-8", errors="ignore"))
    try:
        script = jedi.Script(code, path=os.path.join(root, path), project=project)
        names = script.infer(pline, pcol)
    except Exception as exc:  # noqa: BLE001 - jedi raises a wide range on odd input; recorded, not hidden
        return JediOutcome((), 0, 0, f"jedi-error:{type(exc).__name__}")
    found: set[str] = set()
    external = 0
    root_real = os.path.realpath(root) + os.sep
    for n in names:
        mp = n.module_path
        if mp is None or not os.path.realpath(str(mp)).startswith(root_real):
            external += 1
            continue
        rel = os.path.realpath(str(mp))[len(root_real) :].replace(os.sep, "/")
        uid = unit_at(idx, rel, int(n.line or 0))
        if uid:
            found.add(uid)
        else:
            external += 1
    return JediOutcome(tuple(sorted(found)), external, len(names))


def unit_at(idx: UnitIndex, file: str, line: int) -> str | None:
    """Innermost unit (method over class over module) containing ``line`` of ``file``."""
    if file not in idx.module_unit:
        return None
    return idx.enclosing(file, line) or idx.module_unit[file]


def agreement(site: Site, outcome: JediOutcome) -> str:
    """Outcome label of one site (see the module docstring for the rules)."""
    if outcome.error:
        return f"jedi-no-answer:{outcome.error}"
    e = site.edge
    j = set(outcome.units)
    if e.status == "resolved":
        if j == {e.dst}:
            return "agree-exact"
        if e.dst in j:
            return "agree-overlap"
        return "disagree-jedi-none" if not j else "disagree-different-unit"
    if e.status == "ambiguous":
        c = set(e.candidates)
        if j and j <= c:
            return "agree-contained"
        if j & c:
            return "agree-overlap"
        return "disagree-jedi-none" if not j else "disagree-outside-candidates"
    if not j:
        return "agree-both-no-in-repo-target"
    return "jedi-recovers-site"


def summarize(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Counts per (status, outcome) and agreement rates per status."""
    table: dict[str, Counter[str]] = {}
    for r in rows:
        table.setdefault(r["status"], Counter())[r["outcome"]] += 1
    out: dict[str, Any] = {}
    for status, counts in sorted(table.items()):
        n = sum(counts.values())
        answered = n - sum(v for k, v in counts.items() if k.startswith("jedi-no-answer"))
        agree = sum(v for k, v in counts.items() if k.startswith("agree"))
        out[status] = {
            "n": n,
            "jedi_answered": answered,
            "agree": agree,
            "agreement_rate_over_answered": round(agree / answered, 4) if answered else None,
            "outcomes": dict(sorted(counts.items())),
        }
    n_all = len(rows)
    agree_all = sum(1 for r in rows if r["outcome"].startswith("agree"))
    out["all"] = {
        "n": n_all,
        "agree": agree_all,
        "agreement_rate": round(agree_all / n_all, 4) if n_all else None,
    }
    return out


def units_of(units: list[CodeUnit]) -> UnitIndex:
    """Index helper used by the script."""
    return UnitIndex.build(units)


def run_agreement(
    repos: dict[str, tuple[str, str]], total: int, seed: int
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Build each repository's graph, draw the stratified sample, ask Jedi, summarize.

    ``repos`` maps a label to (checkout directory, repo id). Returns the per-site rows and the
    summary (counts per status and outcome, agreement rates, jedi version).
    """
    import jedi

    from ril.parsing.build import BuildConfig, build_repository

    results = {
        label: build_repository(
            root, BuildConfig(repo_id=rid, with_history=False), exploratory=False
        )
        for label, (root, rid) in sorted(repos.items())
    }
    sites = draw_sites({k: v.graph for k, v in results.items()}, total, seed)
    rows: list[dict[str, str]] = []
    for label, (root, _rid) in sorted(repos.items()):
        res = results[label]
        idx = UnitIndex.build(res.parsed.units)
        extra = [os.path.join(root, d) for d in ("src",) if os.path.isdir(os.path.join(root, d))]
        project = jedi.Project(path=root, added_sys_path=extra)
        cache: dict[str, tuple[str, ast.AST]] = {}
        for site in (s for s in sites if s.repo == label):
            out = jedi_units_for(site, root, idx, project, cache)
            e = site.edge
            rows.append(
                {
                    "repo": label,
                    "site": e.site,
                    "caller": e.src,
                    "target_text": e.target_text,
                    "status": e.status,
                    "rule": e.derivation,
                    "dst_or_candidates": e.dst or "|".join(e.candidates),
                    "jedi_units": "|".join(out.units),
                    "jedi_external_or_unmapped": str(out.n_external),
                    "outcome": agreement(site, out),
                }
            )
    summary = summarize(rows)
    summary["jedi_version"] = jedi.__version__
    summary["seed"] = seed
    summary["sample_size"] = len(rows)
    return rows, summary
