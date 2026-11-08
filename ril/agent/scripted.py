"""Deterministic repair stub; surrogate token counts and prices are test inputs."""

from __future__ import annotations

import math
import re

from ril.agent.contracts import FileEdit, ModelRequest, ModelResponse, Usage


class ScriptedRepair:
    """Uses public issue/context only; no gold patch, tests or resolved label are accepted."""

    def __init__(self, input_per_million: float = 1.0, output_per_million: float = 2.0):
        if any(
            type(rate) not in (int, float) or not math.isfinite(rate) or rate < 0
            for rate in (input_per_million, output_per_million)
        ):
            raise ValueError("synthetic rates must be finite and nonnegative")
        self.input_rate = input_per_million
        self.output_rate = output_per_million

    def propose(self, request: ModelRequest) -> ModelResponse:
        edits: tuple[FileEdit, ...] = ()
        explicit = re.fullmatch(
            r"In (\w+\.py), add (\d+) to the input instead of subtracting\.", request.issue
        )
        if explicit:
            path, offset = explicit.groups()
            edits = (FileEdit(path, f"return value - {offset}", f"return value + {offset}"),)
        elif "multiply" not in request.issue:
            for file in request.context:
                expr = re.search(r"return value - (\d+)", file.content)
                if expr:
                    edits = (FileEdit(file.path, expr.group(), f"return value + {expr.group(1)}"),)
                    break
        text = request.issue + "".join(f.path + f.content for f in request.context)
        input_n = (len(text.encode()) + 3) // 4
        output_n = (len(repr(edits).encode()) + 3) // 4
        usage = Usage(
            input_n,
            output_n,
            (input_n * self.input_rate + output_n * self.output_rate) / 1_000_000,
        )
        return ModelResponse(edits, usage)
