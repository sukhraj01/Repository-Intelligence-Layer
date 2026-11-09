"""LaTeX tables of the RQ1 ladder, built from the stored tables of ``ril.analysis.rq1_ladder``.

Implements ``docs/experiments/B.md`` E-RQ1-LADDER. Reads ``results/tables/rq1_ladder_<label>_*.csv``
and ``rq1_ladder_latency.csv`` (written by ``ril.analysis.rq1_ladder.write_outputs``); every number
passes through ``Trace.num`` as in ``ril.analysis.report_tables`` and the files read are the
sources whose sha256 ``SOURCES.csv`` records. When the stored tables do not exist yet, nothing is
built. Development set only: the tables say so in their facts line.
"""

from __future__ import annotations

from pathlib import Path

from ril.analysis import rq1_ladder as lt
from ril.analysis.report_tables import _L, _R, METRIC_NAMES, READING, RULE, Row, Table, Trace, _csv

ENTRY = "E-RQ1-LADDER"
LABELS = {"cre": "CodeRankEmbed", "qwen3": "Qwen3-Embedding-0.6B"}
SUMMARY = "results/tables/rq1_ladder_{label}_summary.csv"
COMPARE = "results/tables/rq1_ladder_{label}_compare.csv"
LATENCY = "results/tables/rq1_ladder_latency.csv"
SCALE = "django"
"""Latency scale of the per-millisecond column: one index size for every stage."""


def _pick(rows: list[Row], **eq: str) -> Row:
    hit = [r for r in rows if all(r.get(k) == v for k, v in eq.items())]
    if len(hit) != 1:
        raise KeyError(f"{len(hit)} rows match {eq}")
    return hit[0]


def _interval(tr: Trace, r: Row) -> str:
    """The decision (cluster-robust t) interval; ``$^q$`` marks the query-level fallback."""
    mark = "" if r["ci_kind"] == "repository-clustered" else "$^q$"
    return f"{tr.interval(r['t_lo'], r['t_hi'])}{mark}"


def _boot(tr: Trace, r: Row) -> str:
    mark = "" if r["boot_kind"] == "repository-clustered" else "$^q$"
    return f"{tr.interval(r['boot_lo'], r['boot_hi'])}{mark}"


def _latency(rows: list[Row]) -> list[lt.Record]:
    """The stored latency rows with the types the cost functions expect."""
    out: list[lt.Record] = []
    for r in rows:
        rec: lt.Record = dict(r)
        rec["measured"] = r["measured"] == "True"
        if rec["measured"]:
            for k in ("p50_ms", "p95_ms", "p99_ms"):
                rec[k] = float(r[k])
        out.append(rec)
    return out


