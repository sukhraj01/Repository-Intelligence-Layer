"""Repository-level disjointness of the training stack's selection (must always pass).

The selection that feeds training drops every directory whose repository is on the held-out list
(v2, core plus the Loc-Bench tier, aliases and the rename cache), with the real list; keeping them
is possible only through the explicit leakage-pilot switch, and is then recorded in the
selection file.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from ril.config.paths import repo_root
from ril.training.pool_check import split_instance_dir
from ril.training.pool_rank_jobs import held_out_predicate
from ril.training.train_jobs import select_job
from tests.unit._training_fixtures import fake_archive, synthetic_examples

HELD = repo_root() / "data" / "held_out" / "held_out_repos.json"
RENAMES = repo_root() / "data" / "held_out" / "rename_cache.json"


def _listing(tmp: Path) -> str:
    exs = synthetic_examples(repos=2, prs=2)
    held = [
        replace(e, instance_id=f"django__django-{1000 + i}", repo="django/django")
        for i, e in enumerate(exs[:2])
    ]
    held += [replace(exs[2], instance_id="PSF__Requests-77", repo="psf/requests")]  # case-folded
    listing, _ = fake_archive(exs + held)
    path = tmp / "listing.json"
    path.write_text(json.dumps(listing), encoding="utf-8")
    return str(path)


def test_selection_is_repository_disjoint_from_the_held_out_list(tmp_path: Path) -> None:
    listing = _listing(tmp_path)
    pred = held_out_predicate(str(HELD), str(RENAMES))
    assert pred("django/django") and pred("psf/requests") and not pred("own/repo0")
    out = tmp_path / "sel.json"
    rec = select_job(
        listing, str(HELD), str(RENAMES), str(out), feature_table=None, max_instances=None, seed=0
    )
    names = json.loads(out.read_text())["names"]
    assert names and not any(pred(split_instance_dir(n)[0]) for n in names)  # type: ignore[index]
    assert rec["stats"]["held_out_dropped"] == 3 and rec["held_out_directories_selected"] == 0
    rec2 = select_job(
        listing,
        str(HELD),
        str(RENAMES),
        str(tmp_path / "sel2.json"),
        feature_table=None,
        max_instances=None,
        seed=0,
        include_held_out=True,
    )
    assert rec2["include_held_out"] and rec2["held_out_directories_selected"] == 3
