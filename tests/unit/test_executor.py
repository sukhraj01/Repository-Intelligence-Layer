"""Executor: log readers, requirement translation, evaluate on a synthetic repository.

Implements the tests of D106. No network: the repository is a local git repository and the
environment builder is a fake that points ``python`` at the test interpreter.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ril.evaluation.executor import envbuild, log_parsers
from ril.evaluation.executor.envbuild import EnvOutcome, Stepper
from ril.evaluation.executor.runner import ExecConfig, evaluate
from ril.evaluation.executor.spec import InstanceSpec, needs_apt, needs_root

GIT = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid"]

RUNNER = """\
import importlib.util, os, sys
sys.path.insert(0, os.getcwd())
import pkg
print("HOME=" + os.environ["HOME"])
spec = importlib.util.spec_from_file_location("t", "tests/test_pkg.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
for name in sorted(n for n in dir(mod) if n.startswith("test_")):
    try:
        getattr(mod, name)()
        print("PASSED tests/test_pkg.py::" + name)
    except Exception as exc:
        print("FAILED tests/test_pkg.py::" + name + " - " + repr(exc))
"""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [*GIT, *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture()
def synthetic(tmp_path: Path) -> dict[str, str]:
    repo = tmp_path / "src"
    (repo / "tests").mkdir(parents=True)
    (repo / "pkg.py").write_text("def add(a, b):\n    return a - b\n")
    (repo / "run_tests.py").write_text(RUNNER)
    (repo / "tests" / "test_pkg.py").write_text(
        "import pkg\n\n\ndef test_keep():\n    assert pkg.add(0, 0) == 0\n"
    )
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "pkg.py").write_text("def add(a, b):\n    return a + b\n")
    gold = _git(repo, "diff")
    _git(repo, "checkout", "-q", ".")
    (repo / "tests" / "test_pkg.py").write_text(
        "import pkg\n\n\ndef test_keep():\n    assert pkg.add(0, 0) == 0\n\n\n"
        "def test_add():\n    assert pkg.add(2, 3) == 5\n"
    )
    test_patch = _git(repo, "diff")
    _git(repo, "checkout", "-q", ".")
    return {"repo": str(repo), "base": base, "gold": gold, "test_patch": test_patch}


class FakeBuilder:
    """A venv directory whose ``python`` is the test interpreter (no network, no ``uv``)."""

    def __init__(self, outcome: EnvOutcome | None = None) -> None:
        self.outcome = outcome or EnvOutcome(True, departures=["fake builder"])

    def build(
        self, spec: InstanceSpec, venv: Path, step: Stepper, build_timeout: float
    ) -> EnvOutcome:
        if self.outcome.ok:
            (venv / "bin").mkdir(parents=True)
            (venv / "bin" / "python").symlink_to(sys.executable)
        return self.outcome


def _spec(s: dict[str, str], **kw: object) -> InstanceSpec:
    base: dict[str, object] = dict(
        instance_id="synth__pkg-1",
        repo="synth/pkg",
        version="1.0",
        base_commit=s["base"],
        python="3.11",
        install="python -c \"open('installed', 'w').write('x')\"",
        test_cmd="python run_tests.py",
        test_directives=(),
        log_parser="pytest",
        fail_to_pass=("tests/test_pkg.py::test_add",),
        pass_to_pass=("tests/test_pkg.py::test_keep",),
        test_patch=s["test_patch"],
    )
    base.update(kw)
    return InstanceSpec(**base)  # type: ignore[arg-type]


def _config(tmp_path: Path, s: dict[str, str], **kw: float) -> ExecConfig:
    return ExecConfig(
        work_root=tmp_path / "work",
        cache_root=tmp_path / "cache",
        repo_source=lambda repo: s["repo"],
        **kw,  # type: ignore[arg-type]
    )


def test_gold_patch_resolves_and_scratch_is_removed(
    tmp_path: Path, synthetic: dict[str, str]
) -> None:
    cfg = _config(tmp_path, synthetic)
    res = evaluate(_spec(synthetic), synthetic["gold"], cfg, builder=FakeBuilder())
    assert res.built and res.failure_stage == ""
    assert res.f2p_passed == res.f2p_total == 1 and res.p2p_passed == res.p2p_total == 1
    assert res.resolved
    assert res.statuses == {
        "tests/test_pkg.py::test_add": "PASSED",
        "tests/test_pkg.py::test_keep": "PASSED",
    }
    assert list(cfg.work_root.iterdir()) == []
    assert res.seconds["total"] > 0
    assert res.departures == ["fake builder", "build constraint setuptools<=70.0.0"]


def test_subprocesses_run_with_scratch_home(tmp_path: Path, synthetic: dict[str, str]) -> None:
    cfg = _config(tmp_path, synthetic)
    res = evaluate(_spec(synthetic), synthetic["gold"], cfg, builder=FakeBuilder())
    home_line = next(x for x in res.output_tail.splitlines() if x.startswith("HOME="))
    assert home_line.startswith(f"HOME={cfg.work_root}")


def test_empty_patch_leaves_the_fail_to_pass_test_failing(
    tmp_path: Path, synthetic: dict[str, str]
) -> None:
    res = evaluate(_spec(synthetic), "", _config(tmp_path, synthetic), builder=FakeBuilder())
    assert res.tests_ran and not res.resolved
    assert (res.f2p_passed, res.f2p_total, res.p2p_passed) == (0, 1, 1)


def test_inapplicable_patch_is_a_failed_instance_that_still_built(
    tmp_path: Path, synthetic: dict[str, str]
) -> None:
    bad = synthetic["gold"].replace("return a - b", "return a * b")
    res = evaluate(_spec(synthetic), bad, _config(tmp_path, synthetic), builder=FakeBuilder())
    assert res.built and not res.patch_applied and not res.resolved
    assert res.failure_stage == "patch_apply_failed"


def test_missing_test_counts_as_failed(tmp_path: Path, synthetic: dict[str, str]) -> None:
    spec = _spec(synthetic, fail_to_pass=("tests/test_pkg.py::test_absent",))
    res = evaluate(spec, synthetic["gold"], _config(tmp_path, synthetic), builder=FakeBuilder())
    assert res.statuses["tests/test_pkg.py::test_absent"] == "MISSING"
    assert not res.resolved


def test_apt_in_pre_install_excludes_without_building(
    tmp_path: Path, synthetic: dict[str, str]
) -> None:
    spec = _spec(synthetic, pre_install=("apt-get update && apt-get install -y graphviz",))
    assert needs_apt(spec)
    res = evaluate(spec, "", _config(tmp_path, synthetic), builder=FakeBuilder())
    assert not res.built and res.failure_stage == "needs_apt"


def test_environment_failure_is_reported_with_its_stage(
    tmp_path: Path, synthetic: dict[str, str]
) -> None:
    fail = EnvOutcome(False, "python_unavailable", "No interpreter found for Python 3.6")
    res = evaluate(_spec(synthetic), "", _config(tmp_path, synthetic), builder=FakeBuilder(fail))
    assert not res.built and res.failure_stage == "python_unavailable"


def test_timeout_kills_the_tests(tmp_path: Path, synthetic: dict[str, str]) -> None:
    spec = _spec(synthetic, test_cmd="sleep 30; python run_tests.py")
    res = evaluate(
        spec,
        synthetic["gold"],
        _config(tmp_path, synthetic, test_timeout=1.0),
        builder=FakeBuilder(),
    )
    assert res.timed_out and res.failure_stage == "tests_timeout" and not res.resolved
    assert res.seconds["tests"] < 10


def test_install_failure_before_patch_is_not_built(
    tmp_path: Path, synthetic: dict[str, str]
) -> None:
    res = evaluate(
        _spec(synthetic, install="exit 3"), "", _config(tmp_path, synthetic), builder=FakeBuilder()
    )
    assert not res.built and res.failure_stage == "install"


def test_two_runs_agree(tmp_path: Path, synthetic: dict[str, str]) -> None:
    cfg = _config(tmp_path, synthetic)
    a = evaluate(_spec(synthetic), synthetic["gold"], cfg, builder=FakeBuilder())
    b = evaluate(_spec(synthetic), synthetic["gold"], cfg, builder=FakeBuilder())
    assert a.outcome_digest() == b.outcome_digest() and a.resolved == b.resolved


def test_config_hash_ignores_paths_and_tracks_limits(
    tmp_path: Path, synthetic: dict[str, str]
) -> None:
    a = _config(tmp_path / "a", synthetic)
    b = _config(tmp_path / "b", synthetic)
    c = _config(tmp_path, synthetic, test_timeout=5.0)
    assert a.config_hash() == b.config_hash() != c.config_hash()


def test_root_only_commands() -> None:
    assert needs_root("sed -i 's/a/b/' /etc/locale.gen && locale-gen")
    assert needs_root("apt-get install -y x")
    assert not needs_root("sed -i 's/pytest/pytest -rA/' tox.ini")


PYTEST_LOG = """\
PASSED tests/a.py::test_ok
FAILED tests/a.py::test_bad - AssertionError: x
ERROR tests/a.py::test_err
XFAIL tests/a.py::test_xf
SKIPPED [1] tests/a.py:3: reason
"""


def test_pytest_parser_reads_summary_lines() -> None:
    got = log_parsers.parse("pytest", PYTEST_LOG)
    assert got["tests/a.py::test_ok"] == "PASSED"
    assert got["tests/a.py::test_bad"] == "FAILED"
    assert got["tests/a.py::test_err"] == "ERROR"
    assert log_parsers.grade(got, ("tests/a.py::test_ok", "tests/a.py::test_xf"), ()) == (2, 0)
    assert log_parsers.grade(got, ("tests/a.py::test_bad", "tests/a.py::gone"), ()) == (0, 0)


def test_pytest_options_parser_normalises_path_parameters() -> None:
    got = log_parsers.parse("pytest_options", "PASSED tests/t.py::test_x[/tmp/abc/file.txt]\n")
    assert got == {"tests/t.py::test_x[/file.txt]": "PASSED"}


def test_pytest_v2_reads_colours_and_the_older_form() -> None:
    got = log_parsers.parse(
        "pytest_v2", "\x1b[32mPASSED\x1b[0m tests/a.py::test_c\ntests/a.py::test_old PASSED\n"
    )
    assert got["tests/a.py::test_c"] == "PASSED" and got["tests/a.py::test_old"] == "PASSED"


def test_django_parser_reads_runner_output() -> None:
    log = (
        "test_a (m.T) ... ok\ntest_b (m.T) ... FAIL\ntest_c (m.T) ... ERROR\n"
        "test_d (m.T) ... skipped 'x'\ntest_e (m.T) ... Server noise\nok\n"
    )
    got = log_parsers.parse("django", log)
    assert got["test_a (m.T)"] == "PASSED" and got["test_b (m.T)"] == "FAILED"
    assert got["test_c (m.T)"] == "ERROR" and got["test_d (m.T)"] == "SKIPPED"
    assert got["test_e (m.T)"] == "PASSED"


def test_sympy_parser_reads_verbose_output() -> None:
    got = log_parsers.parse("sympy", "test_one ok\ntest_two F\ntest_three E\n")
    assert got == {"test_one": "PASSED", "test_two": "FAILED", "test_three": "ERROR"}


def test_unknown_parser_is_an_error() -> None:
    with pytest.raises(ValueError):
        log_parsers.parse("nope", "")


def test_conda_strings_become_pip_requirements() -> None:
    assert envbuild.package_string_to_requirements(
        "numpy 'scipy==1.5.2' pandas=1.1 python=3.9 'matplotlib<3.9.0' compilers"
    ) == ["numpy", "scipy==1.5.2", "pandas==1.1.*", "matplotlib<3.9.0"]
    assert envbuild.conda_spec_to_pip("netcdf4=1.5.7=py39") == "netCDF4==1.5.7"


def test_environment_yml_dependencies_and_pip_section() -> None:
    text = (
        "name: x\nchannels:\n  - conda-forge\ndependencies:\n  - python=3.9\n  - numpy=1.23\n"
        "  - hdf5\n  - pip:\n    - sphinx-gallery\n    - -e .\n  - pandas\n"
    )
    assert envbuild.environment_yml_to_requirements(text) == [
        "numpy==1.23.*",
        "sphinx-gallery",
        "pandas",
    ]


def test_dependency_requirements_record_the_departure() -> None:
    spec = InstanceSpec(
        instance_id="a",
        repo="r/r",
        version="1",
        base_commit="x",
        python="3.9",
        install="",
        test_cmd="pytest",
        test_directives=(),
        log_parser="pytest",
        fail_to_pass=(),
        pass_to_pass=(),
        test_patch="",
        packages="numpy scipy",
    )
    reqs, departures = envbuild.dependency_requirements(spec)
    assert reqs == ["numpy", "scipy"] and departures


def test_coverage_rows_count_each_resource_per_repository() -> None:
    from ril.evaluation.executor.coverage import coverage_rows

    allx = [
        {"instance_id": "a-1", "repo": "o/a"},
        {"instance_id": "a-2", "repo": "o/a"},
        {"instance_id": "b-1", "repo": "o/b"},
    ]
    execm = [{"instance_id": "a-1"}, {"instance_id": "b-1"}]
    rows = coverage_rows(execm, ["a-1", "a-2"], ["a-1"], ["a-1", "a-2"], allx)
    assert rows[0] == {
        "repo": "o/a",
        "instances": 2,
        "executable": 1,
        "exec_with_l2": 1,
        "exec_with_l3": 1,
        "exec_with_units": 1,
        "exec_l2_and_units": 1,
        "exec_l3_and_units": 1,
    }
    assert rows[1]["executable"] == 1 and rows[1]["exec_with_l2"] == 0


def test_build_cost_scales_with_snapshots(tmp_path: Path) -> None:
    from ril.evaluation.executor.coverage import build_cost, rates_from_measured

    csv_path = tmp_path / "m.csv"
    csv_path.write_text(
        "repository,snapshots,units_median_per_snapshot,e3_prepare_seconds_measured,"
        "distinct_unit_texts_full_measured\n"
        "x/y,10,1000,20,1000\nx/z,10,2000,80,4000\n"
    )
    rates = rates_from_measured(csv_path, 100.0)
    assert rates.seconds_per_snapshot_per_1k_units == (2.0, 3.0, 4.0)
    one = build_cost(10, 1000, rates)
    two = build_cost(20, 1000, rates)
    assert two["cpu_hours"][1] == pytest.approx(2 * one["cpu_hours"][1])
    assert one["gpu_hours_per_checkpoint"][1] > 0


def test_inline_comments_are_dropped_from_requirements() -> None:
    text = "lxml    # Optional dep of pydap\nastroid==2.11.6  # Pinned\n# whole line\n-e .\nnumpy\n"
    assert envbuild.requirements_from_text(text) == ["lxml", "astroid==2.11.6", "numpy"]
    yml = "dependencies:\n  - numpy  # core\n  - pip:\n    - lxml    # optional\n"
    assert envbuild.environment_yml_to_requirements(yml) == ["numpy", "lxml"]


def _row(iid: str, run: int, **kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "instance_id": iid,
        "repo": "o/r",
        "run": run,
        "built": True,
        "failure_stage": "",
        "failure_detail": "",
        "patch_applied": True,
        "tests_ran": True,
        "f2p": [1, 1],
        "p2p": [3, 3],
        "outcome_digest": "d1",
        "seconds": {"total": 10.0},
        "peak_rss_mb": 100.0,
        "departures": [],
    }
    base.update(kw)
    return base


def test_classify_applies_the_rule_in_order() -> None:
    from ril.evaluation.executor.subset import classify

    ok = [_row("a", 1), _row("a", 2)]
    assert classify(ok)[:2] == (True, "executable")
    assert classify([_row("a", 1)])[1] == "incomplete"
    unbuilt = [_row("a", 1, built=False, failure_stage="install"), _row("a", 2)]
    assert classify(unbuilt)[1] == "not_built:install"
    assert classify([_row("a", 1, f2p=[0, 1]), _row("a", 2, f2p=[0, 1])])[1] == "gold_f2p_failed"
    assert classify([_row("a", 1, p2p=[2, 3]), _row("a", 2, p2p=[2, 3])])[1] == "gold_p2p_failed"
    flaky = [_row("a", 1), _row("a", 2, outcome_digest="d2", p2p=[2, 3])]
    assert classify(flaky)[1] == "runs_disagree"
    slow = [_row("a", 1, tests_ran=False, failure_stage="tests_timeout"), _row("a", 2)]
    assert classify(slow)[1] == "tests_not_run:tests_timeout"


def test_build_subset_counts_and_table(tmp_path: Path, synthetic: dict[str, str]) -> None:
    from ril.evaluation.executor.subset import build_subset, repo_table

    specs = [_spec(synthetic, instance_id=i) for i in ("a", "b", "c")]
    rows = [_row("a", 1), _row("a", 2), _row("b", 1), _row("b", 2, f2p=[0, 1])]
    doc = build_subset(
        specs, {"latest": rows}, run_id="r", config_hash="h", commit="c", spec_digest="s"
    )
    assert doc["counts"]["executable"] == 1
    assert doc["counts"]["excluded_by_reason"] == {"incomplete": 1, "runs_disagree": 1}
    assert [m["instance_id"] for m in doc["executable"]] == ["a"]
    table = repo_table(doc, specs)
    assert table == [{"repo": "synth/pkg", "instances": 3, "built": 2, "executable": 1}]


def test_shard_of_partitions_without_overlap() -> None:
    from ril.evaluation.executor.jobs import shard_of

    items = list(range(10))
    parts = [shard_of(items, i, 3) for i in range(3)]  # type: ignore[arg-type]
    assert sum(parts, []) == items
    with pytest.raises(ValueError):
        shard_of(items, 3, 3)  # type: ignore[arg-type]


def test_run_shard_is_resumable(tmp_path: Path, synthetic: dict[str, str]) -> None:
    from ril.evaluation.executor import jobs

    cfg = _config(tmp_path, synthetic)
    spec = _spec(synthetic)
    gold = {spec.instance_id: synthetic["gold"]}
    run_dir = tmp_path / "run"
    first = jobs.run_shard([spec], gold, run_dir, cfg, runs=2, builder=FakeBuilder())
    assert first.done == 2 and not first.stopped_disk
    again = jobs.run_shard([spec], gold, run_dir, cfg, runs=2, builder=FakeBuilder())
    assert again.done == 0 and again.skipped == 1
    rows = [x for x in (run_dir / jobs.RESULT_FILE).read_text().splitlines()]
    assert len(rows) == 2


def test_percentiles_use_nearest_rank() -> None:
    from ril.evaluation.executor.summary import p50_p95_p99

    assert p50_p95_p99(list(map(float, range(1, 101)))) == {"p50": 50.0, "p95": 95.0, "p99": 99.0}


def test_spec_round_trip(tmp_path: Path, synthetic: dict[str, str]) -> None:
    from ril.evaluation.executor.spec import load_specs, write_specs

    spec = _spec(synthetic, pip_packages=("a==1",), requirements_paths=("r.txt",))
    path = tmp_path / "s.jsonl"
    write_specs(path, [spec])
    assert load_specs(path) == [spec]


def test_uv_builder_drops_packages_missing_from_pypi_and_records_it(tmp_path: Path) -> None:
    from ril.evaluation.executor.steps import StepResult

    calls: list[str] = []

    def step(name: str, command: str, timeout: float) -> StepResult:
        calls.append(command)
        if name == "packages" and "cdms2" in command:
            msg = "Because cdms2 was not found in the package registry and you require cdms2"
            return StepResult(1, 0.1, 0.0, False, msg)
        return StepResult(0, 0.1, 0.0, False, "")

    spec = InstanceSpec(
        instance_id="a", repo="r/r", version="1", base_commit="x", python="3.9", install="",
        test_cmd="pytest", test_directives=(), log_parser="pytest", fail_to_pass=(),
        pass_to_pass=(), test_patch="", requirements_kind="requirements",
        requirements_text="numpy\ncdms2\nscipy\n",
    )  # fmt: skip
    out = envbuild.UvEnvBuilder().build(spec, tmp_path / "venv", step, 60.0)
    assert out.ok and out.departures == ["dropped cdms2 (not on PyPI)"]
    assert "cdms2" not in calls[-1] and "numpy" in calls[-1] and "scipy" in calls[-1]


def test_later_run_directory_replaces_an_instance_wholesale() -> None:
    from ril.evaluation.executor.subset import merge_runs

    first = [_row("a", 1, built=False), _row("a", 2, built=False), _row("b", 1), _row("b", 2)]
    later = [_row("a", 1), _row("a", 2)]
    merged = merge_runs([first, later])
    assert [(r["instance_id"], r["built"]) for r in merged] == [
        ("a", True),
        ("a", True),
        ("b", True),
        ("b", True),
    ]


def test_policies_in_priority_order_qualify_an_instance_once() -> None:
    from ril.evaluation.executor.subset import build_subset

    spec = InstanceSpec(
        instance_id="a", repo="o/r", version="1", base_commit="x", python="3.9", install="",
        test_cmd="pytest", test_directives=(), log_parser="pytest", fail_to_pass=(),
        pass_to_pass=(), test_patch="",
    )  # fmt: skip
    bad = [_row("a", 1, f2p=[0, 1]), _row("a", 2, f2p=[0, 1])]
    good = [_row("a", 1), _row("a", 2)]
    doc = build_subset(
        [spec],
        {"latest": bad, "era": good},
        run_id="r",
        config_hash="h",
        commit="c",
        spec_digest="s",
    )
    assert doc["executable"][0]["env_policy"] == "era"
    assert doc["counts"]["executable_by_policy"] == {"era": 1}
    both_bad = build_subset(
        [spec],
        {"latest": bad, "era": bad},
        run_id="r",
        config_hash="h",
        commit="c",
        spec_digest="s",
    )
    assert both_bad["excluded"][0]["reasons_by_policy"] == {
        "latest": "gold_f2p_failed",
        "era": "gold_f2p_failed",
    }
    assert both_bad["excluded"][0]["built"] is True


def test_era_policy_sets_date_limits_and_leaves_pins_undated(
    tmp_path: Path, synthetic: dict[str, str]
) -> None:
    cfg = ExecConfig(
        work_root=tmp_path / "work",
        cache_root=tmp_path / "cache",
        repo_source=lambda repo: synthetic["repo"],
        env_policy="era",
    )
    spec = _spec(
        synthetic, created_at="2021-05-01T00:00:00Z", test_cmd="env | grep -E 'UV_EXCL|PIP_UPL'"
    )
    res = evaluate(spec, "", cfg, builder=FakeBuilder())
    assert "UV_EXCLUDE_NEWER=2021-05-01T00:00:00Z" in res.output_tail
    assert "PIP_UPLOADED_PRIOR_TO=2021-05-01T00:00:00Z" in res.output_tail
    assert any("era-dated" in d for d in res.departures)
    assert (
        cfg.config_hash()
        != ExecConfig(
            work_root=cfg.work_root, cache_root=cfg.cache_root, repo_source=cfg.repo_source
        ).config_hash()
    )


def test_older_python_comes_from_the_provider_when_uv_has_none(tmp_path: Path) -> None:
    from ril.evaluation.executor.steps import StepResult

    seen: list[str] = []

    def step(name: str, command: str, timeout: float) -> StepResult:
        seen.append(name)
        if name == "venv":
            return StepResult(2, 0.1, 0.0, False, "error: No interpreter found for Python 3.6")
        return StepResult(0, 0.1, 0.0, False, "")

    def provider(version: str, _step: Stepper) -> str | None:
        return "/mm/py3.6/bin/python" if version == "3.6" else None

    spec = InstanceSpec(
        instance_id="a", repo="r/r", version="1", base_commit="x", python="3.6", install="",
        test_cmd="pytest", test_directives=(), log_parser="pytest", fail_to_pass=(),
        pass_to_pass=(), test_patch="",
    )  # fmt: skip
    out = envbuild.UvEnvBuilder(provider).build(spec, tmp_path / "v", step, 60.0)
    assert out.ok and "venv_mamba" in seen
    assert out.departures == ["python 3.6 from conda-forge (micromamba)"]
    none = envbuild.UvEnvBuilder(lambda v, s: None).build(spec, tmp_path / "v", step, 60.0)
    assert not none.ok and none.stage == "python_unavailable"
