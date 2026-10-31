"""Figures of the mid report, drawn from the logged runs (needs matplotlib; not a project dependency).

Usage: python reports/mid/make_figures.py   (from the repository root; writes reports/mid/fig_*.pdf/.png)
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 8,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "xtick.color": MUTED,
        "ytick.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def incremental_figure() -> None:
    log = json.loads((ROOT / "results/logs/a2_incremental_graph_2026-10-31.json").read_text())
    repos = log["repositories"]
    names = [r["repo_id"].split("/")[1] for r in repos]
    full = [r["full_seconds"]["p50"] for r in repos]
    inc = [r["incremental_seconds"]["p50"] for r in repos]
    fig, ax = plt.subplots(figsize=(3.4, 1.85))
    ys = list(range(len(names)))[::-1]
    speed = [r["speedup_p50"] for r in repos]  # median of per-commit ratios, as in the text
    for y, f, i, x in zip(ys, full, inc, speed, strict=True):
        ax.plot([i, f], [y, y], color=GRID, lw=2, zorder=1, solid_capstyle="round")
        ax.text(f * 1.18, y, f"{x:.1f}x", va="center", ha="left", color=INK, fontsize=7)
    ax.scatter(full, ys, s=28, color=ORANGE, zorder=2, label="full rebuild", edgecolor="white", lw=1)
    ax.scatter(inc, ys, s=28, color=BLUE, zorder=3, label="incremental", edgecolor="white", lw=1)
    ax.set_xscale("log")
    ax.set_xlim(0.05, 100)
    ax.set_xticks([0.1, 1, 10], ["0.1", "1", "10"])
    ax.set_ylim(-0.6, len(names) - 0.4)
    ax.set_yticks(ys, names)
    ax.set_xlabel("seconds per commit (median of 20, log scale)")
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.legend(
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=2,
        fontsize=7,
        handletextpad=0.2,
        borderpad=0.1,
    )
    fig.tight_layout(pad=0.3)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_incremental.{ext}", dpi=300)
    plt.close(fig)


def bm25_figure() -> None:
    log = json.loads((ROOT / "results/logs/a1_bm25_docstring_pilot_2026-10-31.json").read_text())
    labels = {
        "ref": "reference",
        "split_noorig": "split, drop whole id",
        "split": "split, keep whole id",
        "split_fields": "split + name weight 2",
    }
    order = ["ref", "split_noorig", "split", "split_fields"]
    fig, ax = plt.subplots(figsize=(3.4, 1.6))
    ys = list(range(len(order)))[::-1]
    for y, v in zip(ys, order, strict=True):
        mean, lo, hi = log["summary"][v]["rr"]
        ax.plot([lo, hi], [y, y], color=BLUE, lw=2, solid_capstyle="round", zorder=2)
        ax.scatter([mean], [y], s=26, color=BLUE, zorder=3, edgecolor="white", lw=1)
        ax.text(hi + 0.6, y, f"{mean:.1f}", va="center", ha="left", color=INK, fontsize=7)
    ax.set_yticks(ys, [labels[v] for v in order])
    ax.set_xlim(15, 37)
    ax.set_xlabel("MRR (%), n = 2,649, 95% interval")
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout(pad=0.3)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig_bm25.{ext}", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    incremental_figure()
    bm25_figure()
