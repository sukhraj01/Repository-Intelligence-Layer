"""Turn a test run's output into ``{test id: status}`` for the repositories of Verified.

Implements ``docs/RQ3_PILOT.md`` ("read the PASSED lines; resolved means all FAIL_TO_PASS and
all PASS_TO_PASS pass"). The output formats are the ones the benchmark's own commands print
(pytest ``-rA`` summary lines, the Django runner at verbosity 2, SymPy's ``bin/test``); a test
named by the benchmark that is absent from the output counts as failed, as in the benchmark.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping

PASSED = "PASSED"
FAILED = "FAILED"
ERROR = "ERROR"
SKIPPED = "SKIPPED"
XFAIL = "XFAIL"
STATUSES = (PASSED, FAILED, ERROR, SKIPPED, XFAIL)
PASSING = frozenset({PASSED, XFAIL})

_ANSI = re.compile(r"\x1b\[[0-9;]*m|\[(\d+)m")
_CTRL = {c: None for c in range(1, 32)}
_OPTION = re.compile(r"(.*?)\[(.*)\]")

Parser = Callable[[str], dict[str, str]]


def _summary_lines(log: str, *, clean: bool) -> list[str]:
    lines = []
    for line in log.split("\n"):
        if clean:
            line = _ANSI.sub("", line).translate(_CTRL)
        lines.append(line)
    return lines


def parse_pytest(log: str, *, clean: bool = False, options: bool = False) -> dict[str, str]:
    """Read ``STATUS test-id [- message]`` lines of ``pytest -rA``.

    ``clean`` strips colour codes and control characters and also reads the older
    ``test-id STATUS`` form; ``options`` normalises a parameter that is an absolute path.
    """
    out: dict[str, str] = {}
    for line in _summary_lines(log, clean=clean):
        head = next((s for s in STATUSES if line.startswith(s)), None)
        if head is not None:
            if head == FAILED:
                line = line.replace(" - ", " ")
            parts = line.split()
            if len(parts) < 2:
                continue
            name = parts[1]
            if options:
                m = _OPTION.search(name)
                if m:
                    main, opt = m.groups()
                    if opt.startswith("/") and not opt.startswith("//") and "*" not in opt:
                        opt = "/" + opt.split("/")[-1]
                    name = f"{main}[{opt}]"
            out[name] = parts[0]
        elif clean:
            tail = next((s for s in STATUSES if line.endswith(s)), None)
            parts = line.split()
            if tail is not None and len(parts) >= 2:
                out[parts[0]] = parts[1]
    return out


def parse_seaborn(log: str) -> dict[str, str]:
    """Pytest summary lines, plus the ``test-id PASSED`` form some seaborn runs print."""
    out: dict[str, str] = {}
    for line in log.split("\n"):
        parts = line.split()
        if line.startswith(FAILED) and len(parts) > 1:
            out[parts[1]] = FAILED
        elif f" {PASSED} " in line and len(parts) > 1 and parts[1] == PASSED:
            out[parts[0]] = PASSED
        elif line.startswith(PASSED) and len(parts) > 1:
            out[parts[1]] = PASSED
    return out


def parse_matplotlib(log: str) -> dict[str, str]:
    """Pytest summary lines, with the mouse-button enum names spelled as the ids spell them."""
    return parse_pytest(log.replace("MouseButton.LEFT", "1").replace("MouseButton.RIGHT", "3"))


_DJANGO_OK = (" ... ok", " ... OK", " ...  OK")


def parse_django(log: str) -> dict[str, str]:
    """Read the Django test runner at verbosity 2 (``name ... ok`` and its failure forms)."""
    out: dict[str, str] = {}
    prev: str | None = None
    for raw in log.split("\n"):
        line = raw.strip()
        if "--version is equivalent to version" in line:
            out["--version is equivalent to version"] = PASSED
        if " ... " in line:
            prev = line.split(" ... ")[0]
        for suffix in _DJANGO_OK:
            if line.endswith(suffix):
                out[line.rsplit(suffix, 1)[0]] = PASSED
                break
        if " ... skipped" in line:
            out[line.split(" ... skipped")[0]] = SKIPPED
        if line.endswith(" ... FAIL"):
            out[line.split(" ... FAIL")[0]] = FAILED
        if line.startswith("FAIL:") and len(line.split()) > 1:
            out[line.split()[1].strip()] = FAILED
        if line.endswith(" ... ERROR"):
            out[line.split(" ... ERROR")[0]] = ERROR
        if line.startswith("ERROR:") and len(line.split()) > 1:
            out[line.split()[1].strip()] = ERROR
        if line.startswith("ok") and prev is not None:
            # output printed between "..." and "ok" split the line
            out[prev] = PASSED
    return out


def parse_sympy(log: str) -> dict[str, str]:
    """Read SymPy's ``bin/test --verbose`` (``test_x ok`` / ``F`` / ``E`` and failure headers)."""
    out: dict[str, str] = {}
    for m in re.finditer(r"(_*) (.*)\.py:(.*) (_*)", log):
        out[f"{m.group(2)}.py:{m.group(3)}"] = FAILED
    for raw in log.split("\n"):
        line = raw.strip()
        if line.startswith("test_"):
            name = line.split()[0]
            if line.endswith(" E"):
                out[name] = ERROR
            if line.endswith(" F"):
                out[name] = FAILED
            if line.endswith(" ok"):
                out[name] = PASSED
    return out


PARSERS: Mapping[str, Parser] = {
    "pytest": parse_pytest,
    "pytest_options": lambda log: parse_pytest(log, options=True),
    "pytest_v2": lambda log: parse_pytest(log, clean=True),
    "seaborn": parse_seaborn,
    "matplotlib": parse_matplotlib,
    "django": parse_django,
    "sympy": parse_sympy,
}

# Which reader the benchmark uses for each repository of Verified.
REPO_PARSER: Mapping[str, str] = {
    "astropy/astropy": "pytest_v2",
    "django/django": "django",
    "matplotlib/matplotlib": "matplotlib",
    "mwaskom/seaborn": "seaborn",
    "pallets/flask": "pytest",
    "psf/requests": "pytest_options",
    "pydata/xarray": "pytest",
    "pylint-dev/pylint": "pytest_options",
    "pytest-dev/pytest": "pytest",
    "scikit-learn/scikit-learn": "pytest_v2",
    "sphinx-doc/sphinx": "pytest_v2",
    "sympy/sympy": "sympy",
}


def parse(name: str, log: str) -> dict[str, str]:
    try:
        parser = PARSERS[name]
    except KeyError as exc:
        raise ValueError(f"unknown log parser {name!r}") from exc
    return parser(log)


def grade(
    statuses: Mapping[str, str], fail_to_pass: tuple[str, ...], pass_to_pass: tuple[str, ...]
) -> tuple[int, int]:
    """Count the named tests that pass: (F2P passed, P2P passed). Absent means not passed."""
    f = sum(1 for t in fail_to_pass if statuses.get(t) in PASSING)
    p = sum(1 for t in pass_to_pass if statuses.get(t) in PASSING)
    return f, p
