"""Seeded samples of edges for inspection by reading the source, and their rendering.

Implements recovery definition (d) of ``specs/parse_one_repo.md`` / ADR-012 (a 100-edge sample
inspected by reading the source) and the sampled precision of the exploratory ``tests`` and
``configures`` edges. This module only draws the sample and prints what a reader needs; the
labels are written by whoever reads. In the first build one reader, the author of the build,
assigned all of them; no second reader has checked them yet (the label tables say so).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import os
import random
from collections.abc import Sequence

from ril.parsing.code_unit import CodeUnit
from ril.parsing.repo_graph import Edge


def edge_key(repo: str, e: Edge) -> str:
    """A stable identifier of an edge for the label table."""
    return f"{repo}|{e.type}|{e.src}|{e.site}|{e.dst or '|'.join(e.candidates)}|{e.derivation}"


def draw(
    pools: dict[tuple[str, str], list[Edge]], quotas: dict[tuple[str, str], int], seed: int
) -> list[tuple[str, str, Edge]]:
    """Draw ``quotas[(repo, stratum)]`` edges from ``pools[(repo, stratum)]`` with a seeded RNG.

    Returns (repo, stratum, edge) sorted by repo, stratum and edge order. A pool smaller than its
    quota is taken whole (the shortfall is visible in the returned length).
    """
    out: list[tuple[str, str, Edge]] = []
    for key in sorted(quotas):
        pool = sorted(pools.get(key, []), key=Edge.sort_key)
        rng = random.Random(f"{seed}:{key[0]}:{key[1]}")
        picked = rng.sample(pool, min(quotas[key], len(pool)))
        out.extend((key[0], key[1], e) for e in sorted(picked, key=Edge.sort_key))
    return out


def _lines(root: str, path: str) -> list[str]:
    try:
        with open(os.path.join(root, path), encoding="utf-8", errors="replace") as handle:
            return handle.read().split("\n")
    except OSError:
        return []


def _head(unit: CodeUnit | None, n: int = 4) -> str:
    if unit is None:
        return "(not a unit)"
    doc = (unit.docstring or "").strip().split("\n")[0][:100]
    return f"{unit.id} [{unit.unit_type}] {unit.signature[:110]}" + (f'  "{doc}"' if doc else "")


def render(
    root: str, units: dict[str, CodeUnit], e: Edge, context: int = 2, max_candidates: int = 4
) -> str:
    """Text a reader needs to judge one edge: the site with context, and the target(s)."""
    path, _, rest = e.site.partition(":")
    parts = rest.split(":")
    line = int(parts[0]) if parts and parts[0].isdigit() else 0
    out = [f"[{e.type}/{e.status}/{e.derivation}] {e.src}", f"  text: {e.target_text}"]
    src_lines = _lines(root, path)
    if line and src_lines:
        lo, hi = max(1, line - context), min(len(src_lines), line + context)
        for n in range(lo, hi + 1):
            mark = ">>" if n == line else "  "
            out.append(f"  {mark}{n:5d} {src_lines[n - 1][:140]}")
    if e.status == "resolved":
        out.append(f"  target: {_head(units.get(e.dst))}")
    elif e.candidates:
        out.append(f"  candidates ({len(e.candidates)}):")
        for c in e.candidates[:max_candidates]:
            out.append(f"    - {_head(units.get(c))}")
    return "\n".join(out)


def render_test_edge(root: str, units: dict[str, CodeUnit], e: Edge, max_lines: int = 18) -> str:
    """A ``tests`` edge: the test's first lines and the unit it is linked to."""
    t = units.get(e.src)
    body = "\n".join((t.source if t else "").split("\n")[:max_lines])
    head = f"[{e.type}/{e.derivation}] {e.src}  (call text: {e.target_text})"
    if e.status == "resolved":
        tgt = f"  linked unit: {_head(units.get(e.dst))}"
    else:
        tgt = "  linked units: " + "; ".join(_head(units.get(c)) for c in e.candidates[:4])
    return f"{head}\n{body}\n{tgt}"


def render_config_edge(root: str, units: dict[str, CodeUnit], e: Edge) -> str:
    """A ``configures`` edge: the configuration line and the unit it names."""
    path, _, rest = e.site.partition(":")
    line = int(rest.split(":")[0]) if rest else 0
    lines = _lines(root, path)
    text = lines[line - 1].strip()[:200] if line and line <= len(lines) else ""
    return (
        f"[{e.type}/{e.derivation}] {e.src}:{line}\n  line: {text}\n  matched: {e.target_text}\n"
        f"  linked unit: {_head(units.get(e.dst))}"
    )


