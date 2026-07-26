"""Shared figure style for the Violet and HMV analyses.

One palette, one set of rules, applied everywhere: categorical hues assigned in a
fixed order (never cycled), a single-hue sequential ramp for magnitude, a
two-hue diverging ramp for polarity, recessive grids and axes, thin marks, and a
legend whenever more than one series is on screen.
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# Categorical slots, in fixed assignment order.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = SERIES

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
INK_3 = "#8a8880"
GRID = "#e4e3df"

# Single-hue sequential ramp (magnitude).
SEQ_STEPS = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
             "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
SEQ = LinearSegmentedColormap.from_list("hmv_seq", SEQ_STEPS)

# Diverging ramp (polarity) — warm/cool poles with a neutral midpoint.
DIV = LinearSegmentedColormap.from_list(
    "hmv_div", ["#0d366b", "#2a78d6", "#9ec5f4", "#f0efec", "#f2a09f", "#e34948", "#8c1f1f"])


def use_paper_style() -> None:
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "serif",
        "font.serif": ["DejaVu Serif"],
        "mathtext.fontset": "dejavuserif",
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 8,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": GRID,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "lines.linewidth": 1.8,
        "lines.markersize": 4.5,
        "figure.dpi": 140,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def despine(ax, left: bool = False, bottom: bool = False) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if left:
        ax.spines["left"].set_visible(False)
    if bottom:
        ax.spines["bottom"].set_visible(False)


def title(ax, text: str, subtitle: str | None = None) -> None:
    """Bold title with an optional muted deck line beneath it."""
    if subtitle:
        ax.set_title(text, color=INK, pad=20)
        ax.text(0.0, 1.012, subtitle, transform=ax.transAxes, fontsize=7.6,
                color=INK_3, va="bottom", ha="left")
    else:
        ax.set_title(text, color=INK)


def label_bar(ax, rects, fmt="{:.0f}", dy=1.0, color=INK_2, fontsize=7.5):
    for rect in rects:
        h = rect.get_height()
        ax.text(rect.get_x() + rect.get_width() / 2, h + dy, fmt.format(h),
                ha="center", va="bottom", fontsize=fontsize, color=color)
