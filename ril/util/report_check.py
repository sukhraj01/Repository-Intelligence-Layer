"""Checks on the hand-written text of the final report.

Implements ``reports/README.md`` ("every figure traces to ``results/``"): the generated tables are
checked by ``tests/unit/test_report_tables.py``; this module checks the prose around them. A line of
prose that holds a number must end in a ``%`` comment naming the experiment entry or the stored file
the number was read from, so that no number is typed from memory. It also lists the slots that are
still empty with the entry each waits for, and the citations and cross-references that do not
resolve.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SOURCE_COMMENT = re.compile(
    r"(?<!\\)%.*?(paper_reported|E-[A-Z0-9]+(?:-[A-Z0-9]+)*|docs/|results/|data/|specs/|knowledge/|ADR-\d+|DEV-\d+|\bD\d+\b)"
)
# tokens that contain digits but are names, labels or fixed vocabulary, not quantities
NAMES = re.compile(
    r"\\(?:ref|cref|cite|entry|label|input)\{[^}]*\}"
    r"|\bRQ\d\b|Level~\d|\bL[123]\b|\b[OTDQ]\d+\b|ADR-\d+|DEV-\d+|BM25|nDCG@10|Recall@100"
    r"|\\vspace\{[^}]*\}|\\texttt\{[^}]*\}|\bp\d{2}\b|Python~2|E-[A-Z0-9]+(?:-[A-Z0-9]+)*|\\section\{[^}]*\}|\\subsection\{[^}]*\}|\\paragraph\{[^}]*\}"
)
NUMBER = re.compile(r"\d")


@dataclass(frozen=True)
class Finding:
    line: int
    kind: str
    text: str

    def render(self) -> str:
        return f"line {self.line}: {self.kind}: {self.text}"


def _blank_balanced(text: str, opener: str) -> str:
    """Replace every ``opener{...}`` (braces balanced) by spaces, keeping the newlines."""
    out: list[str] = []
    i = 0
    while True:
        j = text.find(opener, i)
        if j < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        k = j + len(opener)
        depth = 1
        while k < len(text) and depth:
            if text[k] == "{" and text[k - 1] != "\\":
                depth += 1
            elif text[k] == "}" and text[k - 1] != "\\":
                depth -= 1
            k += 1
        out.append(re.sub(r"[^\n]", " ", text[j:k]))
        i = k
    return "".join(out)


def _body(text: str) -> str:
    """The prose: after ``\\begin{document}``, before the bibliography (or the end)."""
    start = text.index("\\begin{document}")
    end = text.find("\\begin{thebibliography}")
    end = text.index("\\end{document}") if end < 0 else end
    body = text[start:end]
    body = _blank_balanced(body, "\\todo{")
    return re.sub(
        r"\\begin\{table\*\}.*?\\end\{table\*\}",
        lambda m: re.sub(r"[^\n]", " ", m.group(0)),
        body,
        flags=re.S,
    )


def _flush(pending: list[Finding], findings: list[Finding]) -> None:
    findings.extend(pending)
    pending.clear()


def untraced_numbers(text: str) -> list[Finding]:
    """Prose lines with a number and no source comment.

    A source comment closes the lines above it in the same paragraph (a sentence group ends with
    its comment); a paragraph, item or environment boundary with numbers still open is a finding.
    """
    offset = text[: text.index("\\begin{document}")].count("\n")
    findings: list[Finding] = []
    pending: list[Finding] = []
    for n, line in enumerate(_body(text).splitlines(), start=offset + 1):
        if not line.strip() or re.match(
            r"\s*\\(paragraph|subsection|section|item|begin|end)\b", line
        ):
            _flush(pending, findings)
        code = re.split(r"(?<!\\)%", line, maxsplit=1)[0]
        code = NAMES.sub(" ", code)
        if NUMBER.search(code):
            pending.append(Finding(n, "number without a source comment", line.strip()[:90]))
        if SOURCE_COMMENT.search(line):
            pending.clear()
    _flush(pending, findings)
    return findings


def slots(text: str) -> list[tuple[int, str, list[str]]]:
    """Every ``\\todo`` slot: its line, its text and the entries it names."""
    out: list[tuple[int, str, list[str]]] = []
    for m in re.finditer(r"\\todo\{((?:[^{}]|\{[^{}]*\})*)\}", text):
        body = " ".join(m.group(1).split())
        out.append(
            (
                text[: m.start()].count("\n") + 1,
                body,
                re.findall(r"\\entry\{(E-[A-Z0-9-]+)\}", body),
            )
        )
    return out


def unresolved(text: str) -> list[Finding]:
    """Citations without a ``\\bibitem`` and references without a ``\\label``."""
    findings: list[Finding] = []
    keys = set(re.findall(r"\\bibitem\{([^}]+)\}", text))
    labels = set(re.findall(r"\\label\{([^}]+)\}", text))
    for n, line in enumerate(text.splitlines(), start=1):
        code = re.split(r"(?<!\\)%", line, maxsplit=1)[0]
        for group in re.findall(r"\\cite\{([^}]+)\}", code):
            for key in group.split(","):
                if key.strip() not in keys:
                    findings.append(Finding(n, "undefined citation", key.strip()))
        for group in re.findall(r"\\(?:ref|cref)\{([^}]+)\}", code):
            if group not in labels and not group.startswith("tab:"):
                findings.append(Finding(n, "undefined reference", group))
    return findings


STORED_PATH = re.compile(
    r"(?:results|knowledge|docs|specs|data|configs)/[A-Za-z0-9_./\-]*[A-Za-z0-9_]"
    r"\.(?:csv|json|md|txt|yaml)"
)


def missing_sources(text: str, root: Path) -> list[Finding]:
    """Stored files named in a ``%`` source comment that do not exist under ``root``.

    A comment that names a file which is not there is a number nobody can trace; the existence of
    the named path is the cheapest check that the comment was written from the file.
    """
    findings: list[Finding] = []
    for n, line in enumerate(text.splitlines(), start=1):
        parts = re.split(r"(?<!\\)%", line, maxsplit=1)
        if len(parts) < 2:
            continue
        for path in sorted(set(STORED_PATH.findall(parts[1]))):
            if not (root / path).exists():
                findings.append(Finding(n, "source file not found", path))
    return findings


# ---------------------------------------------------------------------------------------------
# The two-page report (reports/short): stricter source comments and a consistency check against
# the full report. Implements docs/experiments/B.md E-REPORT-SHORT.

_AMOUNT = re.compile(r"\d[\d,]*(?:\.\d+)?")
_FRAGMENT_NOISE = re.compile(
    r"\\label\{[^}]*\}|\\entry\{[^}]*\}|\\begin\{tabular\}\{.*\}|\\setlength\{[^}]*\}\{[^}]*\}"
    r"|\\begin\{table\*?\}\[[^\]]*\]|\bR\d\b|\bp(?:50|95|99)\b"
)


def untraced_numbers_same_line(text: str) -> list[Finding]:
    """Prose lines of a short report with a number and no source comment *on the same line*.

    Stricter than ``untraced_numbers``: a comment does not close the lines above it, so every
    sentence group that holds a number is one line ending in its own comment.
    """
    offset = text[: text.index("\\begin{document}")].count("\n")
    findings: list[Finding] = []
    for n, line in enumerate(_body(text).splitlines(), start=offset + 1):
        code = NAMES.sub(" ", re.split(r"(?<!\\)%", line, maxsplit=1)[0])
        if NUMBER.search(code) and not SOURCE_COMMENT.search(line):
            findings.append(
                Finding(n, "number without a source comment on its line", line.strip()[:90])
            )
    return findings


def _amounts(text: str) -> list[str]:
    """Numbers of a text with names, labels and markup removed; thousands commas dropped."""
    out: list[str] = []
    for raw in text.splitlines():
        code = re.split(r"(?<!\\)%", raw, maxsplit=1)[0]
        code = _FRAGMENT_NOISE.sub(" ", NAMES.sub(" ", code))
        out += [m.replace(",", "") for m in _AMOUNT.findall(code)]
    return out


def _places(number: str) -> int:
    return len(number.split(".")[1]) if "." in number else 0


def _round_half_up(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def numbers_missing_from_full(short_text: str, full_text: str) -> list[Finding]:
    """Numbers of the short report that stand nowhere in the full report with the same value.

    ``short_text`` and ``full_text`` are the report source followed by its generated fragments.
    A number matches when the full text holds the same value, or a value with more decimals that
    rounds to it (a table printed at one decimal where the full report prints two).
    """
    full: dict[Decimal, int] = {}
    for a in _amounts(full_text):
        full[Decimal(a)] = max(full.get(Decimal(a), 0), _places(a))
    findings: list[Finding] = []
    for n, raw in enumerate(short_text.splitlines(), start=1):
        for a in _amounts(raw):
            x = Decimal(a)
            p = _places(a)
            if x in full or any(
                places > p and _round_half_up(y, p) == x for y, places in full.items()
            ):
                continue
            findings.append(Finding(n, "number not in the full report", a))
    return findings