def summarize_labels(
    rows: Sequence[dict[str, str]], stratum_key: str = "stratum"
) -> dict[str, dict[str, float | int]]:
    """Precision per stratum from rows carrying ``label`` in {correct, incorrect, unclear}.

    Precision counts ``correct`` over ``correct + incorrect``; ``unclear`` is reported, not hidden.
    A 95% Wilson interval is attached.
    """
    out: dict[str, dict[str, float | int]] = {}
    strata = sorted({r[stratum_key] for r in rows})
    for s in [*strata, "ALL"]:
        sub = [r for r in rows if s == "ALL" or r[stratum_key] == s]
        c = sum(1 for r in sub if r["label"] == "correct")
        w = sum(1 for r in sub if r["label"] == "incorrect")
        u = sum(1 for r in sub if r["label"] == "unclear")
        n = c + w
        lo, hi = wilson(c, n)
        out[s] = {
            "n": len(sub),
            "correct": c,
            "incorrect": w,
            "unclear": u,
            "precision": round(c / n, 4) if n else 0.0,
            "wilson95_low": round(lo, 4),
            "wilson95_high": round(hi, 4),
        }
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def weighted_estimates(
    rows: Sequence[dict[str, str]],
    populations: dict[tuple[str, str], int],
    seed: int = 0,
    n_boot: int = 2000,
) -> dict[str, dict[str, float]]:
    """Population-weighted shares from a stratified inspection sample, with bootstrap intervals.

    ``rows`` carry ``repo``, ``stratum`` (the recorded status), ``label`` and ``truth``;
    ``populations[(repo, status)]`` is the number of call sites in that stratum. A site is
    *in-repository* when its ``truth`` starts with ``in_repo``. Estimates (shares of all sampled
    populations' sites): the in-repository share, the share recorded ``resolved`` with a correct
    target, the share recorded ``ambiguous`` with the true target in the candidate set, and the
    recall of each over the in-repository sites. Sites whose truth depends on the environment are
    left out of numerator and denominator.
    """
    rng = random.Random(seed)
    strata = sorted({(r["repo"], r["stratum"]) for r in rows})
    by_stratum: dict[tuple[str, str], list[dict[str, str]]] = {
        k: [r for r in rows if (r["repo"], r["stratum"]) == k] for k in strata
    }

    def estimate(sample: dict[tuple[str, str], list[dict[str, str]]]) -> dict[str, float]:
        acc = {
            "all": 0.0,
            "in_repo": 0.0,
            "resolved_ok": 0.0,
            "ambiguous_ok": 0.0,
            "unresolved_in_repo": 0.0,
        }
        for key, rs in sample.items():
            if not rs:
                continue
            w = populations.get(key, 0) / len(rs)
            for r in rs:
                if r["truth"] == "environment_dependent":
                    continue
                acc["all"] += w
                in_repo = r["truth"].startswith("in_repo")
                if in_repo:
                    acc["in_repo"] += w
                if r["stratum"] == "resolved" and r["label"] == "correct" and in_repo:
                    acc["resolved_ok"] += w
                if r["stratum"] == "ambiguous" and r["label"] == "correct" and in_repo:
                    acc["ambiguous_ok"] += w
                if r["stratum"] == "unresolved" and in_repo:
                    acc["unresolved_in_repo"] += w
        n = acc["in_repo"] or 1.0
        return {
            "in_repo_share_of_sites": acc["in_repo"] / acc["all"],
            "resolved_correct_share_of_sites": acc["resolved_ok"] / acc["all"],
            "recall_resolved_over_in_repo_sites": acc["resolved_ok"] / n,
            "recall_resolved_or_ambiguous_over_in_repo_sites": (
                acc["resolved_ok"] + acc["ambiguous_ok"]
            )
            / n,
            "in_repo_sites_left_unresolved_share": acc["unresolved_in_repo"] / n,
        }

    point = estimate(by_stratum)
    boots: dict[str, list[float]] = {k: [] for k in point}
    for _ in range(n_boot):
        resampled = {k: [rng.choice(v) for _ in v] for k, v in by_stratum.items()}
        for name, value in estimate(resampled).items():
            boots[name].append(value)
    out: dict[str, dict[str, float]] = {}
    for name, value in point.items():
        b = sorted(boots[name])
        out[name] = {
            "estimate": round(value, 4),
            "boot95_low": round(b[int(0.025 * len(b))], 4),
            "boot95_high": round(b[int(0.975 * len(b)) - 1], 4),
        }
    return out
