"""Retained final models: list them, check each manifest, print the archiving plan.

ROOT [--dest-alias ALIAS] [--dest-dir DIR]

Reads only. The copy to the archive account is a separate numbered script kept outside the
repository; this tool exits 1 if any manifest check fails.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", help="directory of retained folders (the job's RETAIN_DIR)")
    p.add_argument("--dest-alias", default=None)
    p.add_argument("--dest-dir", default="ril_retained")
    a = p.parse_args(argv)
    from ril.training import retention as rt

    rows = rt.inventory(a.root)
    for r in rows:
        size = int(r["bytes"] or 0)
        sys.stdout.write(
            f"{r['folder']}\t{r['cell']}\tseed {r['seed']}\t{size} bytes\t{r['status']}\n"
        )
    for line in rt.archive_plan(rows, source=a.root, dest_alias=a.dest_alias, dest_dir=a.dest_dir):
        sys.stdout.write(line + "\n")
    return 0 if all(r["status"] == "ok" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
