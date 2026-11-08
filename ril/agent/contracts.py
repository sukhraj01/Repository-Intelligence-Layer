"""Separate public task context from labels and executable grading inputs."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def validate_path(path: str) -> None:
    p = PurePosixPath(path)
    if not p.parts or p.is_absolute() or ".." in p.parts or "\\" in path or str(p) != path:
        raise ValueError("repository paths must be canonical relative paths")


@dataclass(frozen=True)
class Task:
    instance_id: str
    repo: str
    issue: str
    files: Mapping[str, str]
    role: str = "fixture"

    def __post_init__(self) -> None:
        if self.role != "fixture" or not self.instance_id.startswith("fixture-"):
            raise ValueError("this pilot admits synthetic fixtures only; real harness is gated")
        if not self.repo.startswith("fixture/") or not self.files:
            raise ValueError("fixture repository and source files required")
        for path in self.files:
            validate_path(path)


@dataclass(frozen=True)
class RetrievedFile:
    path: str
    content: str
    score: float | None = None


class RetrievalTool(Protocol):
    """One replaceable tool; input/output does not depend on the repair model."""

    def search(self, query: str, limit: int) -> Sequence[RetrievedFile]: ...


@dataclass(frozen=True)
class ModelRequest:
    instance_id: str
    issue: str
    context: tuple[RetrievedFile, ...]
    seed: int
    temperature: float


@dataclass(frozen=True)
class FileEdit:
    path: str
    old: str
    new: str


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    synthetic_usd: float

    def __post_init__(self) -> None:
        if any(type(x) is not int or x < 0 for x in (self.input_tokens, self.output_tokens)):
            raise ValueError("usage counts must be nonnegative integers")
        if not math.isfinite(self.synthetic_usd) or self.synthetic_usd < 0:
            raise ValueError("synthetic cost must be finite and nonnegative")


@dataclass(frozen=True)
class ModelResponse:
    edits: tuple[FileEdit, ...]
    usage: Usage


class RepairModel(Protocol):
    def propose(self, request: ModelRequest) -> ModelResponse: ...


@dataclass(frozen=True)
class Grade:
    resolved: bool
    status: str
    test_log: str


class PatchGrader(Protocol):
    def grade(self, task: Task, edits: Sequence[FileEdit]) -> Grade: ...
