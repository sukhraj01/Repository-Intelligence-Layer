"""Instance specification consumed by the executor (plain data, no benchmark package needed).

Implements ``docs/RQ3_PILOT.md`` ("If measured on the cluster, the steps"). The specification
is produced from the benchmark's install specifications by ``swebench_specs.py`` on the cluster
and read back from JSON lines, so the executor and its tests import nothing outside the
standard library.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SPEC_VERSION = "exec-spec/v1"


@dataclass(frozen=True)
class InstanceSpec:
    """Everything needed to build, patch and test one instance."""

    instance_id: str
    repo: str
    version: str
    base_commit: str
    python: str
    install: str
    test_cmd: str
    test_directives: tuple[str, ...]
    log_parser: str
    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]
    test_patch: str
    packages: str = ""
    # "" | "requirements" | "environment_yml": what ``requirements_text`` holds
    requirements_kind: str = ""
    requirements_text: str = ""
    # files the benchmark reads for ``requirements_kind``, tried in order at the setup commit
    requirements_paths: tuple[str, ...] = ()
    pip_packages: tuple[str, ...] = ()
    pre_install: tuple[str, ...] = ()
    eval_commands: tuple[str, ...] = ()
    difficulty: str = ""
    created_at: str = ""
    environment_setup_commit: str = ""
    # fixed-name extras a test or a variant may carry without a schema change
    extra: Mapping[str, str] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, row: Mapping[str, Any]) -> InstanceSpec:
        data = dict(row)
        for key in (
            "test_directives",
            "fail_to_pass",
            "pass_to_pass",
            "pip_packages",
            "pre_install",
            "eval_commands",
            "requirements_paths",
        ):
            data[key] = tuple(data.get(key, ()))
        data["extra"] = dict(data.get("extra", {}))
        return cls(**data)

    @property
    def env_key(self) -> str:
        """Instances sharing a key share the dependency layer (and the package cache)."""
        return f"{self.repo}@{self.version}"


def load_specs(path: Path) -> list[InstanceSpec]:
    """Read specifications from JSON lines in file order."""
    out: list[InstanceSpec] = []
    with path.open() as src:
        for line in src:
            if line.strip():
                out.append(InstanceSpec.from_json(json.loads(line)))
    return out


def write_specs(path: Path, specs: Iterable[InstanceSpec]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w") as out:
        for spec in specs:
            out.write(json.dumps(spec.to_json(), sort_keys=True, separators=(",", ":")) + "\n")
            n += 1
    return n


_ROOT_ONLY = re.compile(r"\bapt(?:-get)?\b|\bsudo\b|\blocale-gen\b|/etc/")


def needs_root(command: str) -> bool:
    """True for a command that installs system packages or edits ``/etc`` (needs root)."""
    return bool(_ROOT_ONLY.search(command))


def needs_apt(spec: InstanceSpec) -> bool:
    """A pre-install step that needs the system package manager excludes the instance (D106)."""
    return any(re.search(r"\bapt(?:-get)?\b|\bsudo\b", c) for c in spec.pre_install)
