"""Compact tables of the two-page report, built from the same stored files as the full report.

Implements ``docs/experiments/B.md`` E-REPORT-SHORT. Two fragments: the RQ1 ladder with the latency
of each added stage (stored ladder tables and latency rows of E-RQ1-LADDER, E-FREEZE-AND-LATENCY)
and the RQ3 arms (stored result tables of E-RQ3-AGENT, E-RQ3-ORACLE, E-RQ3-FLOOR). Every number
passes through ``Trace`` as in ``ril.analysis.report_tables``; nothing is typed. The fragments are
written next to the short report, never into the full report's generated folder.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ril.analysis.report_tables import (
    _L,
    _R,
    READING,
    RULE,
    Row,
    Table,
    Trace,
    _csv,
    _pick,
)

LADDER_SUMMARY = "results/tables/rq1_ladder_cre_summary.csv"
LADDER_COMPARE = "results/tables/rq1_ladder_cre_compare.csv"
LADDER_LATENCY = "results/tables/rq1_ladder_latency.csv"
SCALE = "django"
PERCENTILE_NAMES = ("50", "95", "99")
"""Digits of the names p50, p95 and p99 in the caption: vocabulary, not quantities."""
AGENT = "results/rq3_driver/remaining_arms/rq3_results_arms.csv"
AGENT_CONTRASTS = "results/rq3_driver/remaining_arms/rq3_results_contrasts.csv"
ORACLE = "results/rq3_oracle/rq3_oracle_arms.csv"
FLOOR = "results/rq3_floor/pooled/rq3_floor_arms.csv"

# rung id, label, summary key, stages shown under it (stage name, short label)
RUNGS: tuple[tuple[str, str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "R1",
        "dense alone",
        "r1|dense",
        (("query_encode", "query encode"), ("dense_search", "dense search")),
    ),
    (
        "R2",
        "plus BM25 (RRF)",
        "p|first",
        (("bm25", "BM25"), ("rrf_fusion", "rank fusion")),
    ),
    (
        "R3",
        "plus same-file expansion",
        "p|sfscore|b",
        (("same_file_expansion", "same-file expansion"),),
    ),
    (
        "R4",
        "plus typed graph",
        "p|graph|e",
        (("graph_expansion", "graph expansion"),),
    ),
)

ARMS: tuple[tuple[str, str, str], ...] = (
    ("rrf", "Untrained", "registered"),
    ("tr_mined_raw_u100_s100", "Raw", "registered"),
    ("tr_mined_filter_bm25_u100_s100", "Filter (BM25 teacher)", "registered"),
    ("tr_mined_sub_u100_s100", "Size-matched subsample", "registered"),
)


@dataclass
class ShortTable(Table):
    """A single-column or full-width compact table (small type, as the full report's tables)."""

    env: str = "table"

    def caption(self) -> str:
        ids = ", ".join(f"\\entry{{{e}}}" for e in self.entries)
        parts = [f"{self.title}.", f"Evidence class: \\emph{{{self.evidence}}}.", f"{self.facts}."]
        if self.notes:
            parts.append(f"{self.notes}.")
        parts.append(f"Entry {ids}.")
        return " ".join(parts)

    def render(self) -> str:
        lines = [
            f"\\begin{{{self.env}}}[t]",
            "\\centering\\small",
            "\\setlength{\\tabcolsep}{3pt}",
            f"\\caption{{{self.caption()}}}",
            f"\\label{{tab:{self.name}}}",
            f"\\begin{{tabular}}{{{self.colspec}}}",
            "\\toprule",
            " & ".join(self.header) + " \\\\",
            "\\midrule",
        ]
        for row in self.rows:
            lines.append("\\midrule" if not row else " & ".join(row) + " \\\\")
        lines += ["\\bottomrule", "\\end{tabular}", f"\\end{{{self.env}}}", ""]
        return "\n".join(lines)


def _interval(tr: Trace, r: Row) -> str:
    """The decision interval (cluster-robust t); ``$^q$`` marks the query-level fallback."""
    mark = "" if r["ci_kind"] == "repository-clustered" else "$^q$"
    return f"{tr.interval(r['t_lo'], r['t_hi'])}{mark}"


def short_rq1(root: Path) -> ShortTable:
    """RQ1 ladder on the development set with the latency of each added stage.

    Implements ``docs/experiments/B.md`` E-RQ1-LADDER: rungs one to four read from the stored
    summary, the typed rung against the size-matched same-file control from the stored paired
    table, and the p50, p95 and p99 of every stage from the stored latency rows at one index size.
    """
    tr = Trace()
    summ = _csv(root, LADDER_SUMMARY, tr)
    comp = _csv(root, LADDER_COMPARE, tr)
    lat = _csv(root, LADDER_LATENCY, tr)

    def value(level: str, metric: str, key: str) -> str:
        r = _pick(summ, level=level, reading=READING, metric=metric, key=key)
        return f"{tr.num(r['mean'])} {_interval(tr, r)}"

    rows: list[list[str]] = []
    for rung, label, key, stages in RUNGS:
        for i, (stage, short) in enumerate(stages):
            s = _pick(lat, scale=SCALE, rung=rung, stage=stage)
            cells = [
                tr.label(f"{rung} {label}") if i == 0 else "",
                value("L2", "ndcg10", key) if i == 0 else "",
                value("L3", "recall100", key) if i == 0 else "",
                tr.lit(short),
                f"{tr.num(s['p50_ms'], 3)} / {tr.num(s['p95_ms'], 3)} / {tr.num(s['p99_ms'], 3)}",
            ]
            rows.append(cells)
    rows.append(RULE)
    c2 = _pick(
        comp,
        pair="R4 minus same-file control",
        level="L2",
        reading=READING,
        metric="ndcg10",
    )
    c3 = _pick(
        comp,
        pair="R4 minus same-file control",
        level="L3",
        reading=READING,
        metric="recall100",
    )
    rows.append(
        [
            tr.label("R4 minus the same-file control"),
            f"{tr.num(c2['mean'], 1, True)} {_interval(tr, c2)}",
            f"{tr.num(c3['mean'], 1, True)} {_interval(tr, c3)}",
            "",
            "",
        ]
    )
    tr.numbers.update(PERCENTILE_NAMES)
    one = _pick(summ, level="L2", reading=READING, metric="ndcg10", key="r1|dense")
    two = _pick(summ, level="L3", reading=READING, metric="ndcg10", key="r1|dense")
    index = _pick(lat, scale=SCALE, rung="R1", stage="query_encode")["index_units"]
    facts = (
        f"Development set only: {tr.count(one['n'])} {tr.level('L2')} queries in "
        f"{tr.count(one['repos'])} repositories and {tr.count(two['n'])} {tr.level('L3')} "
        f"queries in {tr.count(two['repos'])} repositories; encoder CodeRankEmbed; points with the "
        "cluster-robust t interval over repositories, $^q$ marks query level (fewer than three "
        f"repositories); stage latency in ms (p50 / p95 / p99) at an index of {tr.count(index)} "
        "units, the dense stages on a GPU node and the others on a laptop CPU, so the stages "
        "are not an end-to-end percentile"
    )
    return ShortTable(
        name="short_rq1",
        title="RQ1 ladder with the latency of each added stage",
        evidence="measured on the development set, exploratory",
        facts=facts,
        entries=["E-RQ1-LADDER", "E-FREEZE-AND-LATENCY"],
        colspec=_L(0.2) + _R(0.15) + _R(0.18) + _L(0.15) + _R(0.2),
        header=[
            tr.lit("Rung"),
            tr.label("L2 nDCG@10"),
            tr.label("L3 Recall@100"),
            tr.lit("Stage"),
            tr.lit("Latency (ms)"),
        ],
        rows=rows,
        trace=tr,
        env="table*",
        wide=True,
    )


def _pct(tr: Trace, value: str) -> str:
    return tr.num(100 * float(value), 2)


def short_rq3(root: Path) -> ShortTable:
    """RQ3 arms: registered arms, then the exploratory oracle and floor arms.

    Implements ``docs/experiments/B.md`` E-RQ3-AGENT, E-RQ3-ORACLE and E-RQ3-FLOOR: resolved
    fraction, bootstrap interval, repeats per instance and instances graded, as stored.
    """
    tr = Trace()
    arms = _csv(root, AGENT, tr)
    orc = _csv(root, ORACLE, tr)
    flo = _csv(root, FLOOR, tr)
    rows: list[list[str]] = []

    def line(name: str, role: str, r: Row) -> list[str]:
        return [
            tr.lit(name if role == "registered" else f"{name}, {role}"),
            tr.count(r["runs_per_instance"]),
            tr.count(r["instances"]),
            f"{_pct(tr, r['resolved_score'])} "
            f"{tr.interval(100 * float(r['ci_low']), 100 * float(r['ci_high']))}",
        ]

    for key, name, role in ARMS:
        rows.append(line(name, role, _pick(arms, arm=key, reading="exact")))
    rows.append(RULE)
    rows.append(
        line("Oracle calibration", "exploratory", _pick(orc, arm="oracle", reading="exact"))
    )
    rows.append(
        line(
            "No-retrieval floor",
            "exploratory",
            _pick(flo, instance_set="floor-covered (272)", arm="floor", reading="exact"),
        )
    )
    facts = (
        "Resolved fraction of graded runs with the bootstrap interval over instances; $k$ is the "
        "number of adjacent repeats per instance and $N$ the instances graded of the confirmatory "
        "set; each trained arm is one model from one training seed; the floor row is "
        "the first instances by identifier, not a random draw, and adjacent repeats are not "
        "independent runs"
    )
    return ShortTable(
        name="short_rq3",
        title="RQ3 arms on the confirmatory instances",
        evidence="measured; four arms pre-registered, oracle and floor exploratory",
        facts=facts,
        entries=["E-RQ3-AGENT", "E-RQ3-ORACLE", "E-RQ3-FLOOR"],
        colspec=_L(0.4) + _R(0.05) + _R(0.08) + _R(0.3),
        header=[
            tr.lit("Arm"),
            "$k$",
            "$N$",
            tr.lit("Resolved (%) [interval]"),
        ],
        rows=rows,
        trace=tr,
    )


BUILDERS = (short_rq1, short_rq3)


def build_all(root: Path) -> list[ShortTable]:
    """The short report's tables, each checked: every digit string came from a stored file."""
    tables = [b(root) for b in BUILDERS]
    for t in tables:
        t.check()
    return tables


def write_all(root: Path, out_dir: Path) -> list[ShortTable]:
    """Write one ``.tex`` fragment per table and ``SOURCES.csv`` (sources with their SHA-256)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tables = build_all(root)
    lines = ["fragment,source,sha256"]
    for t in tables:
        (out_dir / f"{t.name}.tex").write_text(t.render(), encoding="utf-8")
        for src in sorted(t.trace.sources):
            digest = hashlib.sha256((root / src).read_bytes()).hexdigest()
            lines.append(f"{t.name}.tex,{src},{digest}")
    (out_dir / "SOURCES.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tables


__all__ = ["BUILDERS", "ShortTable", "build_all", "short_rq1", "short_rq3", "write_all"]
