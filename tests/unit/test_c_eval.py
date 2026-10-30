"""Original-label Rewrite pairing, cached dense validation and the CPU evaluator."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from ril.evaluation.core_bench import evaluate_folder, read_split
from ril.evaluation.rewrite import CachedScores, anchor_counts, folder_hashes
from ril.evaluation.run import run_config

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/c_eval"


def _config(tmp_path: Path) -> Path:
    cfg = yaml.safe_load((ROOT / "configs/experiments/c_eval_smoke.yaml").read_text())
    cfg["data_root"] = str(FIXTURE)
    cfg["output"] = str(tmp_path / "out")
    cfg.pop("log_path")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return path


@pytest.mark.parametrize("level", ["L2", "L3"])
def test_rewrite_ignores_defective_labels_and_candidates(level: str) -> None:
    original = read_split(str(FIXTURE), level, "fixture", "alpha")
    rewrite = read_split(str(FIXTURE), level, "fixture", "alpha", rewrite=True)
    assert original.corpus_ids == rewrite.corpus_ids
    assert rewrite.qrels == {"q1": {"c1"}}
    assert rewrite.queries[0].candidates == ("c1", "c2", "c3")
    assert evaluate_folder(original)[0]["positives"]["c1"]["protocol"] == 1
    assert evaluate_folder(rewrite)[0]["positives"]["c1"]["protocol"] == 2


def test_rewrite_requires_exact_query_identity_but_no_qrels(tmp_path: Path) -> None:
    shutil.copytree(FIXTURE, tmp_path / "data_copy")
    folder = tmp_path / "data_copy/data/Rewrite-LEVEL-2/fixture/alpha"
    (folder / "qrels.jsonl").unlink()
    assert read_split(
        str(tmp_path / "data_copy"), "L2", "fixture", "alpha", rewrite=True
    ).qrels == {"q1": {"c1"}}
    (folder / "queries.jsonl").write_text('{"_id":"wrong", "text":"x"}\n')
    with pytest.raises(ValueError, match="ids must match"):
        read_split(str(tmp_path / "data_copy"), "L2", "fixture", "alpha", rewrite=True)


def _cache(path: Path, *, bad_hash: bool = False) -> None:
    original = read_split(str(FIXTURE), "L2", "fixture", "alpha")
    rewrite = read_split(str(FIXTURE), "L2", "fixture", "alpha", rewrite=True)
    metadata = {
        "encoder": "fixture-encoder",
        "revision": "fixture-v1",
        "max_tokens": 512,
        "query_template": "{query}",
        **folder_hashes(original, rewrite),
    }
    if bad_hash:
        metadata["rewrite_sha256"] = "wrong"
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        corpus_ids=original.corpus_ids,
        query_ids=["q1"],
        original_scores=[[3.0, 2.0, 1.0]],
        rewrite_scores=[[2.0, 3.0, 1.0]],
        metadata=json.dumps(metadata),
    )


def test_cached_dense_scores_validate_wording_and_rank_without_runtime(tmp_path: Path) -> None:
    original = read_split(str(FIXTURE), "L2", "fixture", "alpha")
    rewrite = read_split(str(FIXTURE), "L2", "fixture", "alpha", rewrite=True)
    path = tmp_path / "scores.npz"
    _cache(path)
    cache = CachedScores(str(path), original, rewrite)
    np.testing.assert_array_equal(cache.score(original.queries[0], "original"), [3.0, 2.0, 1.0])
    _cache(path, bad_hash=True)
    with pytest.raises(ValueError, match="content hashes"):
        CachedScores(str(path), original, rewrite)


def test_cpu_entry_point_writes_clustered_metrics_and_standard_rows(tmp_path: Path) -> None:
    path = _config(tmp_path)
    a = run_config(str(path))
    b = run_config(str(path))
    assert a["config_hash"] == b["config_hash"]
    assert a["metrics"] == b["metrics"]
    delta = next(
        r
        for r in a["metrics"]
        if r["level"] == "L2"
        and r["condition"] == "rewrite_minus_original"
        and r["metric"] == "ndcg10"
    )
    assert delta["n"] == 2 and delta["repositories"] == 2
    assert delta["mean"] < 0 and delta["low"] == delta["high"]
    with (tmp_path / "out/latency_log.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 16  # 4 folders x 2 wordings x 2 invocations
    assert all(float(r["p50_ms"]) <= float(r["p95_ms"]) <= float(r["p99_ms"]) for r in rows)
    assert len(a["git_hash"]) == 40


def test_dense_entry_point_uses_pinned_fixture_scores(tmp_path: Path) -> None:
    path = _config(tmp_path)
    cfg = yaml.safe_load(path.read_text())
    cfg["folders"] = [
        {"repo": "example/alpha", "dataset": "fixture", "folder": "alpha", "levels": ["L2"]}
    ]
    cfg["retriever"] = {
        "kind": "cached_dense",
        "cache_root": str(tmp_path / "cache"),
        "encoder": "fixture-encoder",
        "revision": "fixture-v1",
        "max_tokens": 512,
    }
    _cache(tmp_path / "cache/L2/fixture/alpha.npz")
    path.write_text(yaml.safe_dump(cfg))
    result = run_config(str(path))
    assert "excludes encoding" in result["latency_scope"]
    assert result["latency_rows"][0]["stage"] == "cached_scores_lookup"
    cfg["retriever"]["revision"] = "wrong"
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError, match="revision differ"):
        run_config(str(path))


def test_cli_never_imports_torch(tmp_path: Path) -> None:
    path = _config(tmp_path)
    code = (
        "import sys; from ril.evaluation.run import run_config; "
        "run_config(sys.argv[1]); assert 'torch' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code, str(path)], cwd=ROOT, check=True)


def test_anchor_diagnostic_is_exact_and_does_not_claim_a_cause() -> None:
    assert anchor_counts("ConnectionError in `api.connect`", "connect failure") == {
        "anchors_original": 2,
        "anchors_lost": 2,
    }


def test_published_bm25_artifact_rows_exact_to_recorded_precision() -> None:
    # Artifact regression only: raw corpora are required for a new retrieval reproduction.
    with (ROOT / "results/tables/e1_aggregation.csv").open() as handle:
        rows = {(r["set"], r["level"], r["convention"]): r for r in csv.DictReader(handle)}
    for key, expected in {
        ("verified12", "L2", "macro_over_folders"): (11.9392, 46.7412),
        ("verified12", "L3", "macro_over_folders"): (22.1917, 33.8884),
        ("full_l2", "L2", "mean_of_dataset_macro_over_folders"): (13.0029, 38.818),
    }.items():
        row = rows[key]
        assert (float(row["ndcg10"]), float(row["recall100"])) == expected
        assert round(expected[0], 1) == float(row["paper_ndcg10"])
        assert round(expected[1], 1) == float(row["paper_recall100"])


def test_cache_preparer_calls_existing_encoder_and_respects_memory_ceiling(tmp_path: Path) -> None:
    from ril.evaluation.rewrite_cache import write_score_cache
    from ril.retrieval.dense_encoder import DenseEncoder, EncoderSpec

    class Backend:
        max_seq_length = 512
        tokenizer = None

        def encode(self, sentences: list[str], **kwargs: object) -> np.ndarray:
            return np.asarray(
                [[float("render" not in text), float("render" in text)] for text in sentences],
                dtype=np.float32,
            )

    encoder = DenseEncoder(
        EncoderSpec("fixture-encoder", "fixture", "{query}", revision="fixture-v1"), Backend()
    )
    original = read_split(str(FIXTURE), "L2", "fixture", "alpha")
    rewrite = read_split(str(FIXTURE), "L2", "fixture", "alpha", rewrite=True)
    path = tmp_path / "scores.npz"
    with pytest.raises(ValueError, match="memory estimate"):
        write_score_cache(path, original, rewrite, encoder, max_score_bytes=1)
    metadata = write_score_cache(path, original, rewrite, encoder)
    assert metadata["score_memory_bound_bytes"] == 72
    cached = CachedScores(str(path), original, rewrite)
    assert cached.score(original.queries[0], "original")[0] == 1
    assert cached.score(original.queries[0], "rewrite")[0] == 0


@pytest.mark.parametrize("role", ["dev", "fixture"])
def test_verified_cannot_be_mislabeled_dev_or_fixture(tmp_path: Path, role: str) -> None:
    path = _config(tmp_path)
    cfg = yaml.safe_load(path.read_text())
    cfg["role"] = role
    cfg["folders"][0]["repo"] = "django/django"
    cfg["folders"][0]["dataset"] = "SWE-bench_Verified"
    path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError, match="role"):
        run_config(str(path))
