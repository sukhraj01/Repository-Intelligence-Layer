"""Symbolic-link copy of an E3 instance cache restricted to some repositories (no data copied).

  python -I scripts/curve_subset_cache.py SRC_CACHE DST_DIR REPO_DIR [REPO_DIR ...]

REPO_DIR is the cache's ``repo_dir`` (``owner__name``). Used by the learning-curve evaluation so the
X2 evaluation visits only the repositories whose text stores are encoded.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.evaluation.e3_prepare import read_cache  # noqa: E402


def main(argv: list[str]) -> int:
    src, dst, keep = argv[1], argv[2], {x.lower() for x in argv[3:]}
    os.makedirs(dst, exist_ok=True)
    n = 0
    for name in sorted(os.listdir(src)):
        if not name.endswith(".npz"):
            continue
        _, meta = read_cache(os.path.join(src, name))
        repo = meta.get("repo_dir") or str(meta.get("repo_id", "")).replace("/", "__")
        if repo.lower() in keep:
            link = os.path.join(dst, name)
            if not os.path.lexists(link):
                os.symlink(os.path.abspath(os.path.join(src, name)), link)
            n += 1
    sys.stdout.write(f"{n} instances linked\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
