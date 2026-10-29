"""Syntax-tree hashes of the functions a reference patch edits, before and after the patch.

Implements the edited-function follow-up of decision D23 (``docs/EXPERIMENTS.md``
E-CONTAM-EDITED). The contamination scan matches corpus documents to functions at an instance's base
commit; this module says which of those functions the instance's reference patch edits, so the
match rate of the edited functions can be read beside the match rate of the others.

Definitions (fixed here, not tuned):

* a function is *edited* if an old-file line touched by the patch lies in its line span
  (``ril.evaluation.label_noise.edited_lines``: a removed or changed line counts, a pure insertion
  counts the two old lines around it); functions are the function and method units of the
  CodeUnit definition, nested definitions fold into their parent;
* its *post* version is the unit with the same file, qualified name and occurrence index after the
  patch is applied to the base file (``None`` when the unit is gone or the patch does not apply);
* an edited function is *changed* when its post syntax-tree hash differs from its pre hash (a
  docstring-, comment- or layout-only edit does not change it);
* *added* functions are post-patch units with no pre unit of the same key in a patched file.

Only hashes and node counts are kept, never source text. Needs Python 3.10 (the parser does).
"""

from __future__ import annotations

import ast
import os
import subprocess
import tempfile
from collections import Counter
from collections.abc import Mapping
from typing import Any

from ril.evaluation.label_noise import edited_lines, span_overlaps
from ril.parsing.code_unit import CodeUnit
from ril.parsing.repository_parser import ParseOptions, parse_file
from ril.training.contamination import function_hashes
from ril.training.contamination_index import list_blobs, read_blobs

Record = dict[str, Any]
Keyed = dict[tuple[str, str, int], tuple[str | None, int, int, int]]

EDITED_VERSION = "contam-edited/v1"


def function_units(path: str, raw: bytes, repo: str) -> list[CodeUnit] | None:
    """Function and method units of one file; ``None`` if it does not parse."""
    try:
        text = raw.decode("utf-8")
        tree = ast.parse(raw, filename=path)
    except (SyntaxError, ValueError, UnicodeError, RecursionError, MemoryError):
        return None
    units, _ = parse_file(
        repo_id=repo,
        path=path,
        text=text,
        tree=tree,
        module_name="m",
        is_package=False,
        last_modified="",
        options=ParseOptions(),
    )
    return [u for u in units if u.unit_type in ("function", "method")]


def keyed_hashes(path: str, units: list[CodeUnit]) -> Keyed:
    """``(file, qualified name, occurrence) -> (ast hash, nodes, start line, end line)``."""
    seen: Counter[tuple[str, str]] = Counter()
    out: Keyed = {}
    for u in units:
        seen[(path, u.qualified_name)] += 1
        fh = function_hashes(u.source)
        out[(path, u.qualified_name, seen[(path, u.qualified_name)])] = (
            fh.ast,
            fh.nodes,
            u.start_line,
            u.end_line,
        )
    return out


def apply_patch(files: Mapping[str, bytes], patch: str) -> dict[str, bytes] | None:
    """The patched contents of ``files`` (base file contents by path), or ``None`` on failure.

    Runs ``git apply`` in an empty scratch directory (no repository involved), so only the
    listed files can change. Files the patch creates are returned too.
    """
    with tempfile.TemporaryDirectory() as tmp:
        for rel, data in files.items():
            dest = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(data)
        pfile = os.path.join(tempfile.gettempdir(), f".ril_patch_{os.getpid()}.diff")
        with open(pfile, "w", encoding="utf-8", newline="") as fh:
            fh.write(patch if patch.endswith("\n") else patch + "\n")
        try:
            res = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", pfile],
                cwd=tmp,
                capture_output=True,
                check=False,
            )
        finally:
            os.unlink(pfile)
        if res.returncode != 0:
            return None
        out: dict[str, bytes] = {}
        for root, _, names in os.walk(tmp):
            for n in names:
                full = os.path.join(root, n)
                with open(full, "rb") as fh:
                    out[os.path.relpath(full, tmp)] = fh.read()
        return out


