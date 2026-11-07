# ruff: noqa: E501  (table rows are one line each)
"""Analysis of the finished RQ3 pilot from stored data only. Implements ``docs/RQ3_PILOT.md`` (D104)
and the analysis list of decision D109 (``docs/experiments/B.md`` E-RQ3-PILOT-RESULT).

Inputs are the pilot's call log and hashed reply files, its prepared prompts, and the stored
per-query assembly rows (``results/rq3/assembly_gold_*``), which are joined to the prompts by the
SHA-256 of the context. No model is called and no repository is read. ``unusable`` is exactly what
``ril.agent.providers.patch_format.parse_edits`` returns as a fault (plus the log's ``blocked``);
this module only refines the fault into finer classes. Intervals: Wilson for shares, paired
percentile bootstrap over instances for differences (10,000 resamples, fixed seed).
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from ril.agent.providers.patch_format import parse_edits
from ril.evaluation.stats import exact_mcnemar_p

Row = dict[str, Any]
DRAWS = 10_000
SEED = 0
EXCERPTS = "## Repository excerpts\n\n"
_HEADER = re.compile(r"^### (\S+?):(\d+)-(\d+) .*\(rank \d+\)$", re.MULTILINE)
_DECLINE = re.compile(
    r"\b(cannot|can't|can not|unable to|no (valid |code |edit |further )?(edit|change|block|bug)"
    r"|not (enough|possible)|(do|does) not (contain|include|have|show)|don't have|not provided)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------- statistics


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float, float]:
    """``(share, low, high)``; NaN for an empty sample."""
    if n <= 0:
        return (math.nan, math.nan, math.nan)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (p, centre - half, centre + half)


def boot_mean(
    values: npt.ArrayLike, draws: int = DRAWS, seed: int = SEED
) -> tuple[float, float, float]:
    """Mean and percentile interval over resampled entries (entries are instances)."""
    v = np.asarray(values, dtype=np.float64)
    if v.size == 0:
        return (math.nan, math.nan, math.nan)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, v.size, size=(draws, v.size))].mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return (float(v.mean()), float(lo), float(hi))


def boot_diff(
    a: npt.ArrayLike, b: npt.ArrayLike, draws: int = DRAWS, seed: int = SEED
) -> tuple[float, float, float]:
    """Mean of ``a - b`` with the same instances resampled for both."""
    x = np.asarray(a, dtype=np.float64)
    y = np.asarray(b, dtype=np.float64)
    if x.shape != y.shape:
        raise ValueError("paired samples differ in length")
    return boot_mean(x - y, draws, seed)


def quantile(values: Sequence[float], q: float) -> float:
    """Nearest-rank quantile, as in ``ril.agent.providers.report``."""
    if not values:
        return math.nan
    s = sorted(values)
    return s[min(len(s) - 1, max(0, math.ceil(q * len(s)) - 1))]


# ---------------------------------------------------------------------------- loading


@dataclass(frozen=True)
class Pilot:
    """Everything read from disk: call rows, reply texts, items, prompts, gold rows."""

    calls: list[Row]
    reply_text: dict[str, str]
    items: dict[tuple[str, str], Row]
    prompts: dict[tuple[str, str], str]
    gold: dict[tuple[str, str], Row]


def load_pilot(log_dir: Path, prepared_dir: Path, gold_rows_csv: Path) -> Pilot:
    calls = [json.loads(x) for x in (log_dir / "calls.jsonl").read_text("utf-8").splitlines() if x]
    texts = {
        r["response_sha256"]: (log_dir / "responses" / f"{r['response_sha256']}.txt").read_text(
            "utf-8"
        )
        for r in calls
        if r["response_sha256"]
    }
    items: dict[tuple[str, str], Row] = {}
    prompts: dict[tuple[str, str], str] = {}
    for line in (prepared_dir / "items.jsonl").read_text("utf-8").splitlines():
        if not line:
            continue
        it = json.loads(line)
        key = (it["instance_id"], it["arm"])
        items[key] = it
        prompts[key] = (prepared_dir / "prompts" / f"{it['prompt_sha256']}.txt").read_text("utf-8")
    by_hash: dict[tuple[str, str], Row] = {}
    with gold_rows_csv.open(newline="", encoding="utf-8") as fh:
        for g in csv.DictReader(fh):
            if g["level"] == "L2" and g["budget"] == "8000":
                by_hash[(g["context_sha256"], g["reading"])] = g
    gold: dict[tuple[str, str], Row] = {}
    for key, it in items.items():
        f = by_hash[(it["context_sha256"], "units_all")]
        u = by_hash[(it["context_sha256"], "units_all_nomod")]
        gold[key] = {
            "n_gold_files": int(f["n_gold_files"]),
            "files_in": int(f["files_in"]),
            "n_gold_units": int(u["n_gold_units"]),
            "units_in": int(u["units_in"]),
        }
    return Pilot(calls, texts, items, prompts, gold)


# ---------------------------------------------------------------------------- fault classes


def excerpts_of(prompt: str) -> dict[str, str]:
    """Excerpt text per file path (several blocks of one file are joined), from the prompt only."""
    body = prompt[prompt.index(EXCERPTS) + len(EXCERPTS) :]
    marks = list(_HEADER.finditer(body))
    out: dict[str, str] = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        out[m.group(1)] = out.get(m.group(1), "") + "\n" + body[m.end() : end]
    return out


def _squash(text: str) -> str:
    return " ".join(text.split())


def classify_reply(row: Row, text: str, shown_paths: Sequence[str]) -> str:
    """Finer fault class of one reply; ``ok`` when the log calls it usable.

    Rules, in order: finish reason, empty text, then the log's own code refined by the stored
    text. ``decline_prose`` is a keyword reading (labelled so wherever it is reported).
    """
    code = str(row["format_error"])
    finish = str(row["finish_reason"])
    if code == "" and row["patch_ok"]:
        return "ok"
    if code == "blocked" or finish in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "RECITATION"):
        return "blocked"
    if finish == "MAX_TOKENS":
        return "truncated_at_output_limit"
    if finish == "MALFORMED_FUNCTION_CALL":
        return "malformed_function_call"
    if not text.strip():
        return "empty_text"
    if code == "no_edit_block":
        if "<<<<<<< SEARCH" in text:
            return "markers_without_file_line"
        return "decline_prose" if _DECLINE.search(text) else "other_prose"
    if code == "path_not_in_context":
        paths = {p.removeprefix("./") for p in shown_paths}
        named = [m.strip().strip("`") for m in re.findall(r"^\s*FILE:(.*)$", text, re.MULTILINE)]
        if any(n.removeprefix("./").removeprefix("a/").removeprefix("b/") in paths for n in named):
            return "path_prefix_variant_of_shown_path"
        shown_base = {p.rsplit("/", 1)[-1] for p in paths}
        if any(n.rsplit("/", 1)[-1] in shown_base for n in named):
            return "path_wrong_directory_same_file_name"
        return "path_not_shown"
    return code or "unknown"


def search_check(text: str, prompt: str) -> dict[str, int]:
    """For a reply with edit blocks, how many SEARCH texts occur in the excerpts supplied.

    ``anywhere``: exact substring of the excerpt section; ``in_named_file``: exact substring of
    the excerpts of the file the block names; ``squashed``: equal after collapsing whitespace.
    Uses the parser unchanged with no path filter, so blocks of a ``path_not_in_context`` reply
    are counted too.
    """
    edits, _ = parse_edits(text, None)
    files = excerpts_of(prompt)
    whole = "\n".join(files.values())
    flat = _squash(whole)
    out = {"blocks": len(edits), "anywhere": 0, "in_named_file": 0, "squashed": 0}
    for e in edits:
        if e.old in whole:
            out["anywhere"] += 1
        if e.old in files.get(e.path, ""):
            out["in_named_file"] += 1
        if _squash(e.old) in flat:
            out["squashed"] += 1
    return out


# ---------------------------------------------------------------------------- unit table


def unit_table(p: Pilot) -> list[Row]:
    """One row per (instance, arm, run): calls, tokens, first and final usability, classes."""
    by: dict[tuple[str, str, int], list[Row]] = {}
    for r in p.calls:
        by.setdefault((r["instance_id"], r["arm"], int(r["run_index"])), []).append(r)
    rows: list[Row] = []
    for (iid, arm, run), rs in sorted(by.items()):
        rs.sort(key=lambda r: int(r["attempt"]))
        shown = p.items[(iid, arm)]["paths"]
        classes = [classify_reply(r, p.reply_text.get(r["response_sha256"], ""), shown) for r in rs]
        final = rs[-1]
        usable = bool(final["patch_ok"])
        chk = (
            search_check(p.reply_text[final["response_sha256"]], p.prompts[(iid, arm)])
            if usable
            else {"blocks": 0, "anywhere": 0, "in_named_file": 0, "squashed": 0}
        )
        g = p.gold[(iid, arm)]
        rows.append(
            {
                "instance_id": iid,
                "arm": arm,
                "run": run,
                "calls": len(rs),
                "input_tokens": sum(int(r["input_tokens"]) for r in rs),
                "output_tokens": sum(int(r["output_tokens"]) for r in rs),
                "thought_tokens": sum(int(r["thought_tokens"]) for r in rs),
                "first_input_tokens": int(rs[0]["input_tokens"]),
                "first_ok": bool(rs[0]["patch_ok"]),
                "final_ok": usable,
                "first_class": classes[0],
                "final_class": classes[-1],
                "rescued": (not rs[0]["patch_ok"]) and usable,
                "first_response": rs[0]["response_sha256"],
                "final_response": final["response_sha256"],
                "edits_sha256": final["edits_sha256"],
                "blocks": chk["blocks"],
                "blocks_search_anywhere": chk["anywhere"],
                "blocks_search_in_named_file": chk["in_named_file"],
                "blocks_search_squashed": chk["squashed"],
                "gold_file_in_context": g["files_in"] > 0,
                "gold_unit_in_context": g["units_in"] > 0,
                "has_gold_file": g["n_gold_files"] > 0,
                "has_gold_unit": g["n_gold_units"] > 0,
            }
        )
    return rows


# ---------------------------------------------------------------------------- tables


def _arms(rows: Sequence[Row]) -> list[str]:
    return sorted({r["arm"] for r in rows})


def _fmt(x: float, nd: int = 3) -> str:
    return "" if isinstance(x, float) and math.isnan(x) else f"{x:.{nd}f}"


def _instance_vectors(units: Sequence[Row], key: str, arm: str) -> dict[str, float]:
    """Mean over the runs of one boolean or numeric column, per instance, for one arm."""
    acc: dict[str, list[float]] = {}
    for r in units:
        if r["arm"] == arm:
            acc.setdefault(r["instance_id"], []).append(float(r[key]))
    return {i: sum(v) / len(v) for i, v in acc.items()}


def cost_table(calls: Sequence[Row], units: Sequence[Row]) -> list[Row]:
    """Analysis 1: calls and tokens per unit and per instance, latency, 429 / 5xx, by first stage."""
    out: list[Row] = []
    for arm in [*_arms(units), "all"]:
        u = [r for r in units if arm in ("all", r["arm"])]
        c = [r for r in calls if arm in ("all", r["arm"])]
        inst: dict[str, list[Row]] = {}
        for r in u:
            inst.setdefault(r["instance_id"], []).append(r)
        per_unit = [float(r["calls"]) for r in u]
        lat = [float(r["latency_s"]) for r in c]
        row: Row = {
            "arm": arm,
            "units": len(u),
            "instances": len(inst),
            "calls": len(c),
            "calls_per_unit": boot_mean(
                [sum(r["calls"] for r in v) / len(v) for v in inst.values()]
            ),
            "calls_per_instance_all_units": boot_mean(
                [sum(r["calls"] for r in v) for v in inst.values()]
            ),
            "max_calls_per_unit": int(max(per_unit)),
            "input_tokens_per_unit_mean": float(np.mean([r["input_tokens"] for r in u])),
            "output_tokens_per_unit_mean": float(np.mean([r["output_tokens"] for r in u])),
            "thought_tokens_total": sum(int(r["thought_tokens"]) for r in c),
            "input_tokens_per_call_mean": float(np.mean([r["input_tokens"] for r in c])),
            "output_tokens_per_call_mean": float(np.mean([r["output_tokens"] for r in c])),
            "latency_p50": quantile(lat, 0.50),
            "latency_p95": quantile(lat, 0.95),
            "latency_p99": quantile(lat, 0.99),
            "http_429": sum(int(r["n_429"]) for r in c),
            "http_5xx": sum(int(r["n_5xx"]) for r in c),
            "retries": sum(int(r["retries"]) for r in c),
            "http_non200": sum(1 for r in c if int(r["http_status"]) != 200),
        }
        out.append(row)
    return out


def fault_tables(units: Sequence[Row], calls: Sequence[Row], p: Pilot) -> dict[str, list[Row]]:
    """Analysis 2: usability by arm and run, fault classes, rescue counts, edit-in-context check."""
    usab: list[Row] = []
    for arm in [*_arms(units), "all"]:
        for run in ["all", *sorted({r["run"] for r in units})]:
            u = [r for r in units if arm in ("all", r["arm"]) and run in ("all", r["run"])]
            n = len(u)
            first_bad = sum(not r["first_ok"] for r in u)
            final_bad = sum(not r["final_ok"] for r in u)
            rescued = sum(1 for r in u if r["rescued"])
            usab.append(
                {
                    "arm": arm,
                    "run": run,
                    "units": n,
                    "first_unusable": first_bad,
                    "first_unusable_share": wilson(first_bad, n),
                    "final_unusable": final_bad,
                    "final_unusable_share": wilson(final_bad, n),
                    "rescued_by_followup": rescued,
                    "not_rescued": first_bad - rescued,
                }
            )
    classes: Counter[tuple[str, str, str]] = Counter()
    for r in units:
        classes[(r["arm"], "first_reply", r["first_class"])] += 1
        classes[(r["arm"], "final_after_followups", r["final_class"])] += 1
    for r in calls:
        shown = p.items[(r["instance_id"], r["arm"])]["paths"]
        c = classify_reply(r, p.reply_text.get(r["response_sha256"], ""), shown)
        classes[(r["arm"], f"call_attempt_{int(r['attempt'])}", c)] += 1
    cls_rows = [
        {"arm": a, "stage": s, "class": c, "count": n} for (a, s, c), n in sorted(classes.items())
    ]
    follow: list[Row] = []
    for att in (1, 2):
        cs = [r for r in calls if int(r["attempt"]) == att]
        ok = sum(bool(r["patch_ok"]) for r in cs)
        follow.append(
            {"attempt": att, "calls": len(cs), "usable": ok, "share": wilson(ok, len(cs))}
        )
    final_ok = [r for r in units if r["final_ok"]]
    chk = {
        "usable_units": len(final_ok),
        "with_blocks": sum(r["blocks"] > 0 for r in final_ok),
        "blocks": sum(r["blocks"] for r in final_ok),
        "blocks_search_anywhere": sum(r["blocks_search_anywhere"] for r in final_ok),
        "blocks_search_in_named_file": sum(r["blocks_search_in_named_file"] for r in final_ok),
        "blocks_search_squashed_only": sum(
            r["blocks_search_squashed"] - r["blocks_search_anywhere"] for r in final_ok
        ),
        "units_every_block_exact_in_context": sum(
            1 for r in final_ok if r["blocks_search_anywhere"] == r["blocks"]
        ),
        "units_some_block_not_in_context": sum(
            1 for r in final_ok if r["blocks_search_anywhere"] < r["blocks"]
        ),
    }
    return {"usability": usab, "fault_classes": cls_rows, "followups": follow, "edit_check": [chk]}


def arm_contrast_tables(units: Sequence[Row], p: Pilot) -> dict[str, list[Row]]:
    """Analysis 3: why the first stages differ in usability (strata, discordance, size, bytes)."""
    arms = _arms(units)
    a0, a1 = arms[0], arms[1]  # bm25, rrf
    strata: list[Row] = []
    for key in ("gold_file_in_context", "gold_unit_in_context"):
        for arm in arms:
            for val in (True, False):
                u = [r for r in units if r["arm"] == arm and r[key] == val]
                n = len(u)
                fb = sum(not r["first_ok"] for r in u)
                lb = sum(not r["final_ok"] for r in u)
                strata.append(
                    {
                        "stratum": key,
                        "value": val,
                        "arm": arm,
                        "units": n,
                        "first_unusable_share": wilson(fb, n),
                        "final_unusable_share": wilson(lb, n),
                    }
                )
    discord: list[Row] = []
    inst_ids = sorted({r["instance_id"] for r in units})
    for key, label in (("first_ok", "first_reply"), ("final_ok", "after_followups")):
        by = {(r["instance_id"], r["arm"], r["run"]): r for r in units}
        b = c = both = neither = 0
        for iid in inst_ids:
            for run in sorted({r["run"] for r in units}):
                x, y = by[(iid, a0, run)][key], by[(iid, a1, run)][key]
                b += (not x) and y  # arm0 unusable, arm1 usable
                c += x and (not y)
                both += (not x) and (not y)
                neither += x and y
        v0 = _instance_vectors(units, key, a0)
        v1 = _instance_vectors(units, key, a1)
        diff = boot_diff([1 - v0[i] for i in inst_ids], [1 - v1[i] for i in inst_ids])
        discord.append(
            {
                "reading": label,
                "pairs": len(inst_ids) * 2,
                f"only_{a0}_unusable": b,
                f"only_{a1}_unusable": c,
                "both_unusable": both,
                "both_usable": neither,
                "discordance": (b + c) / (len(inst_ids) * 2),
                "exact_mcnemar_p_runs_as_pairs": exact_mcnemar_p(b, c),
                f"unusable_{a0}_minus_{a1}": diff,
            }
        )
    both_gold: list[Row] = []
    for key in ("gold_file_in_context", "gold_unit_in_context"):
        for cond, label in ((True, "both_arms_have_it"), (False, "neither_arm_has_it")):
            ids = [
                i for i in inst_ids if all(r[key] == cond for r in units if r["instance_id"] == i)
            ]
            for rk, rlab in (("first_ok", "first"), ("final_ok", "final")):
                v0 = _instance_vectors(units, rk, a0)
                v1 = _instance_vectors(units, rk, a1)
                both_gold.append(
                    {
                        "stratum": key,
                        "instances": label,
                        "n_instances": len(ids),
                        "reading": rlab,
                        f"unusable_{a0}_minus_{a1}": boot_diff(
                            [1 - v0[i] for i in ids], [1 - v1[i] for i in ids]
                        )
                        if ids
                        else (math.nan,) * 3,
                    }
                )
    size: list[Row] = []
    for arm in arms:
        its = [v for (i, a), v in p.items.items() if a == arm]
        pr = [p.prompts[(i, a)] for (i, a) in p.items if a == arm]
        ex = [excerpts_of(t) for t in pr]
        test_share = [
            sum(len(t) for f, t in e.items() if "test" in f.lower())
            / max(1, sum(len(t) for t in e.values()))
            for e in ex
        ]
        size.append(
            {
                "arm": arm,
                "prompts": len(pr),
                "input_tokens_first_call_mean": float(
                    np.mean([r["first_input_tokens"] for r in units if r["arm"] == arm])
                ),
                "input_tokens_first_call_min": min(
                    r["first_input_tokens"] for r in units if r["arm"] == arm
                ),
                "input_tokens_first_call_max": max(
                    r["first_input_tokens"] for r in units if r["arm"] == arm
                ),
                "prompt_chars_mean": float(np.mean([len(t) for t in pr])),
                "files_in_context_mean": float(np.mean([len(e) for e in ex])),
                "excerpt_chars_in_test_paths_share_mean": float(np.mean(test_share)),
                "context_hashes_distinct": len({v["context_sha256"] for v in its}),
            }
        )
    ids0 = {i: p.items[(i, a0)] for i in inst_ids}
    ids1 = {i: p.items[(i, a1)] for i in inst_ids}
    head_equal = sum(
        1
        for i in inst_ids
        if p.prompts[(i, a0)][: p.prompts[(i, a0)].index(EXCERPTS)]
        == p.prompts[(i, a1)][: p.prompts[(i, a1)].index(EXCERPTS)]
    )
    byte_rows = [
        {
            "instances": len(inst_ids),
            "same_issue_hash": sum(
                ids0[i]["issue_sha256"] == ids1[i]["issue_sha256"] for i in inst_ids
            ),
            "same_text_before_excerpts": head_equal,
            "same_template_version": sum(
                ids0[i]["template_version"] == ids1[i]["template_version"] for i in inst_ids
            ),
            "same_budget": sum(ids0[i]["budget"] == ids1[i]["budget"] for i in inst_ids),
            "same_context_hash": sum(
                ids0[i]["context_sha256"] == ids1[i]["context_sha256"] for i in inst_ids
            ),
        }
    ]
    # how much of the usability is a property of the instance
    inst_rows: list[Row] = []
    for arm in arms:
        v = _instance_vectors(units, "final_ok", arm)
        inst_rows.append(
            {
                "arm": arm,
                "instances": len(v),
                "both_runs_usable": sum(x == 1.0 for x in v.values()),
                "one_run_usable": sum(x == 0.5 for x in v.values()),
                "no_run_usable": sum(x == 0.0 for x in v.values()),
            }
        )
    both_arms_fail = sum(
        1 for i in inst_ids if all(not r["final_ok"] for r in units if r["instance_id"] == i)
    )
    inst_rows.append(
        {
            "arm": "all four units unusable",
            "instances": len(inst_ids),
            "no_run_usable": both_arms_fail,
        }
    )
    return {
        "strata": strata,
        "discordance": discord,
        "same_stratum": both_gold,
        "size": size,
        "bytes": byte_rows,
        "instance_level": inst_rows,
    }


def standardised_gap(
    units: Sequence[Row], stratum: str, outcome: str, draws: int = DRAWS, seed: int = SEED
) -> dict[str, Any]:
    """Unusable-rate gap (first arm minus second) before and after standardising to the second
    arm's mix of strata (gold present or absent in the arm's own context).

    The first arm's rate is recomputed inside each stratum and reweighted by the second arm's
    share of units in that stratum, so what is left is the part of the gap not explained by how
    often the stratum occurs. Intervals resample instances (both arms, both runs together).
    """
    arms = _arms(units)
    ids = sorted({r["instance_id"] for r in units})
    pos = {i: k for k, i in enumerate(ids)}
    # cells[arm][stratum] -> (units, unusable) per instance
    cell = np.zeros((2, 2, len(ids), 2))
    for r in units:
        a = arms.index(r["arm"])
        cell[a, int(bool(r[stratum])), pos[r["instance_id"]]] += (1.0, float(not r[outcome]))

    def gap(w: npt.NDArray[np.float64]) -> tuple[float, float, float]:
        tot = (cell * w[None, None, :, None]).sum(axis=2)  # arm, stratum, (n, bad)
        raw = tot[0, :, 1].sum() / tot[0, :, 0].sum() - tot[1, :, 1].sum() / tot[1, :, 0].sum()
        share = tot[1, :, 0] / tot[1, :, 0].sum()
        rate0 = tot[0, :, 1] / np.maximum(tot[0, :, 0], 1)
        std = float((rate0 * share).sum() - tot[1, :, 1].sum() / tot[1, :, 0].sum())
        return float(raw), std, 1.0 - (std / raw if raw else math.nan)

    raw, std, explained = gap(np.ones(len(ids)))
    rng = np.random.default_rng(seed)
    res = np.array(
        [
            gap(np.bincount(rng.integers(0, len(ids), len(ids)), minlength=len(ids)).astype(float))
            for _ in range(draws)
        ]
    )
    lo = np.nanquantile(res, 0.025, axis=0)
    hi = np.nanquantile(res, 0.975, axis=0)
    return {
        "stratum": stratum,
        "reading": outcome,
        "raw_gap": (raw, float(lo[0]), float(hi[0])),
        "gap_after_standardising": (std, float(lo[1]), float(hi[1])),
        "share_of_gap_explained": explained,
    }


def repo_of(instance_id: str) -> str:
    """``owner__name`` of an instance id (ids of the Pro set carry an ``instance_`` prefix)."""
    org, rest = instance_id.removeprefix("instance_").split("__", 1)
    return f"{org}__{rest.split('-')[0]}"


def repo_table(units: Sequence[Row]) -> list[Row]:
    """Unusable shares by repository (instance id prefix) and first stage, with n."""
    out: list[Row] = []
    for repo in sorted({repo_of(r["instance_id"]) for r in units}):
        for arm in _arms(units):
            u = [r for r in units if r["arm"] == arm and repo_of(r["instance_id"]) == repo]
            n = len(u)
            out.append(
                {
                    "repository": repo,
                    "arm": arm,
                    "units": n,
                    "instances": n // 2,
                    "first_unusable_share": wilson(sum(not r["first_ok"] for r in u), n),
                    "final_unusable_share": wilson(sum(not r["final_ok"] for r in u), n),
                    "gold_file_in_context_share": wilson(
                        sum(bool(r["gold_file_in_context"]) for r in u), n
                    ),
                }
            )
    return out


REFUSAL_LIKE = ("decline_prose", "other_prose", "path_not_shown")


def class_groups(units: Sequence[Row]) -> list[Row]:
    """Final unusable units grouped: reply is prose or names an unseen file, versus a format fault."""
    out: list[Row] = []
    for arm in [*_arms(units), "all"]:
        u = [r for r in units if arm in ("all", r["arm"]) and not r["final_ok"]]
        n_all = sum(1 for r in units if arm in ("all", r["arm"]))
        ref = sum(r["final_class"] in REFUSAL_LIKE for r in u)
        empty = sum(r["final_class"] == "empty_text" for r in u)
        out.append(
            {
                "arm": arm,
                "units": n_all,
                "final_unusable": len(u),
                "prose_or_unseen_file": ref,
                "empty_text": empty,
                "other_format_fault": len(u) - ref - empty,
                "prose_or_unseen_file_share_of_all_units": wilson(ref, n_all),
            }
        )
    return out


def edit_check_by_arm(units: Sequence[Row]) -> list[Row]:
    """Blocks of usable final replies whose SEARCH text is, or is not, in the excerpts shown."""
    out: list[Row] = []
    for arm in [*_arms(units), "all"]:
        u = [r for r in units if arm in ("all", r["arm"]) and r["final_ok"]]
        blocks = sum(r["blocks"] for r in u)
        exact = sum(r["blocks_search_anywhere"] for r in u)
        out.append(
            {
                "arm": arm,
                "usable_units": len(u),
                "blocks": blocks,
                "exact_in_excerpts": wilson(exact, blocks),
                "exact_in_named_file": wilson(
                    sum(r["blocks_search_in_named_file"] for r in u), blocks
                ),
                "only_after_whitespace_squash": sum(
                    r["blocks_search_squashed"] - r["blocks_search_anywhere"] for r in u
                ),
                "units_with_a_block_not_in_excerpts": wilson(
                    sum(r["blocks_search_anywhere"] < r["blocks"] for r in u), len(u)
                ),
            }
        )
    return out


def rescue_table(units: Sequence[Row]) -> list[Row]:
    """Follow-up outcome of units whose first reply was unusable, by class of that first reply
    and by whether a gold unit was in the context; plus how often a rescued unit's edit text is
    found in the excerpts, against units usable on the first try."""
    out: list[Row] = []
    bad = [r for r in units if not r["first_ok"]]
    groups: list[tuple[str, list[Row]]] = [("all", bad)]
    for cls in sorted({r["first_class"] for r in bad}):
        groups.append((f"first_class={cls}", [r for r in bad if r["first_class"] == cls]))
    for val in (True, False):
        groups.append(
            (f"gold_unit_in_context={val}", [r for r in bad if r["gold_unit_in_context"] == val])
        )
    for name, g in groups:
        out.append(
            {
                "group": name,
                "units_first_unusable": len(g),
                "rescued": wilson(sum(1 for r in g if r["rescued"]), len(g)),
            }
        )
    for name, g in (
        ("usable_on_first_try", [r for r in units if r["first_ok"]]),
        ("rescued_by_followup", [r for r in units if r["rescued"]]),
    ):
        blocks = sum(r["blocks"] for r in g)
        exact = sum(r["blocks_search_anywhere"] for r in g)
        out.append(
            {
                "group": f"edit_text_in_excerpts: {name}",
                "units_first_unusable": len(g),
                "rescued": wilson(exact, blocks),
            }
        )
    return out


def extrapolate_to_executable(units: Sequence[Row], coverage_csv: Path) -> list[Row]:
    """Estimate: the pilot's unusable shares within strata, reweighted to the gold-in-context
    shares of the 377 executable instances (D108, L2, 8,000). Not a measurement on those
    instances: it assumes the within-stratum rates carry over."""
    cover: dict[str, dict[str, float]] = {}
    with coverage_csv.open(newline="", encoding="utf-8") as fh:
        for c in csv.DictReader(fh):
            if c["level"] == "L2" and c["budget"] == "8000" and c["view"] == "file":
                cover[c["arm"]] = {
                    "gold_file_in_context": float(c["pct_gold_file_in_context"]) / 100,
                    "gold_unit_in_context": float(c["pct_gold_unit_in_context"]) / 100,
                }
    out: list[Row] = []
    for arm in _arms(units):
        for st in ("gold_file_in_context", "gold_unit_in_context"):
            for oc in ("first_ok", "final_ok"):
                rate = {
                    v: [r for r in units if r["arm"] == arm and bool(r[st]) == v]
                    for v in (True, False)
                }
                w = cover[arm][st]
                est = sum(
                    wt * sum(not r[oc] for r in rate[v]) / max(1, len(rate[v]))
                    for v, wt in ((True, w), (False, 1 - w))
                )
                out.append(
                    {
                        "arm": arm,
                        "stratum": st,
                        "reading": oc,
                        "pilot_share_stratum_present": len(rate[True])
                        / (len(rate[True]) + len(rate[False])),
                        "executable_share_stratum_present": w,
                        "estimated_unusable_share_executable": est,
                        "kind": "estimate",
                    }
                )
    return out


def run_to_run(units: Sequence[Row]) -> list[Row]:
    """Analysis 4: agreement of the two runs of the same (instance, arm) at temperature 0."""
    out: list[Row] = []
    for arm in [*_arms(units), "all"]:
        by: dict[tuple[str, str], dict[int, Row]] = {}
        for r in units:
            if arm in ("all", r["arm"]):
                by.setdefault((r["instance_id"], r["arm"]), {})[int(r["run"])] = r
        pairs = [(v[0], v[1]) for v in by.values() if 0 in v and 1 in v]
        both = [(a, b) for a, b in pairs if a["final_ok"] and b["final_ok"]]
        n = len(pairs)
        same_first = sum(a["first_response"] == b["first_response"] for a, b in pairs)
        same_final = sum(a["final_response"] == b["final_response"] for a, b in pairs)
        same_use = sum(a["final_ok"] == b["final_ok"] for a, b in pairs)
        same_first_use = sum(a["first_ok"] == b["first_ok"] for a, b in pairs)
        same_edit = sum(a["edits_sha256"] == b["edits_sha256"] for a, b in both)
        out.append(
            {
                "arm": arm,
                "pairs": n,
                "same_first_reply_text": wilson(same_first, n),
                "same_final_reply_text": wilson(same_final, n),
                "same_first_reply_usability": wilson(same_first_use, n),
                "same_final_usability": wilson(same_use, n),
                "runs_disagree_on_final_usability": wilson(n - same_use, n),
                "both_usable_pairs": len(both),
                "same_edits_given_both_usable": wilson(same_edit, len(both)),
            }
        )
    return out


def retrieval_rows(units: Sequence[Row], p: Pilot, dev_summary_csv: Path) -> list[Row]:
    """Analysis 5: gold in context for the 100 pilot instances next to the dev cells (8,000, L2)."""
    out: list[Row] = []
    for arm in sorted({a for _, a in p.items}):
        g = [v for (i, a), v in p.gold.items() if a == arm]
        gf = [v for v in g if v["n_gold_files"] > 0]
        gu = [v for v in g if v["n_gold_units"] > 0]
        out.append(
            {
                "source": "pilot_100",
                "arm": arm,
                "queries_file_level": len(gf),
                "file_share_mean_pct": 100
                * float(np.mean([v["files_in"] / v["n_gold_files"] for v in gf])),
                "no_gold_file_pct": 100 * float(np.mean([v["files_in"] == 0 for v in gf])),
                "queries_unit_level": len(gu),
                "unit_share_mean_pct": 100
                * float(np.mean([v["units_in"] / v["n_gold_units"] for v in gu])),
                "no_gold_unit_pct": 100 * float(np.mean([v["units_in"] == 0 for v in gu])),
            }
        )
        fi = boot_mean([float(v["files_in"] == 0) for v in gf])
        out[-1]["no_gold_file_boot_pct"] = tuple(100 * x for x in fi)
    with dev_summary_csv.open(newline="", encoding="utf-8") as fh:
        for s in csv.DictReader(fh):
            if (
                s["group"] == "dev"
                and s["level"] == "L2"
                and s["budget"] == "8000"
                and s["scope"] == "matched"
                and s["reading"] in ("units_all", "units_all_nomod")
            ):
                out.append(
                    {
                        "source": f"dev_matched_{s['reading']}",
                        "arm": s["first_stage"],
                        "queries_file_level": int(s["queries"]),
                        "file_share_mean_pct": float(s["file_share"]),
                        "no_gold_file_pct": float(s["no_gold_file"]),
                        "unit_share_mean_pct": float(s["unit_share"]),
                    }
                )
    return out


def cost_grid(
    units: Sequence[Row],
    calls: Sequence[Row],
    n_instances: int = 377,
    per_day: Sequence[int] = (450, 500),
    tpm_effective: int = 225_000,
    rpm_effective: int = 13,
) -> dict[str, list[Row]]:
    """Analysis 6: cost of the full runs from the measured rates (everything here is estimated)."""
    inst: dict[str, list[Row]] = {}
    for r in units:
        inst.setdefault(r["instance_id"], []).append(r)
    cpu = boot_mean([sum(r["calls"] for r in v) / len(v) for v in inst.values()])
    in_call = float(np.mean([r["input_tokens"] for r in calls]))
    out_call = float(np.mean([r["output_tokens"] for r in calls]))
    arm_run = [
        {
            "calls_per_unit": cpu,
            "calls_per_arm_run_377": tuple(n_instances * x for x in cpu),
            "input_tokens_per_arm_run_mean": n_instances * cpu[0] * in_call,
            "output_tokens_per_arm_run_mean": n_instances * cpu[0] * out_call,
            "input_tokens_per_call_mean": in_call,
            "output_tokens_per_call_mean": out_call,
            "tokens_per_min_at_13_rpm": rpm_effective * in_call,
            "tokens_per_min_limit_effective": tpm_effective,
            "requests_per_min_limit_effective": rpm_effective,
        }
    ]
    grids = [
        ("arm-runs 1", 1),
        ("arm-runs 2", 2),
        ("arm-runs 3", 3),
        ("arm-runs 4", 4),
        ("arm-runs 6", 6),
        ("2 arms x 1 run (RAW vs untrained encoder)", 2),
        ("2 arms x 2 runs", 4),
        ("2 arms x 3 runs", 6),
        ("4 arms x 1 run (RAW, untrained encoder, BM25, RRF)", 4),
        ("4 arms x 2 runs", 8),
        ("4 arms x 3 runs", 12),
    ]
    rows: list[Row] = []
    for name, k in grids:
        calls_mid = k * n_instances * cpu[0]
        calls_lo = k * n_instances * cpu[1]
        calls_hi = k * n_instances * cpu[2]
        row: Row = {
            "grid": name,
            "arm_runs": k,
            "calls": (calls_mid, calls_lo, calls_hi),
            "input_tokens_total": k * n_instances * cpu[0] * in_call,
        }
        for d in per_day:
            row[f"days_at_{d}"] = (
                math.ceil(calls_mid / d),
                math.ceil(calls_lo / d),
                math.ceil(calls_hi / d),
            )
        row["minutes_of_calls_at_13_rpm"] = calls_mid / rpm_effective
        rows.append(row)
    return {"per_arm_run": arm_run, "grids": rows}


def power_context(units: Sequence[Row], n: int = 377) -> list[Row]:
    """Analysis 7: the placeholder table at ``n`` with the pilot's discordances beside it."""
    from ril.analysis.rq3_power import DISCORDANCES, build_rows

    rows: list[Row] = [
        {
            "kind": "placeholder_discordance",
            "discordance": d,
            "n": n,
            "mde_exact_points": r.mde_exact,
        }
        for d in DISCORDANCES
        for r in build_rows((n,), (d,))
    ]
    arms = _arms(units)
    ids = sorted({r["instance_id"] for r in units})
    by = {(r["instance_id"], r["arm"], r["run"]): r for r in units}
    for label, key in (
        ("pilot usability, final, pairs = instance x run", "final_ok"),
        ("pilot usability, first reply", "first_ok"),
        ("pilot gold file in context, pairs = instance x run", "gold_file_in_context"),
        ("pilot gold unit in context", "gold_unit_in_context"),
    ):
        disc = sum(
            by[(i, arms[0], k)][key] != by[(i, arms[1], k)][key] for i in ids for k in (0, 1)
        )
        rows.append(
            {
                "kind": f"pilot (not resolved rate): {label}",
                "discordance": disc / (2 * len(ids)),
                "n": 2 * len(ids),
                "mde_exact_points": "",
            }
        )
    return rows