def ladder_table(root: Path, label: str) -> Table:
    tr = Trace()
    summ = _csv(root, SUMMARY.format(label=label), tr)
    comp = _csv(root, COMPARE.format(label=label), tr)
    lat = _latency(_csv(root, LATENCY, tr))
    costs = lt.rung_costs(lat, SCALE)
    cum = lt.cumulative_costs(costs)
    rows: list[list[str]] = []

    def value(level: str, metric: str, key: str) -> str:
        r = _pick(summ, level=level, reading=READING, metric=metric, key=key)
        return f"{tr.num(r['mean'])} {_interval(tr, r)}"

    def point(level: str, metric: str, key: str) -> str:
        return tr.num(_pick(summ, level=level, reading=READING, metric=metric, key=key)["mean"])

    rows.append(
        [
            tr.lit("BM25 alone (reference)"),
            value("L2", "ndcg10", "ref|bm25"),
            value("L3", "recall100", "ref|bm25"),
            point("L3", "ndcg10", "ref|bm25"),
            "--",
            "--",
            "--",
        ]
    )
    rows.append(RULE)
    for rung, name, key in lt.LADDER:
        cost = cum[rung]
        added = costs[rung]
        p50 = "--" if cost["p50_ms"] is None else tr.num(cost["p50_ms"], 2)
        if cost["p50_ms"] is not None and not cost["complete"]:
            p50 += tr.lit(" (partial)")
        per_ms = ["--", "--"]
        if rung in lt.PRED_PAIR:
            for j, (level, metric) in enumerate((("L2", "ndcg10"), ("L3", "recall100"))):
                d = _pick(
                    comp, pair=lt.PRED_PAIR[rung], level=level, reading=READING, metric=metric
                )
                g = lt.gain_per_ms(float(d["mean"]), added["added_p50_ms"])
                if g is None:
                    per_ms[j] = tr.lit("not measured")
                else:
                    per_ms[j] = tr.num(g, 1, True) + (
                        "" if added["complete"] else tr.lit(" (partial)")
                    )
        rows.append(
            [
                tr.label(f"{rung} {name}"),
                value("L2", "ndcg10", key),
                value("L3", "recall100", key),
                point("L3", "ndcg10", key),
                p50,
                per_ms[0],
                per_ms[1],
            ]
        )
    hdr = [
        tr.lit("Rung"),
        tr.label(f"L2 {METRIC_NAMES['ndcg10']} [t interval]"),
        tr.label(f"L3 {METRIC_NAMES['recall100']} [t interval]"),
        tr.label(f"L3 {METRIC_NAMES['ndcg10']}"),
        tr.label("p50 ms, path"),
        tr.lit("L2 points per added ms"),
        tr.lit("L3 points per added ms"),
    ]
    one = _pick(summ, level="L2", reading=READING, metric="ndcg10", key="r1|dense")
    two = _pick(summ, level="L3", reading=READING, metric="ndcg10", key="r1|dense")
    index = next(r for r in lat if r["scale"] == SCALE)["index_units"]
    facts = (
        f"Development set only: {tr.count(one['n'])} {tr.level('L2')} queries in "
        f"{tr.count(one['repos'])} repositories and {tr.count(two['n'])} {tr.level('L3')} "
        f"queries in {tr.count(two['repos'])} repositories; encoder {tr.label(LABELS[label])}; "
        "the interval is the cluster-robust t interval over repositories, $^q$ marks query level "
        "(fewer than three repositories); latency from stored rows at an index of "
        f"{tr.count(index)} units, dense stages on one host and BM25 and graph rows on another, "
        "so the path is a sum of stage p50 values and not an end-to-end percentile"
    )
    return Table(
        name="rq1_ladder" if label == "cre" else f"rq1_ladder_{label}",
        title="RQ1 ladder: each signal added to the dense retriever, with latency",
        evidence="measured on the development set, exploratory",
        facts=facts,
        notes=(
            "Rungs two to five share queries, candidate set (every unit of the snapshot) and "
            "expansion budget; the typed-graph rung is read against the same-file control in the "
            "next table; points per added ms is the paired gain over the rung before it on the "
            "stage path (the typed rung branches from the second rung) divided by the p50 of the "
            "stages it adds; a stage without a stored row is not measured and the path is then "
            "partial"
        ),
        entries=[ENTRY],
        colspec=_L(0.25) + _R(0.17) + _R(0.17) + _R(0.07) + _R(0.1) + _R(0.1) + _R(0.1),
        wide=True,
        header=hdr,
        rows=rows,
        trace=tr,
    )


_PAIR_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "adjacent rungs",
        ("R2 minus R1", "R3 minus R2", "R4 minus R3", "R4 minus R2", "R5 minus R4"),
    ),
    (
        "typed graph against its controls",
        (
            "R4 minus same-file control",
            "R4 minus same-file chance",
            "R4 minus top-M control",
            "stored graph minus same-file control",
        ),
    ),
    (
        "recency prior on each stage",
        ("recency on RRF", "recency on typed graph", "recency on same-file"),
    ),
    ("fusion", ("RRF minus BM25",)),
)


