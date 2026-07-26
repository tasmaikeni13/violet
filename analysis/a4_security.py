"""Security accounting: advertised key material against the work factor that survives it.

Electromechanical ciphers were sold on the size of their key space.  The
quantity that decides them is the size of the set of states a message can drive
the machine through, because a known-plaintext adversary enumerates states, not
keys, and reads the static layers off afterwards.  This script tabulates both
numbers for the historical machines and for the two Violet configurations, and
renders the accounting that turns one into the other.
"""

from __future__ import annotations

import json
import os
import sys
from math import comb, factorial, lgamma, log, log2, log10

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "violet_core"))
sys.path.insert(0, os.path.dirname(__file__))

from violet import M, N, state_space_bits  # noqa: E402
import vizstyle as vs  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "figures")
DATA = os.path.join(os.path.dirname(__file__), "results")


def plugboard_bits(pairs: int, n: int = N) -> float:
    """log2 of the number of involutions of `n` points with `pairs` transpositions."""
    return (lgamma(n + 1) - lgamma(n - 2 * pairs + 1) - lgamma(pairs + 1)
            - pairs * log(2)) / log(2)


def ordered_choice_bits(chest: int, take: int) -> float:
    return float(sum(log2(chest - i) for i in range(take)))


MACHINES = [
    # name, advertised key bits, reachable-state bits, period (letters), colour slot
    dict(name="Enigma M3",
         nominal=ordered_choice_bits(5, 3) + 3 * log2(26) + 2 * log2(26) + plugboard_bits(10),
         states=ordered_choice_bits(5, 3) + 3 * log2(26),
         period=26 * 25 * 26),
    dict(name="Purple",
         nominal=log2(factorial(26)) / 2 + 4 * log2(25) + log2(comb(26, 6)),
         states=4 * log2(25),
         period=25 ** 4),
    dict(name="SIGABA",
         nominal=95.0,
         states=5 * log2(26) + 5 * log2(26) + log2(factorial(10) // factorial(5)),
         period=26 ** 5),
    dict(name="Violet 8/8",
         nominal=ordered_choice_bits(12, 8) + state_space_bits(8, 8) + plugboard_bits(10) + 7 * 26,
         states=state_space_bits(8, 8),
         period=650 ** 8),
    dict(name="Violet 14/14",
         nominal=ordered_choice_bits(18, 14) + state_space_bits(14, 14) + plugboard_bits(10) + 13 * 26,
         states=state_space_bits(14, 14),
         period=650 ** 14),
]


def main() -> None:
    vs.use_paper_style()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)

    for mach in MACHINES:
        mach["log10_period"] = float(log10(mach["period"]))
        mach["years_at_100cpm"] = float(mach["period"]) / (100 * 60 * 24 * 365.25)

    # Accounting for the canonical Violet: which key material survives the attack.
    accounting = [
        ("rotor selection\nand order", ordered_choice_bits(18, 14), True),
        ("rotor positions", 14 * log2(26), True),
        ("switch positions", 14 * log2(25), True),
        ("pin rings", 13 * 26, True),
        ("plugboard", plugboard_bits(10), False),
    ]
    summary = {
        "machines": [{k: (float(v) if isinstance(v,(int,float)) and k=="period" else v) for k,v in m.items()} for m in MACHINES],
        "accounting": [(n, float(b), bool(c)) for n, b, c in accounting],
        "violet_effective_floor_bits": float(state_space_bits(14, 14)),
        "violet_field_floor_bits": float(state_space_bits(8, 8)),
        "plugboard_bits": float(plugboard_bits(10)),
        "unicity_distance_letters": float(state_space_bits(14, 14) / (log2(26) - 1.5)),
    }
    with open(os.path.join(DATA, "security.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    # ---------------------------------------------------------------- figure
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 3.4))

    ax = axes[0]
    names = [m["name"] for m in MACHINES]
    nominal = [m["nominal"] for m in MACHINES]
    states = [m["states"] for m in MACHINES]
    xpos = np.arange(len(names))
    b1 = ax.bar(xpos - 0.2, nominal, width=0.38, color=vs.ORANGE, label="advertised key")
    b2 = ax.bar(xpos + 0.2, states, width=0.38, color=vs.BLUE, label="reachable states")
    ax.set_xticks(xpos)
    ax.set_xticklabels(names, fontsize=7.2, rotation=18, ha="right")
    ax.set_ylabel("bits")
    ax.set_ylim(0, 620)
    vs.label_bar(ax, b1, fmt="{:.0f}", dy=8)
    vs.label_bar(ax, b2, fmt="{:.0f}", dy=8)
    vs.title(ax, "a  Two different numbers",
             "the second one is the work factor")
    ax.legend(loc="upper left")
    vs.despine(ax)

    ax = axes[1]
    log10p = [m["log10_period"] for m in MACHINES]
    cols = [vs.ORANGE, vs.ORANGE, vs.ORANGE, vs.BLUE, vs.BLUE]
    bars = ax.barh(xpos, log10p, color=cols, height=0.6)
    ax.set_yticks(xpos)
    ax.set_yticklabels(names, fontsize=7.6)
    ax.invert_yaxis()
    ax.set_xlabel("$\\log_{10}$ period (letters before the state repeats)")
    ax.set_xlim(0, 46)
    for rect, v in zip(bars, log10p):
        ax.text(v + 0.7, rect.get_y() + rect.get_height() / 2, f"$10^{{{v:.1f}}}$",
                va="center", fontsize=7.5, color=vs.INK_2)
    vs.title(ax, "b  Period", "coprime moduli multiply, they do not collide")
    vs.despine(ax, left=True)
    ax.grid(axis="y", visible=False)

    ax = axes[2]
    labels = [a[0] for a in accounting]
    vals = [a[1] for a in accounting]
    counts = [a[2] for a in accounting]
    cols = [vs.BLUE if c else vs.ORANGE for c in counts]
    bars = ax.bar(range(len(labels)), vals, color=cols, width=0.62)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=6.6, rotation=20, ha="right")
    ax.set_ylabel("bits of key material")
    ax.set_ylim(0, 460)
    for rect, v, c in zip(bars, vals, counts):
        ax.text(rect.get_x() + rect.get_width() / 2, v + 7,
                f"{v:.0f}" + ("" if c else "  (inert)"), ha="center",
                fontsize=7.2, color=vs.INK_2 if c else vs.ORANGE)
    handles = [plt.Rectangle((0, 0), 1, 1, color=vs.BLUE),
               plt.Rectangle((0, 0), 1, 1, color=vs.ORANGE)]
    ax.legend(handles, ["affects the trajectory", "static boundary layer"],
              loc="upper left")
    vs.title(ax, "c  Where the key goes", "Violet 14/14")
    vs.despine(ax)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_security.pdf"))
    fig.savefig(os.path.join(OUT, "fig_security.png"))
    print(json.dumps(summary, indent=2)[:1800])


if __name__ == "__main__":
    main()
