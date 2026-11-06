"""Evaluate one patch on one instance: build, patch, test, grade.

Implements ``docs/RQ3_PILOT.md`` ("If measured on the cluster, the steps") and D106. The same
function evaluates a gold patch (does the instance qualify for the executable subset) and a
model patch (RQ3's resolved rate). It works in a node-local scratch directory, sets ``HOME`` to
that scratch directory for every step, and removes it on exit; only the shared package and
repository caches under ``ExecConfig.cache_root`` outlive a call.
"""

from __future__ import annotations

import dataclasses
import fcntl
import hashlib
import json
import os
import posixpath
import re
import shlex
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ril.evaluation.executor import log_parsers
from ril.evaluation.executor.envbuild import EnvBuilder, EnvOutcome, UvEnvBuilder
from ril.evaluation.executor.spec import InstanceSpec, needs_apt, needs_root
from ril.evaluation.executor.steps import StepResult, run_step
from ril.util.log import get_logger

log = get_logger("executor")

EXECUTOR_VERSION = "executor/v1"
PYTEST_PIN = "pytest<8"
FAILURE_DETAIL_CHARS = 8000
BUILD_CONSTRAINTS = ("setuptools<=70.0.0",)
_PYTEST_PINNED = re.compile(r"pytest\s*(==|<=|<|~=)")
_FILES_OF_PATCH = re.compile(r"^diff --git a/(\S+) b/", re.M)


@dataclass(frozen=True)
class ExecConfig:
    """Paths and limits. ``config_hash`` covers what changes an outcome, not where files live."""

    work_root: Path
    cache_root: Path
    repo_source: Callable[[str], str]
    build_timeout: float = 3600.0
    install_timeout: float = 2400.0
    test_timeout: float = 1800.0
    pytest_pin: str = PYTEST_PIN
    # Applied to every install, including pip's isolated build environments: the specifications
    # were written when setuptools still shipped ``pkg_resources`` (removed in later releases).
    build_constraints: tuple[str, ...] = BUILD_CONSTRAINTS

    def config_hash(self) -> str:
        payload = {
            "version": EXECUTOR_VERSION,
            "build_timeout": self.build_timeout,
            "install_timeout": self.install_timeout,
            "test_timeout": self.test_timeout,
            "pytest_pin": self.pytest_pin,
            "build_constraints": list(self.build_constraints),
        }
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode()).hexdigest()[:16]


@dataclass
class ExecResult:
    """One evaluation. ``built`` means the base-commit environment was installed."""

    instance_id: str
    built: bool = False
    failure_stage: str = ""
    failure_detail: str = ""
    patch_applied: bool = False
    tests_ran: bool = False
    timed_out: bool = False
    statuses: dict[str, str] = field(default_factory=dict)
    f2p_total: int = 0
    f2p_passed: int = 0
    p2p_total: int = 0
    p2p_passed: int = 0
    seconds: dict[str, float] = field(default_factory=dict)
    peak_rss_mb: float = 0.0
    departures: list[str] = field(default_factory=list)
    skipped_commands: list[str] = field(default_factory=list)
    output_tail: str = ""

    @property
    def resolved(self) -> bool:
        """All FAIL_TO_PASS and all PASS_TO_PASS tests pass (benchmark rule)."""
        return (
            self.tests_ran
            and self.f2p_total > 0
            and self.f2p_passed == self.f2p_total
            and self.p2p_passed == self.p2p_total
        )

    def outcome_digest(self) -> str:
        """Hash of the per-test statuses of the named tests, to compare two runs."""
        text = json.dumps(sorted(self.statuses.items()), separators=(",", ":"))
        return hashlib.sha256(text.encode()).hexdigest()[:16]


