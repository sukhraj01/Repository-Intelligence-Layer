"""Environment construction with ``uv`` from an instance specification, without root.

Implements ``docs/RQ3_PILOT.md`` ("If measured on the cluster, the steps") and D106. The
benchmark builds conda environments; here the same pins are installed from PyPI into a
``uv`` virtual environment, so conda package strings and ``environment.yml`` files are
translated to pip requirements (a departure that is recorded per instance).
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ril.evaluation.executor.spec import InstanceSpec
from ril.evaluation.executor.steps import StepResult

# (name, command, timeout seconds) -> result; the runner supplies the environment and the log file
Stepper = Callable[[str, str, float], StepResult]

# conda-only names with no PyPI package (compilers, system libraries, the interpreter itself)
CONDA_ONLY = frozenset(
    {
        "python",
        "pip",
        "compilers",
        "c-compiler",
        "cxx-compiler",
        "gfortran",
        "libgcc",
        "libgcc-ng",
        "libstdcxx-ng",
        "hdf5",
        "libnetcdf",
        "netcdf-fortran",
        "proj",
        "geos",
        "libgdal",
        "nodejs",
        "ffmpeg",
        "graphviz",
        "make",
        "cmake",
        "gxx_linux-64",
        "gcc_linux-64",
        "openblas",
        "mkl",
        "libblas",
        "liblapack",
        "cdms2",
        # PyPI's "iris" is a placeholder that raises on import; SciTools Iris is conda-first
        "iris",
    }
)
CONDA_TO_PYPI = {"netcdf4": "netCDF4", "pytables": "tables", "pytorch": "torch"}

_MATCH = re.compile(r"^([A-Za-z0-9_.\-]+)\s*(.*)$")
_COMMENT = re.compile(r"\s*#.*$")


def strip_comment(line: str) -> str:
    """Drop a trailing ``# comment`` (pip and YAML accept it; ``uv`` does not)."""
    return _COMMENT.sub("", line).strip()


def conda_spec_to_pip(token: str) -> str | None:
    """Translate one conda match spec to a pip requirement; ``None`` when it has no PyPI form."""
    token = token.strip().strip("'\"")
    if not token or token.startswith("#"):
        return None
    m = _MATCH.match(token)
    if m is None:
        return token
    name, rest = m.group(1), m.group(2).strip()
    low = name.lower()
    if low in CONDA_ONLY:
        return None
    name = CONDA_TO_PYPI.get(low, name)
    if not rest:
        return name
    if rest.startswith("=") and not rest.startswith("=="):
        # conda "=1.2.3" is a prefix match and "=1.2.3=build" pins a build string
        parts = rest[1:].split("=")
        version = parts[0]
        return f"{name}=={version}" if len(parts) > 1 else f"{name}=={version}.*"
    return f"{name}{rest}"


def package_string_to_requirements(packages: str) -> list[str]:
    """A benchmark ``packages`` string (conda form) as pip requirements."""
    out = []
    for token in shlex.split(packages):
        req = conda_spec_to_pip(token)
        if req:
            out.append(req)
    return out


def environment_yml_to_requirements(text: str) -> list[str]:
    """Dependencies of a conda ``environment.yml`` as pip requirements (pip section included)."""
    reqs: list[str] = []
    in_deps = False
    in_pip = False
    pip_indent = 0
    for raw in text.split("\n"):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if not raw.startswith((" ", "-")) and stripped.endswith(":"):
            in_deps = stripped == "dependencies:"
            in_pip = False
            continue
        if not in_deps or not stripped.startswith("-"):
            continue
        item = strip_comment(stripped[1:])
        if not item:
            continue
        if item.startswith("pip:"):
            in_pip = True
            pip_indent = indent
            continue
        if in_pip and indent > pip_indent:
            if not item.startswith(("-e", "--")):
                reqs.append(item)
            continue
        in_pip = False
        req = conda_spec_to_pip(item)
        if req:
            reqs.append(req)
    return reqs


def requirements_from_text(text: str) -> list[str]:
    """Lines of a ``requirements.txt`` that are requirements (comments and editables dropped)."""
    out = []
    for line in text.split("\n"):
        s = strip_comment(line)
        if s and not s.startswith(("-e", "-r", "--")):
            out.append(s)
    return out


def dependency_requirements(spec: InstanceSpec) -> tuple[list[str], list[str]]:
    """(base requirements, departures) the specification asks to install before ``pip_packages``."""
    departures: list[str] = []
    if spec.requirements_kind == "requirements":
        return requirements_from_text(spec.requirements_text), departures
    if spec.requirements_kind == "environment_yml":
        departures.append("environment.yml read as pip requirements")
        return environment_yml_to_requirements(spec.requirements_text), departures
    if spec.packages and spec.packages not in ("requirements.txt", "environment.yml"):
        departures.append("conda package string read as pip requirements")
        return package_string_to_requirements(spec.packages), departures
    return [], departures


@dataclass
class EnvOutcome:
    """Result of building the dependency layer."""

    ok: bool
    stage: str = ""
    detail: str = ""
    departures: list[str] = field(default_factory=list)


