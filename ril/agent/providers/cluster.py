"""Wiring of the driver to the cluster executor and to repository mirrors. ``docs/RQ3_PILOT.md``.

``executor_for`` binds instance specifications and an ``ExecConfig`` to the driver's ``Executor``
signature. ``reader_factory`` gives, per instance, a reader of base-commit file texts from a bare
mirror (cloned once per repository, under a lock, from a local mirror first and the public remote
second), the same reader the patch-application measurement used.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from pathlib import Path

from ril.agent.providers.driver import Executor, ReaderFactory
from ril.agent.providers.patch_convert import git_reader
from ril.evaluation.executor.envbuild import EnvBuilder
from ril.evaluation.executor.runner import ExecConfig, ExecResult, evaluate
from ril.evaluation.executor.spec import InstanceSpec
from ril.evaluation.patch_validation import ensure_bare


def executor_for(
    specs: Mapping[str, InstanceSpec],
    configs: Mapping[str, ExecConfig],
    policy_of: Mapping[str, str],
    builder: EnvBuilder | None = None,
) -> Executor:
    """Executor over specifications; ``policy_of`` names each instance's environment policy
    (``latest`` or ``era``, as the subset records it); ``configs`` holds one config per policy."""

    def run(instance_id: str, diff: str) -> ExecResult:
        config = configs[policy_of.get(instance_id, "latest")]
        return evaluate(specs[instance_id], diff, config, builder=builder)

    return run


def reader_factory(
    specs: Mapping[str, InstanceSpec], mirror_dir: Path, local_mirrors: Path | None
) -> ReaderFactory:
    lock = threading.Lock()

    def make(instance_id: str):  # type: ignore[no-untyped-def]
        spec = specs[instance_id]
        sources: list[str] = []
        if local_mirrors is not None:
            local = local_mirrors / (spec.repo.replace("/", "__") + ".git")
            if local.exists():
                sources.append(str(local))
        sources.append(f"https://github.com/{spec.repo}.git")
        with lock:
            mirror = ensure_bare(spec.repo, spec.base_commit, mirror_dir, sources)
        if mirror is None:
            raise ValueError(f"no mirror holding {spec.base_commit} for {spec.repo}")
        return git_reader(str(mirror), spec.base_commit)

    return make


def instance_ids(items: Sequence[Mapping[str, object]]) -> list[str]:
    return sorted({str(r["instance_id"]) for r in items})
