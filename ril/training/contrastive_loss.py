"""Multi-positive InfoNCE with in-batch negatives and per-example weights.

Implements the training objective of ``docs/08_experimental_design.md`` (temperature tau is in the
held-identical block; its value comes from the run configuration, never from a default here). Two
multi-positive forms are available, both from read sources; which one the frozen configuration
uses is open (``provisional: ADR-002``):

* ``sum_in_numerator`` (CORE-Bench fine-tune, ``knowledge/papers/core-bench-2606.11864.md``):
  ``L(q) = -log( sum_{d in P} exp(s/tau) / sum_{d in P u N} exp(s/tau) )``.
* ``mean_over_positives`` (SweRank-style, each positive its own instance whose competitors are the
  negatives only; ``knowledge/papers/swerank-2505.07849.md`` Sec. 4.1): the mean over positives of
  ``-log( exp(s_p/tau) / (exp(s_p/tau) + sum_{d in N} exp(s/tau)) )``.

``N`` is every valid document of the batch that is not one of the query's positives (in-batch
positives and negatives of the other examples, and the query's own hard negatives). Per-example
weights (the WEIGHT arm's hook) scale each example's loss; the batch loss is
``sum(w * l) / normaliser`` with ``normaliser`` = the batch size (``batch``) or the weight sum
(``weight_sum``), also ``provisional: ADR-002``; with unit weights both equal the plain mean,
which is what makes RAW the identity of WEIGHT.

Kept compatible with Python 3.10.
"""

from __future__ import annotations

from typing import Any

import torch

PROVISIONAL = "provisional: ADR-002"
FORMS = ("sum_in_numerator", "mean_over_positives")
NORMALISERS = ("batch", "weight_sum")
_NEG = -1.0e9


def info_nce(
    q: torch.Tensor,
    d: torch.Tensor,
    pos_mask: torch.Tensor,
    valid_mask: torch.Tensor,
    weights: torch.Tensor,
    *,
    tau: float,
    form: str,
    normaliser: str,
) -> tuple[torch.Tensor, dict[str, Any]]:
    """Batch loss and diagnostics.

    ``q`` (B, H) and ``d`` (D, H) are L2-normalised embeddings; ``pos_mask`` and ``valid_mask`` are
    (B, D) booleans (a positive must be valid); ``weights`` is (B,).
    """
    if tau <= 0:
        raise ValueError("tau must be positive")
    if form not in FORMS:
        raise ValueError(f"form must be one of {FORMS}")
    if normaliser not in NORMALISERS:
        raise ValueError(f"normaliser must be one of {NORMALISERS}")
    if bool((pos_mask & ~valid_mask).any()):
        raise ValueError("a positive is masked out")
    if not bool(pos_mask.any(dim=1).all()):
        raise ValueError("every query needs at least one positive")
    logits = (q @ d.T).float() / tau  # float32 even under autocast (masks use -1e9)
    masked = logits.masked_fill(~valid_mask, _NEG)
    if form == "sum_in_numerator":
        num = torch.logsumexp(masked.masked_fill(~pos_mask, _NEG), dim=1)
        den = torch.logsumexp(masked, dim=1)
        per = den - num
    else:
        neg_only = masked.masked_fill(pos_mask, _NEG)  # (B, D) negatives
        neg_lse = torch.logsumexp(neg_only, dim=1, keepdim=True)  # (B, 1)
        # per positive: log(exp(s_p) + exp(neg_lse)) - s_p
        both = torch.logaddexp(masked, neg_lse.expand_as(masked))
        term = (both - masked) * pos_mask
        per = term.sum(dim=1) / pos_mask.sum(dim=1)
    w = weights.to(per.dtype)
    norm = per.new_tensor(float(len(per))) if normaliser == "batch" else w.sum()
    if float(norm) <= 0:
        raise ValueError("weights sum to zero")
    loss = (w * per).sum() / norm
    diag = {
        "loss_unweighted": float(per.mean().detach()),
        "candidates_per_query": float(valid_mask.sum(dim=1).float().mean()),
        "positives_per_query": float(pos_mask.sum(dim=1).float().mean()),
    }
    return loss, diag
