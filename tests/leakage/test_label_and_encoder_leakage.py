"""Leakage checks (b), (c) and (d) of the project test policy.

(b) no patch or gold text in a training query, (c) the quality-signal encoder is not the encoder
being trained, (d) no evaluation code reachable from the training package. The mechanisms are
tested on constructed inputs; (d) also runs on the real package, and (b)/(c) run on real data as
soon as a pool export (``data/processed/pools/*.jsonl``) or a config exists. Must always pass.
"""

from __future__ import annotations

import json

import pytest
import yaml

from ril.config.paths import configs_dir, data_root, repo_root
from ril.training.leakage import assert_distinct_encoders, find_patch_leak, forbidden_reachable


def test_training_package_does_not_reach_evaluation_code() -> None:
    assert forbidden_reachable(repo_root()) == []


def test_patch_text_in_a_query_is_caught() -> None:
    patch = (
        "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n"
        "-old_value = compute_something(first, second)\n"
        "+new_value = compute_something(first, second)\n"
    )
    assert find_patch_leak("Fix: new_value = compute_something(first, second)", patch)
    assert find_patch_leak("compute_something is wrong for empty input", patch) == []


def test_identical_encoders_are_refused() -> None:
    with pytest.raises(ValueError):
        assert_distinct_encoders("Org/Encoder", "org/encoder@abc123")
    assert_distinct_encoders("org/pretrained-ranker", "org/encoder-to-train")


def test_no_patch_text_in_exported_pool_queries() -> None:
    """Each pool export row needs ``query`` and ``patch``; a verbatim changed line fails."""
    for path in sorted((data_root() / "processed" / "pools").glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                row = json.loads(line)
                assert find_patch_leak(row["query"], row.get("patch", "")) == [], f"{path.name}:{n}"


def test_configs_keep_quality_encoder_apart_from_trained_encoder() -> None:
    paths = sorted(configs_dir().rglob("*.yaml")) + sorted(configs_dir().rglob("*.yml"))
    for path in paths:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        quality = (cfg.get("quality_signal") or {}).get("encoder")
        trained = (cfg.get("training") or {}).get("encoder")
        if quality and trained:
            assert_distinct_encoders(str(quality), str(trained))
