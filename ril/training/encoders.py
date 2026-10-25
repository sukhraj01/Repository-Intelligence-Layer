"""Trainable encoders for the training stack: a tiny CPU model for tests, and released checkpoints.

The tiny model exists so the whole training path (reader, hooks, batches, loss, optimizer,
checkpoints, evaluation hook) runs end to end on a laptop CPU in seconds; it is **not** a candidate
retriever and no number from it is a result. The released-checkpoint wrapper fine-tunes a
``sentence-transformers`` model registered in ``ril.retrieval.dense_encoder.ENCODERS``; which base
checkpoint RQ2 uses is open (``provisional: ADR-006``).

Both expose :class:`TrainEncoder`: ``module`` (the parameters), ``embed`` (L2-normalised vectors
with gradients), ``save``/``load`` of a model directory, and the evaluation interface of
``ril.retrieval.dense_encoder.DenseEncoder`` (``spec``, ``token_lengths``, ``encode_documents``,
``encode_queries``) so ``ril.evaluation.x2_dense.encode_store`` reads a trained checkpoint
unchanged.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import json
import os
import re
import zlib
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt
import torch
import torch.nn.functional as F
from torch import nn

from ril.retrieval.dense_encoder import ENCODERS, EncoderSpec, normalise_rows

PROVISIONAL = "provisional: ADR-006"
Floats32 = npt.NDArray[np.float32]
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\sA-Za-z0-9_]")


class TrainEncoder(Protocol):
    """What the trainer and the evaluation hook need from an encoder."""

    spec: EncoderSpec
    module: nn.Module

    def embed(self, texts: Sequence[str], is_query: bool) -> torch.Tensor: ...

    def save(self, path: str) -> None: ...

    def token_lengths(self, texts: Sequence[str]) -> list[int]: ...

    def encode_documents(self, texts: Sequence[str], batch_size: int = 32) -> Floats32: ...

    def encode_queries(self, queries: Sequence[str], batch_size: int = 16) -> Floats32: ...


def _no_grad_numpy(enc: TrainEncoder, texts: Sequence[str], is_query: bool, bs: int) -> Floats32:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    was = enc.module.training
    enc.module.eval()
    out: list[Floats32] = []
    with torch.no_grad():
        for i in range(0, len(texts), max(1, bs)):
            v = enc.embed(texts[i : i + bs], is_query).detach().float().cpu().numpy()
            out.append(v.astype(np.float32))
    enc.module.train(was)
    return normalise_rows(np.concatenate(out))


# --------------------------------------------------------------------------- tiny


class _TinyModule(nn.Module):
    def __init__(self, buckets: int, dim: int) -> None:
        super().__init__()
        self.bag = nn.EmbeddingBag(buckets, dim, mode="mean")
        self.proj = nn.Linear(dim, dim)

    def forward(self, flat: torch.Tensor, offsets: torch.Tensor) -> torch.Tensor:
        out: torch.Tensor = F.normalize(self.proj(self.bag(flat, offsets)), dim=-1)
        return out


class TinyEncoder:
    """Hashed-token bag-of-words encoder (CPU test model; not a retriever candidate)."""

    def __init__(self, buckets: int, dim: int, max_tokens: int, seed: int) -> None:
        if buckets < 2 or dim < 2 or max_tokens < 8:
            raise ValueError("buckets >= 2, dim >= 2, max_tokens >= 8")
        self.buckets, self.dim = buckets, dim
        self.spec = EncoderSpec(
            name="tiny", model_id="tiny", query_template="{query}", max_tokens=max_tokens
        )
        gen_state = torch.random.get_rng_state()
        torch.manual_seed(seed)
        self.module: nn.Module = _TinyModule(buckets, dim)
        torch.random.set_rng_state(gen_state)

    def _tokens(self, text: str) -> list[int]:
        toks = _WORD.findall(text.lower())[: self.spec.max_tokens] or ["<empty>"]
        return [zlib.crc32(t.encode("utf-8")) % self.buckets for t in toks]

    def embed(self, texts: Sequence[str], is_query: bool) -> torch.Tensor:
        ids = [self._tokens(self.spec.query_text(t) if is_query else t) for t in texts]
        flat = torch.tensor([x for row in ids for x in row], dtype=torch.long)
        offsets = torch.tensor(np.cumsum([0] + [len(r) for r in ids[:-1]]), dtype=torch.long)
        device = next(self.module.parameters()).device
        out: torch.Tensor = self.module(flat.to(device), offsets.to(device))
        return out

    def token_lengths(self, texts: Sequence[str]) -> list[int]:
        return [len(_WORD.findall(t.lower())) for t in texts]

    def encode_documents(self, texts: Sequence[str], batch_size: int = 32) -> Floats32:
        return _no_grad_numpy(self, texts, False, batch_size)

    def encode_queries(self, queries: Sequence[str], batch_size: int = 16) -> Floats32:
        return _no_grad_numpy(self, queries, True, batch_size)

    def save(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)
        torch.save(self.module.state_dict(), os.path.join(path, "tiny.pt"))
        meta = {
            "kind": "tiny",
            "buckets": self.buckets,
            "dim": self.dim,
            "max_tokens": self.spec.max_tokens,
        }
        with open(os.path.join(path, "encoder.json"), "w", encoding="utf-8") as handle:
            json.dump(meta, handle, sort_keys=True)

    @classmethod
    def load(cls, path: str) -> TinyEncoder:
        with open(os.path.join(path, "encoder.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        enc = cls(int(meta["buckets"]), int(meta["dim"]), int(meta["max_tokens"]), seed=0)
        state = torch.load(os.path.join(path, "tiny.pt"), map_location="cpu", weights_only=True)
        enc.module.load_state_dict(state)
        return enc


# --------------------------------------------------------------------------- released checkpoints


class SentenceTransformerEncoder:
    """A registered ``sentence-transformers`` encoder, fine-tuned in place (GPU job).

    Query template and truncation are the registered spec's (``provisional: ADR-006``), so a trained
    checkpoint is fed exactly as its base was in X2.
    """

    def __init__(self, spec: EncoderSpec, model: Any) -> None:
        self.spec = spec
        self.model = model
        self.model.max_seq_length = spec.max_tokens
        self.module: nn.Module = model

    @classmethod
    def from_registry(
        cls, name: str, max_tokens: int, *, device: str, local_dir: str | None = None
    ) -> SentenceTransformerEncoder:
        from sentence_transformers import (  # type: ignore[import-not-found,unused-ignore]
            SentenceTransformer,
        )

        spec = ENCODERS[name].with_max_tokens(max_tokens)
        if local_dir is None and os.environ.get("HF_HUB_OFFLINE") == "1":
            from ril.retrieval.dense_encoder import local_snapshot

            local_dir = local_snapshot(spec)  # offline: the pinned snapshot directory
        kwargs: dict[str, Any] = {"trust_remote_code": spec.trust_remote_code, "device": device}
        if spec.revision and local_dir is None:
            kwargs["revision"] = spec.revision
        return cls(spec, SentenceTransformer(local_dir or spec.model_id, **kwargs))

    def embed(self, texts: Sequence[str], is_query: bool) -> torch.Tensor:
        feed = [self.spec.query_text(t) for t in texts] if is_query else list(texts)
        feats = self.model.tokenize(feed)
        device = next(self.module.parameters()).device
        feats = {k: v.to(device) for k, v in feats.items()}
        out: torch.Tensor = F.normalize(self.model(feats)["sentence_embedding"], dim=-1)
        return out

    def token_lengths(self, texts: Sequence[str]) -> list[int]:
        enc = self.model.tokenizer(list(texts), add_special_tokens=True, truncation=False)
        return [len(ids) for ids in enc["input_ids"]]

    def encode_documents(self, texts: Sequence[str], batch_size: int = 32) -> Floats32:
        return _no_grad_numpy(self, texts, False, batch_size)

    def encode_queries(self, queries: Sequence[str], batch_size: int = 16) -> Floats32:
        return _no_grad_numpy(self, queries, True, batch_size)

    def save(self, path: str) -> None:
        self.model.save(path)
        meta = {
            "kind": "sentence_transformers",
            "base": self.spec.name,
            "max_tokens": self.spec.max_tokens,
        }
        with open(os.path.join(path, "encoder.json"), "w", encoding="utf-8") as handle:
            json.dump(meta, handle, sort_keys=True)


def build_encoder(cfg: Mapping[str, Any], *, device: str, seed: int) -> TrainEncoder:
    """Encoder from the configuration's ``model`` section (``kind``: tiny or a registry name)."""
    kind = str(cfg["kind"])
    max_tokens = int(cfg["max_tokens"])
    if kind == "tiny":
        enc: TrainEncoder = TinyEncoder(int(cfg["buckets"]), int(cfg["dim"]), max_tokens, seed)
    elif kind == "sentence_transformers":
        enc = SentenceTransformerEncoder.from_registry(
            str(cfg["encoder"]), max_tokens, device=device, local_dir=cfg.get("local_dir")
        )
    else:
        raise ValueError(f"unknown model kind {kind!r}")
    enc.module.to(device)
    return enc


def load_trained(path: str, *, device: str) -> TrainEncoder:
    """A saved model directory back as an encoder (evaluation hook)."""
    with open(os.path.join(path, "encoder.json"), encoding="utf-8") as handle:
        meta = json.load(handle)
    if meta["kind"] == "tiny":
        enc: TrainEncoder = TinyEncoder.load(path)
    else:
        from sentence_transformers import (  # type: ignore[import-not-found,unused-ignore]
            SentenceTransformer,
        )

        spec = ENCODERS[str(meta["base"])].with_max_tokens(int(meta["max_tokens"]))
        model = SentenceTransformer(path, trust_remote_code=spec.trust_remote_code, device=device)
        enc = SentenceTransformerEncoder(spec, model)
    enc.module.to(device)
    return enc
