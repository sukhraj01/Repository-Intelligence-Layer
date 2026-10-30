"""Collect a bounded raw PR pilot or replay synthetic recorded responses."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ril.data_mining.github import (  # noqa: E402
    Client,
    GitHubTransport,
    RecordedTransport,
    atomic_json,
    digest,
)
from ril.data_mining.miner import GitSnapshots, RecordedSnapshots, mine  # noqa: E402
from ril.data_mining.ranks import dense_audit_scores, rank_audit  # noqa: E402
from ril.data_mining.recording import synthetic_recording  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("record", "mine", "ranks", "dense"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--recording", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--held-out", type=Path, default=Path("data/held_out/held_out_repos.json"))
    parser.add_argument(
        "--overlap-index",
        type=Path,
        help="JSON object: hashes (integers), corpus_sha256, complete (boolean)",
    )
    parser.add_argument("--dense-scores", type=Path)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.stage == "record":
        atomic_json(args.out, synthetic_recording())
        return
    if args.stage == "ranks":
        rank_audit(args.out, dense_scores=args.dense_scores)
        return
    if args.stage == "dense":
        dense_audit_scores(args.out)
        return
    if args.recording:
        if args.live:
            parser.error("choose live acquisition or recorded responses")
        recording = json.loads(args.recording.read_text())
        config = yaml.safe_load(args.config.read_text()) if args.config else recording["config"]
        held_out = recording["held_out"]
        transport = RecordedTransport(recording)
        snapshots = RecordedSnapshots(recording)
        source_kind = "synthetic_recorded_responses"
        source_identity = digest(recording)
        # The recording's rate waits advance a virtual clock, never a live measurement.
        virtual_time = [0.0]
        client = Client(
            args.out / "api",
            transport,
            clock=lambda: virtual_time[0],
            sleep=lambda seconds: virtual_time.__setitem__(0, virtual_time[0] + seconds),
        )
    else:
        if not args.live or not args.config:
            parser.error("live mode needs --live --config; otherwise supply --recording")
        if not os.environ.get("SLURM_JOB_ID") or not os.environ.get("GITHUB_TOKEN"):
            parser.error("live acquisition requires a Slurm CPU job and GITHUB_TOKEN")
        config = yaml.safe_load(args.config.read_text())
        held_out = json.loads(args.held_out.read_text())
        client = Client(args.out / "api", GitHubTransport())
        snapshots = GitSnapshots(args.out / "git")
        source_kind, source_identity = "live_github", "github-api-cached-at-first-acquisition"
    overlap_index = None
    overlap_identity = None
    if args.overlap_index:
        document = json.loads(args.overlap_index.read_text())
        if not document.get("complete") or not document.get("corpus_sha256"):
            parser.error("a complete held-out corpus index with a corpus identity is required")
        overlap_index = set(map(int, document["hashes"]))
        overlap_identity = digest(document)
    result = mine(
        config,
        args.out,
        client,
        snapshots,
        held_out,
        source_kind=source_kind,
        source_identity=source_identity,
        overlap_index=overlap_index,
        overlap_identity=overlap_identity,
    )
    atomic_json(args.out / "summary.json", result)


if __name__ == "__main__":
    main()
