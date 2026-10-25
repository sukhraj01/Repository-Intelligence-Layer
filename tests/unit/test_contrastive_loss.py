"""Tests for the multi-positive InfoNCE loss."""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")  # Ada only: the local machine has no torch (Makefile header)
pytestmark = pytest.mark.torch

import math

from ril.training.contrastive_loss import info_nce


def _inputs() -> tuple[torch.Tensor, ...]:
    g = torch.Generator().manual_seed(0)
    q = torch.nn.functional.normalize(torch.randn(2, 4, generator=g), dim=-1)
    d = torch.nn.functional.normalize(torch.randn(5, 4, generator=g), dim=-1)
    pos = torch.tensor([[1, 1, 0, 0, 0], [0, 0, 1, 0, 0]], dtype=torch.bool)
    valid = torch.tensor([[1, 1, 1, 0, 1], [1, 1, 1, 1, 1]], dtype=torch.bool)
    return q, d, pos, valid


def _manual(
    q: torch.Tensor, d: torch.Tensor, pos: torch.Tensor, valid: torch.Tensor, tau: float, form: str
) -> list[float]:
    s = (q @ d.T / tau).tolist()
    out = []
    for i in range(q.shape[0]):
        P = [j for j in range(d.shape[0]) if pos[i, j]]
        N = [j for j in range(d.shape[0]) if valid[i, j] and not pos[i, j]]
        if form == "sum_in_numerator":
            num = sum(math.exp(s[i][j]) for j in P)
            den = sum(math.exp(s[i][j]) for j in P + N)
            out.append(-math.log(num / den))
        else:
            neg = sum(math.exp(s[i][j]) for j in N)
            out.append(
                sum(-math.log(math.exp(s[i][p]) / (math.exp(s[i][p]) + neg)) for p in P) / len(P)
            )
    return out


@pytest.mark.parametrize("form", ["sum_in_numerator", "mean_over_positives"])
def test_matches_the_written_formula(form: str) -> None:
    q, d, pos, valid = _inputs()
    per = _manual(q, d, pos, valid, 0.5, form)
    loss, diag = info_nce(q, d, pos, valid, torch.ones(2), tau=0.5, form=form, normaliser="batch")
    assert float(loss) == pytest.approx(sum(per) / 2, rel=1e-5)
    w = torch.tensor([2.0, 0.5])
    lw, _ = info_nce(q, d, pos, valid, w, tau=0.5, form=form, normaliser="weight_sum")
    assert float(lw) == pytest.approx((2 * per[0] + 0.5 * per[1]) / 2.5, rel=1e-5)
    lb, _ = info_nce(q, d, pos, valid, w, tau=0.5, form=form, normaliser="batch")
    assert float(lb) == pytest.approx((2 * per[0] + 0.5 * per[1]) / 2, rel=1e-5)
    assert diag["positives_per_query"] == 1.5


def test_masked_documents_do_not_matter_and_errors() -> None:
    q, d, pos, valid = _inputs()
    a, _ = info_nce(
        q, d, pos, valid, torch.ones(2), tau=1.0, form="sum_in_numerator", normaliser="batch"
    )
    d2 = d.clone()
    d2[3] = -d2[3]  # document 3 is masked for query 0; change it, query 0's term must not move
    valid2 = valid.clone()
    valid2[1, 3] = False
    b, _ = info_nce(
        q, d2, pos, valid2, torch.ones(2), tau=1.0, form="sum_in_numerator", normaliser="batch"
    )
    c, _ = info_nce(
        q, d, pos, valid2, torch.ones(2), tau=1.0, form="sum_in_numerator", normaliser="batch"
    )
    assert float(b) == pytest.approx(float(c))
    assert float(a) != pytest.approx(float(c))
    with pytest.raises(ValueError):
        info_nce(
            q,
            d,
            pos,
            valid & ~pos,
            torch.ones(2),
            tau=0.1,
            form="sum_in_numerator",
            normaliser="batch",
        )
    with pytest.raises(ValueError):
        info_nce(
            q, d, pos, valid, torch.ones(2), tau=0.0, form="sum_in_numerator", normaliser="batch"
        )
    with pytest.raises(ValueError):
        info_nce(
            q,
            d,
            pos,
            valid,
            torch.zeros(2),
            tau=0.1,
            form="sum_in_numerator",
            normaliser="weight_sum",
        )
