"""Leakage check of the oracle arm's prompts (RQ3, E-RQ3-ORACLE, D168).

The oracle context holds the pre-patch contents of the files the gold patch modifies. The gold
patch itself, the test patch and the test names must never reach a prompt. The check runs on every
prompt (as it would be sent, restored to the original text, context part only: the issue text is
the benchmark's own and equal for every arm) and fails the build on a finding:

* ``patch_header``: a line of the gold or test patch that only a diff has (``diff --git``,
  hunk header, ``--- a/``, ``+++ b/``, ``index``);
* ``added_run``: three consecutive non-blank added lines of the gold or test patch (whitespace
  normalised, at least 40 characters together) as consecutive lines of the context;
* ``test_id``: a full test identifier of FAIL_TO_PASS or PASS_TO_PASS (pytest node id with
  ``::``, or the ``name (module.Class)`` form) as a substring of the context.

Bare test function names occur in test files that any arm may retrieve, so they are counted for
information (``short_test_names``) and never fail the build. A finding is reported by instance,
kind and the SHA-256 of the matched text, never the text.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

EXCERPT_MARK = "## Repository excerpts"
LEAK_CHECK_VERSION = "rq3-oracle-leak/v1"
RUN_LINES = 3
RUN_MIN_CHARS = 40
MIN_ID_CHARS = 8

_HEADER_LINE = re.compile(
    r"^(diff --git |@@ -\d|--- a/|\+\+\+ b/|--- /dev/null|\+\+\+ /dev/null|index [0-9a-f]{6,}\.\.)"
)
_BARE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class GoldTexts:
    """What must not appear in a prompt, for one instance."""

    gold_patch: str
    test_patch: str
    test_ids: tuple[str, ...]


def _norm(line: str) -> str:
    return " ".join(line.split())


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def header_lines(patch: str) -> list[str]:
    """The lines of ``patch`` that only a diff has."""
    return [ln.rstrip() for ln in patch.splitlines() if _HEADER_LINE.match(ln)]


def added_windows(patch: str) -> list[str]:
    """Windows of ``RUN_LINES`` consecutive non-blank added lines, normalised, joined by newlines.

    Blank added lines are skipped (the context's own blank lines would break the match); a window
    shorter than ``RUN_MIN_CHARS`` is dropped (a run of ``pass`` and ``return`` lines is not text).
    """
    out: list[str] = []
    run: list[str] = []

    def flush() -> None:
        for i in range(len(run) - RUN_LINES + 1):
            window = "\n".join(run[i : i + RUN_LINES])
            if len(window.replace("\n", "")) >= RUN_MIN_CHARS:
                out.append(window)
        run.clear()

    for ln in patch.splitlines():
        if ln.startswith("+") and not ln.startswith("+++"):
            body = _norm(ln[1:])
            if body:
                run.append(body)
        elif ln.startswith("\\"):
            continue
        else:
            flush()
    flush()
    return out


def full_test_ids(names: Iterable[str]) -> tuple[list[str], list[str]]:
    """``(identifiers, bare names)``: node ids and ``name (module.Class)`` forms vs plain names."""
    ids: list[str] = []
    bare: list[str] = []
    for n in names:
        n = n.strip()
        if len(n) < MIN_ID_CHARS:
            continue
        (bare if _BARE.match(n) else ids).append(n)
    return ids, bare


def context_of(prompt: str) -> str:
    """The text after the excerpt heading (the part the arm controls)."""
    return prompt.partition(EXCERPT_MARK + "\n\n")[2]


def check_prompt(prompt: str, gold: GoldTexts) -> list[dict[str, str]]:
    """Findings of one prompt: ``[{"kind", "digest"}]``; empty when clean."""
    ctx = context_of(prompt)
    findings: list[dict[str, str]] = []
    ctx_lines = {ln.rstrip() for ln in ctx.splitlines()}
    for which, patch in (("gold", gold.gold_patch), ("test", gold.test_patch)):
        for ln in header_lines(patch):
            if ln in ctx_lines:
                findings.append({"kind": "patch_header", "source": which, "digest": _digest(ln)})
    nonblank = "\n".join(n for n in (_norm(ln) for ln in ctx.splitlines()) if n)
    for which, patch in (("gold", gold.gold_patch), ("test", gold.test_patch)):
        seen: set[str] = set()
        for w in added_windows(patch):
            if w in nonblank and w not in seen:
                seen.add(w)
                findings.append({"kind": "added_run", "source": which, "digest": _digest(w)})
    ids, _ = full_test_ids(gold.test_ids)
    for t in ids:
        if t in ctx:
            findings.append({"kind": "test_id", "source": "tests", "digest": _digest(t)})
    return findings


def short_test_name_count(prompt: str, gold: GoldTexts) -> int:
    """Number of bare test names (information only) that occur in the context."""
    ctx = context_of(prompt)
    _, bare = full_test_ids(gold.test_ids)
    return sum(1 for b in set(bare) if re.search(rf"\b{re.escape(b)}\b", ctx))


def check_items(
    items: Sequence[Mapping[str, Any]], gold: Mapping[str, GoldTexts], restore: Any = None
) -> dict[str, Any]:
    """Check every prepared item (``load_items`` rows with ``prompt`` and optional ``restore``).

    The prompt is restored to its original text first when a map exists, so a placeholder cannot
    hide a match. An item whose instance has no gold texts is an error, not a pass.
    """
    from ril.agent.providers.pseudonymise import restore_text

    rows: list[dict[str, Any]] = []
    by_kind: Counter[str] = Counter()
    short_total = 0
    for it in items:
        iid = str(it["instance_id"])
        if iid not in gold:
            raise ValueError(f"no gold texts for {iid}: the check cannot pass an unchecked prompt")
        prompt = restore_text(str(it["prompt"]), it.get("restore"))
        found = check_prompt(prompt, gold[iid])
        short = short_test_name_count(prompt, gold[iid])
        short_total += short
        for f in found:
            by_kind[f["kind"]] += 1
        rows.append(
            {
                "instance_id": iid,
                "arm": str(it["arm"]),
                "prompt_sha256": str(it["prompt_sha256"]),
                "findings": found,
                "short_test_names": short,
            }
        )
    return {
        "version": LEAK_CHECK_VERSION,
        "prompts_checked": len(rows),
        "instances": len({r["instance_id"] for r in rows}),
        "findings": sum(len(r["findings"]) for r in rows),
        "prompts_with_findings": sum(1 for r in rows if r["findings"]),
        "by_kind": dict(sorted(by_kind.items())),
        "short_test_names_total": short_total,
        "clean": not any(r["findings"] for r in rows),
        "rows": rows,
    }


def report_json(report: Mapping[str, Any]) -> str:
    return json.dumps(report, indent=1, sort_keys=True) + "\n"


def parse_test_list(value: Any) -> list[str]:
    """A FAIL_TO_PASS / PASS_TO_PASS cell: a JSON list string or a list."""
    if isinstance(value, str):
        out = json.loads(value) if value.strip() else []
    else:
        out = list(value) if value is not None else []
    return [str(x) for x in out]
