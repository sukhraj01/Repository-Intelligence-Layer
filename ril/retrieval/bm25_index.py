"""BM25 index over text documents (chunks of a benchmark folder, or code units of a snapshot).

Implements the sparse signal of ``docs/09_architecture.md`` "Online retrieval" in the plainest
standard form, so that the same code can reproduce the published BM25 reference of the
benchmark and then run on units:

* tokenisation as in the reference toolkit: lower-case, ``\\b\\w\\w+\\b`` tokens, a 33-word English
  stop list (applied before stemming), Snowball English stemming;
* scoring as the "Lucene" variant: ``idf = ln(1 + (N - df + 0.5) / (df + 0.5))`` and
  ``tf / (tf + k1 * (1 - b + b * len / avg_len))``; repeated query tokens count repeatedly;
* ``k1 = 1.5`` and ``b = 0.75`` are the reference toolkit's defaults and are recorded as
  ``provisional: ADR-004`` (they are an implementation choice for the reproduction, not a tuned
  value; any sweep belongs on the development repositories, never on the test repositories).

Ties are broken by document order (lower index first), so a ranking is a pure function of the
scores and the input order. Zero-score documents are ranked too, after every positive score, in
document order (the reference toolkit returns them as well when a query has few matching terms).

Pure Python 3.10-compatible apart from numpy and PyStemmer.
"""

from __future__ import annotations

import re
from array import array
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import Stemmer

STOPWORDS_EN: frozenset[str] = frozenset(
    (
        "a an and are as at be but by for if in into is it no not of on or such that the their "
        "then there these they this to was will with"
    ).split()
)
"""The stop list of the reference toolkit (33 words)."""

_TOKEN = re.compile(r"(?u)\b\w\w+\b")
_STEMMER = Stemmer.Stemmer("english")
_STEM_CACHE: dict[str, str] = {}

Float = npt.NDArray[np.float64]
Int = npt.NDArray[np.int64]


@dataclass(frozen=True)
class BM25Params:
    """Scoring parameters. ``provisional: ADR-004`` (reference defaults, not tuned)."""

    k1: float = 1.5
    b: float = 0.75

    def __post_init__(self) -> None:
        if self.k1 < 0 or not 0.0 <= self.b <= 1.0:
            raise ValueError(f"invalid BM25 parameters k1={self.k1}, b={self.b}")


def _stem(token: str) -> str:
    stem = _STEM_CACHE.get(token)
    if stem is None:
        stem = _STEMMER.stemWord(token)
        _STEM_CACHE[token] = stem
    return stem


def tokenize(text: str) -> list[str]:
    """Stemmed tokens of ``text`` (see the module docstring for the exact rule)."""
    return [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS_EN]


class BM25Index:
    """Inverted index with precomputed per-posting weights; scores a query as a weighted sum.

    ``documents`` is an iterable of token lists (one per document, in the order that fixes tie
    breaking). The token lists are consumed once; only postings are kept.
    """

    def __init__(self, documents: Iterable[Sequence[str]], params: BM25Params | None = None):
        self.params = params or BM25Params()
        vocab: dict[str, int] = {}
        terms: array[int] = array("i")
        docs: array[int] = array("i")
        tfs: array[int] = array("i")
        lengths: list[int] = []
        for doc_id, tokens in enumerate(documents):
            lengths.append(len(tokens))
            for tok, tf in Counter(tokens).items():
                tid = vocab.get(tok)
                if tid is None:
                    tid = vocab[tok] = len(vocab)
                terms.append(tid)
                docs.append(doc_id)
                tfs.append(tf)
        self.vocab = vocab
        self.n_docs = len(lengths)
        self.doc_len: Int = np.asarray(lengths, dtype=np.int64)
        self.avg_len = float(self.doc_len.mean()) if self.n_docs else 0.0
        t = np.frombuffer(terms, dtype=np.int32).astype(np.int64)
        d = np.frombuffer(docs, dtype=np.int32).astype(np.int64)
        f = np.frombuffer(tfs, dtype=np.int32).astype(np.float64)
        order = np.argsort(t, kind="stable")  # postings of a term stay in document order
        t, d, f = t[order], d[order], f[order]
        df = np.bincount(t, minlength=len(vocab)).astype(np.float64)
        idf = np.log1p((self.n_docs - df + 0.5) / (df + 0.5))
        denom = self.params.k1 * (
            (1.0 - self.params.b) + self.params.b * self.doc_len[d] / max(self.avg_len, 1e-12)
        )
        self._weights: Float = idf[t] * (f / (f + denom))
        self._docs: Int = d
        self._starts: Int = np.concatenate(([0], np.cumsum(df.astype(np.int64))))

    def scores(self, query_tokens: Sequence[str]) -> Float:
        """BM25 score of every document for the query (length ``n_docs``)."""
        out: Float = np.zeros(self.n_docs, dtype=np.float64)
        for tok, qtf in Counter(query_tokens).items():
            tid = self.vocab.get(tok)
            if tid is None:
                continue
            a, z = int(self._starts[tid]), int(self._starts[tid + 1])
            out[self._docs[a:z]] += qtf * self._weights[a:z]
        return out


def order_by_score(scores: Float, subset: Int | None = None) -> Int:
    """Document indices by decreasing score, ties by increasing index.

    With ``subset`` (an array of document indices) only those documents are ranked.
    """
    idx: Int = np.arange(len(scores), dtype=np.int64) if subset is None else np.sort(subset)
    # lexsort sorts by the last key first; the stable order of ``idx`` is already ascending
    return idx[np.lexsort((idx, -scores[idx]))]
