"""Batches for contrastive retriever training: ordering, positives, negatives, masks, weights.

Implements the batching of ``docs/08_experimental_design.md`` "Experimental design" (a fixed number
of optimizer updates at a fixed batch size; filtering reuses data more, which is recorded, not
eliminated). The planner is shared code for every arm: the arm enters only through the example list
it is given (after the arm's filter), the weights (the arm's weigher) and the ordering (the arm's
ordering hook). Everything else here is held identical across arms.

One batch holds ``batch_size`` distinct examples. For each example: up to ``max_positives``
positives (a seeded subset when it has more) and up to ``negatives_per_example`` hard negatives from
the negative policy (``ril.training.negatives``). Every document of the batch is a candidate for
every query (in-batch negatives), except where a mask removes it:

* ``pos_mask[i, j]``: document ``j`` is one of example ``i``'s selected positives;
* ``valid_mask[i, j]``: document ``j`` enters example ``i``'s softmax at all. It is false when ``j``
  is another example's document that is the same function as one of ``i``'s positives or masked ids
  (same repository and id) or has the same text as one of ``i``'s positives: pull requests of one
  repository share functions, and such a document would be a false negative.

Randomness is keyed by (seed, instance, visit number), so the positives and negatives an example
gets on its n-th visit do not depend on which other examples are in the pool or where it sits in
the order. The plan is a pure function of its inputs; a resumed run replays it to the checkpoint.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import hashlib
from collections import deque
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ril.training.negatives import Mined, NegativePolicy
from ril.training.pool_reader import PoolExample
from ril.training.supervision import Ordering, rng_for

PROVISIONAL = "provisional: ADR-002 (batch size, positives and negatives per example)"
Record = dict[str, Any]
Arr = np.ndarray[Any, Any]


@dataclass(frozen=True)
class BatchSpec:
    """Shape of a batch (held identical across arms; values are provisional)."""

    batch_size: int
    negatives_per_example: int
    max_positives: int

    def __post_init__(self) -> None:
        if self.batch_size < 1 or self.max_positives < 1 or self.negatives_per_example < 0:
            raise ValueError("batch_size and max_positives >= 1, negatives_per_example >= 0")


@dataclass(frozen=True)
class Batch:
    """One optimizer update's inputs."""

    update: int
    instance_ids: tuple[str, ...]
    queries: tuple[str, ...]
    docs: tuple[str, ...]
    doc_ids: tuple[tuple[str, str], ...]
    """``(repository, function id)`` of every document."""
    owner: tuple[int, ...]
    """Index of the example that brought each document."""
    pos_mask: Arr
    valid_mask: Arr
    weights: Arr

    def fingerprint(self) -> str:
        """SHA-256 over everything that reaches the model and the loss (for identity tests)."""
        h = hashlib.sha256()
        for part in (self.instance_ids, self.queries, self.docs, self.doc_ids, self.owner):
            h.update(repr(part).encode("utf-8"))
        for arr in (self.pos_mask, self.valid_mask, self.weights):
            h.update(np.ascontiguousarray(arr).tobytes())
        return h.hexdigest()


def _text_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


@dataclass
class PlanCounts:
    """Exposure counts of a plan (budget accounting, ``docs/EXPERIMENTS.md`` RQ2 extras)."""

    pool_examples: int = 0
    examples_seen: int = 0
    positives_seen: int = 0
    negatives_seen: int = 0
    passes_started: int = 0
    unique: set[str] = field(default_factory=set)
    negative_shortfall: int = 0
    """Example visits that got fewer hard negatives than requested (policy had too few)."""

    def to_dict(self) -> Record:
        return {
            "pool_examples": self.pool_examples,
            "examples_seen": self.examples_seen,
            "unique_examples_seen": len(self.unique),
            "effective_epochs": self.examples_seen / self.pool_examples
            if self.pool_examples
            else 0.0,
            "positives_seen": self.positives_seen,
            "negatives_seen": self.negatives_seen,
            "passes_started": self.passes_started,
            "negative_shortfall_visits": self.negative_shortfall,
        }