# ---------------------------------------------------------------------------- output


def flatten(row: Mapping[str, Any]) -> dict[str, str]:
    """Tuples ``(value, low, high)`` become three columns; floats are rounded."""
    out: dict[str, str] = {}
    for k, v in row.items():
        if isinstance(v, tuple):
            names = ("", "_lo", "_hi")
            for nme, x in zip(names, v, strict=False):
                out[f"{k}{nme}"] = _fmt(float(x), 4) if isinstance(x, float) else str(x)
        elif isinstance(v, float):
            out[k] = _fmt(v, 4)
        else:
            out[k] = str(v)
    return out


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    flat = [flatten(r) for r in rows]
    keys: list[str] = []
    for r in flat:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        w.writerows(flat)


def run_all(
    log_dir: Path,
    prepared_dir: Path,
    gold_rows: Path,
    dev_summary: Path,
    coverage: Path,
    out_dir: Path,
) -> dict[str, Any]:
    """Build every table and write it under ``out_dir``; return the headline numbers."""
    p = load_pilot(log_dir, prepared_dir, gold_rows)
    units = unit_table(p)
    out_dir.mkdir(parents=True, exist_ok=True)
    tables: dict[str, list[Row]] = {"cost": cost_table(p.calls, units)}
    tables.update({f"faults_{k}": v for k, v in fault_tables(units, p.calls, p).items()})
    tables.update({f"contrast_{k}": v for k, v in arm_contrast_tables(units, p).items()})
    tables["run_to_run"] = run_to_run(units)
    tables["contrast_standardised"] = [
        standardised_gap(units, st, oc)
        for st in ("gold_file_in_context", "gold_unit_in_context")
        for oc in ("first_ok", "final_ok")
    ]
    tables["by_repository"] = repo_table(units)
    tables["faults_rescue"] = rescue_table(units)
    tables["extrapolation_executable"] = extrapolate_to_executable(units, coverage)
    tables["faults_class_groups"] = class_groups(units)
    tables["faults_edit_check_by_arm"] = edit_check_by_arm(units)
    tables["retrieval"] = retrieval_rows(units, p, dev_summary)
    tables.update({f"cost_{k}": v for k, v in cost_grid(units, p.calls).items()})
    tables["power_context"] = power_context(units)
    for name, rows in tables.items():
        write_csv(out_dir / f"rq3_pilot_{name}.csv", rows)
    slim = [
        {
            k: v
            for k, v in r.items()
            if k not in ("first_response", "final_response", "edits_sha256")
        }
        for r in units
    ]
    write_csv(out_dir / "rq3_pilot_units.csv", slim)
    days = sorted({str(r["date_pacific"]) for r in p.calls})
    per_day = {d: sum(1 for r in p.calls if r["date_pacific"] == d) for d in days}
    units_done_day1 = _units_finished_by(p.calls, days[0])
    headline = {
        "calls": len(p.calls),
        "units": len(units),
        "calls_per_pacific_day": per_day,
        "units_final_by_end_of_first_day": units_done_day1,
        "models": sorted({str(r["model"]) for r in p.calls}),
        "finish_reasons": dict(Counter(str(r["finish_reason"]) for r in p.calls)),
    }
    (out_dir / "rq3_pilot_headline.json").write_text(
        json.dumps(headline, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return headline


def _units_finished_by(calls: Sequence[Row], day: str) -> int:
    return len(
        {
            (r["instance_id"], r["arm"], r["run_index"])
            for r in calls
            if r["final"] and r["date_pacific"] <= day
        }
    )
