"""Redraw the key-recovery figure from stored results, with the scaling fit
restricted to the runs whose wall-clock time is dominated by the search rather
than by table construction."""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vizstyle as vs  # noqa: E402

OUT = os.path.join(HERE, "..", "figures")
DATA = os.path.join(HERE, "results")


def main() -> None:
    vs.use_paper_style()
    with open(os.path.join(DATA, "attack.json")) as fh:
        summary = json.load(fh)
    runs = summary["runs"]
    taps = np.array(summary["mean_distinct_taps"])

    states = np.array([r["states"] for r in runs], dtype=float)
    secs = np.array([r["seconds"] for r in runs], dtype=float)
    big = states >= 1e8
    slope, intercept = np.polyfit(np.log(states[big]), np.log(secs[big]), 1)
    summary["scaling_exponent"] = float(slope)
    summary["throughput_states_per_second"] = float(states[big].sum() / secs[big].sum())

    # per-letter filter strength, from the survivor curve of the largest run
    largest = max(runs, key=lambda r: r["states"])
    s = np.array(largest["survivors"], dtype=float)
    lo, hi = 8, 16
    per_letter = (s[hi] / s[lo]) ** (1.0 / (hi - lo))
    summary["filter_bits_per_letter"] = float(-np.log2(per_letter))

    fig, axes = plt.subplots(1, 3, figsize=(11.6, 3.25))

    ax = axes[0]
    order = np.argsort(states)
    ax.loglog(states[order], secs[order], marker="o", color=vs.BLUE, label="measured")
    grid = np.logspace(np.log10(states.min()), np.log10(states.max()), 50)
    ax.loglog(grid, np.exp(intercept) * grid ** slope, color=vs.ORANGE, ls="--",
              lw=1.2, label=f"fit on $|\\Omega|\\geq10^8$: exponent {slope:.2f}")
    ax.set_xlabel("$|\\Omega|$ — reachable states")
    ax.set_ylabel("wall-clock seconds (36 threads)")
    vs.title(ax, "a  The work factor is the state count",
             f"{summary['throughput_states_per_second']/1e6:.0f} M hypotheses/s")
    ax.legend(loc="upper left")
    vs.despine(ax)

    ax = axes[1]
    show = [(2, 2), (3, 3), (4, 4)]
    for (r_, k_), colour in zip(show, [vs.BLUE, vs.ORANGE, vs.AQUA]):
        run = next(x for x in runs if (x["r"], x["k"]) == (r_, k_))
        y = np.array(run["survivors"], dtype=float)
        ax.semilogy(np.arange(len(y)), np.maximum(y, 0.5), color=colour,
                    label=f"$r={r_},\\ k={k_}$  ({run['state_bits']:.0f} bits)")
    ax.axhline(1, color=vs.INK_3, lw=0.9, ls="--")
    ax.text(27.5, 1.6, "unique key", ha="right", fontsize=7.5, color=vs.INK_3)
    ax.set_xlabel("crib length (letters)")
    ax.set_ylabel("surviving hypotheses")
    ax.set_xlim(0, 28)
    ax.set_ylim(0.4, 1e12)
    vs.title(ax, "b  How much crib is needed",
             f"filter strength {summary['filter_bits_per_letter']:.1f} bits/letter")
    ax.legend(loc="upper right")
    vs.despine(ax)

    ax = axes[2]
    t = np.arange(1, len(taps) + 1)
    for r_, colour in zip([4, 8, 14], [vs.BLUE, vs.ORANGE, vs.AQUA]):
        ax.plot(t, (r_ - 1) * taps, color=colour, label=f"$r={r_}$ rotors")
    ax.set_xlabel("crib length (letters)")
    ax.set_ylabel("pin bits the attacker must resolve")
    vs.title(ax, "c  What feedback costs the attacker",
             "one fresh pin column per new tap symbol")
    ax.legend(loc="upper left")
    vs.despine(ax)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_attack.pdf"))
    fig.savefig(os.path.join(OUT, "fig_attack.png"))
    with open(os.path.join(DATA, "attack.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps({k: v for k, v in summary.items() if k != "runs"
                      and k != "mean_distinct_taps"}, indent=2))
    for run in runs:
        print(f"r={run['r']} k={run['k']}  bits={run['state_bits']:.1f}  "
              f"unicity={run['unicity_letters']}  t={run['seconds']:.2f}s")


if __name__ == "__main__":
    main()
