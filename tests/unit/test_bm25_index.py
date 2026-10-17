"""BM25 index: tokenisation, scoring formula, tie order, edge cases (docs/09_architecture.md)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from ril.retrieval.bm25_index import BM25Index, BM25Params, order_by_score, tokenize


def test_tokenize_lowercases_drops_stopwords_short_tokens_and_stems() -> None:
    assert tokenize("The Runners are running, a b x1 of it") == ["runner", "run", "x1"]
    assert tokenize("") == []
    assert tokenize("!!! 1 -") == []  # single characters and punctuation are not tokens
    assert tokenize("snake_case") == ["snake_cas"]  # underscores are word characters


def test_score_matches_the_lucene_formula_by_hand() -> None:
    docs = [["apple", "pie"], ["apple", "apple", "tart"], ["tart"]]
    idx = BM25Index(docs, BM25Params(k1=1.5, b=0.75))
    avg = (2 + 3 + 1) / 3
    n, df = 3, 2  # "apple" in two documents
    idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
    expect = [
        idf * 1 / (1 + 1.5 * (0.25 + 0.75 * 2 / avg)),
        idf * 2 / (2 + 1.5 * (0.25 + 0.75 * 3 / avg)),
        0.0,
    ]
    assert np.allclose(idx.scores(["apple"]), expect)


def test_repeated_query_tokens_count_repeatedly_and_unknown_tokens_are_ignored() -> None:
    idx = BM25Index([["a1", "b2"], ["b2"]])
    once = idx.scores(["b2"])
    assert np.allclose(idx.scores(["b2", "b2"]), 2 * once)
    assert np.allclose(idx.scores(["b2", "never_seen"]), once)
    assert not idx.scores(["never_seen"]).any()


def test_ties_break_by_document_order_and_zero_scores_follow_positive_ones() -> None:
    idx = BM25Index([["x1"], ["y1"], ["x1"], ["z1"]])
    s = idx.scores(["x1"])
    assert list(order_by_score(s)) == [0, 2, 1, 3]
    assert list(order_by_score(s, np.array([3, 2, 1]))) == [2, 1, 3]  # subset, same rule


def test_empty_corpus_and_empty_documents_do_not_crash() -> None:
    assert BM25Index([]).scores(["a1"]).shape == (0,)
    idx = BM25Index([[], ["k1"]])
    assert list(idx.scores(["k1"]))[0] == 0.0


def test_invalid_parameters_are_rejected() -> None:
    with pytest.raises(ValueError):
        BM25Params(k1=-1.0)
    with pytest.raises(ValueError):
        BM25Params(b=1.5)


def test_agrees_with_the_reference_library_on_ranking() -> None:
    bm25s = pytest.importorskip("bm25s")
    stemmer_mod = pytest.importorskip("Stemmer")
    texts = [
        "def parse_config(path): return open(path).read()",
        "class ConfigParser: handles configuration files and parsing errors",
        "the quick brown fox jumps over the lazy dog",
        "parsing parses parsed configs; configuration parsing is hard",
        "unrelated words about networking sockets and timeouts",
    ]
    stem = stemmer_mod.Stemmer("english")
    enc = bm25s.tokenize(["\n" + t for t in texts], stopwords="en", stemmer=stem)
    ref = bm25s.BM25()
    ref.index(enc, show_progress=False)
    q = "parsing configuration files"
    q_tok = bm25s.tokenize([q], stopwords="en", stemmer=stem, return_ids=False)
    res, _ = ref.retrieve(q_tok, k=len(texts), show_progress=False)
    idx = BM25Index(tokenize("\n" + t) for t in texts)
    ours = list(order_by_score(idx.scores(tokenize(q))))
    assert ours[:2] == list(res[0][:2])  # the later ranks are zero-score ties