class _Ctx:
    """Per-call state: scratch directory, environment, accumulating timings."""

    def __init__(self, config: ExecConfig, scratch: Path) -> None:
        self.config = config
        self.scratch = scratch
        self.repo = scratch / "repo"
        self.venv = scratch / "venv"
        home = scratch / "home"
        tmp = scratch / "tmp"
        for d in (home, tmp, config.cache_root / "uv", config.cache_root / "python"):
            d.mkdir(parents=True, exist_ok=True)
        base_path = os.environ.get("PATH", "/usr/bin:/bin")
        self.env: dict[str, str] = {
            "PATH": f"{self.venv / 'bin'}:{base_path}",
            "VIRTUAL_ENV": str(self.venv),
            "HOME": str(home),
            "TMPDIR": str(tmp),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "UV_CACHE_DIR": str(config.cache_root / "uv"),
            "UV_PYTHON_INSTALL_DIR": str(config.cache_root / "python"),
            "PIP_CACHE_DIR": str(config.cache_root / "pip"),
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        if config.build_constraints:
            constraints = scratch / "constraints.txt"
            constraints.write_text("\n".join(config.build_constraints) + "\n")
            self.env["PIP_CONSTRAINT"] = str(constraints)
            self.env["UV_CONSTRAINT"] = str(constraints)
            self.env["UV_BUILD_CONSTRAINT"] = str(constraints)
        self.result_seconds: dict[str, float] = {}
        self.peak = 0.0
        self._n = 0

    def step(self, name: str, command: str, timeout: float, cwd: Path | None = None) -> StepResult:
        self._n += 1
        res = run_step(
            command,
            cwd=cwd or self.scratch,
            env=self.env,
            log_path=self.scratch / "logs" / f"{self._n:02d}_{name}.log",
            timeout=timeout,
        )
        self.result_seconds[name] = round(self.result_seconds.get(name, 0.0) + res.seconds, 3)
        self.peak = max(self.peak, res.peak_rss_mb)
        return res


def _mirror_name(repo: str) -> str:
    return repo.replace("/", "__") + ".git"


def ensure_mirror(ctx: _Ctx, spec: InstanceSpec) -> StepResult:
    """Bare mirror of the repository under the shared cache; created once, under a lock."""
    cache = ctx.config.cache_root / "git"
    cache.mkdir(parents=True, exist_ok=True)
    mirror = cache / _mirror_name(spec.repo)
    source = ctx.config.repo_source(spec.repo)
    with (cache / (_mirror_name(spec.repo) + ".lock")).open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not mirror.exists():
            res = ctx.step(
                "mirror",
                f"git clone -q --bare {shlex.quote(source)} {shlex.quote(str(mirror))}",
                ctx.config.build_timeout,
            )
            if not res.ok:
                shutil.rmtree(mirror, ignore_errors=True)
                return res
        have = ctx.step(
            "mirror_has",
            f"git -C {shlex.quote(str(mirror))} cat-file -e {spec.base_commit}^{{commit}}",
            60,
        )
        if not have.ok:
            return ctx.step(
                "mirror_fetch",
                f"git -C {shlex.quote(str(mirror))} fetch -q"
                f" {shlex.quote(source)} {spec.base_commit}",
                ctx.config.build_timeout,
            )
        return have


def checkout(ctx: _Ctx, spec: InstanceSpec) -> StepResult:
    res = ensure_mirror(ctx, spec)
    if not res.ok:
        return res
    mirror = ctx.config.cache_root / "git" / _mirror_name(spec.repo)
    return ctx.step(
        "checkout",
        f"git clone -q --no-checkout {shlex.quote(str(mirror))} {shlex.quote(str(ctx.repo))}"
        f" && git -C {shlex.quote(str(ctx.repo))} checkout -q {spec.base_commit}",
        ctx.config.build_timeout,
    )


_EXCLUDED_REQ_LINES = ("-e .", "#", ".[test")
_REQ_REPLACE = (("types-pkg_resources", "types-setuptools"),)


def _show(ctx: _Ctx, spec: InstanceSpec, commit: str, path: str) -> str | None:
    mirror = ctx.config.cache_root / "git" / _mirror_name(spec.repo)
    res = ctx.step(
        "req_show", f"git -C {shlex.quote(str(mirror))} show {commit}:{shlex.quote(path)}", 120
    )
    return res.output if res.ok else None


def resolve_requirements(ctx: _Ctx, spec: InstanceSpec) -> InstanceSpec | None:
    """Fill ``requirements_text`` from the repository history at the setup commit.

    Follows the benchmark: the first listed file that exists; for a requirements file, one level
    of ``-r`` includes, with editable and comment lines dropped. ``None`` when no file exists.
    """
    if not spec.requirements_kind or spec.requirements_text:
        return spec
    commit = spec.environment_setup_commit or spec.base_commit
    for path in spec.requirements_paths:
        text = _show(ctx, spec, commit, path)
        if text is None:
            continue
        if spec.requirements_kind == "requirements":
            keep: list[str] = []
            extra: list[str] = []
            base_dir = posixpath.dirname(path)
            for line in text.split("\n"):
                if line.strip().startswith("-r"):
                    inc = _show(
                        ctx, spec, commit, posixpath.join(base_dir, line.strip()[2:].strip())
                    )
                    for sub in (inc or "").split("\n"):
                        if not sub.strip().startswith(_EXCLUDED_REQ_LINES):
                            extra.append(sub)
                elif not line.strip().startswith(_EXCLUDED_REQ_LINES):
                    keep.append(line)
            text = "\n".join([*extra, "\n".join(keep)])
        for old, new in _REQ_REPLACE:
            text = re.sub(rf"^{re.escape(old)}([<>=!~]=?.*|$)", new, text, flags=re.M)
        return dataclasses.replace(spec, requirements_text=text)
    return None


def _apply(ctx: _Ctx, name: str, patch: str) -> StepResult:
    """``git apply``, then ``patch --fuzz=5`` as the benchmark's evaluation does."""
    path = ctx.scratch / f"{name}.patch"
    path.write_text(patch if patch.endswith("\n") else patch + "\n")
    q = shlex.quote(str(path))
    res = ctx.step(name, f"git apply --whitespace=nowarn {q}", 300, cwd=ctx.repo)
    if res.ok:
        return res
    return ctx.step(name + "_fuzz", f"patch --batch --fuzz=5 -p1 -i {q}", 300, cwd=ctx.repo)


def _rewrite_testbed(command: str, repo: Path) -> str:
    """The benchmark's commands name its container path; the checkout lives elsewhere here."""
    return command.replace("/testbed", str(repo))


def _fail(result: ExecResult, ctx: _Ctx, stage: str, detail: str) -> ExecResult:
    result.failure_stage = stage
    result.failure_detail = detail[-FAILURE_DETAIL_CHARS:]
    return result


def evaluate(
    spec: InstanceSpec,
    patch: str,
    config: ExecConfig,
    *,
    builder: EnvBuilder | None = None,
) -> ExecResult:
    """Build ``spec``'s environment, apply ``patch`` (may be empty), run the tests, grade."""
    result = ExecResult(instance_id=spec.instance_id)
    config.work_root.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="rilx_", dir=config.work_root))
    ctx = _Ctx(config, scratch)
    try:
        return _evaluate(spec, patch, ctx, result, builder or UvEnvBuilder())
    finally:
        result.seconds = {**ctx.result_seconds, "total": round(sum(ctx.result_seconds.values()), 3)}
        result.peak_rss_mb = ctx.peak
        shutil.rmtree(scratch, ignore_errors=True)


