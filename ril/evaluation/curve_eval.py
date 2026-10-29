"""Learning-curve evaluation hook: score the encoder at chosen update counts of one training run.

Implements the evaluation half of ``docs/EXPERIMENTS.md`` E-PILOT-CURVE (exploratory). A
:class:`CurveHook` is handed to ``ril.training.training.train``; at every listed update count it
writes a float16 copy of the encoder to node-local space, evaluates it with the X2 hook
(``ril.evaluation.checkpoint_eval.eval_checkpoint``, development role), keeps only the small
result tables under ``<result_dir>/step_<n>/``, and deletes the copy and the encoded stores. Why:
``$HOME`` holds no checkpoints (about 0.5 GB free), and a curve needs the same evaluation at
several update counts of one run, which the post-hoc ``eval`` command (final model only) cannot do.

The hook is idempotent: a step whose tables exist is skipped, so a resumed run re-entering at a
checkpoint does not repeat it. It copies the model (the training weights stay in float32 and are
not touched) and does not consume the training random number generators.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import copy
import gc
import json
import os
import shutil
import time
from collections.abc import Mapping, Sequence
from typing import Any

from ril.evaluation.checkpoint_eval import eval_checkpoint
from ril.training.encoders import SentenceTransformerEncoder, TrainEncoder, load_trained

CURVE_EVAL_VERSION = "curve-eval/v1"
Record = dict[str, Any]


def step_dir(result_dir: str, n: int) -> str:
    """Where the tables of the evaluation at ``n`` updates go."""
    return os.path.join(result_dir, f"step_{n:05d}")


def save_half(enc: TrainEncoder, path: str) -> None:
    """Write a float16 copy of ``enc`` to ``path`` without changing ``enc``."""
    if not isinstance(enc, SentenceTransformerEncoder):
        enc.save(path)  # the tiny test encoder: nothing to halve
        return
    clone = SentenceTransformerEncoder(enc.spec, copy.deepcopy(enc.module).half())
    clone.save(path)
    del clone


class CurveHook:
    """Evaluate the encoder at ``steps`` update counts (see the module docstring)."""

    def __init__(
        self,
        steps: Sequence[int],
        *,
        eval_cfg: Mapping[str, Any],
        result_dir: str,
        tmp_dir: str,
        e1_config: str,
        prep_dir: str,
        cache_dir: str,
        data_root: str,
        device: str,
    ) -> None:
        self.steps = frozenset(int(s) for s in steps)
        self.eval_cfg = dict(eval_cfg)
        self.result_dir = result_dir
        self.tmp_dir = tmp_dir
        self.e1_config = e1_config
        self.prep_dir = prep_dir
        self.cache_dir = cache_dir
        self.data_root = data_root
        self.device = device
        self.log: list[Record] = []

    def __call__(self, n: int, enc: TrainEncoder) -> None:
        out_dir = step_dir(self.result_dir, n)
        done = os.path.join(out_dir, "step.json")
        if os.path.exists(done):
            return
        t0 = time.perf_counter()
        model_dir = os.path.join(self.tmp_dir, f"snapshot_{n:05d}")
        shutil.rmtree(model_dir, ignore_errors=True)
        save_half(enc, model_dir)
        if self.device.startswith("cuda"):
            import torch

            torch.cuda.empty_cache()
        cfg = {**self.eval_cfg, "variant": f"{self.eval_cfg['variant']}__step{n:05d}"}
        work = os.path.join(self.tmp_dir, f"eval_{n:05d}")
        shutil.rmtree(work, ignore_errors=True)
        trained = load_trained(model_dir, device=self.device)
        res = eval_checkpoint(
            trained,
            cfg,
            e1_config=self.e1_config,
            prep_dir=self.prep_dir,
            cache_dir=self.cache_dir,
            data_root=self.data_root,
            work_dir=work,
            result_dir=out_dir,
            baseline_enc_dirs=None,
            dense_root=os.path.join(work, "dense"),
        )
        del trained
        shutil.rmtree(model_dir, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)
        gc.collect()
        if self.device.startswith("cuda"):
            import torch

            torch.cuda.empty_cache()
        rec = {
            "version": CURVE_EVAL_VERSION,
            "updates": n,
            "variant": cfg["variant"],
            "eval_seconds": round(time.perf_counter() - t0, 1),
            "unit_queries": res.get("unit_queries"),
            "headline": res.get("headline"),
        }
        with open(done, "w", encoding="utf-8") as handle:
            json.dump(rec, handle, sort_keys=True, default=str)
        self.log.append(rec)
