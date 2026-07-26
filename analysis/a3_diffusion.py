"""Diffusion and depth: what feedback in the control path actually buys.

Two experiments, run against both stepping regimes.

*Diffusion.*  Change one plaintext letter and count how far the change travels.
An autonomous machine confines it to the position that changed; a machine whose
rotor bank is driven by the inter-stage tap propagates it forward at the rate a
fresh permutation would, 25/26 per position.

*Depth.*  Encrypt two different messages under one key and ask how long the two
state trajectories agree.  Autonomous stepping keeps them locked together for
the whole message -- this is exactly the depth that classical cryptanalysis
lives on.  Tap-driven stepping separates them at the first differing letter and
they do not come back.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "violet_core"))
sys.path.insert(0, os.path.dirname(__file__))

from violet import M, Mode, N, STRATEGIC, VioletMachine, state_space_bits  # noqa: E402
import corpus  # noqa: E402
import vizstyle as vs  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "figures")
DATA = os.path.join(os.path.dirname(__file__), "results")


def avalanche(mode: Mode, length: int, trials: int, seed: int) -> np.ndarray:
    """Fraction of ciphertext positions that change after a single-letter edit."""
    rng = np.random.default_rng(seed)
    changed = np.zeros(length)
    for trial in range(trials):
        machine = VioletMachine.canonical(STRATEGIC, mode=mode, key_seed=1000 + trial)
        plain = corpus.english_text(length, seed=seed + trial)
        base = machine.encrypt_indices(plain)
        edited = plain.copy()
        edited[0] = (edited[0] + 1 + rng.integers(0, N - 1)) % N
        alt = machine.encrypt_indices(edited)
        changed += (base != alt)
    return changed / trials


def depth_divergence(mode: Mode, length: int, trials: int, seed: int) -> np.ndarray:
    """Fraction of trials whose two state trajectories still agree at time t."""
    rng = np.random.default_rng(seed)
    agree = np.zeros(length)
    for trial in range(trials):
        machine = VioletMachine.canonical(STRATEGIC, mode=mode, key_seed=2000 + trial)
        a = corpus.english_text(length, seed=seed + 3 * trial)
        b = corpus.english_text(length, seed=seed + 3 * trial + 1)
        states_a, states_b = [], []
        for msg, store in ((a, states_a), (b, states_b)):
            machine.reset()
            for x in msg:
                store.append((machine.p.copy(), machine.q.copy()))
                machine.encrypt_symbol(int(x))
        for t in range(length):
            same = (np.array_equal(states_a[t][0], states_b[t][0])
                    and np.array_equal(states_a[t][1], states_b[t][1]))
            agree[t] += same
    return agree / trials


def main() -> None:
    vs.use_paper_style()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)

    length, trials = 200, 60
    av_open = avalanche(Mode.OPEN, length, trials, seed=17)
    av_closed = avalanche(Mode.CLOSED, length, trials, seed=17)
    dp_open = depth_divergence(Mode.OPEN, 120, 40, seed=31)
    dp_closed = depth_divergence(Mode.CLOSED, 120, 40, seed=31)

    # positional heat map of the closed-loop avalanche
    rng = np.random.default_rng(4)
    grid = np.zeros((24, 96))
    for i in range(24):
        machine = VioletMachine.canonical(STRATEGIC, mode=Mode.CLOSED, key_seed=3000 + i)
        plain = corpus.english_text(96, seed=800 + i)
        base = machine.encrypt_indices(plain)
        pos = i * 4
        edited = plain.copy()
        edited[pos] = (edited[pos] + 1 + rng.integers(0, N - 1)) % N
        grid[i] = (base != machine.encrypt_indices(edited)).astype(float)

    stats = {
        "avalanche_open_tail_mean": float(av_open[1:].mean()),
        "avalanche_closed_tail_mean": float(av_closed[1:].mean()),
        "avalanche_ideal": (N - 1) / N,
        "depth_open_final": float(dp_open[-1]),
        "depth_closed_final": float(dp_closed[-1]),
        "resync_bound_per_step": 1.0 / (N ** STRATEGIC["num_rotors"]),
        "state_bits_strategic": float(state_space_bits(14, 14)),
        "state_bits_field": float(state_space_bits(8, 8)),
    }
    with open(os.path.join(DATA, "diffusion.json"), "w") as fh:
        json.dump(stats, fh, indent=2)

    # ---------------------------------------------------------------- figure
    fig = plt.figure(figsize=(11.4, 3.3))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.05, 1.0, 1.15], wspace=0.32)

    ax = fig.add_subplot(gs[0, 0])
    t = np.arange(length)
    ax.plot(t, av_closed, color=vs.BLUE, label="tap-driven stepping")
    ax.plot(t, av_open, color=vs.ORANGE, label="autonomous stepping")
    ax.axhline((N - 1) / N, color=vs.INK_3, lw=0.9, ls="--")
    ax.text(length * 0.5, (N - 1) / N - 0.10, "$25/26$", ha="center",
            fontsize=7.5, color=vs.INK_3)
    ax.set_xlabel("position after the edited letter")
    ax.set_ylabel("probability the letter changes")
    ax.set_ylim(-0.04, 1.08)
    vs.title(ax, "a  Diffusion", "one changed letter, 60 keys")
    ax.legend(loc=(0.34, 0.42))
    vs.despine(ax)

    ax = fig.add_subplot(gs[0, 1])
    ax.plot(np.arange(120), dp_open, color=vs.ORANGE, label="autonomous stepping")
    ax.plot(np.arange(120), dp_closed, color=vs.BLUE, label="tap-driven stepping")
    ax.set_xlabel("letters processed")
    ax.set_ylabel("trajectories still in step")
    ax.set_ylim(-0.04, 1.08)
    vs.title(ax, "b  Depth", "two messages, one key")
    ax.legend(loc="center right")
    vs.despine(ax)

    ax = fig.add_subplot(gs[0, 2])
    im = ax.imshow(grid, aspect="auto", cmap=vs.SEQ, vmin=0, vmax=1,
                   interpolation="nearest")
    ax.set_xlabel("ciphertext position")
    ax.set_ylabel("edit position (every 4th)")
    ax.set_yticks(range(0, 24, 4))
    ax.set_yticklabels(range(0, 96, 16))
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, pad=0.02, fraction=0.045)
    cb.set_label("letter changed", fontsize=7.5)
    cb.outline.set_visible(False)
    vs.title(ax, "c  Where the change lands", "tap-driven stepping")

    fig.savefig(os.path.join(OUT, "fig_diffusion.pdf"))
    fig.savefig(os.path.join(OUT, "fig_diffusion.png"))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