def _evaluate(
    spec: InstanceSpec, patch: str, ctx: _Ctx, result: ExecResult, builder: EnvBuilder
) -> ExecResult:
    cfg = ctx.config
    if needs_apt(spec):
        return _fail(
            result, ctx, "needs_apt", "; ".join(c for c in spec.pre_install if "apt" in c)[:300]
        )
    res = checkout(ctx, spec)
    if not res.ok:
        return _fail(result, ctx, "repo_unavailable", res.output)
    resolved = resolve_requirements(ctx, spec)
    if resolved is None:
        return _fail(result, ctx, "requirements_unavailable", ", ".join(spec.requirements_paths))
    spec = resolved

    def stepper(name: str, command: str, timeout: float) -> StepResult:
        return ctx.step(name, command, timeout, cwd=ctx.repo)

    env: EnvOutcome = builder.build(spec, ctx.venv, stepper, cfg.build_timeout)
    result.departures.extend(env.departures)
    result.departures.extend(f"build constraint {c}" for c in cfg.build_constraints)
    if not env.ok:
        return _fail(result, ctx, env.stage, env.detail)
    for command in spec.pre_install:
        if needs_root(command):
            result.skipped_commands.append(command[:120])
            continue
        res = ctx.step(
            "pre_install", _rewrite_testbed(command, ctx.repo), cfg.install_timeout, cwd=ctx.repo
        )
        if not res.ok:
            return _fail(result, ctx, "pre_install", res.output)
    if spec.install:
        res = ctx.step(
            "install", _rewrite_testbed(spec.install, ctx.repo), cfg.install_timeout, cwd=ctx.repo
        )
        if not res.ok:
            return _fail(result, ctx, "install", res.output)
    result.built = True
    if not _ensure_runner(spec, ctx, result):
        return _fail(result, ctx, "test_runner_unavailable", "pytest or tox could not be installed")
    if patch.strip():
        res = _apply(ctx, "apply_patch", patch)
        if not res.ok:
            return _fail(result, ctx, "patch_apply_failed", res.output)
        result.patch_applied = True
        if spec.install:
            res = ctx.step(
                "reinstall",
                _rewrite_testbed(spec.install, ctx.repo),
                cfg.install_timeout,
                cwd=ctx.repo,
            )
            if not res.ok:
                return _fail(result, ctx, "install_after_patch", res.output)
    else:
        result.patch_applied = True
    test_files = sorted(set(_FILES_OF_PATCH.findall(spec.test_patch)))
    if test_files:
        quoted = " ".join(shlex.quote(f) for f in test_files)
        ctx.step(
            "reset_tests", f"git checkout -q {spec.base_commit} -- {quoted}", 120, cwd=ctx.repo
        )
    res = _apply(ctx, "apply_test_patch", spec.test_patch)
    if not res.ok:
        return _fail(result, ctx, "test_patch_apply_failed", res.output)
    commands = []
    for c in spec.eval_commands:
        if needs_root(c):
            result.skipped_commands.append(c[:120])
        else:
            commands.append(_rewrite_testbed(c, ctx.repo))
    commands.append(" ".join([spec.test_cmd, *(shlex.quote(d) for d in spec.test_directives)]))
    res = ctx.step("tests", "\n".join(commands), cfg.test_timeout, cwd=ctx.repo)
    result.output_tail = res.output[-2000:]
    if res.timed_out:
        result.timed_out = True
        return _fail(result, ctx, "tests_timeout", res.output)
    statuses = log_parsers.parse(spec.log_parser, res.output)
    if not statuses:
        return _fail(result, ctx, "no_test_output", res.output)
    named = set(spec.fail_to_pass) | set(spec.pass_to_pass)
    result.statuses = {t: statuses.get(t, "MISSING") for t in sorted(named)}
    result.tests_ran = True
    result.f2p_total = len(spec.fail_to_pass)
    result.p2p_total = len(spec.pass_to_pass)
    result.f2p_passed, result.p2p_passed = log_parsers.grade(
        statuses, spec.fail_to_pass, spec.pass_to_pass
    )
    return result


