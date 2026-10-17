"""A function-level call tracer: the dynamic side of the edge-recovery measurement.

Implements recovery definition (b) of ``specs/parse_one_repo.md`` / ADR-012: record, while a
repository's own test suite runs, which function (by file and first line) called which. It uses
``sys.setprofile`` (and ``threading.setprofile``): a ``call`` event gives the callee's code object
and, through ``frame.f_back``, the caller's; a ``c_call`` event gives a builtin or extension
callee called from a Python frame.

Only calls whose *caller* lives under the repository root are kept (the oracle for "in-repo caller
to callee"); every code object entered inside the root is also counted, which gives the suite's
function-level coverage. Pairs are aggregated with counts, so the output size is bounded by the
number of distinct pairs, not by the number of calls.

Standard library only and compatible with Python 3.9+, so it runs on the cluster's interpreters.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from collections import Counter
from types import CodeType, FrameType
from typing import Any

CallerKey = tuple[str, int, str]  # (repo-relative path, first line, code name)


class Tracer:
    """Collects caller/callee pairs for code under ``root``."""

    def __init__(self, root: str) -> None:
        self.root = os.path.realpath(root) + os.sep
        self.entered: Counter[CallerKey] = Counter()
        self.pairs_py: Counter[tuple[CallerKey, CallerKey]] = Counter()
        self.pairs_ext_py: Counter[tuple[CallerKey, str, str]] = Counter()
        self.pairs_c: Counter[tuple[CallerKey, str, str]] = Counter()
        self._info: dict[CodeType, CallerKey | None] = {}

    def _key(self, code: CodeType) -> CallerKey | None:
        try:
            return self._info[code]
        except KeyError:
            pass
        filename = code.co_filename
        key: CallerKey | None = None
        if filename and not filename.startswith("<"):
            real = os.path.realpath(filename)
            if real.startswith(self.root):
                key = (
                    real[len(self.root) :].replace(os.sep, "/"),
                    code.co_firstlineno,
                    code.co_name,
                )
        self._info[code] = key
        return key

    def profile(self, frame: FrameType, event: str, arg: Any) -> None:
        if event == "call":
            callee = self._key(frame.f_code)
            if callee is not None:
                self.entered[callee] += 1
            back = frame.f_back
            if back is None:
                return
            caller = self._key(back.f_code)
            if caller is None:
                return
            if callee is not None:
                self.pairs_py[(caller, callee)] += 1
            else:
                module = str(frame.f_globals.get("__name__", ""))
                self.pairs_ext_py[(caller, module, frame.f_code.co_name)] += 1
        elif event == "c_call":
            caller = self._key(frame.f_code)
            if caller is None:
                return
            module = getattr(arg, "__module__", None) or "builtins"
            name = getattr(arg, "__qualname__", None) or getattr(arg, "__name__", "?")
            self.pairs_c[(caller, str(module), str(name))] += 1

    def start(self) -> None:
        sys.setprofile(self.profile)
        threading.setprofile(self.profile)

    def stop(self) -> None:
        sys.setprofile(None)
        threading.setprofile(None)

    def to_dict(self) -> dict[str, Any]:
        """JSON-able result with deterministic ordering."""

        def k(x: CallerKey) -> list[Any]:
            return [x[0], x[1], x[2]]

        return {
            "root": self.root,
            "python": sys.version.split()[0],
            "entered": [[*k(c), n] for c, n in sorted(self.entered.items())],
            "pairs_py": [[*k(a), *k(b), n] for (a, b), n in sorted(self.pairs_py.items())],
            "pairs_ext_py": [
                [*k(a), m, f, n] for (a, m, f), n in sorted(self.pairs_ext_py.items())
            ],
            "pairs_c": [[*k(a), m, f, n] for (a, m, f), n in sorted(self.pairs_c.items())],
        }


def write_trace(tracer: Tracer, path: str, extra: dict[str, Any] | None = None) -> None:
    """Write the trace as JSON (``extra`` carries the test outcome and environment)."""
    data = tracer.to_dict()
    if extra:
        data.update(extra)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, sort_keys=True)
