"""LaTeX fragments of the final report, generated from the stored result files.

Implements ``reports/README.md`` ("every figure traces to ``results/``"). Every number in a
fragment is read from a file under ``results/`` and passes through ``Trace.num``; text written in
this module may not contain a digit (``Trace.lit`` refuses it), and the only other way a digit
enters is a label read from a source file (``Trace.label``). ``Table.numbers`` therefore lists every
digit string a fragment may contain, which ``tests/unit/test_report_tables.py`` checks against the
committed files. Each caption states the evidence class, n and the experiment entry id.

Reads ``results/`` only; writes ``reports/final/generated/*.tex`` and ``SOURCES.csv`` (path and
sha256 of every file a fragment was built from).
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

Row = dict[str, str]
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
RULE: list[str] = []
METRIC_NAMES = {"ndcg10": "nDCG@10", "recall100": "Recall@100"}
READING = "units_all_nomod"
DAGGER = r"$^\dagger$"


def _L(width: float) -> str:
    """A left-aligned wrapping column of a fraction of the line width."""
    return f">{{\\raggedright\\arraybackslash}}p{{{width}\\linewidth}}"


def _R(width: float) -> str:
    """A right-aligned wrapping column of a fraction of the line width."""
    return f">{{\\raggedleft\\arraybackslash}}p{{{width}\\linewidth}}"


# names that contain digits but are not numbers; removed before any digit check
VOCAB = ("Qwen3-Embedding-0.6B", "nDCG@10", "Recall@100", "BM25", "L2", "L3")


def _digits(text: str) -> list[str]:
    for word in VOCAB:
        text = text.replace(word, " ")
    return NUM_RE.findall(text)


def _escape(text: str) -> str:
    """Escape the LaTeX characters that occur in labels; refuse the ones that need thought."""
    if re.search(r"[${}~^\\]", text):
        raise ValueError(f"unescaped LaTeX character in {text!r}")
    for ch in "&%#_":
        text = text.replace(ch, "\\" + ch)
    return text


class Trace:
    """Collects the digit strings a table may contain and the files it was built from."""

    def __init__(self) -> None:
        self.numbers: set[str] = set()
        self.sources: set[str] = set()

    def num(self, value: float | str, nd: int = 1, sign: bool = False) -> str:
        """A number read from a file, rounded to ``nd`` decimals (minus as math, plus optional)."""
        v = float(value)
        body = f"{abs(v):.{nd}f}"
        self.numbers.add(body)
        if round(abs(v), nd) == 0:
            return body
        if v < 0:
            return "$-$" + body
        return ("+" if sign else "") + body

    def count(self, value: float | str) -> str:
        """An integer count read from a file."""
        body = str(int(float(value)))
        self.numbers.add(body)
        return body

    def interval(self, lo: float | str, hi: float | str, nd: int = 1) -> str:
        return f"[{self.num(lo, nd)}, {self.num(hi, nd)}]"

    def label(self, text: str) -> str:
        """Text taken from a source file or a fixed vocabulary; its digit strings are allowed."""
        for tok in NUM_RE.findall(text):
            self.numbers.add(tok)
        return _escape(text)

    def level(self, name: str) -> str:
        """A level name (``L2``, ``L3``) as read from a source file."""
        return self.label(name)

    def lit(self, text: str) -> str:
        """Text written in this module: no digit allowed."""
        if _digits(text):
            raise ValueError(f"a digit in literal text: {text!r}")
        return _escape(text)


@dataclass
class Table:
    name: str
    title: str
    evidence: str
    facts: str
    entries: list[str]
    colspec: str
    header: list[str]
    rows: list[list[str]]
    notes: str = ""
    wide: bool = False
    trace: Trace = field(default_factory=Trace)

    def check(self) -> None:
        """Every digit string of the rendered fragment must have come from a source file."""
        text = re.sub(
            r"\\label\{[^}]*\}|\\entry\{[^}]*\}|\\begin\{tabular\}\{.*\}\n", "", self.render()
        )
        stray = sorted(set(_digits(text)) - self.trace.numbers)
        if stray:
            raise ValueError(f"{self.name}: numbers not read from a file: {stray}")

    def caption(self) -> str:
        ids = ", ".join(f"\\entry{{{e}}}" for e in self.entries)
        parts = [
            f"{self.title}.",
            f"Evidence class: \\emph{{{self.evidence}}}.",
            f"{self.facts}.",
        ]
        if self.notes:
            parts.append(f"{self.notes}.")
        parts.append(f"Entry {ids}.")
        return " ".join(parts)

    def render(self) -> str:
        env = "table*" if self.wide else "table"
        lines = [
            f"\\begin{{{env}}}[t]",
            "\\centering\\small",
            f"\\caption{{{self.caption()}}}",
            f"\\label{{tab:{self.name}}}",
            f"\\begin{{tabular}}{{{self.colspec}}}",
            "\\toprule",
            " & ".join(self.header) + " \\\\",
            "\\midrule",
        ]
        for row in self.rows:
            lines.append("\\midrule" if not row else " & ".join(row) + " \\\\")
        lines += ["\\bottomrule", "\\end{tabular}", f"\\end{{{env}}}", ""]
        return "\n".join(lines)


def _csv(root: Path, rel: str, tr: Trace) -> list[Row]:
    tr.sources.add(rel)
    with open(root / rel, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _json(root: Path, rel: str, tr: Trace) -> dict[str, object]:
    tr.sources.add(rel)
    with open(root / rel, encoding="utf-8") as handle:
        doc: dict[str, object] = json.load(handle)
    return doc


def _pick(rows: list[Row], **eq: str) -> Row:
    """Exactly one row matching every condition; anything else is an error."""
    hit = [r for r in rows if all(r.get(k) == v for k, v in eq.items())]
    if len(hit) != 1:
        raise KeyError(f"{len(hit)} rows match {eq}")
    return hit[0]


def _delta(tr: Trace, r: Row, lo: str, hi: str) -> str:
    return f"{tr.num(r['d'], 1, True)} {tr.interval(r[lo], r[hi])}"


# ---------------------------------------------------------------------------------------------
# E-BM25-REPRO


def bm25_repro(root: Path) -> Table:
    tr = Trace()
    agg = _csv(root, "results/tables/e1_aggregation.csv", tr)
    conv = "mean_of_dataset_macro_over_folders"
    sets = (
        ("verified12", "L2", "Verified"),
        ("verified12", "L3", "Verified"),
        ("full_l2", "L2", "All sub-datasets"),
    )
    rows: list[list[str]] = []
    nq: list[str] = []
    for key, level, name in sets:
        r = _pick(agg, set=key, level=level, convention=conv)
        rows.append(
            [
                tr.label(f"{name} {level}"),
                tr.count(r["folders"]),
                tr.count(r["queries"]),
                tr.num(r["ndcg10"], 2),
                tr.num(r["paper_ndcg10"], 1),
                tr.num(r["recall100"], 2),
                tr.num(r["paper_recall100"], 1),
            ]
        )
        nq.append(f"{r['queries']}")
    hdr = [
        tr.lit("Set"),
        tr.lit("Folders"),
        tr.lit("Queries"),
        tr.label(f"{METRIC_NAMES['ndcg10']}"),
        tr.label(f"{METRIC_NAMES['ndcg10']} paper"),
        tr.label(f"{METRIC_NAMES['recall100']}"),
        tr.label(f"{METRIC_NAMES['recall100']} paper"),
    ]
    return Table(
        name="bm25_repro",
        title=(
            "BM25 reproduction of the published baseline rows at chunk level, mean over folders "
            "(the reading that reproduces them)"
        ),
        evidence="measured; the paper columns are paper\\_reported",
        facts=(
            "n is the folder and query count of each row; the query-level mean over the same "
            "queries is in the source table and differs"
        ),
        entries=["E-BM25-REPRO"],
        colspec="lrrrrrr",
        wide=True,
        header=hdr,
        rows=rows,
        trace=tr,
    )


# ---------------------------------------------------------------------------------------------
# E-DENSE-FUSION

_SYSTEMS = (
    ("bm25", "BM25"),
    ("dense|coderankembed__t1024", "CodeRankEmbed"),
    ("rrf|coderankembed__t1024|k100", "BM25 + CodeRankEmbed (RRF)"),
    ("dense|qwen3-embedding-0.6b__t512", "Qwen3-Embedding-0.6B"),
    ("rrf|qwen3-embedding-0.6b__t512|k20", "BM25 + Qwen3-Embedding-0.6B (RRF)"),
)


def dense_fusion(root: Path) -> Table:
    tr = Trace()
    rows_in = _csv(root, "results/tables/x2_first_confirm.csv", tr)
    out: list[list[str]] = []
    n: dict[str, Row] = {}
    for key, display in _SYSTEMS:
        cells = [tr.label(display)]
        cut = re.search(r"__t(\d+)", key)
        kk = re.search(r"\|k(\d+)$", key)
        cells.append(tr.label(cut.group(1)) if cut else "")
        cells.append(tr.label(kk.group(1)) if kk else "")
        for level, metric in (("L2", "ndcg10"), ("L3", "recall100")):
            r = _pick(
                rows_in,
                group="test",
                level=level,
                reading=READING,
                metric=metric,
                name=key,
                against="bm25",
            )
            n[level] = r
            cells.append(f"{tr.num(r['value'])} {tr.interval(r['c_lo'], r['c_hi'])}")
        out.append(cells)
    hdr = [
        tr.lit("System"),
        tr.lit("Cut"),
        tr.lit("RRF k"),
        tr.label(f"L2 {METRIC_NAMES['ndcg10']}"),
        tr.label(f"L3 {METRIC_NAMES['recall100']}"),
    ]
    facts = (
        f"Verified-six, {tr.count(n['L2']['queries'])} {tr.level('L2')} and "
        f"{tr.count(n['L3']['queries'])} {tr.level('L3')} queries in "
        f"{tr.count(n['L2']['repos'])} repositories; the interval is "
        "repository-clustered; cut and k were chosen on the development repositories"
    )
    return Table(
        name="dense_fusion",
        title="Zero-shot dense encoders and rank fusion with BM25 (final-test-style reading)",
        evidence="measured, exploratory",
        facts=facts,
        entries=["E-DENSE-FUSION"],
        colspec="lrrrr",
        wide=True,
        header=hdr,
        rows=out,
        trace=tr,
    )


# ---------------------------------------------------------------------------------------------
# E-GRAPH-ROLE

_GRAPH_ROWS = (
    ("graph|b", "a_none", "graph as stored"),
    ("sfscore|b", "a_none", "same file, by first-stage score (control)"),
    ("sfrand|b", "a_none", "same file, random order"),
    ("topm|b", "a_none", "next best units, no file constraint"),
    ("graph|e", "a_none", "graph, non-contain edges only"),
    ("graph|f", "a_none", "graph, contain edges only"),
)
_GRAPH_VS_CONTROL = (
    ("graph|b", "graph as stored"),
    ("graph|e", "graph, non-contain edges only"),
    ("graph|f", "graph, contain edges only"),
)


def graph_role(root: Path) -> Table:
    tr = Trace()
    rows_in = _csv(root, "results/tables/s1/s1_graph_role_cre_compare.csv", tr)
    panels = (
        ("test", "L2", "ndcg10"),
        ("test", "L3", "recall100"),
        ("dev", "L2", "ndcg10"),
        ("dev", "L3", "recall100"),
    )
    sel = dict(reading=READING, weight="0.5")

    def row(group: str, level: str, metric: str, name: str, against: str) -> Row:
        return _pick(
            rows_in, group=group, level=level, metric=metric, name=name, against=against, **sel
        )

    def interval_of(r: Row) -> str:
        clustered = int(r["repos"]) >= 3
        lo, hi = ("d_c_lo", "d_c_hi") if clustered else ("d_q_lo", "d_q_hi")
        mark = "" if clustered else "$^q$"
        return f"{tr.interval(r[lo], r[hi])}{mark}"

    out: list[list[str]] = []
    first = [tr.lit("first stage, RRF of BM25 and CodeRankEmbed (value)")]
    for g, lv, m in panels:
        first.append(tr.num(row(g, lv, m, "a_none", "a_none")["value"]))
    out.append(first)
    out.append(RULE)
    for name, against, display in _GRAPH_ROWS:
        cells = [tr.label(f"{display}: change against first stage")]
        for g, lv, m in panels:
            r = row(g, lv, m, name, against)
            cells.append(f"{tr.num(r['d'], 1, True)} {interval_of(r)}")
        out.append(cells)
    out.append(RULE)
    for name, display in _GRAPH_VS_CONTROL:
        cells = [tr.label(f"{display}: minus the same-file control")]
        for g, lv, m in panels:
            r = row(g, lv, m, name, "sfscore")
            cells.append(f"{tr.num(r['d'], 1, True)} {interval_of(r)}")
        out.append(cells)
    hdr = [tr.lit("Candidate source")]
    for g, lv, m in panels:
        who = "Verified-six" if g == "test" else "dev"
        hdr.append(tr.label(f"{who} {lv} {METRIC_NAMES[m]}"))
    qs = {(g, lv): row(g, lv, m, "a_none", "a_none") for g, lv, m in panels}
    facts = (
        f"Verified-six: {tr.count(qs[('test', 'L2')]['queries'])} {tr.level('L2')} and "
        f"{tr.count(qs[('test', 'L3')]['queries'])} {tr.level('L3')} queries in "
        f"{tr.count(qs[('test', 'L2')]['repos'])} repositories; dev: "
        f"{tr.count(qs[('dev', 'L2')]['queries'])} and {tr.count(qs[('dev', 'L3')]['queries'])} "
        f"queries in {tr.count(qs[('dev', 'L2')]['repos'])} and "
        f"{tr.count(qs[('dev', 'L3')]['repos'])} repositories. Intervals are repository-clustered, "
        "except $^q$ (two repositories: query-level only)"
    )
    return Table(
        name="graph_role",
        title=(
            "Graph expansion against the same-file control on a fused first stage, equal "
            "candidate budget"
        ),
        evidence="measured, exploratory",
        facts=facts,
        entries=["E-GRAPH-ROLE"],
        colspec=_L(0.28) + _R(0.16) * 4,
        header=hdr,
        rows=out,
        wide=True,
        trace=tr,
    )


# ---------------------------------------------------------------------------------------------
# E-PILOT-NOISE

_NOISE_ARMS = (
    ("oracle", "ORACLE-CLEAN"),
    ("filter_bm25", "FILTER, BM25 teacher"),
    ("filter_srs", "FILTER, SweRankEmbed-Small teacher"),
    ("weight_srs", "WEIGHT, SweRankEmbed-Small teacher"),
    ("sub", "size-matched subsample"),
)


def noise_dose_response(root: Path) -> Table:
    tr = Trace()
    eff = _csv(root, "results/tables/n1/n1_effects.csv", tr)
    mdd = _csv(root, "results/tables/n1/n1_r40_mdd_three_seeds.csv", tr)
    lv = (("L2", "ndcg10", "d_c_lo", "d_c_hi"), ("L3", "recall100", "d_q_lo", "d_q_hi"))

    def pick(rate: str, ref: str, name: str, level: str, metric: str) -> Row:
        return _pick(
            eff,
            label=f"E-PILOT-NOISE r={rate}",
            reference=ref,
            name=f"{name}:mean",
            ref=f"{ref}:mean",
            level=level,
            reading=READING,
            metric=metric,
            kind="dense",
        )

    out: list[list[str]] = []
    queries: dict[str, Row] = {}
    for rate in ("0.2", "0.4"):
        rr = f"n1_r{int(float(rate) * 100)}"
        out.append([tr.label(f"r = {rate}")] + [""] * 5)
        # RAW's own loss against clean RAW (the sanity check of the calibration)
        cells = [tr.lit("RAW minus clean RAW"), ""]
        for level, metric, lo, hi in lv:
            r = _pick(
                eff,
                label=f"E-PILOT-NOISE r={rate}",
                reference="t5a_raw",
                name=f"{rr}_raw:mean",
                ref="t5a_raw:mean",
                level=level,
                reading=READING,
                metric=metric,
                kind="dense",
            )
            queries[level] = r
            cells[1] = tr.count(r["seeds"])
            cells += [_delta(tr, r, lo, hi), ""]
        out.append(cells)
        oracle = {
            level: float(pick(rate, f"{rr}_raw", f"{rr}_oracle", level, metric)["d"])
            for level, metric, _, _ in lv
        }
        for key, display in _NOISE_ARMS:
            name = f"{rr}_{key}"
            cells = [tr.label(display) + (DAGGER if key.endswith("_srs") else ""), ""]
            for level, metric, lo, hi in lv:
                r = pick(rate, f"{rr}_raw", name, level, metric)
                cells[1] = tr.count(r["seeds"])
                share = ""
                if key != "oracle":
                    share = tr.num(float(r["d"]) / oracle[level], 2)
                cells += [_delta(tr, r, lo, hi), share]
            out.append(cells)
    out.append(RULE)
    for variant, text in (
        ("with_repo_term", "with the repository term"),
        ("query_level", "query level"),
    ):
        r2 = _pick(mdd, rate="0.4", level="L2", seeds_per_arm="3", variant=variant)
        r3 = _pick(mdd, rate="0.4", level="L3", seeds_per_arm="3", variant=variant)
        out.append(
            [
                tr.label(f"minimum detectable difference, r = {r2['rate']}, {text}"),
                tr.count(r2["seeds_per_arm"]),
                tr.num(r2["mdd_points"], 2),
                "",
                tr.num(r3["mdd_points"], 2),
                "",
            ]
        )
    hdr = [
        tr.lit("Arm minus RAW at the same r"),
        tr.lit("Seeds"),
        tr.label(f"L2 {METRIC_NAMES['ndcg10']} change"),
        tr.lit("Share of oracle"),
        tr.label(f"L3 {METRIC_NAMES['recall100']} change"),
        tr.lit("Share of oracle"),
    ]
    facts = (
        f"Development repositories: {tr.count(queries['L2']['queries'])} {tr.level('L2')} queries "
        f"in {tr.count(queries['L2']['repos'])} repositories, "
        f"{tr.count(queries['L3']['queries'])} {tr.level('L3')} queries in "
        f"{tr.count(queries['L3']['repos'])}; {tr.level('L2')} intervals are "
        f"repository-clustered, {tr.level('L3')} intervals are query-level (two repositories). "
        "Share of oracle is the arm's change "
        "divided by the ORACLE-CLEAN change. Injected noise is a proxy for real label noise"
    )
    notes = (
        f"{DAGGER}SweRankEmbed-Small shaped the selection of the public pool (E-POOL-RANKS), so "
        "its cells are the favoured teacher; the BM25 cells are the ones the confirmatory "
        "protocol rests on"
    )
    return Table(
        name="noise_dose_response",
        title="Injected-noise dose-response: supervision arms against RAW at matched updates",
        evidence="measured, exploratory",
        facts=facts,
        entries=["E-PILOT-NOISE"],
        colspec=_L(0.30) + _R(0.06) + _R(0.17) + _R(0.09) + _R(0.17) + _R(0.09),
        header=hdr,
        rows=out,
        notes=notes,
        wide=True,
        trace=tr,
    )


# ---------------------------------------------------------------------------------------------
# E-MINE-PILOT (M3)

_TEACHERS = (
    ("bm25", "BM25"),
    ("coderankembed", "CodeRankEmbed"),
    ("swerankembed-small", "SweRankEmbed-Small"),
)


def mined_vs_pool_ranks(root: Path) -> Table:
    tr = Trace()
    m3 = _json(root, "results/mining/m3_rank_shares.json", tr)
    pool = _csv(root, "results/tables/x3_pool_ranks_topk.csv", tr)
    mined = m3["rows"]
    assert isinstance(mined, list)
    out: list[list[str]] = []
    for key, display in _TEACHERS:
        for k in ("10", "20", "40"):
            m = [r for r in mined if r["teacher"] == key and str(r["k"]) == k]
            if len(m) != 1:
                raise KeyError(f"{len(m)} mined rows for {key} K={k}")
            wilson = m[0]["wilson"]
            p = _pick(pool, teacher=key, k=k)
            plo, phi = p["pool_pct_dirs_none_ci"].split(";")
            out.append(
                [
                    tr.label(display),
                    tr.count(k),
                    tr.count(m[0]["directories"]),
                    f"{tr.num(100 * float(m[0]['share']))} "
                    + tr.interval(100 * float(wilson[0]), 100 * float(wilson[1])),
                    f"{tr.num(p['pool_pct_dirs_none'])} {tr.interval(plo, phi)}",
                ]
            )
    reading = m3["reading"]
    assert isinstance(reading, dict)
    hdr = [
        tr.lit("Teacher"),
        tr.lit("K"),
        tr.lit("Mined directories"),
        tr.lit("Mined set, no positive in top K (%)"),
        tr.lit("Published pool (%)"),
    ]
    facts = (
        "Pool-like reading of the mined pilot set: "
        f"{tr.count(reading['directories_with_positive'])} "
        "directories with a positive (fewer where a teacher did not finish, see the Mined column); "
        "Wilson intervals; the pool column is the pool estimate from a stratified sample of "
        "directories; one seed, one pilot"
    )
    return Table(
        name="mined_vs_pool_ranks",
        title=(
            "Share of directories without a positive in the teacher's top K: pull-request-mined "
            "set against the published pool"
        ),
        evidence="measured, exploratory",
        facts=facts,
        entries=["E-MINE-PILOT", "E-POOL-RANKS"],
        colspec="lrrrr",
        wide=True,
        header=hdr,
        rows=out,
        trace=tr,
    )


# ---------------------------------------------------------------------------------------------
# E-MINED-PILOT

_MINED_ROWS = (
    ("mp_raw", "mp_raw", "base", "RAW on the mined set, minus the untrained encoder"),
    ("t5a_raw", "t5a_raw", "base", "RAW on the published pool, minus the untrained encoder"),
    ("t5a_raw", "mp_raw", "t5a_raw", "RAW on the mined set minus RAW on the pool"),
    ("mp_raw", "mp_filter_bm25", "mp_raw", "FILTER (BM25 teacher) minus RAW, mined set"),
    ("mp_raw", "mp_sub", "mp_raw", "size-matched subsample minus RAW, mined set"),
)


def mined_pilot(root: Path) -> Table:
    tr = Trace()
    eff = _csv(root, "results/tables/mp/mp_effects.csv", tr)
    mdd = _csv(root, "results/tables/mp/mp_mdd.csv", tr)
    lv = (("L2", "ndcg10", "d_c_lo", "d_c_hi"), ("L3", "recall100", "d_q_lo", "d_q_hi"))
    out: list[list[str]] = []
    nq: dict[str, Row] = {}
    for reference, name, ref, display in _MINED_ROWS:
        cells = [tr.label(display), ""]
        for level, metric, lo, hi in lv:
            ref_name = ref if ref == "base" else f"{ref}:mean"
            r = _pick(
                eff,
                reference=reference,
                name=f"{name}:mean",
                ref=ref_name,
                level=level,
                reading=READING,
                metric=metric,
                kind="dense",
                part="mean",
            )
            nq[level] = r
            cells[1] = tr.count(r["seeds"])
            cells.append(_delta(tr, r, lo, hi))
        out.append(cells)
    out.append(RULE)
    cells = [tr.lit("minimum detectable difference, FILTER minus RAW, with repository term"), ""]
    for level, *_ in lv:
        r = _pick(mdd, level=level, contrast="mp_filter_bm25 - mp_raw", variant="with_repo_term")
        cells[1] = tr.count(r["seeds_per_arm"])
        cells.append(tr.num(r["mdd_points"], 2))
    out.append(cells)
    hdr = [
        tr.lit("Contrast"),
        tr.lit("Seeds"),
        tr.label(f"L2 {METRIC_NAMES['ndcg10']}"),
        tr.label(f"L3 {METRIC_NAMES['recall100']}"),
    ]
    facts = (
        f"Development repositories: {tr.count(nq['L2']['queries'])} {tr.level('L2')} queries in "
        f"{tr.count(nq['L2']['repos'])} repositories, {tr.count(nq['L3']['queries'])} "
        f"{tr.level('L3')} queries in {tr.count(nq['L3']['repos'])}; {tr.level('L2')} intervals "
        f"are repository-clustered, {tr.level('L3')} query-level; "
        "mined set and pool both at a matched number of optimizer updates and distinct examples"
    )
    return Table(
        name="mined_pilot",
        title="Training on the pull-request-mined set: gains over the untrained encoder and arms",
        evidence="measured, exploratory",
        facts=facts,
        notes=(
            "Intervals carry query and repository sampling, not retraining variance; at this "
            "number of seeds a difference is read against the minimum detectable difference "
            "in the last row"
        ),
        entries=["E-MINED-PILOT"],
        colspec=_L(0.40) + _R(0.07) + _R(0.2) + _R(0.2),
        wide=True,
        header=hdr,
        rows=out,
        trace=tr,
    )


# ---------------------------------------------------------------------------------------------
# E-ASSEMBLY, E-ASSEMBLY-CAP


def assembly_gold(root: Path) -> Table:
    tr = Trace()
    rows_in = _csv(root, "results/tables/assembly/assembly_gold_summary.csv", tr)
    out: list[list[str]] = []
    seen: dict[str, Row] = {}
    for stage, display in (("bm25", "BM25"), ("rrf", "RRF of BM25 and CodeRankEmbed")):
        for budget in ("4000", "8000", "16000", "32000"):
            cells = [tr.label(display), tr.count(budget)]
            for level in ("L2", "L3"):
                r = _pick(
                    rows_in,
                    group="verified_six",
                    level=level,
                    reading=READING,
                    first_stage=stage,
                    scope="matched",
                    budget=budget,
                )
                seen[level] = r
                lo, hi = _bounds(r["file_share_cl"])
                nlo, nhi = _bounds(r["no_gold_file_cl"])
                cells += [
                    f"{tr.num(r['file_share'])} {tr.interval(lo, hi)}",
                    f"{tr.num(r['no_gold_file'])} {tr.interval(nlo, nhi)}",
                ]
            out.append(cells)
        out.append(RULE)
    out.pop()
    hdr = [
        tr.lit("First stage"),
        tr.lit("Budget"),
        tr.label("L2 gold files in context (%)"),
        tr.label("L2 queries with no gold file (%)"),
        tr.label("L3 gold files in context (%)"),
        tr.label("L3 queries with no gold file (%)"),
    ]
    facts = (
        f"Verified-six, {tr.count(seen['L2']['queries'])} {tr.level('L2')} and "
        f"{tr.count(seen['L3']['queries'])} {tr.level('L3')} queries in "
        f"{tr.count(seen['L2']['repositories'])} repositories; budget in approximate "
        "tokens (not the agent model's tokenizer); repository-clustered intervals; unit cap "
        "as in the cap table; read once"
    )
    return Table(
        name="assembly_gold",
        title="Gold in the assembled context by token budget and first stage",
        evidence="measured, exploratory",
        facts=facts,
        entries=["E-ASSEMBLY"],
        colspec=_L(0.19) + _R(0.07) + _R(0.15) * 4,
        header=hdr,
        rows=out,
        wide=True,
        trace=tr,
    )


def assembly_cap(root: Path) -> Table:
    tr = Trace()
    sel = _csv(root, "results/tables/assembly_cap/assembly_cap_selection.csv", tr)
    summ = _csv(root, "results/tables/assembly_cap/assembly_cap_summary.csv", tr)
    out: list[list[str]] = []
    cells_n = ""
    for cap in ("500", "1000", "2000"):
        r = _pick(sel, max_unit_tokens=cap, cell="")
        cells_n = r["cells"]
        out.append(
            [
                tr.count(cap),
                tr.num(r["intact_share_selection_metric"], 2),
                tr.num(r["file_share_beside"], 2),
                tr.lit("yes" if r["selected"] == "True" else "no"),
            ]
        )
    ref = _pick(
        summ,
        group="dev",
        level="L2",
        reading=READING,
        first_stage="bm25",
        scope="matched",
        budget="8000",
        max_unit_tokens="1000",
    )
    hdr = [
        tr.lit("Unit cap (approximate tokens)"),
        tr.lit("Gold units intact (%)"),
        tr.lit("Gold files in context (%)"),
        tr.lit("Selected"),
    ]
    facts = (
        f"Development repositories only, mean over {tr.count(cells_n)} cells of level, budget and "
        f"first stage ({tr.count(ref['queries'])} {tr.level('L2')} queries in "
        f"{tr.count(ref['repositories'])} repositories in an {tr.level('L2')} cell); the rule "
        "was fixed before the run"
    )
    return Table(
        name="assembly_cap",
        title="Per-unit cap of the assembled context: share of gold units kept intact",
        evidence="measured, exploratory",
        facts=facts,
        entries=["E-ASSEMBLY-CAP"],
        colspec=_R(0.2) + _R(0.2) + _R(0.2) + _L(0.16),
        header=hdr,
        rows=out,
        trace=tr,
    )


def _bounds(text: str) -> tuple[str, str]:
    """Bounds of an interval stored as ``[lo, hi]`` text."""
    lo, hi = text.strip("[]").split(",")
    return lo.strip(), hi.strip()


def contamination(root: Path) -> Table:
    tr = Trace()
    rows_in = _csv(root, "results/tables/x4_contam_scan_by_repo.csv", tr)
    out: list[list[str]] = []
    total = ""
    for r in rows_in:
        if r["floor_nodes"] != "20":
            continue
        if r["repo"].startswith("ALL"):
            total = r["instances"]
            continue
        lo, hi = _bounds(r["functions_matched_share_ci95"])
        share = f"{tr.num(float(r['functions_matched']) / float(r['functions_above_floor']) * 100)}"
        out.append(
            [
                tr.label(r["repo"]).replace("/", "/\\allowbreak "),
                tr.count(r["instances"]),
                tr.count(r["functions_above_floor"]),
                f"{share} [{tr.num(float(lo) * 100)}, {tr.num(float(hi) * 100)}]",
            ]
        )
    allrow = _pick(rows_in, repo="ALL (hash counted once)", floor_nodes="20")
    lo, hi = _bounds(allrow["functions_matched_share_ci95"])
    share_all = tr.num(
        float(allrow["functions_matched"]) / float(allrow["functions_above_floor"]) * 100
    )
    out.append([])
    out.append(
        [
            tr.lit("All twelve (a function counted once)"),
            tr.count(allrow["instances"]),
            tr.count(allrow["functions_above_floor"]),
            f"{share_all} [{tr.num(float(lo) * 100)}, {tr.num(float(hi) * 100)}]",
        ]
    )
    facts = (
        f"Probe: functions of at least {tr.count('20')} syntax-tree nodes at the base commits of "
        f"{tr.count(total)} instances of the final-test benchmark in twelve repositories, "
        "matched by "
        "syntax-tree hash against the documents of a public training corpus. Intervals are Wilson "
        "intervals over functions, descriptive only (functions are not independent draws); a match "
        "is equal code, not evidence that any model was trained on the pair"
    )
    return Table(
        name="contamination",
        title="Share of base-commit functions found in a public code-retrieval training corpus",
        evidence="measured, exploratory",
        facts=facts,
        entries=["E-CONTAM-SCAN"],
        colspec=_L(0.30) + _R(0.15) + _R(0.17) + _R(0.21),
        header=[
            tr.lit("Repository"),
            tr.lit("Instances"),
            tr.lit("Functions"),
            tr.lit("In corpus (%)"),
        ],
        rows=out,
        trace=tr,
    )


def rq3_subset(root: Path) -> Table:
    tr = Trace()
    rows_in = _csv(root, "results/rq3_exec/repo_table.csv", tr)
    out: list[list[str]] = []
    tot = [0, 0, 0]
    for r in sorted(rows_in, key=lambda x: -int(x["executable"])):
        out.append(
            [
                tr.label(r["repo"]).replace("/", "/\\allowbreak "),
                tr.count(r["instances"]),
                tr.count(r["built"]),
                tr.count(r["executable"]),
            ]
        )
        for i, k in enumerate(("instances", "built", "executable")):
            tot[i] += int(r[k])
    out.append([])
    out.append([tr.lit("All")] + [tr.count(v) for v in tot])
    facts = (
        "Counts of instances of the final-test benchmark for which the environment builds "
        "without root or a "
        "container (built in two runs), and for which the reference patch then passes every "
        "named test in two agreeing runs (executable). The executable set is the population of the "
        "resolved-rate claim; it is not a sample of the benchmark"
    )
    return Table(
        name="rq3_subset",
        title="Executable subset of the final-test benchmark by repository",
        evidence="measured, apparatus counts",
        facts=facts,
        entries=["E-RQ3-EXEC"],
        colspec=_L(0.30) + _R(0.16) + _R(0.13) + _R(0.21),
        header=[
            tr.lit("Repository"),
            tr.lit("Instances"),
            tr.lit("Built"),
            tr.lit("Executable"),
        ],
        rows=out,
        trace=tr,
    )


def rq3_power(root: Path) -> Table:
    tr = Trace()
    mdd = _csv(root, "results/rq3_driver/rq3_power_run_noise_mdd.csv", tr)
    asm = _json(root, "results/rq3_driver/rq3_power_run_noise_assumptions.json", tr)
    out: list[list[str]] = []
    for rate in ("0.1", "0.2", "0.3"):
        for kappa in ("1.0", "4.0"):
            cells = [
                _pick(mdd, n="327", rate=rate, kappa=kappa, runs=k)["mdd_points"]
                for k in ("1", "2", "3")
            ]
            out.append(
                [
                    tr.num(float(rate) * 100, 0),
                    tr.num(kappa, 0),
                    *[tr.num(c, 1) for c in cells],
                ]
            )
    facts = (
        f"Simulation of the primary paired contrast on {tr.count('327')} confirmatory instances, "
        f"power {tr.num('0.8', 1)}, {tr.count(str(asm['sims']))} simulated datasets per cell. "
        "The baseline resolved rate and the "
        "instance-heterogeneity parameter are assumptions, since no resolved rate exists; only the "
        "run-to-run agreement of repeated replies is measured in the pilot. The unit is "
        "percentage points of resolved rate"
    )
    return Table(
        name="rq3_power",
        title="Minimum detectable resolved-rate difference with run-to-run noise",
        evidence="reasoned, exploratory (assumed inputs)",
        facts=facts,
        entries=["E-RQ3-DRIVER"],
        colspec=_R(0.17) + _R(0.24) + _R(0.13) + _R(0.13) + _R(0.13),
        header=[
            tr.lit("Baseline rate (%)"),
            tr.lit("Heterogeneity"),
            tr.lit("One run"),
            tr.lit("Two runs"),
            tr.lit("Three runs"),
        ],
        rows=out,
        trace=tr,
    )


def graph_recovery(root: Path) -> Table:
    """Edge recovery of the stored graph under the four stated definitions (ADR-012)."""
    tr = Trace()
    rows_in = _csv(root, "results/tables/p_recovery_summary.csv", tr)
    picks = [
        ("a", f"{repo} (ada)", q)
        for repo in ("flask", "requests", "django")
        for q in ("resolved / non-external", "(resolved + ambiguous) / non-external")
    ]
    picks += [
        ("b", "flask: all in-repo pairs", "recall, resolved"),
        ("b", "flask: all in-repo pairs", "recall, resolved or ambiguous"),
        ("b", "flask: excluding implicit-protocol dunder callees", "recall, resolved"),
        ("b", "flask: excluding implicit-protocol dunder callees", "recall, resolved or ambiguous"),
        ("c", "flask+requests, all", "agreement rate"),
        ("d", "flask+requests, recorded resolved", "claim holds (correct / decided)"),
        ("d", "flask+requests, recorded ambiguous", "claim holds (correct / decided)"),
        ("d", "flask+requests, recorded unresolved", "claim holds (correct / decided)"),
        (
            "d",
            "flask+requests, population-weighted",
            "recall_resolved_over_in_repo_sites",
        ),
        (
            "d",
            "flask+requests, population-weighted",
            "recall_resolved_or_ambiguous_over_in_repo_sites",
        ),
    ]
    out: list[list[str]] = []
    for definition, scope, quantity in picks:
        r = _pick(rows_in, definition=definition, scope=scope, quantity=quantity)
        n = tr.count(r["n"]) if r["n"] else tr.lit("--")
        out.append(
            [
                tr.label(definition),
                tr.label(scope),
                tr.label(quantity.replace("_", " ")),
                n,
                tr.num(float(r["value"]) * 100, 1),
            ]
        )
    facts = (
        "Definition a: share of call sites with a stored resolved edge (and resolved or "
        "ambiguous), among sites whose callee is not external, from the graph build of each "
        "repository at one commit. Definition b: recall against calls observed in a test "
        "suite run, over pairs of units inside the repository (n pairs). Definition c: agreement "
        "with an independent static analyser over a sample of call sites (n sites). Definition d: "
        "manual inspection of a sample of recorded edges, and the population-weighted recall "
        "derived from it. The definitions measure different things and are not averaged"
    )
    return Table(
        name="graph_recovery",
        title="Edge recovery of the stored graph under four definitions",
        evidence="measured, exploratory (three repositories)",
        facts=facts,
        entries=["E-GRAPH-BUILD"],
        colspec=_L(0.05) + _L(0.30) + _L(0.30) + _R(0.09) + _R(0.12),
        header=[
            tr.lit("Def."),
            tr.lit("Scope"),
            tr.lit("Quantity"),
            tr.lit("n"),
            tr.lit("Value (%)"),
        ],
        rows=out,
        trace=tr,
        wide=True,
    )


def graph_storage(root: Path) -> Table:
    """Storage options for the first stored graph: size, load time and expansion latency."""
    tr = Trace()
    rows_in = [
        r
        for r in _csv(root, "results/tables/p_storage_measurements.csv", tr)
        if r["machine"] == "ada"
    ]
    backends = [r["backend"] for r in rows_in if r["repo"] == "django"]
    out: list[list[str]] = []
    for b in backends:
        dj = _pick(rows_in, repo="django", backend=b)
        fl = _pick(rows_in, repo="flask", backend=b)
        out.append(
            [
                tr.label(b).replace("\\_", "\\_\\allowbreak "),
                tr.num(float(fl["size_kb"]) / 1024, 2),
                tr.num(float(dj["size_kb"]) / 1024, 1),
                tr.num(dj["load_s"], 2),
                tr.num(dj["2hop_warm_p50_ms"], 2),
                tr.num(dj["2hop_warm_p99_ms"], 2),
            ]
        )
    facts = (
        "Size on disk of the stored graph of two repositories, and for the larger one the time to "
        "load it and the warm two-hop expansion latency at batch size one (p50 and p99, not the "
        "mean), per storage backend. One cluster node, CPU only; the expansion workload is the "
        "set of queries of the graph pilot, and the number of units reached is the same for every "
        "backend. Nothing here chooses a backend"
    )
    return Table(
        name="graph_storage",
        title="Graph storage options: size, load time and expansion latency",
        evidence="measured, exploratory (two repositories, one node)",
        facts=facts,
        entries=["E-GRAPH-BUILD"],
        colspec=_L(0.17) + _R(0.13) + _R(0.13) + _R(0.11) + _R(0.12) + _R(0.12),
        header=[
            tr.lit("Backend"),
            tr.lit("Size, small repository (MB)"),
            tr.lit("Size, large repository (MB)"),
            tr.lit("Load (s)"),
            tr.label("Two-hop p50 (ms)"),
            tr.label("Two-hop p99 (ms)"),
        ],
        rows=out,
        trace=tr,
    )


# (query_set_id, stage, host prefix, label of the hardware); the latest warm row of each is read
LATENCY_ROWS = (
    ("qenc-coderankembed-t512-v1", "query_encode", "gnode044", "GPU node"),
    ("qenc-coderankembed-t512-v1", "query_encode", "gnode006", "CPU node"),
    ("retrieval-django-v1", "bm25", "Sukhraj", "laptop CPU"),
    ("dsearch-coderankembed-django-torch-v1", "dense_search", "gnode044", "GPU node"),
    ("dsearch-coderankembed-django-v1", "dense_search", "gnode006", "CPU node"),
    ("retrieval-django-v1", "graph_expansion", "Sukhraj", "laptop CPU"),
    ("assembly-django-b8000-v1", "assemble", "Sukhraj", "laptop CPU"),
    ("assembly-django-b8000-v1", "end_to_end", "Sukhraj", "laptop CPU"),
)


def latency_stages(root: Path) -> Table:
    """Per-stage latency from the stored log; stages come from different machines."""
    tr = Trace()
    log = _csv(root, "results/latency/latency_log.csv", tr)
    out: list[list[str]] = []
    for qset, stage, host, hw in LATENCY_ROWS:
        hit = [
            r
            for r in log
            if r["query_set_id"] == qset
            and r["stage"] == stage
            and r["cache_state"] == "warm"
            and r["host"].startswith(host)
        ]
        if not hit:
            raise KeyError((qset, stage, host))
        r = hit[-1]
        out.append(
            [
                tr.label(stage).replace("\\_", "\\_\\allowbreak "),
                tr.lit(hw),
                tr.count(r["n_queries"]),
                tr.num(r["p50_ms"], 2),
                tr.num(r["p95_ms"], 2),
                tr.num(r["p99_ms"], 2),
            ]
        )
    facts = (
        "Warm-cache per-query latency at batch size one, in milliseconds, with the warm-up calls "
        "discarded, from the latest logged row of each stage. The query encoder and dense search "
        "rows use the working code encoder (the encoder does not depend on the repository); every "
        "other row and the dense index use the largest of the three first repositories and its "
        "stored graph. Rows come from different "
        "machines and commits and are not summed; the end-to-end row is lexical retrieval plus "
        "assembly, not the full pipeline"
    )
    return Table(
        name="latency_stages",
        title="Per-stage latency of the query path",
        evidence="measured, exploratory (one query set per stage, mixed hardware)",
        facts=facts,
        entries=["E-LAT-STAGES"],
        colspec=_L(0.22) + _L(0.18) + _R(0.12) + _R(0.10) + _R(0.10) + _R(0.10),
        header=[
            tr.lit("Stage"),
            tr.lit("Hardware"),
            tr.lit("Queries"),
            tr.label("p50"),
            tr.label("p95"),
            tr.label("p99"),
        ],
        rows=out,
        trace=tr,
        wide=True,
    )


def eval_stores(root: Path) -> Table:
    """The eight test-role repositories: queries, snapshots, units and encoding cost."""
    tr = Trace()
    rows_in = _csv(root, "results/tables/eval_repo_build_measured.csv", tr)
    out: list[list[str]] = []
    tot = [0, 0, 0.0]
    for r in rows_in:
        out.append(
            [
                tr.label(r["repository"]),
                tr.count(r["l2_queries"]),
                tr.count(r["units_median_per_snapshot"]),
                tr.count(r["distinct_unit_texts_full_measured"]),
                tr.num(r["encode_gpu_hours_measured"], 3),
            ]
        )
        tot[0] += int(r["l2_queries"])
        tot[1] += int(r["distinct_unit_texts_full_measured"])
        tot[2] += float(r["encode_gpu_hours_measured"])
    out.append([])
    out.append([tr.lit("All"), tr.count(tot[0]), tr.lit("--"), tr.count(tot[1]), tr.num(tot[2], 3)])
    facts = (
        "Build of the unit records, instance caches and dense stores of the eight repositories "
        "that take the test role, fixed by a rule before any result: queries at L2, median "
        "units per snapshot, distinct unit texts of the full class form, and GPU-hours of one "
        "encoding pass (each text of all forms was encoded, so the hours cover more texts than "
        "the column shows). Nothing was evaluated on these repositories"
    )
    return Table(
        name="eval_stores",
        title="Evaluation repositories of the test role: stores built",
        evidence="measured, apparatus counts",
        facts=facts,
        entries=["E-EVAL-REPOS-BUILD"],
        colspec=_L(0.34) + _R(0.14) + _R(0.12) + _R(0.12) + _R(0.12),
        header=[
            tr.lit("Repository"),
            tr.lit("Queries"),
            tr.lit("Units"),
            tr.lit("Texts"),
            tr.lit("GPU-h"),
        ],
        rows=out,
        trace=tr,
        wide=True,
    )


BUILDERS = (
    bm25_repro,
    dense_fusion,
    graph_role,
    noise_dose_response,
    mined_vs_pool_ranks,
    mined_pilot,
    assembly_gold,
    assembly_cap,
    contamination,
    rq3_subset,
    rq3_power,
    graph_recovery,
    graph_storage,
    latency_stages,
    eval_stores,
)


def build_all(root: Path) -> list[Table]:
    """Every table, in report order."""
    tables = [b(root) for b in BUILDERS]
    for t in tables:
        t.check()
    return tables


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_all(root: Path, out_dir: Path, extra: Sequence[str] = ()) -> list[Table]:
    """Write one ``.tex`` fragment per table and ``SOURCES.csv``; return the tables.

    ``extra`` names optional table sets that the report does not input yet: ``rq1_ladder`` adds
    the RQ1 ladder fragments (``ril.analysis.rq1_ladder_tables``), built only from stored tables.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    from ril.analysis import (
        rq2_final_tables,
    )  # after the tables above: nothing is built before the final rows exist

    tables = build_all(root) + rq2_final_tables.build_if_present(root)
    if "rq1_ladder" in extra:
        from ril.analysis import rq1_ladder_tables

        tables += rq1_ladder_tables.build_if_present(root)
    unknown = set(extra) - {"rq1_ladder"}
    if unknown:
        raise ValueError(f"unknown table sets: {sorted(unknown)}")
    lines = ["fragment,source,sha256"]
    for t in tables:
        (out_dir / f"{t.name}.tex").write_text(t.render(), encoding="utf-8")
        for src in sorted(t.trace.sources):
            lines.append(f"{t.name}.tex,{src},{sha256(root / src)}")
    (out_dir / "SOURCES.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tables