class EnvBuilder(Protocol):
    def build(
        self, spec: InstanceSpec, venv: Path, step: Stepper, build_timeout: float
    ) -> EnvOutcome: ...


MAX_DROPS = 12
_NOT_ON_PYPI = re.compile(r"Because (\S+) was not found in the package registry")
_NAME = re.compile(r"^[A-Za-z0-9_.\-]+")


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_name(req: str) -> str:
    m = _NAME.match(req.strip())
    return m.group(0) if m else req


_NO_PYTHON = re.compile(
    r"no interpreter found|no download found|not found for|failed to download", re.I
)


MICROMAMBA_URL = "https://micro.mamba.pm/api/micromamba/linux-64/latest"

# (version, step) -> absolute path of an interpreter, or None when none can be provided
PythonProvider = Callable[[str, Stepper], str | None]


class MicromambaPythons:
    """Interpreters older than ``uv`` offers (3.5 to 3.7), from conda-forge, node-local, no root.

    A static ``micromamba`` binary and one environment per version live under ``root`` (the
    job's cache directory) and are created once, under a lock, then shared by later calls.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def get(self, version: str, step: Stepper) -> str | None:
        import fcntl

        self.root.mkdir(parents=True, exist_ok=True)
        env = self.root / f"py{version}"
        python = env / "bin" / "python"
        mm = self.root / "bin" / "micromamba"
        with (self.root / "lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if python.exists():
                return str(python)
            tarball = shlex.quote(str(self.root / "mm.tar.bz2"))
            if not mm.exists():
                got = step(
                    "micromamba_fetch",
                    f"curl -sfL -m 600 -o {tarball} {MICROMAMBA_URL}"
                    f" && tar xjf {tarball} -C {shlex.quote(str(self.root))} bin/micromamba",
                    900,
                )
                if not got.ok:
                    return None
            made = step(
                "micromamba_python",
                f"MAMBA_ROOT_PREFIX={shlex.quote(str(self.root / 'root'))} {shlex.quote(str(mm))}"
                f" create -y -q -p {shlex.quote(str(env))} -c conda-forge --override-channels"
                f" python={shlex.quote(version)}",
                1800,
            )
            return str(python) if made.ok and python.exists() else None


class UvEnvBuilder:
    """Virtual environment from ``uv``: interpreter, requirements, then ``pip_packages``.

    When ``uv`` has no interpreter for the specification's Python (it starts at 3.8), an
    optional ``pythons`` provider supplies one (micromamba) and the rest is unchanged.
    """

    def __init__(self, pythons: PythonProvider | None = None) -> None:
        self.pythons = pythons

    def build(
        self, spec: InstanceSpec, venv: Path, step: Stepper, build_timeout: float
    ) -> EnvOutcome:
        res = step(
            "venv",
            f"uv venv --seed --python {shlex.quote(spec.python)} {shlex.quote(str(venv))}",
            600,
        )
        extra: list[str] = []
        if not res.ok and self.pythons is not None and _NO_PYTHON.search(res.output):
            interpreter = self.pythons(spec.python, step)
            if interpreter is not None:
                extra.append(f"python {spec.python} from conda-forge (micromamba)")
                res = step(
                    "venv_mamba",
                    f"uv venv --seed --python {shlex.quote(interpreter)} {shlex.quote(str(venv))}",
                    600,
                )
        if not res.ok:
            stage = "python_unavailable" if _NO_PYTHON.search(res.output) else "venv"
            return EnvOutcome(False, stage, _tail(res.output))
        py = shlex.quote(str(venv / "bin" / "python"))
        # the seeded setuptools is the newest and lacks ``pkg_resources``; the step's constraint
        # file (build_constraints) decides which release is installed
        res = step("setuptools", f"uv pip install --python {py} setuptools", 600)
        if not res.ok:
            return EnvOutcome(False, "venv", _tail(res.output))
        base, departures = dependency_requirements(spec)
        departures.extend(extra)
        for name, reqs in (("packages", base), ("pip_packages", list(spec.pip_packages))):
            for _ in range(MAX_DROPS + 1):
                if not reqs:
                    break
                quoted = " ".join(shlex.quote(r) for r in reqs)
                # the specification's own pins are installed without the era date: a pin may name
                # a release newer than the instance
                undated = (
                    "env -u UV_EXCLUDE_NEWER -u PIP_UPLOADED_PRIOR_TO "
                    if name == "pip_packages"
                    else ""
                )
                res = step(name, f"{undated}uv pip install --python {py} {quoted}", build_timeout)
                if res.ok:
                    break
                missing = _NOT_ON_PYPI.search(res.output)
                if name != "packages" or missing is None:
                    return EnvOutcome(False, f"{name}_install", _tail(res.output), departures)
                # a conda-only dependency of the specification's environment file
                gone = _canonical(missing.group(1))
                reqs = [r for r in reqs if _canonical(_requirement_name(r)) != gone]
                departures.append(f"dropped {missing.group(1)} (not on PyPI)")
            else:
                return EnvOutcome(
                    False, f"{name}_install", "too many unavailable packages", departures
                )
        return EnvOutcome(True, departures=departures)


def _tail(text: str, n: int = 600) -> str:
    return text[-n:]
