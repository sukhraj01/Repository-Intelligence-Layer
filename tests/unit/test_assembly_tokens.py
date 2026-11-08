"""Token counting for the assembly budget (specs/assembly.md, "Tokenizer")."""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

import pytest

from ril.assembly.tokens import ApproxTokenizer, ratio_against

TOK = ApproxTokenizer()


def test_known_counts() -> None:
    assert TOK.count("") == 0
    assert TOK.count("make_response") == 3  # make, _, response
    assert TOK.count("x = 10") == 4  # x, =, 1, 0
    assert TOK.count("a\nb") == 3  # a, b, newline


def test_additive_over_a_newline_split() -> None:
    rng = random.Random(0)
    alphabet = "ab_ 1(){}:=\n\t#é"
    for _ in range(200):
        a = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40))).rstrip("\n")
        b = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        assert TOK.count(a + "\n" + b) == TOK.count(a) + 1 + TOK.count(b)


@pytest.mark.slow
def test_ratio_to_a_real_tokenizer_on_sampled_units() -> None:
    """Needs ``tokenizers`` and RIL_TOKENIZER_JSON (a tokenizer.json) and RIL_UNIT_TEXTS (a JSON
    list of unit texts); writes the measured ratio next to the texts (RIL_RATIO_OUT)."""
    pytest.importorskip("tokenizers")
    tok_json = os.environ.get("RIL_TOKENIZER_JSON")
    texts_path = os.environ.get("RIL_UNIT_TEXTS")
    if not tok_json or not texts_path:
        pytest.skip("RIL_TOKENIZER_JSON and RIL_UNIT_TEXTS not set")
    from ril.assembly.tokens import HFTokenizer

    real = HFTokenizer(tok_json, Path(tok_json).parent.name)
    texts = json.loads(Path(texts_path).read_text(encoding="utf-8"))
    result = ratio_against(TOK, real, texts)
    out = os.environ.get("RIL_RATIO_OUT")
    if out:
        Path(out).write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    assert 0.5 < float(result["ratio_total"]) < 2.0  # type: ignore[arg-type]


class _Words:
    name = "words"

    def count(self, text: str) -> int:
        return len(text.split())


def test_ratio_against_is_deterministic_and_checks_the_sample_size() -> None:
    texts = [f"def f{i}(x):\n    return x + {i}" for i in range(300)]
    one = ratio_against(TOK, _Words(), texts)
    assert one == ratio_against(TOK, _Words(), texts)
    assert one["n"] == 200 and float(one["ratio_total"]) > 1.0  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ratio_against(TOK, _Words(), texts[:10])
