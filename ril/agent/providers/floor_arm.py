"""Floor reference arm of RQ3: the prompt carries the issue and no retrieved code.

Implements ``docs/experiments/B.md`` E-RQ3-FLOOR (D169). The rows have the shape that
``ril.agent.providers.rq3_prompts.rows_from_records`` returns, with an empty context, so the same
``build_prompt``, pseudonymisation, screen and item writer prepare them. Because the context shows
no file, the reply parser's path filter (a block's path must be among the files shown) has nothing
to check against; ``prepare_screened`` writes ``paths: null`` for this arm (see
``UNRESTRICTED_PATH_ARMS``).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from ril.agent.providers.calllog import sha256_text

FLOOR_ARM = "floor"
UNRESTRICTED_PATH_ARMS = frozenset({FLOOR_ARM})
Row = dict[str, Any]


def floor_rows(
    issues: Mapping[str, str],
    repos: Mapping[str, str],
    instance_ids: Collection[str],
    budget: int,
) -> tuple[list[Row], list[Row]]:
    """(context rows, skipped): one empty-context row per instance that has an issue text."""
    rows: list[Row] = []
    skipped: list[Row] = []
    for iid in sorted(instance_ids):
        if iid not in issues:
            skipped.append({"instance_id": iid, "reason": "no_issue_text"})
            continue
        rows.append(
            {
                "instance_id": iid,
                "arm": FLOOR_ARM,
                "first_stage": FLOOR_ARM,
                "repo": repos.get(iid, ""),
                "issue": issues[iid],
                "context": "",
                "context_sha256": sha256_text(""),
                "files": [],
                "budget": budget,
                "tokenizer": "none",
            }
        )
    return rows, skipped
