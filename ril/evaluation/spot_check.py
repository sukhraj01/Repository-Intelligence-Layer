"""Second-reader spot-check of edge labels produced by one reader: draw, render, score agreement.

The precision and inspection labels of the first graph build (ADR-012 definition (d), the 20
`ambiguous` sets inside it, and the sampled precision of the exploratory `tests` and `configures`
edges, ADR-011 addendum D19) were assigned by one reader, the author of the build. This module draws
a seeded sample of those labelled items, renders each with its source context and the claim under
test but **without** the label, keeps the labels in a separate key, and scores a second reader's
answers against the key (raw agreement and Cohen's kappa).

Implements the open step named in ADR-012 ("a second reader for the 100-edge sample").
"""

from __future__ import annotations

import csv
import random
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

LABELS: tuple[str, ...] = ("correct", "incorrect", "unclear")
"""Answer categories, shared by every source table."""

SourceReader = Callable[[str, str], list[str] | None]
"""(repository label, path in the repository) -> file lines, or None if unavailable."""


@dataclass(frozen=True)
class EdgeKey:
    """The parts of an edge key written by ``ril.evaluation.edge_samples.edge_key``."""

    repo: str
    family: str
    src: str
    site: str
    targets: tuple[str, ...]
    derivation: str

    @property
    def site_path(self) -> str:
        return self.site.partition(":")[0]

    @property
    def site_line(self) -> int:
        rest = self.site.partition(":")[2].split(":")[0]
        return int(rest) if rest.isdigit() else 0


def parse_edge_key(key: str) -> EdgeKey:
    """Split ``repo|family|src|site|target[|target...]|derivation`` (targets may be empty)."""
    parts = key.split("|")
    if len(parts) < 6:
        raise ValueError(f"edge key has {len(parts)} fields, expected at least 6: {key!r}")
    targets = tuple(t for t in parts[4:-1] if t)
    return EdgeKey(parts[0], parts[1], parts[2], parts[3], targets, parts[-1])


@dataclass(frozen=True)
class LabelledItem:
    """One labelled row of a source table."""

    source: str  # "call_site", "ambiguous_set", "tests", "configures"
    table: str  # file name of the source table
    row: str  # the table's own row number ("n")
    stratum: str
    edge: EdgeKey
    label: str


@dataclass
class SpotCheck:
    """A drawn sample: items in sheet order with their public ids."""

    seed: int
    quotas: dict[str, int]
    items: list[tuple[str, LabelledItem]] = field(default_factory=list)


def load_items(tables_dir: Path) -> dict[str, list[LabelledItem]]:
    """Read the three label tables into the four sources of the spot-check.

    The 20 `ambiguous` rows of the 100-edge inspection sample form their own source, so the
    100-edge source holds the other 80 rows; no row appears in two sources.
    """
    specs = (
        ("p_edge_inspection_sample.csv", None),
        ("p_tests_edges_precision_sample.csv", "tests"),
        ("p_configures_edges_precision_sample.csv", "configures"),
    )
    out: dict[str, list[LabelledItem]] = {
        "call_site": [],
        "ambiguous_set": [],
        "tests": [],
        "configures": [],
    }
    for name, fixed in specs:
        with (tables_dir / name).open(encoding="utf-8", newline="") as handle:
            for r in csv.DictReader(handle):
                if fixed is not None:
                    source = fixed
                else:
                    source = "ambiguous_set" if r["stratum"] == "ambiguous" else "call_site"
                label = r["label"].strip()
                if label not in LABELS:
                    raise ValueError(f"{name} row {r['n']}: unknown label {label!r}")
                item = LabelledItem(
                    source, name, r["n"], r["stratum"], parse_edge_key(r["edge_key"]), label
                )
                out[source].append(item)
    return out


def draw(
    pools: Mapping[str, Sequence[LabelledItem]], quotas: Mapping[str, int], seed: int
) -> SpotCheck:
    """Draw ``quotas[source]`` items per source with a seeded RNG, then shuffle the sheet order.

    Each source uses its own RNG stream (``f"{seed}:{source}"``) so that changing one quota does not
    change the items drawn from another. Ids are ``S01``, ``S02``, ... in the shuffled order.
    """
    picked: list[LabelledItem] = []
    for source in sorted(quotas):
        pool = sorted(pools.get(source, []), key=lambda i: (i.table, int(i.row)))
        k = quotas[source]
        if k > len(pool):
            raise ValueError(f"quota {k} for {source} exceeds its pool of {len(pool)}")
        picked.extend(random.Random(f"{seed}:{source}").sample(pool, k))
    random.Random(f"{seed}:order").shuffle(picked)
    width = max(2, len(str(len(picked))))
    return SpotCheck(
        seed=seed,
        quotas=dict(quotas),
        items=[(f"S{i + 1:0{width}d}", it) for i, it in enumerate(picked)],
    )


