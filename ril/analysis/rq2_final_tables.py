"""LaTeX tables of the RQ2 final analysis, built from its machine-readable summary.

Implements docs/experiments/B.md "E-RQ2-ANALYSIS". Reads only the summary written by
``ril.analysis.rq2_final.write_summary`` (``results/rq2_final/analysis/summary.json``); every number
passes through ``Trace.num`` as in ``ril.analysis.report_tables``, and the summary file is the
source whose sha256 ``SOURCES.csv`` records (the summary itself carries the hashes of the run files
and the config hashes). A summary whose ``source_kind`` is not ``final`` is refused: no synthetic
or pilot number enters a headline table. When the summary file does not exist yet, nothing is built.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ril.analysis.report_tables import _L, _R, METRIC_NAMES, RULE, Table, Trace

SUMMARY_REL = "results/rq2_final/analysis/summary.json"
CONFIRMATORY_FAMILIES = ("confirmatory",)
ENTRY = "E-RQ2-ANALYSIS"

Rec = Mapping[str, Any]


def load_summary(root: Path, rel: str, tr: Trace) -> dict[str, Any]:
    """The summary, refused unless it was built from final rows."""
    tr.sources.add(rel)
    with open(root / rel, encoding="utf-8") as fh:
        doc: dict[str, Any] = json.load(fh)
    if doc.get("source_kind") != "final":
        raise ValueError(
            f"{rel}: source_kind {doc.get('source_kind')!r} cannot enter a headline table"
        )
    return doc


def _iv(tr: Trace, ci: Sequence[float] | None) -> str:
    return tr.interval(ci[0], ci[1]) if ci else "--"


def _distinct(diag: Mapping[str, Rec], cell: str, tr: Trace) -> str:
    d = diag.get(cell)
    return tr.count(d["distinct_min"]) if d else "--"


def _facts(summary: Rec, tr: Trace) -> str:
    sets = ", ".join(tr.label(s) for s in summary["eval_sets"])
    return (
        f"Evaluation sets: {sets}; delta {tr.num(summary['delta'], 1)} points; Holm within each "
        f"family on each set; the interval beside the Holm interval is uncorrected; "
        f"{tr.count(summary['draws'])} bootstrap draws, seed {tr.count(summary['bootstrap_seed'])}"
    )


def arms_table(summary: Rec, tr: Trace) -> Table:
    diag = summary["diagnostics"]
    keyed: dict[tuple[str, str], dict[tuple[str, str], Rec]] = {}
    for c in summary["cells"]:
        keyed.setdefault((c["eval_set"], c["cell"]), {})[(c["level"], c["metric"])] = c
    rows: list[list[str]] = []
    last = ""
    for (eset, cell), by in sorted(keyed.items()):
        if last and eset != last:
            rows.append(RULE)
        last = eset
        seeds = len(next(iter(by.values()))["seeds"])
        cells = [tr.label(eset), tr.label(cell), tr.count(seeds), _distinct(diag, cell, tr)]
        for level, primary, beside in (
            ("L2", "ndcg10", "recall100"),
            ("L3", "recall100", "ndcg10"),
        ):
            p = by.get((level, primary))
            b = by.get((level, beside))
            cells.append(f"{tr.num(p['mean'])} {_iv(tr, p['ci'])}" if p else "--")
            cells.append(tr.num(b["mean"]) if b else "--")
        rows.append(cells)
    hdr = [
        tr.lit("Set"),
        tr.lit("Cell"),
        tr.lit("Seeds"),
        tr.lit("Distinct dirs"),
        tr.label(f"L2 {METRIC_NAMES['ndcg10']}"),
        tr.label(f"L2 {METRIC_NAMES['recall100']}"),
        tr.label(f"L3 {METRIC_NAMES['recall100']}"),
        tr.label(f"L3 {METRIC_NAMES['ndcg10']}"),
    ]
    return Table(
        name="rq2_final_arms",
        title="Final RQ2 cells: mean over queries, clustered over repositories from three up",
        evidence="measured",
        facts=_facts(summary, tr),
        notes=(
            "The metric beside each primary one is a point value; intervals carry query and "
            "repository sampling, not retraining variance"
        ),
        entries=[ENTRY],
        colspec=_L(0.12) + _L(0.16) + _R(0.05) + _R(0.08) + _R(0.2) + _R(0.07) + _R(0.2) + _R(0.07),
        wide=True,
        header=hdr,
        rows=rows,
        trace=tr,
    )


def contrast_table(
    summary: Rec, tr: Trace, *, name: str, title: str, families: Sequence[str] | None, exclude: bool
) -> Table:
    diag = summary["diagnostics"]
    rows: list[list[str]] = []
    last = ""
    chosen = [
        c
        for c in summary["contrasts"]
        if c["primary"] and (families is None or (c["family"] in families) != exclude)
    ]
    for c in sorted(chosen, key=lambda c: (c["eval_set"], c["family"], c["contrast"], c["level"])):
        if last and c["eval_set"] != last:
            rows.append(RULE)
        last = c["eval_set"]
        h = c["holm"]
        rows.append(
            [
                tr.label(c["eval_set"]),
                tr.label(c["contrast"]),
                tr.level(c["level"]),
                f"{tr.num(c['d'], 1, True)} {_iv(tr, h['ci'] if h else None)}",
                _iv(tr, c["ci_uncorrected"]),
                tr.lit(
                    {"repository-clustered": "repository", "query-level": "query"}[c["interval"]]
                ),
                tr.lit(c["class"].replace("-", " ") if c["class"] else "--"),
                f"{_distinct(diag, c['arm'], tr)} / {_distinct(diag, c['reference'], tr)}",
            ]
        )
    hdr = [
        tr.lit("Set"),
        tr.lit("Contrast"),
        tr.lit("Level"),
        tr.lit("Difference, Holm interval"),
        tr.lit("Uncorrected"),
        tr.lit("Interval"),
        tr.lit("Reading"),
        tr.lit("Distinct dirs"),
    ]
    return Table(
        name=name,
        title=title,
        evidence="measured",
        facts=_facts(summary, tr),
        notes=(
            "Reading: a reported effect needs a Holm interval above zero and a difference of at "
            "least delta; a difference below delta is an estimate with bounds"
        ),
        entries=[ENTRY],
        colspec=_L(0.1) + _L(0.26) + _L(0.05) + _R(0.2) + _R(0.14) + _L(0.07) + _L(0.15) + _R(0.1),
        wide=True,
        header=hdr,
        rows=rows,
        trace=tr,
    )


def claims_table(summary: Rec, tr: Trace) -> Table:
    rows: list[list[str]] = []
    for c in sorted(summary["claims"], key=lambda c: (c["family"], c["contrast"], c["eval_set"])):
        rows.append(
            [
                tr.label(c["eval_set"]),
                tr.label(c["contrast"]),
                tr.lit(c["claim"].replace("-", " ")),
                " ".join(
                    f"{tr.level(k)}: {tr.lit(v.replace('-', ' '))}"
                    for k, v in sorted(c["levels"].items())
                ),
            ]
        )
    fb = summary["fallback"]
    rows.append(RULE)
    rows.append(
        [
            tr.label("RQ3"),
            tr.lit("primary contrast"),
            tr.lit("arms separate" if fb["separates"] else "arms do not separate"),
            tr.label(fb["rq3_primary_contrast"]),
        ]
    )
    return Table(
        name="rq2_final_claims",
        title="Final RQ2 verdicts by rule of the protocol and the RQ3 contrast they fix",
        evidence="measured",
        facts=_facts(summary, tr),
        notes=(
            "A set with one level cannot give a positive reading; exploratory families never "
            "decide the RQ3 contrast"
        ),
        entries=[ENTRY],
        colspec=_L(0.1) + _L(0.3) + _L(0.15) + _L(0.4),
        wide=True,
        header=[tr.lit("Set"), tr.lit("Contrast"), tr.lit("Verdict"), tr.lit("By level")],
        rows=rows,
        trace=tr,
    )


def build_tables(root: Path, rel: str = SUMMARY_REL) -> list[Table]:
    """The four fragments of the final analysis (arms, confirmatory, exploratory, verdicts)."""
    out: list[Table] = []
    builders: list[Any] = [
        arms_table,
        lambda s, tr: contrast_table(
            s,
            tr,
            name="rq2_final_confirmatory",
            title=(
                "Confirmatory contrasts: FILTER (BM25 teacher) against RAW and against the "
                "size-matched subsample"
            ),
            families=CONFIRMATORY_FAMILIES,
            exclude=False,
        ),
        lambda s, tr: contrast_table(
            s,
            tr,
            name="rq2_final_exploratory",
            title=(
                "Exploratory contrasts (other teacher, WEIGHT, CURRICULUM, injected-noise "
                "calibration)"
            ),
            families=CONFIRMATORY_FAMILIES,
            exclude=True,
        ),
        claims_table,
    ]
    for build in builders:
        tr = Trace()
        table = build(load_summary(root, rel, tr), tr)
        table.check()
        out.append(table)
    return out


def build_if_present(root: Path, rel: str = SUMMARY_REL) -> list[Table]:
    """Nothing before the final rows exist; the four tables once the summary is written."""
    return build_tables(root, rel) if (root / rel).exists() else []
