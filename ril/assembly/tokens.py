"""Token counting for the assembly budget.

Implements ``specs/assembly.md`` ("Tokenizer"). The budget is a number of tokens, so the assembler
needs a counter. The default is a deterministic approximation that needs no model files; the
ratio to a real tokenizer is measured by ``tests/unit/test_assembly_tokens.py`` (slow, needs the
``tokenizers`` package and a ``tokenizer.json``) and recorded in the experiment entry. The final
agent run must pass the agent model's own tokenizer, so the budget is then in the agent's tokens.
"""

from __future__ import annotations

import random
import re
from collections.abc import Sequence
from typing import Protocol

_PIECE = re.compile(r"[A-Za-z]+|[0-9]|[^\sA-Za-z0-9]")


class Tokenizer(Protocol):
    """Anything that names itself and counts tokens of a text (pure and deterministic)."""

    name: str

    def count(self, text: str) -> int: ...


class ApproxTokenizer:
    """Deterministic approximation: one token per word, digit or punctuation mark, one per newline.

    Words are runs of ASCII letters (``make_response`` is three pieces), digits count one each (as
    in the byte-pair vocabularies of recent code models), any other non-space character counts
    one, and every newline counts one (it stands for the line break plus the indentation after
    it). Additive over text split at a newline, which the assembler relies on for its budget
    check (and verifies on the final string).
    """

    name = "approx-words-v1"

    def count(self, text: str) -> int:
        return len(_PIECE.findall(text)) + text.count("\n")


class HFTokenizer:
    """A real tokenizer from a ``tokenizer.json`` (``tokenizers`` package), no special tokens."""

    def __init__(self, path: str, name: str) -> None:
        from tokenizers import Tokenizer as _Tok  # optional dependency, Ada only

        self._tok = _Tok.from_file(path)
        self.name = name

    def count(self, text: str) -> int:
        return len(self._tok.encode(text, add_special_tokens=False).ids)


def ratio_against(
    approx: Tokenizer, real: Tokenizer, texts: Sequence[str], n: int = 200, seed: int = 0
) -> dict[str, object]:
    """Approximate-to-real token ratio on ``n`` texts sampled with ``seed`` (total, quantiles)."""
    if len(texts) < n:
        raise ValueError(f"need at least {n} texts, got {len(texts)}")
    sample = random.Random(seed).sample(list(texts), n)
    pairs = [(approx.count(t), max(1, real.count(t))) for t in sample]
    ratios = sorted(a / r for a, r in pairs)
    return {
        "approx": approx.name,
        "real": real.name,
        "n": n,
        "seed": seed,
        "ratio_total": round(sum(a for a, _ in pairs) / sum(r for _, r in pairs), 4),
        "ratio_median": round(ratios[n // 2], 4),
        "ratio_p5": round(ratios[n // 20], 4),
        "ratio_p95": round(ratios[(19 * n) // 20], 4),
    }