def claim(item: LabelledItem) -> str:
    """The statement the reader judges, from the recorded status or rule; never the label."""
    e = item.edge
    if item.source == "configures":
        target = e.targets[0] if e.targets else "(none)"
        return (
            f"The configuration line at `{e.site_path}:{e.site_line}` refers to, configures or "
            f"loads the unit `{target}` (rule `{e.derivation}`)."
        )
    if item.source == "tests":
        target = ", ".join(f"`{t}`" for t in e.targets) or "(none)"
        return (
            f"The test `{e.src}` tests {target}: the unit is the subject or part of the subject "
            f"of the test, not incidental set-up (rule `{e.derivation}`)."
        )
    if item.stratum == "resolved":
        return f"The call at the marked line calls the repository unit `{e.targets[0]}`."
    if item.stratum == "ambiguous":
        cands = ", ".join(f"`{t}`" for t in e.targets)
        return f"The call at the marked line calls one of these repository units: {cands}."
    if item.stratum == "external":
        return (
            "The call at the marked line calls nothing defined in the repository (a builtin, the "
            "standard library or a third-party package)."
        )
    if item.stratum == "unresolved":
        return (
            "The callee at the marked line cannot be named by reading the source: it is neither an "
            "identifiable repository unit nor an identifiable external callee (genuinely dynamic)."
        )
    raise ValueError(f"no claim template for source {item.source!r}, stratum {item.stratum!r}")


def context(lines: Sequence[str], line: int, radius: int = 6) -> list[tuple[int, str, bool]]:
    """Lines ``line - radius`` .. ``line + radius`` (1-based, clipped) with the site line marked."""
    if line < 1 or not lines:
        return []
    lo, hi = max(1, line - radius), min(len(lines), line + radius)
    return [(n, lines[n - 1], n == line) for n in range(lo, hi + 1)]


def definition_line(lines: Sequence[str], unit_id: str) -> tuple[int, str] | None:
    """First ``def``/``class`` line of the unit's last name in its file, for orientation only."""
    qual = unit_id.partition("::")[2].split("#")[0]
    name = qual.rsplit(".", 1)[-1]
    if not name or name == "<module>":
        return None
    for n, text in enumerate(lines, start=1):
        s = text.lstrip()
        for kw in ("def ", "async def ", "class "):
            if s.startswith(kw + name) and s[len(kw) + len(name) : len(kw) + len(name) + 1] in (
                "(",
                ":",
            ):
                return n, text.rstrip()
    return None


def _fence(rows: Iterable[tuple[int, str, bool]]) -> list[str]:
    out = ["```text"]
    for n, text, mark in rows:
        out.append(f"{'>>' if mark else '  '}{n:6d} | {text.rstrip()[:160]}")
    out.append("```")
    return out


def render_sheet(check: SpotCheck, read: SourceReader, radius: int = 6) -> str:
    """The reader's sheet: per item, the claim, the site with +-``radius`` lines and the targets.

    No label, stratum outcome or first-reader note appears in the sheet.
    """
    out = [
        "# Edge-label spot-check (second reader)",
        "",
        f"{len(check.items)} items drawn at random (seed {check.seed}; quotas "
        + ", ".join(f"{k} {v}" for k, v in sorted(check.quotas.items()))
        + ") from the labelled samples of the first graph build.",
        "",
        "For each item, read the source and decide whether the **claim** holds. Answer in a CSV "
        "with the header `item,label` and one row per item, `label` one of "
        + ", ".join(f"`{x}`" for x in LABELS)
        + ". Use `unclear` when the source shown (and the repository at that commit) does not "
        "settle it. Do not open the key file before answering.",
        "",
    ]
    for item_id, it in check.items:
        e = it.edge
        kind = {
            "call_site": "call-site edge",
            "ambiguous_set": "call-site edge with a candidate set",
            "tests": "`tests` edge",
            "configures": "`configures` edge",
        }[it.source]
        out += [f"## {item_id} — {kind} ({e.repo})", "", f"**Claim.** {claim(it)}", ""]
        out.append(f"Caller or source unit: `{e.src}`. Site: `{e.site}`.")
        out.append("")
        lines = read(e.repo, e.site_path)
        rows = context(lines or [], e.site_line, radius)
        if rows:
            out += _fence(rows)
        else:
            out.append("_(source file not available; judge from the repository at the commit)_")
        targets = e.targets if it.source != "call_site" or it.stratum == "resolved" else ()
        for t in targets[:6]:
            tpath = t.partition("::")[0]
            tlines = read(e.repo, tpath) or []
            d = definition_line(tlines, t)
            if d:
                where = f"line {d[0]}: `{d[1].strip()[:140]}`"
            elif t.endswith("::<module>"):
                where = "the module unit: the file's code outside every definition"
            else:
                where = "definition line not found"
            out.append(f"- target `{t}` — {where}")
        if len(targets) > 6:
            out.append(f"- ... and {len(targets) - 6} more candidates")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def key_records(check: SpotCheck) -> dict[str, object]:
    """The answer key: for each item id, the first reader's label and where it came from."""
    return {
        "seed": check.seed,
        "quotas": check.quotas,
        "labels_by": "one reader, the author of the first graph build",
        "items": {
            item_id: {
                "label": it.label,
                "source": it.source,
                "table": it.table,
                "row": it.row,
                "stratum": it.stratum,
                "edge_key": "|".join(
                    [it.edge.repo, it.edge.family, it.edge.src, it.edge.site]
                    + list(it.edge.targets)
                    + [it.edge.derivation]
                ),
            }
            for item_id, it in check.items
        },
    }


