"""Retrieval adapters with one shared file-level boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ril.agent.contracts import RetrievedFile
from ril.retrieval.bm25_index import BM25Index, BM25Params, tokenize


class FileRetrieval:
    def __init__(
        self,
        files: Mapping[str, str],
        kind: str,
        *,
        gold_files: Sequence[str] = (),
        params: BM25Params | None = None,
    ) -> None:
        if kind not in {"none", "bm25", "oracle"}:
            raise ValueError("unknown retrieval condition")
        if gold_files and kind != "oracle":
            raise ValueError("only the oracle tool may receive gold file identities")
        if kind == "oracle" and (not gold_files or set(gold_files) - files.keys()):
            raise ValueError("oracle requires existing gold file identities")
        self.files = dict(files)
        self.paths = sorted(files)
        self.kind = kind
        self.gold_files = tuple(gold_files)
        self.index = (
            BM25Index((tokenize(p + "\n" + files[p]) for p in self.paths), params)
            if kind == "bm25"
            else None
        )

    def search(self, query: str, limit: int) -> tuple[RetrievedFile, ...]:
        if type(limit) is not int or limit <= 0:
            raise ValueError("retrieval limit must be positive")
        if self.kind == "none":
            return ()
        if self.kind == "oracle":
            return tuple(RetrievedFile(p, self.files[p]) for p in self.gold_files[:limit])
        assert self.index is not None
        scores = self.index.scores(tokenize(query))
        order = self.index.top_k(tokenize(query), limit)
        return tuple(
            RetrievedFile(self.paths[int(i)], self.files[self.paths[int(i)]], float(scores[i]))
            for i in order
        )
