"""Measured cost of the evaluation-repository build next to the inventory estimate (D100).

Implements the "measured against estimated" table of ``docs/experiments/B.md``
E-EVAL-REPOS-BUILD. The inventory itself is not edited (the selection records its hash); the
estimate columns are copied from it beside the measured ones.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from typing import Any

Record = dict[str, Any]
COLUMNS = (
    "repository",
    "l2_queries",
    "snapshots",
    "units_median_per_snapshot",
    "units_per_snapshot_estimated",
    "parse_seconds_measured",
    "e3_prepare_seconds_measured",
    "parse_seconds_estimated",
    "distinct_unit_texts_full_measured",
    "distinct_unit_texts_estimated",
    "texts_encoded_all_forms",
    "encode_seconds_units",
    "texts_per_second",
    "encode_gpu_hours_measured",
    "encode_gpu_hours_estimated_at_229",
    "encode_gpu_hours_estimated_at_178",
)


def store_key(repository: str) -> str:
    return repository.replace("/", "__")


def build_rows(
    selected: Sequence[Mapping[str, Any]],
    inventory: Mapping[str, Mapping[str, str]],
    cache_stats: Mapping[str, Mapping[str, Any]],
    verify: Mapping[str, Mapping[str, Any]],
    encode_stores: Sequence[Mapping[str, Any]],
) -> list[Record]:
    """One row per selected repository; ``encode_stores`` is the ``stores`` list of the run log."""
    seconds = {s["store"]: float(s["seconds_now"]) for s in encode_stores}
    texts = {s["store"]: int(s["texts"]) for s in encode_stores}
    rows: list[Record] = []
    for item in selected:
        repo = str(item["repository"])
        inv = inventory[repo]
        cs = cache_stats[repo]
        key = store_key(repo)
        ver = verify[key]
        if ver["missing"]:
            raise ValueError(f"{repo}: {ver['missing']} unit texts have no stored vector")
        enc_s = seconds[f"units__{key}"]
        rows.append(
            {
                "repository": repo,
                "l2_queries": int(item["l2_queries"]),
                "snapshots": int(cs["snapshots"]),
                "units_median_per_snapshot": int(cs["units_median"]),
                "units_per_snapshot_estimated": int(float(inv["units_per_snapshot"])),
                "parse_seconds_measured": round(float(cs["seconds"]["parse"]), 1),
                "e3_prepare_seconds_measured": round(float(cs["seconds_total"]), 1),
                "parse_seconds_estimated": float(inv["parse_seconds"]),
                "distinct_unit_texts_full_measured": int(ver["distinct_hashes"]),
                "distinct_unit_texts_estimated": int(float(inv["distinct_unit_texts"])),
                "texts_encoded_all_forms": texts[f"units__{key}"],
                "encode_seconds_units": round(enc_s, 1),
                "texts_per_second": round(texts[f"units__{key}"] / enc_s, 1),
                "encode_gpu_hours_measured": round(enc_s / 3600, 4),
                "encode_gpu_hours_estimated_at_229": float(inv["encode_gpu_hours_at_229"]),
                "encode_gpu_hours_estimated_at_178": float(inv["encode_gpu_hours_at_178"]),
            }
        )
    return rows


def write_csv(rows: Sequence[Mapping[str, Any]], path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=list(COLUMNS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
