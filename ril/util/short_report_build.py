"""Build and check of the two-page report (``reports/short``).

Implements ``docs/experiments/B.md`` E-REPORT-SHORT: the hard limit is two pages, verified on the
built PDF with ``pdfinfo``; a build with an overfull box, an undefined reference or a citation
warning fails; the tables are regenerated from the stored files first. Type size and margins are
not touched to meet the limit: the source fixes 10 pt and 0.7 in and ``check_source_format``
refuses a smaller body size or margin.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

PAGE_LIMIT = 2
MIN_BODY_PT = 10
MIN_MARGIN_IN = 0.7
BAD_LOG = re.compile(r"Overfull|undefined|Undefined|Citation .* undefined|Rerun to get")


def page_count(pdf: Path) -> int:
    """Number of pages of a PDF, read with ``pdfinfo``."""
    out = subprocess.run(["pdfinfo", str(pdf)], check=True, capture_output=True, text=True).stdout
    m = re.search(r"^Pages:\s+(\d+)", out, flags=re.M)
    if m is None:
        raise ValueError(f"pdfinfo printed no page count for {pdf}")
    return int(m.group(1))


def log_problems(log: str) -> list[str]:
    """Lines of a typesetting log that fail the build: overfull boxes and unresolved references."""
    return [line.strip() for line in log.splitlines() if BAD_LOG.search(line)]


def check_source_format(text: str) -> list[str]:
    """Problems in the document class line and margins: body below 10 pt or margins below 0.7 in."""
    problems: list[str] = []
    m = re.search(r"\\documentclass\[([^\]]*)\]", text)
    size = re.search(r"(\d+)pt", m.group(1)) if m else None
    if size is None or int(size.group(1)) < MIN_BODY_PT:
        problems.append("body size is not given or is below 10 pt")
    g = re.search(r"\\usepackage\[margin=([\d.]+)in\]\{geometry\}", text)
    if g is None or float(g.group(1)) < MIN_MARGIN_IN:
        problems.append("margins are not given or are below 0.7 in")
    for shrink in (r"\\linespread", r"\\renewcommand\{\\baselinestretch", r"\\fontsize", r"\\tiny"):
        if re.search(shrink, text):
            problems.append(f"type or line spacing is changed ({shrink})")
    return problems


def build(root: Path) -> list[str]:
    """Regenerate the tables, typeset, and return the problems (an empty list means success)."""
    from ril.analysis import short_report_tables

    folder = root / "reports" / "short"
    short_report_tables.write_all(root, folder / "generated")
    source = folder / "short_report.tex"
    problems = check_source_format(source.read_text(encoding="utf-8"))
    run = subprocess.run(
        ["tectonic", source.name], cwd=folder, capture_output=True, text=True, check=False
    )
    if run.returncode:
        return [*problems, f"tectonic failed: {run.stderr.strip()[-300:]}"]
    problems += log_problems(run.stdout + run.stderr)
    pages = page_count(folder / "short_report.pdf")
    if pages != PAGE_LIMIT:
        problems.append(f"the PDF has {pages} pages, the limit is exactly {PAGE_LIMIT}")
    return problems