def read_answers(path: Path) -> dict[str, str]:
    """Read ``item,label`` rows; labels are case- and space-normalised and must be in LABELS."""
    out: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not {"item", "label"} <= set(reader.fieldnames):
            raise ValueError("answers CSV needs the header `item,label`")
        for r in reader:
            item = (r["item"] or "").strip()
            label = (r["label"] or "").strip().lower()
            if not item:
                continue
            if label not in LABELS:
                raise ValueError(f"item {item}: label {label!r} not in {LABELS}")
            if item in out:
                raise ValueError(f"item {item} answered twice")
            out[item] = label
    return out


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    """Cohen's kappa for two paired label sequences; 1.0 when both use one identical label."""
    if len(a) != len(b):
        raise ValueError("sequences differ in length")
    n = len(a)
    if n == 0:
        raise ValueError("no paired labels")
    po = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


def agreement(
    key: Mapping[str, Mapping[str, str]], answers: Mapping[str, str]
) -> dict[str, object]:
    """Raw agreement and Cohen's kappa over the items answered, overall and per source.

    Items in the key without an answer are counted as missing, not as disagreement; answers for
    ids not in the key are reported and ignored.
    """
    paired = [(k, v["label"], answers[k], v["source"]) for k, v in key.items() if k in answers]
    report: dict[str, object] = {
        "n_key": len(key),
        "n_answered": len(paired),
        "missing": sorted(k for k in key if k not in answers),
        "unknown_items": sorted(k for k in answers if k not in key),
    }
    if not paired:
        return report
    first = [p[1] for p in paired]
    second = [p[2] for p in paired]
    report["agreement"] = round(
        sum(x == y for x, y in zip(first, second, strict=True)) / len(paired), 4
    )
    report["cohen_kappa"] = round(cohen_kappa(first, second), 4)
    report["confusion_first_by_second"] = {
        f: {s: sum(1 for p in paired if p[1] == f and p[2] == s) for s in LABELS} for f in LABELS
    }
    per: dict[str, dict[str, float | int]] = {}
    for src in sorted({p[3] for p in paired}):
        sub = [p for p in paired if p[3] == src]
        per[src] = {
            "n": len(sub),
            "agree": sum(1 for p in sub if p[1] == p[2]),
        }
    report["per_source"] = per
    report["disagreements"] = [
        {"item": p[0], "first": p[1], "second": p[2], "source": p[3]}
        for p in paired
        if p[1] != p[2]
    ]
    return report


def raw_url(name: str, commit: str, path: str) -> str:
    """URL of one file of ``owner/name`` at ``commit`` on the public raw-content host."""
    return f"https://raw.githubusercontent.com/{name}/{commit}/{path}"


def make_source_reader(
    repos: Mapping[str, Mapping[str, str]],
    root: Path,
    cache: Path,
    fetch: Callable[[str], bytes] | None = None,
) -> SourceReader:
    """A reader that prefers a local checkout at the right commit and falls back to a cached fetch.

    ``repos[label]`` holds ``name``, ``commit`` and optionally ``local`` (a checkout relative to
    ``root``). The commit of a local checkout is not checked here; the build script checks it.
    Fetched files are cached under ``cache/<label>/<commit>/<path>`` so that a rerun is offline.
    """

    def read(label: str, path: str) -> list[str] | None:
        spec = repos.get(label)
        if spec is None or not path:
            return None
        local = spec.get("local")
        if local:
            p = root / local / path
            return (
                p.read_text(encoding="utf-8", errors="replace").split("\n") if p.is_file() else None
            )
        cached = cache / label / spec["commit"] / path
        if not cached.is_file():
            if fetch is None:
                return None
            try:
                data = fetch(raw_url(spec["name"], spec["commit"], path))
            except OSError:
                return None
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(data)
        return cached.read_text(encoding="utf-8", errors="replace").split("\n")

    return read
