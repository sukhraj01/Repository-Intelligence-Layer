"""Build the exploratory ``configures`` edges of several checkouts and render each for inspection.

Usage: configures_pool.py OUT.json LABEL=DIR=owner/name [...]
Writes, per repository, every ``configures`` edge with the text a reader needs (the configuration
line and the unit it names). The sample for the precision estimate is drawn from this pool by the
caller. Parsing only; nothing is trained on these repositories.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ril.evaluation.edge_samples import edge_key, render_config_edge  # noqa: E402
from ril.parsing.build import BuildConfig, build_repository  # noqa: E402


def main() -> int:
    out = sys.argv[1]
    pool: dict[str, list[dict[str, str]]] = {}
    for spec in sys.argv[2:]:
        label, root, rid = spec.split("=", 2)
        res = build_repository(root, BuildConfig(repo_id=rid, with_history=False))
        units = res.parsed.unit_by_id()
        assert res.configures is not None
        pool[label] = [
            {
                "key": edge_key(label, e),
                "derivation": e.derivation,
                "text": render_config_edge(root, units, e),
                "commit": res.commit,
            }
            for e in res.configures.edges
        ]
    Path(out).write_text(json.dumps(pool, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