def _install(ctx: _Ctx, spec: InstanceSpec, name: str, result: ExecResult) -> StepResult:
    """Run the specification's install command; retry a pip install without PEP 517 when the
    project's pinned build backend has no ``build_editable`` hook (old ``setuptools`` pins)."""
    command = _rewrite_testbed(spec.install, ctx.repo)
    res = ctx.step(name, command, ctx.config.install_timeout, cwd=ctx.repo)
    if res.ok or "build_editable" not in res.output or "pip install" not in command:
        return res
    note = "install retried with --no-use-pep517 (build backend lacks build_editable)"
    if note not in result.departures:
        result.departures.append(note)
    return ctx.step(
        name + "_legacy",
        command.replace("pip install", "pip install --no-use-pep517", 1),
        ctx.config.install_timeout,
        cwd=ctx.repo,
    )


def _ensure_runner(spec: InstanceSpec, ctx: _Ctx, result: ExecResult) -> bool:
    """Make the specification's test command runnable; pin pytest below 8 where it is unpinned.

    The specification leaves pytest unpinned for some repositories and today's pytest 8 removed an
    API they use (flask-5014 in ``results/rq3_pilot/part_a``): a recorded departure, not silent.
    """
    py = shlex.quote(str(ctx.venv / "bin" / "python"))
    if spec.test_cmd.lstrip().startswith("tox"):
        if not ctx.step("tox_check", f"{py} -m tox --version", 120, cwd=ctx.repo).ok:
            result.departures.append("tox installed (not in the specification)")
            return ctx.step(
                "tox_install", f"uv pip install --python {py} tox", 900, cwd=ctx.repo
            ).ok
        return True
    if "pytest" not in spec.test_cmd or spec.repo == "pytest-dev/pytest":
        return True
    pinned = bool(
        _PYTEST_PINNED.search(" ".join([spec.packages, spec.requirements_text, *spec.pip_packages]))
    )
    probe = ctx.step(
        "pytest_version", f"{py} -c 'import pytest; print(pytest.__version__)'", 120, cwd=ctx.repo
    )
    version = probe.output.strip().splitlines()[-1] if probe.ok and probe.output.strip() else ""
    major = version.split(".")[0]
    if version and (pinned or not major.isdigit() or int(major) < 8):
        return True
    result.departures.append(f"{ctx.config.pytest_pin} (specification leaves pytest unpinned)")
    return ctx.step(
        "pytest_pin",
        f"uv pip install --python {py} {shlex.quote(ctx.config.pytest_pin)}",
        900,
        cwd=ctx.repo,
    ).ok
