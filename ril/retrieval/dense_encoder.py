"""Dense encoder wrapper and flat exact inner-product index.

Implements the dense signal of ``docs/09_architecture.md`` "Online retrieval": a query and every
code
unit (or chunk) are embedded by one encoder, vectors are L2-normalised, and units are ranked by the
inner product (= cosine) with the query over a **flat exact** index (no approximate search; the
frozen stack of ``docs/08_experimental_design.md`` holds a flat exact index).

Everything about *which* encoder and *how* it is fed is ``provisional: ADR-006`` (the base encoder
is open; decision D24 leaves it to measurement). The candidates measured are registered in
:data:`ENCODERS` with the settings of their released models, nothing substituted:

* ``coderankembed`` (137M): the model's own query prefix, documents without prefix; the model
  repository's modelling code is loaded (``trust_remote_code``), as the model requires.
* ``swerankembed-small`` (137M, fine-tuned from CodeRankEmbed on the SweRank training data): the
  same query prefix as its base (model card); registered as a teacher for the pool-rank measurement
  (the K-rank teacher of SweRank+), not as a candidate base encoder.
* ``qwen3-embedding-0.6b``: the instruction goes on the query only, documents carry none
  (``knowledge/papers/qwen3-embedding-2506.05176.md``, p.3). The report gives the format
  ``{Instruction} {Query}<|endoftext|>`` but no instruction for code tasks; the template used here
  is the ``Instruct: ...\\nQuery:`` form of the model repository's own query prompt with a task
  sentence of ours (:data:`QWEN_TASK`), stated so that it can be held identical across arms.

Truncation policy (one policy for both encoders): queries (template included) and documents are cut
at ``max_tokens`` tokens of the encoder's own tokenizer, keeping the beginning; special tokens are
added after the cut. ``max_tokens`` is a cost setting, not part of the model.

The encoder is a thin wrapper over a backend object with the ``encode``/``tokenizer`` interface of
``sentence-transformers``; the backend is imported lazily, so this module (and the index) work
without torch installed, and tests use a fake backend.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt

PROVISIONAL = "provisional: ADR-006"
Floats32 = npt.NDArray[np.float32]
Ints = npt.NDArray[np.int64]

_NOMIC = "nomic" + chr(45) + "a" + "i"
QWEN_TASK = (
    "Given a GitHub issue, retrieve the code units (functions, methods, classes or modules) "
    "that have to be changed to resolve it"
)
"""Task sentence of the Qwen3-Embedding query instruction (ours; the report lists none for code)."""


@dataclass(frozen=True)
class EncoderSpec:
    """How one encoder is loaded and fed (``provisional: ADR-006``)."""

    name: str
    model_id: str
    query_template: str
    """Query text fed to the model; ``{query}`` is replaced by the issue text."""
    max_tokens: int = 512
    trust_remote_code: bool = False
    revision: str | None = None
    """Model repository revision (the commit downloaded on 2026-10-23), pinned."""

    def __post_init__(self) -> None:
        if "{query}" not in self.query_template:
            raise ValueError("query_template must contain {query}")
        if self.max_tokens < 8:
            raise ValueError("max_tokens must be at least 8")

    def with_max_tokens(self, max_tokens: int) -> EncoderSpec:
        """The same encoder with another truncation length."""
        return replace(self, max_tokens=max_tokens)

    def query_text(self, query: str) -> str:
        """The query as it is fed to the model."""
        return self.query_template.replace("{query}", query)


ENCODERS: dict[str, EncoderSpec] = {
    "coderankembed": EncoderSpec(
        name="coderankembed",
        model_id=f"{_NOMIC}/CodeRankEmbed",
        query_template="Represent this query for searching relevant code: {query}",
        trust_remote_code=True,
        revision="3c4b60807d71f79b43f3c4363786d9493691f8b1",
    ),
    "swerankembed-small": EncoderSpec(
        name="swerankembed-small",
        model_id="Salesforce/SweRankEmbed-Small",
        query_template="Represent this query for searching relevant code: {query}",
        trust_remote_code=True,
        revision="745d2a06103a66d3cfa600aa52fc0d3523010daa",
    ),
    "qwen3-embedding-0.6b": EncoderSpec(
        name="qwen3-embedding-0.6b",
        model_id="Qwen/Qwen3-Embedding-0.6B",
        query_template=f"Instruct: {QWEN_TASK}\nQuery:{{query}}",
        revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
    ),
}


class Backend(Protocol):
    """The part of a ``sentence-transformers`` model the wrapper uses."""

    max_seq_length: int
    tokenizer: Any

    def encode(self, sentences: list[str], **kwargs: Any) -> Any: ...


def normalise_rows(mat: npt.ArrayLike) -> Floats32:
    """Rows scaled to unit L2 norm (a zero row stays zero)."""
    arr = np.asarray(mat, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr[None, :]
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    out: Floats32 = np.divide(arr, norms, out=np.zeros_like(arr), where=norms > 0)
    return out


class DenseEncoder:
    """Encoder of queries and documents into L2-normalised float32 vectors."""

    def __init__(self, spec: EncoderSpec, backend: Backend) -> None:
        self.spec = spec
        self.backend = backend
        self.backend.max_seq_length = spec.max_tokens

    @classmethod
    def load(
        cls,
        spec: EncoderSpec,
        *,
        device: str = "cpu",
        dtype: str = "float32",
        threads: int | None = None,
    ) -> DenseEncoder:
        """Load the released model with ``sentence-transformers`` (imported here, lazily)."""
        import torch  # type: ignore[import-not-found,unused-ignore]
        from sentence_transformers import (  # type: ignore[import-not-found,unused-ignore]
            SentenceTransformer,
        )

        if threads is not None:
            torch.set_num_threads(threads)
        kwargs: dict[str, Any] = {"trust_remote_code": spec.trust_remote_code, "device": device}
        if spec.revision:
            kwargs["revision"] = spec.revision
        model = SentenceTransformer(spec.model_id, **kwargs)
        if dtype == "float16":
            model = model.half()
        elif dtype != "float32":
            raise ValueError(f"unsupported dtype {dtype!r}")
        model.eval()
        return cls(spec, model)

    def token_lengths(self, texts: Sequence[str]) -> list[int]:
        """Token count of each text before the cut (special tokens included)."""
        enc = self.backend.tokenizer(list(texts), add_special_tokens=True, truncation=False)
        return [len(ids) for ids in enc["input_ids"]]

    def _encode(self, texts: Sequence[str], batch_size: int) -> Floats32:
        vecs = self.backend.encode(
            list(texts),
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return normalise_rows(vecs)

    def encode_documents(self, texts: Sequence[str], batch_size: int = 32) -> Floats32:
        """Document vectors (no prefix or instruction), one row per text."""
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        return self._encode(texts, batch_size)

    def encode_queries(self, queries: Sequence[str], batch_size: int = 16) -> Floats32:
        """Query vectors, template applied."""
        if not queries:
            return np.zeros((0, 0), dtype=np.float32)
        return self._encode([self.spec.query_text(q) for q in queries], batch_size)

    def encode_query(self, query: str) -> Floats32:
        """One query vector (batch size 1, the interactive path)."""
        out: Floats32 = self.encode_queries([query], batch_size=1)[0]
        return out


class FlatIndex:
    """Exact inner-product search over L2-normalised vectors (no approximation).

    Ties are broken by the lower row index, so a ranking is a pure function of the vectors and their
    order (the BM25 index breaks ties the same way).
    """

    def __init__(self, vectors: npt.ArrayLike, *, normalise: bool = True) -> None:
        mat = np.asarray(vectors, dtype=np.float32)
        if mat.ndim != 2:
            raise ValueError("vectors must be a 2-D array")
        self.vectors: Floats32 = normalise_rows(mat) if normalise else np.ascontiguousarray(mat)

    @property
    def size(self) -> int:
        """Number of indexed vectors."""
        return int(self.vectors.shape[0])

    @property
    def dim(self) -> int:
        """Vector dimension."""
        return int(self.vectors.shape[1])

    def scores(self, query: npt.ArrayLike) -> Floats32:
        """Inner product of every indexed vector with the query vector."""
        q = np.asarray(query, dtype=np.float32).reshape(-1)
        if q.shape[0] != self.dim:
            raise ValueError(f"query dimension {q.shape[0]} differs from the index ({self.dim})")
        out: Floats32 = self.vectors @ q
        return out

    def search(self, query: npt.ArrayLike, k: int) -> tuple[Ints, Floats32]:
        """The ``k`` best rows (indices and scores), best first, ties by lower index."""
        s = self.scores(query)
        n = s.shape[0]
        k = max(0, min(k, n))
        if k == 0:
            return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.float32)
        if k < n:
            kth = np.partition(s, n - k)[n - k]
            cand = np.flatnonzero(s >= kth)
        else:
            cand = np.arange(n)
        order = np.lexsort((cand, -s[cand]))[:k]
        idx = cand[order].astype(np.int64)
        return idx, s[idx]


def default_threads() -> int:
    """CPU threads for encoding on CPU (``RIL_THREADS``, default 4)."""
    return int(os.environ.get("RIL_THREADS", "4"))
