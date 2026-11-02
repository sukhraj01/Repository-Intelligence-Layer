"""Stage M3 glue: the mined run as a local archive for the lead's rank tooling.

Implements ``docs/experiments/B.md`` E-MINE-PILOT question 4. The rank measurement itself is
``ril.training.pool_rank_jobs`` (published definition of the rank, same text forms, same cut); this
module packs the run root as a zip with a member listing, writes the selection file that covers
every mined directory, and turns rank files into the share table of ``rank_compare``.

Kept compatible with Python 3.10 (the cluster's compute nodes).
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from ril.data_mining.pack import list_dirs, local_fetch, pack_zip, write_listing
from ril.data_mining.rank_compare import min_ranks, rank_sample, reading_rule, share_row
from ril.training import pool_ranks as pr

TOP_KS: tuple[int, ...] = (10, 20, 40)


def prepare(run_root: str, work: str, drop_tests: bool = False) -> dict[str, Any]:
    """Zip, listing and selection file of a run root under ``work`` (idempotent, same bytes).

    ``drop_tests`` prepares the pool-like reading (no test-file functions in the corpora, no test
    positives, directories left without a positive dropped).
    """
    os.makedirs(work, exist_ok=True)
    zip_path = os.path.join(work, "mined.zip")
    n = pack_zip(run_root, zip_path, drop_tests=drop_tests)
    write_listing(zip_path, os.path.join(work, "mined.listing.json"))
    sample = rank_sample(run_root, drop_tests)
    with open(os.path.join(work, "sample.json"), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(sample, sort_keys=True) + "\n")
    return {"directories": n, "zip": zip_path, "drop_tests": drop_tests}


def bm25(work: str, out: str, *, form: str = "code") -> dict[str, Any]:
    """BM25 ranks of every mined directory (CPU)."""
    from ril.training import pool_rank_jobs as jobs

    return jobs.bm25_job(
        os.path.join(work, "mined.listing.json"),
        out,
        sample_path=os.path.join(work, "sample.json"),
        form=form,
        fetch=local_fetch,
    )


def dense(
    work: str, out: str, log: str, *, teachers: Sequence[str], cut: int, form: str = "code"
) -> dict[str, Any]:
    """Dense ranks of every mined directory (GPU; the CUDA gate runs inside the job)."""
    from ril.training import pool_rank_jobs as jobs

    return jobs.dense_job(
        os.path.join(work, "mined.listing.json"),
        out,
        log,
        teachers=teachers,
        cut=cut,
        sample_path=os.path.join(work, "sample.json"),
        form=form,
        fetch=local_fetch,
    )


def tables(
    sample_path: str, rank_files: Sequence[str], *, yield_per_pr: float, seed: int = 0
) -> dict[str, Any]:
    """Shares with no positive in the top K per teacher and text form, plus the reading rule."""
    with open(sample_path, encoding="utf-8") as handle:
        sample = json.load(handle)["sample"]
    repo_of = {str(r["dir"]): str(r["repo"]) for r in sample}
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for path in rank_files:
        for row in pr.read_jsonl(path):
            groups[(str(row["teacher"]), str(row.get("form", "code")))].append(row)
    rows: list[dict[str, Any]] = []
    with_positive = 0
    for (teacher, form), recs in sorted(groups.items()):
        ranks = min_ranks(recs)
        with_positive = max(with_positive, len(ranks))
        for k in TOP_KS:
            s = share_row(teacher, k, ranks, repo_of, seed)
            rows.append(
                {
                    "teacher": teacher,
                    "form": form,
                    "k": k,
                    "directories": s.directories,
                    "no_positive_in_top_k": s.no_positive_in_top_k,
                    "share": round(s.share, 4),
                    "wilson": [round(s.wilson_low, 4), round(s.wilson_high, 4)],
                    "cluster_bootstrap": [round(s.cluster_low, 4), round(s.cluster_high, 4)],
                    "repositories": len({repo_of[d] for d in ranks}),
                }
            )
    return {"rows": rows, "reading": reading_rule(with_positive, yield_per_pr)}


def estimate(run_root: str, texts_per_second: float, teachers: int = 3) -> dict[str, Any]:
    """Distinct function texts per repository over the run's directories, and the GPU cost.

    The rank tooling encodes each distinct text of a repository once (``RepoVectorCache``), so the
    cost is the number of distinct texts, not of corpus rows. Counted twice: over whole corpora,
    and over corpora outside test files (the pool-like variant). ``teachers`` is the number of
    dense passes (SweRankEmbed-Small and CodeRankEmbed on the code text, SweRankEmbed-Small on the
    stored text). ``texts_per_second`` is a measured rate the caller names.
    """
    import hashlib
    import json as _json

    from ril.data_mining.agreement import is_test_id
    from ril.data_mining.files import read_corpus

    seen_all: dict[str, set[str]] = {}
    seen_non_test: dict[str, set[str]] = {}
    rows_all = rows_non_test = 0
    for name in list_dirs(run_root):
        base = os.path.join(run_root, "pr", name)
        with open(os.path.join(base, "pr_meta.json"), encoding="utf-8") as handle:
            repo = str(_json.load(handle)["repo"])
        a = seen_all.setdefault(repo, set())
        b = seen_non_test.setdefault(repo, set())
        for line in read_corpus(base).decode("utf-8").splitlines():
            if not line.strip():
                continue
            row = _json.loads(line)
            digest = hashlib.sha1(str(row["text"]).encode("utf-8")).hexdigest()
            rows_all += 1
            a.add(digest)
            if not is_test_id(str(row["_id"])):
                rows_non_test += 1
                b.add(digest)
    distinct_all = sum(len(v) for v in seen_all.values())
    distinct_nt = sum(len(v) for v in seen_non_test.values())
    hours = pr.gpu_hours_estimate

    return {
        "directories": len(list_dirs(run_root)),
        "repositories": len(seen_all),
        "corpus_rows": {"all": rows_all, "non_test": rows_non_test},
        "distinct_texts": {"all": distinct_all, "non_test": distinct_nt},
        "texts_per_second": texts_per_second,
        "dense_passes": teachers,
        "gpu_hours": {
            "all": round(hours(distinct_all, texts_per_second, encoders=teachers), 3),
            "non_test": round(hours(distinct_nt, texts_per_second, encoders=teachers), 3),
        },
    }
