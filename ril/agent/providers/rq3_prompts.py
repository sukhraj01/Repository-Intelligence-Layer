"""Prompts of the executable subset for the RQ3 runs. Implements ``docs/RQ3_PILOT.md`` (D113).

``rows_from_records`` reads the stored contexts of ``ril.assembly.rq3_contexts`` (one record per
instance, arms and budgets inside) and pairs each with the instance's issue text.
``prepare_screened`` then follows the pilot's ``prepare`` path: the same ``build_prompt`` and the
same prompt screen
(public text only; an e-mail address is accepted only if its digest is on the reviewed list). Where
the pilot's ``prepare_items`` raises on the first screen finding, this version writes the prompts
that pass and reports each rejection by (instance, arm) with the finding kinds and digests, so a
whole run can be prepared and the rejections reviewed afterwards.
``check_prefix_identity`` verifies that, for every instance, the prompt text before the excerpts is
byte-identical across arms.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ril.agent.providers.calllog import sha256_text
from ril.agent.providers.patch_format import TEMPLATE_VERSION, build_prompt
from ril.agent.providers.pilot_run import PREPARED_VERSION
from ril.agent.providers.screen import screen_text

EXCERPT_MARK = "## Repository excerpts"
Row = dict[str, Any]


def issues_from_parquet(path: str, instance_ids: Collection[str]) -> dict[str, str]:
    """``problem_statement`` of the benchmark table by instance id, for ``instance_ids``.

    One source for every instance: the 57 executable instances without an L2 label have no query
    folder, and for the labelled ones the folder's L2 text equals this text (E-RQ3-UNITS, 284 of
    284), which ``issue_agreement`` re-checks at preparation.
    """
    import pyarrow.parquet as pq

    table = pq.read_table(path, columns=["instance_id", "problem_statement"]).to_pylist()
    wanted = set(instance_ids)
    return {
        str(r["instance_id"]): str(r["problem_statement"])
        for r in table
        if str(r["instance_id"]) in wanted
    }


def issue_agreement(
    table_issues: Mapping[str, str], folder_issues: Mapping[str, str], instance_ids: Collection[str]
) -> dict[str, Any]:
    """Where an instance has both a table text and a folder L2 text: how many are equal."""
    both = sorted(i for i in instance_ids if i in table_issues and i in folder_issues)
    different = [i for i in both if table_issues[i] != folder_issues[i]]
    return {
        "instances": len(set(instance_ids)),
        "with_table_text": sum(1 for i in instance_ids if i in table_issues),
        "compared_with_folder": len(both),
        "equal": len(both) - len(different),
        "different": different,
    }


def rows_from_records(
    ctx_dir: str,
    issues: Mapping[str, str],
    budget: int,
    arms: Sequence[str],
    instance_ids: Collection[str] | None = None,
) -> tuple[list[Row], list[Row]]:
    """(context rows, skipped) from ``<ctx_dir>/instances/*.gz`` at ``budget`` for ``arms``."""
    from ril.assembly.rq3_contexts import decode_record

    rows: list[Row] = []
    skipped: list[Row] = []
    inst_dir = os.path.join(ctx_dir, "instances")
    for name in sorted(os.listdir(inst_dir)):
        if not name.endswith(".gz"):
            continue
        with open(os.path.join(inst_dir, name), "rb") as handle:
            rec = decode_record(handle.read())
        iid = str(rec["instance"])
        if instance_ids is not None and iid not in instance_ids:
            continue
        if iid not in issues:
            skipped.append({"instance_id": iid, "reason": "no_issue_text"})
            continue
        for arm in arms:
            ctx = rec["contexts"].get(f"{arm}|{budget}")
            if ctx is None:
                skipped.append({"instance_id": iid, "arm": arm, "reason": "no_context"})
                continue
            m = ctx["manifest"]
            rows.append(
                {
                    "instance_id": iid,
                    "arm": arm,
                    "first_stage": arm,
                    "repo": str(rec["repo_id"]),
                    "issue": issues[iid],
                    "context": ctx["context"],
                    "context_sha256": m["context_sha256"],
                    "files": sorted({e["file"] for e in m["entries"]}),
                    "budget": budget,
                    "tokenizer": rec["tokenizer"],
                }
            )
    return rows, skipped


def prepare_screened(
    context_rows: Iterable[Mapping[str, Any]],
    out_dir: str | Path,
    allowed_email_digests: Collection[str] = (),
    forbidden_emails: Iterable[str] = (),
) -> tuple[int, list[Row]]:
    """Write the sendable items; return (number written, rejections).

    A rejection row has ``instance_id``, ``arm``, the finding ``kinds`` and the ``digests`` of the
    matched texts (never the texts). A context that does not match its recorded hash still raises:
    that is a corrupt input, not a screen finding.
    """
    root = Path(out_dir)
    (root / "prompts").mkdir(parents=True, exist_ok=True)
    forbidden = tuple(forbidden_emails)
    items: list[Row] = []
    rejected: list[Row] = []
    seen: set[tuple[str, str]] = set()
    for row in context_rows:
        key = (str(row["instance_id"]), str(row["arm"]))
        if key in seen:
            raise ValueError(f"duplicate (instance, arm) {key}")
        seen.add(key)
        context = str(row["context"])
        if sha256_text(context) != row["context_sha256"]:
            raise ValueError(f"{key}: context does not match its recorded hash")
        prompt = build_prompt(str(row["issue"]), context)
        findings = screen_text(prompt, allowed_email_digests, forbidden)
        if findings:
            rejected.append(
                {
                    "instance_id": key[0],
                    "arm": key[1],
                    "kinds": sorted({f.kind for f in findings}),
                    "digests": sorted({f.digest for f in findings}),
                }
            )
            continue
        digest = sha256_text(prompt)
        (root / "prompts" / f"{digest}.txt").write_text(prompt, encoding="utf-8")
        items.append(
            {
                "instance_id": key[0],
                "arm": key[1],
                "first_stage": row.get("first_stage", key[1]),
                "repo": row.get("repo", ""),
                "budget": row.get("budget"),
                "tokenizer": row.get("tokenizer"),
                "context_sha256": row["context_sha256"],
                "issue_sha256": sha256_text(str(row["issue"])),
                "prompt_sha256": digest,
                "paths": sorted(set(row["files"])),
                "template_version": TEMPLATE_VERSION,
                "prepared_version": PREPARED_VERSION,
            }
        )
    items.sort(key=lambda r: (r["instance_id"], r["arm"]))
    (root / "items.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in items), encoding="utf-8"
    )
    return len(items), rejected


def rejection_table(rejected: Sequence[Mapping[str, Any]]) -> list[Row]:
    """Counts by finding kind and arm, and the number of distinct instances and digests."""
    by: Counter[tuple[str, str]] = Counter()
    for r in rejected:
        for k in r["kinds"]:
            by[(str(r["arm"]), str(k))] += 1
    rows: list[Row] = [
        {"arm": arm, "kind": kind, "prompts_rejected": n} for (arm, kind), n in sorted(by.items())
    ]
    rows.append(
        {
            "arm": "all",
            "kind": "any",
            "prompts_rejected": len(rejected),
            "instances_affected": len({r["instance_id"] for r in rejected}),
            "distinct_digests": len({d for r in rejected for d in r["digests"]}),
        }
    )
    return rows


def prefix_of(prompt: str) -> str:
    """The prompt text before the excerpts (header, issue)."""
    head, mark, _ = prompt.partition(EXCERPT_MARK)
    if not mark:
        raise ValueError("prompt has no excerpt section")
    return head


def check_prefix_identity(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per instance, whether every arm's prompt has the same text before the excerpts.

    ``items`` carry ``prompt`` (as ``load_items`` returns them). The report names the instances that
    differ; an empty list means byte-identity for all.
    """
    by_inst: dict[str, set[str]] = {}
    arms: Counter[str] = Counter()
    for it in items:
        by_inst.setdefault(str(it["instance_id"]), set()).add(sha256_text(prefix_of(it["prompt"])))
        arms[str(it["arm"])] += 1
    bad = sorted(i for i, hashes in by_inst.items() if len(hashes) > 1)
    return {
        "instances": len(by_inst),
        "prompts_by_arm": dict(sorted(arms.items())),
        "differing_instances": bad,
        "identical": not bad,
    }
