import json
from pathlib import Path

from ril.analysis.rq2_final_table import COLUMNS, write_table

_C = {
    "eval_set": "eight",
    "family": "confirmatory",
    "level": "L2",
    "metric": "ndcg10",
    "contrast": "a - b",
    "repos": 8,
    "queries": 177,
    "d": -0.136,
    "df": 7,
    "ci_cluster": [-1.0, 1.0],
    "ci_uncorrected": [-1.5, 1.22],
    "ci_boot_uncorrected": [-1.0, 1.0],
    "class": "inconclusive",
    "primary": True,
    "status": "confirmatory",
    "holm": {"ci": [-1.7, 1.5], "p_adjusted": 1.0, "rejected": False, "boot": {"rejected": False}},
}


def test_table_reads_summary_without_recomputing(tmp_path: Path) -> None:
    src = tmp_path / "s.json"
    other = {**_C, "metric": "recall100", "holm": None}
    src.write_text(json.dumps({"contrasts": [_C, other]}))
    out = tmp_path / "t.csv"
    assert write_table(src, out) == 2
    lines = out.read_text().splitlines()
    assert lines[0].split(",") == COLUMNS
    row = lines[1]
    assert "-0.14" in row and "[-1.50, +1.22]" in row  # the t interval, centred on the estimate
    assert "[-1.00, +1.00]" in row  # the bootstrap beside it
    assert lines[2].count(",,") >= 1  # no decision for a contrast outside the family
