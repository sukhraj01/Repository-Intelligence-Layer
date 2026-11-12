"""Final-report tables (``ril.analysis.report_tables``): rebuilt from stored files, no typed number.

Implements the check of ``reports/README.md``: every figure traces to ``results/``. The committed
fragments must equal a fresh build from the stored files; every digit string in a fragment must
have been read from a file; each caption states the evidence class, n and an entry id that the
experiment index lists.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from ril.analysis import report_tables as rt

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "reports" / "final" / "generated"
INDEX_FILES = (
    "docs/EXPERIMENTS.md",
    "docs/experiments/B.md",
    "docs/experiments/A.md",
    "docs/experiments/C.md",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_committed_fragments_equal_a_fresh_build(tmp_path: Path) -> None:
    tables = rt.write_all(ROOT, tmp_path)
    names = sorted([f"{t.name}.tex" for t in tables] + ["SOURCES.csv"])
    assert names == sorted(p.name for p in GENERATED.iterdir())
    for name in names:
        assert _read(tmp_path / name) == _read(GENERATED / name), name


def test_no_number_is_typed_in_a_fragment() -> None:
    for t in rt.build_all(ROOT):
        text = re.sub(
            r"\\label\{[^}]*\}|\\entry\{[^}]*\}|\\begin\{tabular\}\{.*\}\n",
            "",
            _read(GENERATED / f"{t.name}.tex"),
        )
        assert not set(rt._digits(text)) - t.trace.numbers, t.name


def test_a_typed_digit_is_refused() -> None:
    tr = rt.Trace()
    with pytest.raises(ValueError):
        tr.lit("about 7 points")
    t = rt.bm25_repro(ROOT)
    t.facts = t.facts + ", about 7 points"
    with pytest.raises(ValueError):
        t.check()


def test_spot_values_equal_the_stored_tables() -> None:
    with open(ROOT / "results/tables/e1_aggregation.csv", encoding="utf-8") as h:
        agg = [
            r
            for r in csv.DictReader(h)
            if r["set"] == "verified12"
            and r["level"] == "L2"
            and r["convention"] == "mean_of_dataset_macro_over_folders"
        ]
    assert len(agg) == 1
    text = _read(GENERATED / "bm25_repro.tex")
    assert f"{float(agg[0]['ndcg10']):.2f}" in text
    assert f"{float(agg[0]['recall100']):.2f}" in text
    with open(ROOT / "results/tables/n1/n1_effects.csv", encoding="utf-8") as h:
        rows = [
            r
            for r in csv.DictReader(h)
            if r["label"] == "E-PILOT-NOISE r=0.4"
            and r["reference"] == "n1_r40_raw"
            and r["name"] == "n1_r40_filter_bm25:mean"
            and r["level"] == "L2"
            and r["reading"] == "units_all_nomod"
            and r["kind"] == "dense"
        ]
    assert len(rows) == 1
    assert f"+{float(rows[0]['d']):.1f}" in _read(GENERATED / "noise_dose_response.tex")


def test_captions_state_evidence_class_n_and_entry() -> None:
    index = "\n".join(_read(ROOT / p) for p in INDEX_FILES)
    for t in rt.build_all(ROOT):
        cap = t.caption()
        assert "Evidence class" in cap and t.evidence.split(";")[0].split(",")[0] in (
            "measured",
            "operator_reported",
            "reasoned",
            "synthetic",
        )
        assert any(
            w in cap
            for w in (
                "queries",
                "folder",
                "directories",
                "instances",
                "call sites",
                "repositories",
                "pull requests",
            )
        ), t.name
        for entry in t.entries:
            assert f"| {entry} " in index, (t.name, entry)
        if t.name not in (
            "bm25_repro",
            "rq3_subset",
            "graph_recovery",
            "graph_storage",
            "latency_stages",
            "eval_stores",
            "mined_full",
            "mined_quarantine",
        ):
            assert "exploratory" in t.evidence, t.name


def test_every_source_exists_and_is_hashed() -> None:
    with open(GENERATED / "SOURCES.csv", encoding="utf-8") as h:
        rows = list(csv.DictReader(h))
    assert rows
    for r in rows:
        assert rt.sha256(ROOT / r["source"]) == r["sha256"], r["source"]
        assert r["source"].startswith("results/")


REPORT = ROOT / "reports" / "final" / "final_report.tex"


# Built with every report build and read from the stored tables, but not input: the second encoder
# of the ladder and its per-stage latency table (the report states their content in prose).
BUILT_NOT_INPUT = {"rq1_ladder_qwen3", "rq1_ladder_pairs_qwen3", "rq1_ladder_latency"}


def test_report_inputs_every_fragment_and_every_slot_names_an_entry() -> None:
    text = _read(REPORT)
    for p in GENERATED.glob("*.tex"):
        if p.stem in BUILT_NOT_INPUT:
            assert f"\\input{{generated/{p.stem}}}" not in text, p.name
            continue
        assert f"\\input{{generated/{p.stem}}}" in text, p.name
    index = "\n".join(_read(ROOT / p) for p in INDEX_FILES)
    slots = re.findall(r"\\todo\{((?:[^{}]|\{[^{}]*\})*)\}", text)
    assert slots
    named = [
        s
        for s in slots
        if re.search(r"\\entry\{E-[A-Z0-9-]+\}|Related-work refresh|Abstract|^cite:", s)
    ]
    # every slot but the literature refresh and a missing citation names the entry that fills it
    assert len(named) == len(slots)
    for entry in re.findall(r"\\entry\{(E-[A-Z0-9-]+)\}", text):
        assert f"| {entry} " in index, entry


def test_citations_resolve_to_notes_read_in_full() -> None:
    text = _read(REPORT)
    keys = set(re.findall(r"\\bibitem\{([^}]+)\}", text))
    cited = {k for group in re.findall(r"\\cite\{([^}]+)\}", text) for k in group.split(",")}
    assert cited <= keys, sorted(cited - keys)
    notes = re.findall(r"\\bibitem\{([^}]+)\}\s*% note: (\S+)", text)
    assert {k for k, _ in notes} == keys
    for _, slug in notes:
        first = _read(ROOT / "knowledge" / "papers" / f"{slug}.md").splitlines()[0]
        if first.startswith("read: in full except"):
            # a partly read note may be cited only if the report states the exception
            assert "numbered source listings" in text, slug
        else:
            assert first.startswith("read: full"), slug


def test_report_keeps_the_claim_discipline() -> None:
    text = _read(REPORT).lower()
    for phrase in (
        "first systematic study",
        "no one has studied",
        "novel approach to code retrieval",
        "fixed training budget",
    ):
        assert phrase not in text, phrase
    assert "matched optimization budgets" in text
    assert "our literature audit did not identify a study that systematically evaluates" in text


def test_new_tables_equal_the_stored_files() -> None:
    with open(ROOT / "results/tables/eval_repo_build_measured.csv", encoding="utf-8") as h:
        evals = list(csv.DictReader(h))
    text = _read(GENERATED / "eval_stores.tex")
    assert f"{sum(int(r['l2_queries']) for r in evals)}" in text
    assert f"{sum(int(r['distinct_unit_texts_full_measured']) for r in evals)}" in text
    with open(ROOT / "results/tables/p_recovery_summary.csv", encoding="utf-8") as h:
        rec = [
            r
            for r in csv.DictReader(h)
            if r["definition"] == "a"
            and r["scope"] == "flask (ada)"
            and r["quantity"] == "resolved / non-external"
        ]
    assert len(rec) == 1
    assert f"{float(rec[0]['value']) * 100:.1f}" in _read(GENERATED / "graph_recovery.tex")
    with open(ROOT / "results/latency/latency_log.csv", encoding="utf-8") as h:
        log = [
            r
            for r in csv.DictReader(h)
            if r["query_set_id"] == "retrieval-django-v1"
            and r["stage"] == "bm25"
            and r["cache_state"] == "warm"
        ]
    assert f"{float(log[-1]['p99_ms']):.2f}" in _read(GENERATED / "latency_stages.tex")


def test_latency_rows_are_never_summed_or_averaged() -> None:
    text = _read(GENERATED / "latency_stages.tex").lower()
    assert "mean" not in text.replace("not the mean", "")
    assert "not summed" in text


def test_full_mined_tables_equal_the_stored_files() -> None:
    import json

    y = json.loads((ROOT / "results/mining/full/yield_report.json").read_text())["yield"]
    text = _read(GENERATED / "mined_full.tex")
    assert str(y["status"]["mined"]) in text and str(y["positives_unrestricted"]) in text
    q = _read(GENERATED / "mined_quarantine.tex")
    assert str(y["status"]["quarantined"]) in q
    assert sum(y["quarantine_by_reason"].values()) == y["status"]["quarantined"]