def pairs_table(root: Path, label: str) -> Table:
    tr = Trace()
    comp = _csv(root, COMPARE.format(label=label), tr)
    rows: list[list[str]] = []
    for i, (_group, names) in enumerate(_PAIR_GROUPS):
        if i:
            rows.append(RULE)
        for name in names:
            cells = [tr.label(name)]
            for level, metric in (("L2", "ndcg10"), ("L3", "recall100")):
                r = _pick(comp, pair=name, level=level, reading=READING, metric=metric)
                cells.append(f"{tr.num(r['mean'], 1, True)} {_interval(tr, r)}")
                cells.append(_boot(tr, r))
                cells.append(tr.lit(r["verdict"]))
            rows.append(cells)
    hdr = [tr.lit("Paired difference")]
    for level, metric in (("L2", "ndcg10"), ("L3", "recall100")):
        hdr += [
            tr.label(f"{level} {METRIC_NAMES[metric]}, t interval"),
            tr.lit("bootstrap beside"),
            tr.lit("reading"),
        ]
    one = _pick(comp, pair="R2 minus R1", level="L2", reading=READING, metric="ndcg10")
    two = _pick(comp, pair="R2 minus R1", level="L3", reading=READING, metric="recall100")
    facts = (
        f"Development set only: {tr.count(one['n'])} {tr.level('L2')} and {tr.count(two['n'])} "
        f"{tr.level('L3')} queries in {tr.count(one['repos'])} and {tr.count(two['repos'])} "
        f"repositories; encoder {tr.label(LABELS[label])}; differences are paired on the query; "
        "decisions read from the cluster-robust t interval over repositories, the percentile "
        "bootstrap over whole repositories beside it; $^q$ marks query level (fewer than three "
        "repositories)"
    )
    return Table(
        name="rq1_ladder_pairs" if label == "cre" else f"rq1_ladder_pairs_{label}",
        title="RQ1 ladder: paired differences between rungs and against the controls",
        evidence="measured on the development set, exploratory",
        facts=facts,
        notes=(
            "A typed-graph gain that does not exceed the same-file control is not a graph gain; "
            "the typed rung is an alternative expansion of the same budget, not stacked on the "
            "same-file rung"
        ),
        entries=[ENTRY],
        colspec=_L(0.22) + (_R(0.13) + _R(0.11) + _R(0.1)) * 2,
        wide=True,
        header=hdr,
        rows=rows,
        trace=tr,
    )


def latency_table(root: Path) -> Table:
    tr = Trace()
    lat = _latency(_csv(root, LATENCY, tr))
    rows: list[list[str]] = []
    last = ""
    for r in lat:
        if last and r["scale"] != last:
            rows.append(RULE)
        last = r["scale"]
        head = [tr.label(r["scale"]), tr.label(r["rung"]), tr.label(r["stage"])]
        if not r["measured"]:
            rows.append(
                head + [tr.lit("not measured")] + ["--"] * 5 + [tr.label(str(r["query_set_id"]))]
            )
            continue
        rows.append(
            head
            + [
                tr.label(r["host"]),
                tr.num(r["p50_ms"], 3),
                tr.num(r["p95_ms"], 3),
                tr.num(r["p99_ms"], 3),
                tr.count(r["n"]),
                tr.label(r["cache_state"]),
                tr.label(r["query_set_id"]),
            ]
        )
    hdr = [
        tr.lit("Scale"),
        tr.lit("Rung"),
        tr.lit("Stage"),
        tr.lit("Host"),
        tr.label("p50 ms"),
        tr.label("p95 ms"),
        tr.label("p99 ms"),
        tr.lit("Calls"),
        tr.lit("Cache"),
        tr.lit("Query set"),
    ]
    sizes = ", ".join(
        f"{tr.label(s)} {tr.count(next(r['index_units'] for r in lat if r['scale'] == s))}"
        for s in dict.fromkeys(r["scale"] for r in lat)
    )
    return Table(
        name="rq1_ladder_latency",
        title="RQ1 ladder: per-stage latency from stored rows",
        evidence="measured, per hardware spec",
        facts=(
            f"Index units per scale: {sizes} (the small scale mixes a dense row at the development "
            "median snapshot with BM25 and graph rows of a smaller repository); host names are "
            "those of the stored rows; each stage is the latest warm row of its query set; a "
            "stage without a stored row is not measured and nothing is interpolated"
        ),
        entries=["E-LAT-STAGES", ENTRY],
        colspec=_L(0.08)
        + _L(0.05)
        + _L(0.1)
        + _L(0.1)
        + _R(0.07) * 3
        + _R(0.05)
        + _L(0.05)
        + _L(0.3),
        wide=True,
        header=hdr,
        rows=rows,
        trace=tr,
    )


def build_if_present(root: Path) -> list[Table]:
    """The ladder tables, or nothing when the stored tables are absent."""
    tables: list[Table] = []
    if not (root / LATENCY).exists():
        return tables
    for label in LABELS:
        if (root / SUMMARY.format(label=label)).exists():
            tables += [ladder_table(root, label), pairs_table(root, label)]
    tables.append(latency_table(root))
    for t in tables:
        t.check()
    return tables
