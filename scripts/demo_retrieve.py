"""Run the retriever demonstration on one held-out instance (thin wrapper).

Usage: demo_retrieve.py [INSTANCE] [--no-dense] [--pause] [--color] [--archive FILE.tar.gz]
Implements ``docs/DEMO.md``. Logic lives in ``ril/bench/demo_retrieve.py``.
"""

from __future__ import annotations

import argparse
import datetime
import io
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TextIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.bench import demo_retrieve as demo  # noqa: E402
from ril.config.paths import configs_dir, processed_dir, repo_root  # noqa: E402
from ril.util.seed import set_seed  # noqa: E402


class _Tee:
    """Write to the terminal and to a buffer."""

    def __init__(self, first: TextIO, second: TextIO) -> None:
        self.first, self.second = first, second

    def write(self, text: str) -> int:
        self.second.write(text)
        return self.first.write(text)

    def flush(self) -> None:
        self.first.flush()


def _commit(root: Path) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    dirty = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--", "ril", "scripts", "configs"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return done.stdout.strip() + (" (working tree has uncommitted changes)" if dirty else "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("instance", nargs="?", default="", help="default: the fixed selection rule")
    ap.add_argument("--no-dense", action="store_true", help="fast mode: BM25 only, no dense stage")
    ap.add_argument("--pause", action="store_true", help="wait for Enter before each stage")
    ap.add_argument("--color", choices=("auto", "always", "never"), default="auto")
    ap.add_argument("--archive", default="", help="context archive to compare byte by byte")
    ap.add_argument("--repo-dir", default="", help="checkout at the base commit (default: export)")
    ap.add_argument("--transcript", default="", help="also write a recorded transcript to FILE")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    set_seed(args.seed)

    root = repo_root()
    ids = (root / "results/rq3_driver/ids_heldout.txt").read_text().split()
    instance = args.instance
    if instance:
        chosen = "given on the command line"
    else:
        counts = demo.unit_counts(
            ids, str(root / demo.UNIT_COUNTS_TABLE), str(processed_dir() / demo.CACHE_DIR)
        )
        instance, n = demo.select_instance(counts)
        chosen = f"fewest units of {len(ids)} held-out instances ({n}); ties by identifier"
    cfg = demo.load_frozen(str(configs_dir() / "frozen" / "rq3_contexts.json"))
    color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty())

    def pause() -> None:
        sys.stdout.write("   [Enter to continue] ")
        sys.stdout.flush()
        sys.stdin.readline()
        sys.stdout.write("\r" + " " * 30 + "\r")

    with tempfile.TemporaryDirectory(prefix="demo_checkout_") as tmp:
        inputs = demo.real_inputs(
            instance,
            checkout_dir=tmp,
            use_dense=not args.no_dense,
            chosen_by=chosen,
            archive=args.archive or None,
            repo_dir=args.repo_dir or None,
        )
        buffer = io.StringIO()
        stream = _Tee(sys.stdout, buffer) if args.transcript else sys.stdout
        report = demo.run_demo(
            inputs,
            cfg,
            stream,
            pause=pause if args.pause else None,
            color=color,
        )
    if args.transcript:
        text = demo.transcript_text(
            report,
            buffer.getvalue(),
            commit=_commit(root),
            mode="no dense stage" if args.no_dense else "dense stage on stored scores",
            date=datetime.date.today().isoformat(),
        )
        Path(args.transcript).parent.mkdir(parents=True, exist_ok=True)
        Path(args.transcript).write_text(text, encoding="utf-8")
    return 1 if report.identity == "different" else 0


if __name__ == "__main__":
    raise SystemExit(main())
