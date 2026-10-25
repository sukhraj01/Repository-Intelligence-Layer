"""Retriever training stack: thin command line over ``ril.training.train_jobs``.

Subcommands (logic in ``ril/``):
  select LISTING HELD_OUT RENAME_CACHE OUT [--feature-table T] [--max N] --seed S
         [--include-held-out]  (leakage pilot only)
  cache  LISTING SELECTION OUT_CACHE [--feature-table T] [--form code|pool]
  mine   CACHE OUT --teacher bm25|<encoder> --keep N [--cut C] [--device cpu|cuda]
  train  CONFIG CACHE --results-root R --work-root W --date YYYY-MM-DD [--device cpu|cuda]
         [--feature-table T] [--mined M] [--stop-after U]
  measure CONFIG CACHE OUT_LOG LOG_DIR --shapes B,N,P,T ... [--device cpu|cuda]  (train_step rows)
  eval   CONFIG MODEL_DIR RESULT_DIR --e1-config E --prep P --e3-cache C --data-root D
         --work W [--device cpu|cuda] [--baseline NAME=ENC_DIR ...] [--dense-root R]
         [--eval-override O.yaml]  (merged into the configuration's evaluation section; its
         results go to RESULT_DIR/<label>/ and the results.json key evaluation_<label>)
  teacher CACHE RANKS_OUT MINED_OUT --teacher bm25|<encoder> --keep N [--cut C] [--device D]
         (one pass: K-ranks of every positive and mined candidates)
  features RANKS [RANKS ...] --out CSV --teachers T [T ...] --held-out H --rename-cache R
  run-batch CONFIG [CONFIG ...] --cache C [--feature-table T] [--mined M] --results-root R
         --work-root W --date D --device D <eval options> [--extra-eval O.yaml ...] [--keep-models]
         (train then evaluate each configuration; the cache is read once; finished runs skipped)
Every stage prints a JSON summary; the example cache holds text and stays on the cluster.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _evaluate(
    a: argparse.Namespace,
    config: str,
    model_dir: str,
    result_dir: str,
    override: str | None = None,
) -> dict[str, object]:
    """Wiring only: the configuration's evaluation section (plus an override), the trained model,
    the X2 hook."""
    import os

    import yaml

    from ril.evaluation.checkpoint_eval import eval_checkpoint
    from ril.training.encoders import load_trained
    from ril.training.training import load_train_config, merge_results
    from ril.util.gpu import cuda_gate

    cfg = load_train_config(config)
    ev = dict(cfg["evaluation"])
    ev.setdefault("variant", f"{cfg['exp_id']}__{os.path.basename(result_dir)}")
    key, out_dir = "evaluation", result_dir
    if override:
        with open(override, encoding="utf-8") as handle:
            extra = dict(yaml.safe_load(handle))
        label = str(extra.pop("label"))
        ev.update(extra)
        ev["variant"] = f"{ev['variant']}__{label}"
        key, out_dir = f"evaluation_{label}", os.path.join(result_dir, label)
    gate = cuda_gate() if a.device.startswith("cuda") else None
    out = eval_checkpoint(
        load_trained(model_dir, device=a.device),
        ev,
        e1_config=a.e1_config,
        prep_dir=a.prep,
        cache_dir=a.e3_cache,
        data_root=a.data_root,
        work_dir=a.work,
        result_dir=out_dir,
        baseline_enc_dirs=dict(x.split("=", 1) for x in a.baseline),
        dense_root=a.dense_root,
    )
    out["gate"] = gate
    out["override"] = override
    merge_results(result_dir, key, out)
    return out


def _run_batch(a: argparse.Namespace) -> dict[str, object]:
    """Wiring only: train each configuration from one loaded cache, evaluate it, drop the model.

    A run whose results.json already holds every requested evaluation is skipped (resumable).
    """
    import json as _json
    import os
    import shutil

    from ril.training import train_jobs as tj
    from ril.training.training import RunPaths, load_train_config

    inputs = tj.load_inputs(a.cache, a.feature_table, a.mined)
    done: list[str] = []
    skipped: list[str] = []
    for config in a.configs:
        cfg = load_train_config(config)
        paths = RunPaths.of(cfg, a.results_root, a.work_root, a.date)
        want = ["evaluation"] + [f"evaluation_{_label(o)}" for o in a.extra_eval]
        res = os.path.join(paths.result_dir, "results.json")
        if os.path.exists(res):
            with open(res, encoding="utf-8") as handle:
                have = _json.load(handle)
            if all(k in have for k in want):
                skipped.append(config)
                continue
        rec = tj.train_job(
            config,
            a.cache,
            results_root=a.results_root,
            work_root=a.work_root,
            device=a.device,
            date=a.date,
            feature_table=a.feature_table,
            mined_path=a.mined,
            inputs=inputs,
        )
        sys.stdout.write(_json.dumps({"trained": config, "result_dir": rec["result_dir"]}) + "\n")
        sys.stdout.flush()
        final = str(rec["final_model"])
        _evaluate(a, config, final, str(rec["result_dir"]))
        for o in a.extra_eval:
            _evaluate(a, config, final, str(rec["result_dir"]), override=o)
        if not a.keep_models:
            shutil.rmtree(paths.ckpt_root, ignore_errors=True)
        done.append(config)
    return {"done": done, "skipped": skipped, "inputs": inputs.hashes}


def _label(override: str) -> str:
    import yaml

    with open(override, encoding="utf-8") as handle:
        return str(yaml.safe_load(handle)["label"])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    for a in ("listing", "held_out", "rename_cache", "out"):
        s.add_argument(a)
    s.add_argument("--feature-table")
    s.add_argument("--max", type=int)
    s.add_argument("--seed", type=int, required=True)
    s.add_argument("--include-held-out", action="store_true", help="leakage pilot only")
    c = sub.add_parser("cache")
    for a in ("listing", "selection", "out_cache"):
        c.add_argument(a)
    c.add_argument("--feature-table")
    c.add_argument("--form", default="code")
    c.add_argument("--ahead", type=int, default=4)
    m = sub.add_parser("mine")
    m.add_argument("cache")
    m.add_argument("out")
    m.add_argument("--teacher", required=True)
    m.add_argument("--keep", type=int, required=True)
    m.add_argument("--cut", type=int, default=1024)
    m.add_argument("--device", default="cpu")
    m.add_argument("--batch-size", type=int, default=64)
    t = sub.add_parser("train")
    t.add_argument("config")
    t.add_argument("cache")
    t.add_argument("--results-root", required=True)
    t.add_argument("--work-root", required=True)
    t.add_argument("--date", required=True)
    t.add_argument("--device", default="cpu")
    t.add_argument("--feature-table")
    t.add_argument("--mined")
    t.add_argument("--stop-after", type=int)
    b = sub.add_parser("measure")
    for x in ("config", "cache", "out_log", "log_dir"):
        b.add_argument(x)
    b.add_argument("--device", default="cpu")
    b.add_argument("--shapes", nargs="+", required=True, help="BATCH,NEGATIVES,POSITIVES,TOKENS")
    b.add_argument("--warmup", type=int, default=3)
    b.add_argument("--timed", type=int, default=10)
    b.add_argument("--precision", choices=["fp32", "amp_fp16"])
    b.add_argument("--grad-ckpt", action="store_true")
    e = sub.add_parser("eval")
    for a in ("config", "model_dir", "result_dir"):
        e.add_argument(a)
    rb = sub.add_parser("run-batch")
    rb.add_argument("configs", nargs="+")
    rb.add_argument("--cache", required=True)
    rb.add_argument("--feature-table")
    rb.add_argument("--mined")
    rb.add_argument("--results-root", required=True)
    rb.add_argument("--work-root", required=True)
    rb.add_argument("--date", required=True)
    rb.add_argument("--extra-eval", nargs="*", default=[])
    rb.add_argument("--keep-models", action="store_true")
    for q in (e, rb):
        for a in ("--e1-config", "--prep", "--e3-cache", "--data-root", "--work"):
            q.add_argument(a, required=True)
        q.add_argument("--device", default="cpu")
        q.add_argument("--baseline", nargs="*", default=[])
        q.add_argument("--dense-root")
    e.add_argument("--eval-override")
    th = sub.add_parser("teacher")
    for a in ("cache", "ranks_out", "mined_out"):
        th.add_argument(a)
    th.add_argument("--teacher", required=True)
    th.add_argument("--keep", type=int, required=True)
    th.add_argument("--cut", type=int, default=1024)
    th.add_argument("--device", default="cpu")
    th.add_argument("--batch-size", type=int, default=64)
    ft = sub.add_parser("features")
    ft.add_argument("ranks", nargs="+")
    ft.add_argument("--out", required=True)
    ft.add_argument("--teachers", nargs="+", required=True)
    ft.add_argument("--held-out", required=True)
    ft.add_argument("--rename-cache")
    a = p.parse_args(argv)

    from ril.training import train_jobs as tj

    if a.cmd == "select":
        out = tj.select_job(
            a.listing,
            a.held_out,
            a.rename_cache,
            a.out,
            feature_table=a.feature_table,
            max_instances=a.max,
            seed=a.seed,
            include_held_out=a.include_held_out,
        )
    elif a.cmd == "cache":
        out = tj.cache_job(
            a.listing,
            a.selection,
            a.out_cache,
            feature_table=a.feature_table,
            form=a.form,
            ahead=a.ahead,
        )
    elif a.cmd == "mine":
        out = tj.mine_job(
            a.cache,
            a.out,
            teacher=a.teacher,
            keep=a.keep,
            cut=a.cut,
            device=a.device,
            batch_size=a.batch_size,
        )
    elif a.cmd == "train":
        out = tj.train_job(
            a.config,
            a.cache,
            results_root=a.results_root,
            work_root=a.work_root,
            device=a.device,
            date=a.date,
            feature_table=a.feature_table,
            mined_path=a.mined,
            stop_after=a.stop_after,
        )
    elif a.cmd == "measure":
        from ril.bench.train_measure import measure_job

        shapes = [tuple(int(v) for v in x.split(",")) for x in a.shapes]
        out = measure_job(
            a.config,
            a.cache,
            shapes,
            a.out_log,
            a.log_dir,
            device=a.device,  # type: ignore[arg-type]
            warmup=a.warmup,
            timed=a.timed,
            precision=a.precision,
            gradient_checkpointing=True if a.grad_ckpt else None,
        )
    elif a.cmd == "teacher":
        out = tj.teacher_job(
            a.cache,
            a.ranks_out,
            a.mined_out,
            teacher=a.teacher,
            keep=a.keep,
            cut=a.cut,
            device=a.device,
            batch_size=a.batch_size,
        )
    elif a.cmd == "features":
        out = tj.feature_table_job(
            a.ranks,
            a.out,
            teachers=a.teachers,
            held_out_path=a.held_out,
            rename_cache_path=a.rename_cache,
        )
    elif a.cmd == "run-batch":
        out = _run_batch(a)
    else:
        out = _evaluate(a, a.config, a.model_dir, a.result_dir, a.eval_override)
    json.dump(out, sys.stdout, indent=1, sort_keys=True, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
