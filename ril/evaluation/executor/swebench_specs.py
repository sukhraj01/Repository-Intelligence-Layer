"""Build executor specifications from the benchmark's install specifications.

Implements ``docs/RQ3_PILOT.md`` ("If measured on the cluster, the steps") and D106. The
install specifications (Python version, packages, install and test commands) are read from
the benchmark package's constants, version 4.1.0 (later majors no longer carry them,
``results/rq3_pilot/part_a``); the package is only read, never run, so it can be a directory
of unpacked sources. The requirements files the specifications name are read later from the
repository's own history (``runner.resolve_requirements``), so no hosting API is needed.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import re
import sys
import types
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ril.evaluation.executor.log_parsers import REPO_PARSER
from ril.evaluation.executor.spec import InstanceSpec

SWEBENCH_VERSION = "4.1.0"
_DIFF_FILE = re.compile(r"diff --git a/.* b/(.*)")


def load_constants(sources: Path | None = None) -> Any:
    """The benchmark's constants module: from unpacked sources if given, else the installed package.

    With ``sources`` (the ``swebench`` directory of an unpacked wheel) only the constants package
    is executed; the rest of the package, which needs a container library, is never imported.
    """
    if sources is None:
        return importlib.import_module("swebench.harness.constants")
    for name, path in (("swebench", sources), ("swebench.harness", sources / "harness")):
        stub = types.ModuleType(name)
        stub.__path__ = [str(path)]
        sys.modules[name] = stub
    target = sources / "harness" / "constants"
    spec = importlib.util.spec_from_file_location(
        "swebench.harness.constants",
        target / "__init__.py",
        submodule_search_locations=[str(target)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"no constants package under {target}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def directives_for(instance: Mapping[str, Any], non_test_exts: Iterable[str]) -> tuple[str, ...]:
    """Test files the test patch touches (Django: dotted module names), as the benchmark does."""
    exts = tuple(non_test_exts)
    files = [f for f in _DIFF_FILE.findall(instance["test_patch"]) if not f.endswith(exts)]
    if instance["repo"] == "django/django":
        mods = []
        for f in files:
            f = f[: -len(".py")] if f.endswith(".py") else f
            f = f[len("tests/") :] if f.startswith("tests/") else f
            mods.append(f.replace("/", "."))
        files = mods
    return tuple(files)


def _as_list(value: Any) -> tuple[str, ...]:
    return tuple(json.loads(value)) if isinstance(value, str) else tuple(value)


def build_spec(instance: Mapping[str, Any], constants: Any) -> InstanceSpec:
    """One instance row plus the constants module as an :class:`InstanceSpec`."""
    repo, version = instance["repo"], instance["version"]
    specs = constants.MAP_REPO_VERSION_TO_SPECS[repo][version]
    packages = specs.get("packages", "")
    kind, paths = "", ()
    if packages == "requirements.txt":
        kind, paths = "requirements", tuple(constants.MAP_REPO_TO_REQS_PATHS[repo])
    elif packages == "environment.yml":
        kind, paths = "environment_yml", tuple(constants.MAP_REPO_TO_ENV_YML_PATHS[repo])
    test_cmd = specs["test_cmd"]
    if not isinstance(test_cmd, str):
        raise TypeError(f"{instance['instance_id']}: test_cmd is not a string")
    return InstanceSpec(
        instance_id=instance["instance_id"],
        repo=repo,
        version=version,
        base_commit=instance["base_commit"],
        python=specs["python"],
        install=specs.get("install", ""),
        test_cmd=test_cmd,
        test_directives=directives_for(instance, constants.NON_TEST_EXTS),
        log_parser=REPO_PARSER[repo],
        fail_to_pass=_as_list(instance["FAIL_TO_PASS"]),
        pass_to_pass=_as_list(instance["PASS_TO_PASS"]),
        test_patch=instance["test_patch"],
        packages=packages,
        requirements_kind=kind,
        requirements_paths=paths,
        pip_packages=tuple(specs.get("pip_packages", ())),
        pre_install=tuple(specs.get("pre_install", ())),
        eval_commands=tuple(specs.get("eval_commands", ())),
        difficulty=instance.get("difficulty", ""),
        created_at=instance.get("created_at", ""),
        environment_setup_commit=instance.get("environment_setup_commit", ""),
    )


def build_all(
    rows: Iterable[Mapping[str, Any]], constants: Any
) -> tuple[list[InstanceSpec], dict[str, str]]:
    """Specifications and gold patches (by instance id) for every row, sorted by environment."""
    rows = list(rows)
    specs = [build_spec(r, constants) for r in rows]
    gold = {r["instance_id"]: r["patch"] for r in rows}
    specs.sort(key=lambda s: (s.repo, s.version, s.instance_id))
    return specs, gold
