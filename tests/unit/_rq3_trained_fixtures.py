"""Synthetic inputs for the trained-arm tests: retained folders, a prepared store, caches, units.

No torch, no cluster: the encoder is the bag-of-characters fake of ``test_dense_encoder`` behind the
real ``DenseEncoder`` interface, the prepared store has the layout ``score_units`` reads, and the
instance caches are replaced by a stand-in for ``read_cache``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from ril.assembly.assemble import UnitText
from ril.evaluation import eval_sets
from ril.evaluation.x2_dense import append_store, query_key, text_hash
from ril.retrieval.dense_encoder import ENCODERS, DenseEncoder
from ril.training import retention
from tests.unit.test_dense_encoder import FakeBackend

REPO = "o/r"
REPO_DIR = "o__r"
DATASET = "ds"
FOLDER = "fd"
INSTANCES = ("o__r-1", "o__r-2", "o__r-3")
EXTRA = "o__r-extra"
"""An instance of the stored part that is not in the executable subset (must be dropped)."""
RUN_ID = "mined_raw_u100_s100"
EMAIL = "someone.real@corp.example"


def unit_texts(instance: str) -> list[str]:
    """Six unit texts per instance; the first carries an e-mail address (pseudonymisation)."""
    base = int(instance.rsplit("-", 1)[1]) if instance[-1].isdigit() else 9
    out = []
    for i in range(6):
        body = "\n".join(f"    v{i}_{j}_{base} = {j + base}" for j in range(8))
        mail = f"    # contact {EMAIL}\n" if i == 0 else ""
        out.append(f"def u{i}():\n{mail}{body}")
    return out


def unit_records(instance: str) -> list[UnitText]:
    files = ["a.py", "a.py", "b.py", "c.py", "c.py", "d.py"]
    return [
        UnitText(f"{f}::u{i}", f, 10 * i + 1, 10 * i + 9, "function", f"u{i}", t)
        for i, (f, t) in enumerate(zip(files, unit_texts(instance), strict=True))
    ]


def retained_folder(root: Path, cell: str, seed: int, payload: bytes = b"w" * 16) -> Path:
    """A retained model folder with a real manifest (``verify_retained`` passes)."""
    name = f"{cell}__s{seed}__abcd{seed}"
    folder = root / name
    (folder / retention.MODEL_SUBDIR).mkdir(parents=True)
    (folder / retention.MODEL_SUBDIR / "weights.bin").write_bytes(payload + bytes([seed % 256]))
    files = retention.tree_files(str(folder / retention.MODEL_SUBDIR))
    manifest = {
        "version": retention.MANIFEST_VERSION,
        "cell": cell,
        "seed": seed,
        "updates": 100,
        "config_hash": f"{seed:064x}",
        "commit": "deadbeef",
        "arm": {"name": cell},
        "sha256": retention.tree_digest(files),
        "bytes": sum(int(r["bytes"]) for r in files),
        "files": files,
    }
    retention.write_manifest(str(folder), manifest)
    return folder


def fake_encoder(max_tokens: int = 64) -> DenseEncoder:
    return DenseEncoder(ENCODERS["coderankembed"].with_max_tokens(max_tokens), FakeBackend())


def build_prepared_store(
    home: Path, instances: tuple[str, ...] = (*INSTANCES, EXTRA)
) -> eval_sets.EvalSetSpec:
    """A prepared store under ``home`` and the one-part set that points at it."""
    prep = home / "prep"
    home.mkdir(parents=True, exist_ok=True)
    cfg = home / "e1.yaml"
    cfg.write_text(
        "folders:\n"
        f"  - {{role: test, dataset: {DATASET}, folder: {FOLDER}, repo: {REPO}, "
        "levels: [L2], units: true}\n",
        encoding="utf-8",
    )
    store = str(prep / "texts_units" / f"{REPO_DIR}.s0.jsonl")
    qstore = prep / "queries" / f"L2__{DATASET}__{FOLDER}.jsonl"
    qstore.parent.mkdir(parents=True, exist_ok=True)
    (prep / "units").mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    qrows = []
    for iid in instances:
        texts = unit_texts(iid)
        append_store(store, texts, seen)
        meta = {
            "version": "x2-dense/v1",
            "instance": iid,
            "repo_dir": REPO_DIR,
            "role": "test",
            "dataset": DATASET,
            "folder": FOLDER,
            "levels": ["L2"],
            "units": len(texts),
        }
        np.savez_compressed(
            prep / "units" / f"{iid}.npz",
            meta=np.asarray(json.dumps(meta)),
            hashes_full=np.asarray([text_hash(t) for t in texts], dtype="U40"),
        )
        qrows.append(
            {"h": query_key("L2", DATASET, FOLDER, iid), "t": f"fix the failing case in {iid} u3"}
        )
    qstore.write_text("".join(json.dumps(r) + "\n" for r in qrows), encoding="utf-8")
    part = eval_sets.EvalPart("p", str(cfg), "prep", "e3", "raw")
    return eval_sets.EvalSetSpec("exec377", eval_sets.FINAL, ("test",), (part,), "test", "D127")


def instance_inputs(instance: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """(arrays, meta) standing in for ``read_cache`` of one instance."""
    rng = np.random.default_rng(int(instance[-1]) if instance[-1].isdigit() else 9)
    arrays = {
        "scores_L2": rng.random(6),
        "gold_L2_units_all": np.asarray([1, 5], dtype=np.int32),
        "gold_L2_units_all_nomod": np.asarray([1], dtype=np.int32),
        "gold_L3_units_all": np.asarray([5], dtype=np.int32),
        "gold_L3_units_all_nomod": np.asarray([], dtype=np.int32),
    }
    meta = {"instance": instance, "repo_id": REPO, "base_commit": "abc", "units": 6}
    return arrays, meta