class BatchPlanner:
    """Deterministic stream of batches for a fixed number of updates."""

    def __init__(
        self,
        examples: Sequence[PoolExample],
        weights: Sequence[float],
        ordering: Ordering,
        policy: NegativePolicy,
        spec: BatchSpec,
        seed: int,
        mined: Mapping[str, Mined] | None = None,
    ) -> None:
        if len(examples) != len(weights):
            raise ValueError("one weight per example")
        ids = [e.instance_id for e in examples]
        if len(set(ids)) != len(ids):
            raise ValueError("instance ids must be unique")
        if len(examples) < spec.batch_size:
            raise ValueError(
                f"pool of {len(examples)} examples is smaller than the batch ({spec.batch_size})"
            )
        if any(not np.isfinite(w) or w < 0 for w in weights):
            raise ValueError("weights must be finite and non-negative")
        self.examples = list(examples)
        self.weights = [float(w) for w in weights]
        self.ordering, self.policy, self.spec, self.seed = ordering, policy, spec, seed
        self.mined = mined or {}
        self.counts = PlanCounts(pool_examples=len(examples))

    def _stream(self) -> Iterator[int]:
        epoch = 0
        while True:
            self.counts.passes_started += 1
            order = self.ordering.order(self.examples, self.seed, epoch)
            if sorted(order) != list(range(len(self.examples))):
                raise ValueError("an ordering must be a permutation of the examples")
            yield from order
            epoch += 1

    def batches(self, updates: int) -> Iterator[Batch]:
        """The first ``updates`` batches."""
        stream = self._stream()
        deferred: deque[int] = deque()
        visits: dict[str, int] = {}
        for u in range(updates):
            members: list[int] = []
            seen: set[int] = set()
            carry: deque[int] = deque()
            while len(members) < self.spec.batch_size:
                i = deferred.popleft() if deferred else next(stream)
                if i in seen:  # the pass boundary brought an example back into this batch
                    carry.append(i)
                    continue
                seen.add(i)
                members.append(i)
            deferred.extendleft(reversed(carry))
            yield self._build(u, members, visits)

    def _build(self, update: int, members: list[int], visits: dict[str, int]) -> Batch:
        sp = self.spec
        queries: list[str] = []
        docs: list[str] = []
        doc_ids: list[tuple[str, str]] = []
        owner: list[int] = []
        own_pos: list[list[int]] = []
        for b, i in enumerate(members):
            ex = self.examples[i]
            v = visits.get(ex.instance_id, 0)
            visits[ex.instance_id] = v + 1
            npos = len(ex.positive_ids)
            if npos > sp.max_positives:
                pick = rng_for(self.seed, "pos", ex.instance_id, v).choice(
                    npos, size=sp.max_positives, replace=False
                )
                pos_idx = sorted(int(x) for x in pick)
            else:
                pos_idx = list(range(npos))
            neg_idx = self.policy.select(
                ex,
                self.mined.get(ex.instance_id),
                sp.negatives_per_example,
                rng_for(self.seed, "neg", ex.instance_id, v),
            )
            if len(neg_idx) < sp.negatives_per_example:
                self.counts.negative_shortfall += 1
            queries.append(ex.query)
            mine: list[int] = []
            for p in pos_idx:
                mine.append(len(docs))
                docs.append(ex.positive_texts[p])
                doc_ids.append((ex.repo, ex.positive_ids[p]))
                owner.append(b)
            for n in neg_idx:
                docs.append(ex.candidate_texts[n])
                doc_ids.append((ex.repo, ex.candidate_ids[n]))
                owner.append(b)
            own_pos.append(mine)
            self.counts.examples_seen += 1
            self.counts.positives_seen += len(pos_idx)
            self.counts.negatives_seen += len(neg_idx)
            self.counts.unique.add(ex.instance_id)
        bsz, nd = len(members), len(docs)
        pos_mask = np.zeros((bsz, nd), dtype=bool)
        valid = np.ones((bsz, nd), dtype=bool)
        dkeys = [_text_key(t) for t in docs]
        for b, i in enumerate(members):
            ex = self.examples[i]
            for j in own_pos[b]:
                pos_mask[b, j] = True
            blocked = {(ex.repo, p) for p in ex.positive_ids + ex.masked_ids}
            ptexts = {_text_key(t) for t in ex.positive_texts}
            for j in range(nd):
                if pos_mask[b, j]:
                    continue
                if doc_ids[j] in blocked or dkeys[j] in ptexts:
                    valid[b, j] = False
        return Batch(
            update=update,
            instance_ids=tuple(self.examples[i].instance_id for i in members),
            queries=tuple(queries),
            docs=tuple(docs),
            doc_ids=tuple(doc_ids),
            owner=tuple(owner),
            pos_mask=pos_mask,
            valid_mask=valid,
            weights=np.asarray([self.weights[i] for i in members], dtype=np.float64),
        )