def patch_py_paths(patch: str) -> list[str]:
    """Python paths on the ``---`` / ``+++`` lines of a patch (``a/``, ``b/`` removed)."""
    paths: list[str] = []
    for line in patch.splitlines():
        if line.startswith(("--- ", "+++ ")):
            p = line[4:].strip().split("\t")[0]
            if p == "/dev/null":
                continue
            p = p[2:] if p.startswith(("a/", "b/")) else p
            if p.endswith(".py") and p not in paths:
                paths.append(p)
    return paths


def python_part(patch: str) -> str:
    """The sections of a ``diff --git`` patch that touch ``.py`` files (the rest cannot apply)."""
    sections: list[list[str]] = []
    for line in patch.splitlines(keepends=True):
        if line.startswith("diff --git "):
            sections.append([])
        if sections:
            sections[-1].append(line)
    if not sections:
        return patch
    keep = [s for s in sections if s[0].split(" b/")[-1].strip().endswith(".py")]
    return "".join("".join(s) for s in keep)


def edited_functions(git_dir: str, repo: str, commit: str, patch: str) -> Record:
    """Edited and added functions of one instance (hashes and sizes, no text).

    Returns ``edited`` (one record per edited function: file, qualified name, pre hash and nodes,
    post hash and nodes or ``None``), ``added``, ``same_file_unedited`` (hash and nodes of the
    other functions of the patched files, the matched comparator), file counts, and flags for a
    patch that does not apply or a file that does not parse.
    """
    patch = python_part(patch)
    blobs = dict(list_blobs(git_dir, commit))
    named = patch_py_paths(patch)
    paths = [p for p in named if p in blobs]
    new_paths = [p for p in named if p not in blobs]
    contents = read_blobs(git_dir, [blobs[p] for p in paths])
    base = {p: contents[blobs[p]] for p in paths}
    patched = apply_patch(base, patch) if patch.strip() else {}
    lines = edited_lines(patch)
    rec: Record = {
        "patched_py_files": len(paths),
        "created_py_files": len(new_paths),
        "patch_applied": patched is not None,
        "unparseable_pre": 0,
        "unparseable_post": 0,
        "edited": [],
        "added": [],
        "same_file_unedited": [],
    }
    for p in paths:
        pre_units = function_units(p, base[p], repo)
        if pre_units is None:
            rec["unparseable_pre"] += 1
            continue
        pre = keyed_hashes(p, pre_units)
        post: Keyed | None = None
        if patched is not None and p in patched:
            post_units = function_units(p, patched[p], repo)
            if post_units is None:
                rec["unparseable_post"] += 1
            else:
                post = keyed_hashes(p, post_units)
        elif patched is not None:
            post = {}  # the file was deleted by the patch
        edited = lines.get(p, frozenset())
        for key, (h, n, a, z) in pre.items():
            if not span_overlaps(edited, a, z):
                if h is not None:
                    rec["same_file_unedited"].append([h, n])
                continue
            after = None if post is None else post.get(key)
            rec["edited"].append(
                {
                    "file": key[0],
                    "qname": key[1],
                    "occurrence": key[2],
                    "pre_hash": h,
                    "pre_nodes": n,
                    "post_hash": None if after is None else after[0],
                    "post_nodes": None if after is None else after[1],
                    "post_known": post is not None,
                }
            )
        if post is not None:
            for key, (h, n, _a, _z) in post.items():
                if key not in pre:
                    rec["added"].append({"file": key[0], "qname": key[1], "hash": h, "nodes": n})
    for p in new_paths:
        if patched is None or p not in patched:
            continue
        units = function_units(p, patched[p], repo)
        if units is None:
            rec["unparseable_post"] += 1
            continue
        for key, (h, n, _a, _z) in keyed_hashes(p, units).items():
            rec["added"].append({"file": key[0], "qname": key[1], "hash": h, "nodes": n})
    return rec


def edited_for_instances(
    git_dirs: Mapping[str, str],
    instances: Mapping[str, tuple[str, str, str]],
) -> dict[str, Record]:
    """``edited_functions`` for ``instance id -> (repo, base commit, patch)``."""
    return {
        iid: edited_functions(git_dirs[repo], repo, commit, patch)
        for iid, (repo, commit, patch) in sorted(instances.items())
    }
