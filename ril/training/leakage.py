"""Checks that keep evaluation data and its labels out of training.

Implements the project's leakage checks (a to d) and ``docs/04_data_and_ground_truth.md``
("The trap"): (b) no patch or gold text inside a training query, (c) the quality-signal encoder is
not the encoder being trained, (d) no evaluation code or data is reachable from the training
package. Check (a), repository disjointness, lives in ``ril.training.held_out``.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path

_WS_RE = re.compile(r"\s+")
FORBIDDEN_FROM_TRAINING: tuple[str, ...] = ("ril.evaluation", "ril.analysis", "ril.bench")


def _norm(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def patch_lines(patch: str) -> list[str]:
    """Return the changed code lines of a unified diff (added or removed), whitespace-normalised.

    File headers (``+++``/``---``) and lines shorter than ``min_len`` are handled by the caller;
    this only strips the diff markers.
    """
    out: list[str] = []
    for line in patch.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            body = _norm(line[1:])
            if body:
                out.append(body)
    return out


def find_patch_leak(query: str, patch: str, min_len: int = 20) -> list[str]:
    """Return changed patch lines of ``min_len``+ characters that occur verbatim in ``query``.

    A non-empty result means the query repeats text of the gold patch. Short lines are ignored
    because lines such as ``return x`` occur by chance.
    """
    haystack = _norm(query)
    return [ln for ln in patch_lines(patch) if len(ln) >= min_len and ln in haystack]


def assert_distinct_encoders(quality_signal_encoder: str, trained_encoder: str) -> None:
    """Raise ``ValueError`` if the K-rank encoder is the encoder being trained.

    Compared case-insensitively after stripping a trailing path separator and any ``@revision``,
    so ``org/Model``, ``org/model/`` and ``org/model@abc`` are all the same encoder.
    """

    def key(s: str) -> str:
        return s.strip().rstrip("/").split("@", 1)[0].casefold()

    if not key(quality_signal_encoder) or not key(trained_encoder):
        raise ValueError("both encoder identifiers must be non-empty")
    if key(quality_signal_encoder) == key(trained_encoder):
        raise ValueError(
            f"quality signal encoder {quality_signal_encoder!r} is the encoder being trained"
        )


def _module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(path: Path, package: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.rsplit(".", node.level - 1)[0] if node.level > 1 else package
                mod = f"{base}.{node.module}" if node.module else base
            else:
                mod = node.module or ""
            if mod:
                found.add(mod)
                found.update(f"{mod}.{a.name}" for a in node.names)
    return found


def reachable_modules(root: Path, start: str) -> set[str]:
    """Return every ``ril`` module transitively imported by modules under package ``start``.

    ``root`` is the repository root. Modules outside the repository are ignored.
    """
    files = {_module_name(p, root): p for p in (root / "ril").rglob("*.py")}
    todo = [m for m in files if m == start or m.startswith(start + ".")]
    seen: set[str] = set(todo)
    reached: set[str] = set()
    while todo:
        mod = todo.pop()
        pkg = mod if files[mod].name == "__init__.py" else mod.rpartition(".")[0]
        for imp in _imports(files[mod], pkg):
            reached.add(imp)
            parts = imp.split(".")
            for i in range(len(parts), 0, -1):
                cand = ".".join(parts[:i])
                if cand in files and cand not in seen:
                    seen.add(cand)
                    todo.append(cand)
    return reached | seen


def forbidden_reachable(root: Path, start: str = "ril.training") -> list[str]:
    """Return forbidden modules (``FORBIDDEN_FROM_TRAINING``) that ``start`` can reach."""
    reached = reachable_modules(root, start)
    return sorted(
        m for m in reached if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_FROM_TRAINING)
    )


def intersect(a: Iterable[str], b: Iterable[str]) -> list[str]:
    """Return the sorted intersection of two canonical repository collections."""
    return sorted(set(a) & set(b))
