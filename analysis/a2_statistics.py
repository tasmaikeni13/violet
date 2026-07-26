"""Ciphertext statistics: flattening, coincidence, and the transparency of the plugboard.

Three measurements.  First, how completely each machine erases the letter
statistics of English.  Second, how the index of coincidence of the ciphertext
converges to the uniform value with message length.  Third — the measurement
that matters for the security argument — that the index of coincidence of the
*reduced* stream, the stream an attacker forms by undoing a trajectory
hypothesis, identifies the correct trajectory without any knowledge of the
plugboard whatsoever.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "violet_core"))
sys.path.insert(0, os.path.dirname(__file__))

from violet import (M, Mode, N, STRATEGIC, VioletBuild, VioletKey, VioletMachine,  # noqa: E402
                    compose, identity, invert, involution_from_pairs)
import corpus  # noqa: E402
import vizstyle as vs  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "figures")
DATA = os.path.join(os.path.dirname(__file__), "results")


def reduced_stream_ic(r: int, k: int, length: int, trials: int, seed: int) -> dict:
    """Measure the coincidence index of the reduced stream for the true and for
    wrong trajectory hypotheses, under three different plugboards."""
    rng = np.random.default_rng(seed)
    build = VioletMachine.build_hardware(chest=r + 2, num_switches=k, seed=0x5657)
    rot_period, sw_period = N ** r, M ** k

    # Precompute the stage permutations at every counter value.
    def stage_tables(order):
        rho = np.empty((rot_period, N), dtype=np.int64)
        for c in range(rot_period):
            digits = [(c // N ** i) % N for i in range(r)]
            out = identity(N)
            for i, d in enumerate(digits):
                from violet import displace
                out = compose(displace(build.rotor_chest[order[i]], d), out)
            rho[c] = out
        sig = np.empty((sw_period, N), dtype=np.int64)
        for c in range(sw_period):
            digits = [(c // M ** j) % M for j in range(k)]
            out = identity(N)
            for j, d in enumerate(digits):
                out = compose(build.switch_banks[j][d], out)
            sig[c] = out
        return rho, sig

    order = list(range(r))
    rho, sig = stage_tables(order)
    rho_inv = np.stack([invert(p) for p in rho])
    sig_inv = np.stack([invert(p) for p in sig])

    plain = corpus.english_text(length, seed=seed)
    results = {"true": [], "wrong": [], "plugboards": []}
    for trial in range(trials):
        pairs = rng.permutation(N)[:20].reshape(10, 2)
        plug = involution_from_pairs([(int(a), int(b)) for a, b in pairs])
        c0 = int(rng.integers(0, rot_period))
        d0 = int(rng.integers(0, sw_period))
        t = np.arange(length)
        cipher = sig[(d0 + t) % sw_period, rho[(c0 + t) % rot_period, plug[plain]]]

        z_true = rho_inv[(c0 + t) % rot_period, sig_inv[(d0 + t) % sw_period, cipher]]
        results["true"].append(corpus.index_of_coincidence(z_true))
        for _ in range(6):
            c1 = int(rng.integers(0, rot_period))
            d1 = int(rng.integers(0, sw_period))
            if (c1, d1) == (c0, d0):
                continue
            z_bad = rho_inv[(c1 + t) % rot_period, sig_inv[(d1 + t) % sw_period, cipher]]
            results["wrong"].append(corpus.index_of_coincidence(z_bad))
        results["plugboards"].append(int(np.sum(plug != np.arange(N))))
    return results


def main() -> None:
    vs.use_paper_style()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)

    length = 20000
    plain = corpus.english_text(length, seed=5)
    machine = VioletMachine.canonical(STRATEGIC, mode=Mode.CLOSED, key_seed=21)
    cipher = machine.encrypt_indices(plain)
    machine_open = VioletMachine.canonical(STRATEGIC, mode=Mode.OPEN, key_seed=21)
    cipher_open = machine_open.encrypt_indices(plain)

    stats = {
        "plain_ic": corpus.index_of_coincidence(plain),
        "cipher_ic_closed": corpus.index_of_coincidence(cipher),
        "cipher_ic_open": corpus.index_of_coincidence(cipher_open),
        "uniform_ic": corpus.UNIFORM_IC,
        "plain_chi2": corpus.chi_square_uniform(plain),
        "cipher_chi2_closed": corpus.chi_square_uniform(cipher),
        "cipher_chi2_open": corpus.chi_square_uniform(cipher_open),
        "chi2_df": N - 1,
    }

    # convergence of IC with message length
    lengths = np.unique(np.round(np.logspace(1.7, np.log10(length), 26)).astype(int))
    ic_plain, ic_cipher = [], []
    for L in lengths:
        ic_plain.append(corpus.index_of_coincidence(plain[:L]))
        ic_cipher.append(corpus.index_of_coincidence(cipher[:L]))

    red = reduced_stream_ic(r=2, k=2, length=600, trials=40, seed=99)
    stats["reduced_true_ic_mean"] = float(np.mean(red["true"]))
    stats["reduced_wrong_ic_mean"] = float(np.mean(red["wrong"]))
    stats["reduced_separation_sigma"] = float(
        (np.mean(red["true"]) - np.mean(red["wrong"])) / np.std(red["wrong"]))

    with open(os.path.join(DATA, "statistics.json"), "w") as fh:
        json.dump(stats, fh, indent=2)

    # ---------------------------------------------------------------- figure
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.2))

    ax = axes[0]
    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    pf = np.bincount(plain, minlength=N) / len(plain)
    cf = np.bincount(cipher, minlength=N) / len(cipher)
    x = np.arange(N)
    ax.bar(x - 0.21, pf * 100, width=0.4, color=vs.BLUE, label="plaintext")
    ax.bar(x + 0.21, cf * 100, width=0.4, color=vs.ORANGE, label="Violet ciphertext")
    ax.axhline(100 / N, color=vs.INK_3, lw=0.9, ls="--")
    ax.set_xticks(x)
    ax.set_xticklabels(letters, fontsize=5.6)
    ax.set_ylabel("frequency (%)")
    vs.title(ax, "a  Frequency flattening",
             f"$\\chi^2$: {stats['plain_chi2']:.0f} $\\to$ {stats['cipher_chi2_closed']:.1f} "
             f"(25 d.f.)")
    ax.legend(loc="upper right")
    vs.despine(ax)

    ax = axes[1]
    ax.semilogx(lengths, ic_plain, marker="o", color=vs.BLUE, label="plaintext")
    ax.semilogx(lengths, ic_cipher, marker="s", color=vs.ORANGE, label="Violet ciphertext")
    ax.axhline(corpus.ENGLISH_IC, color=vs.BLUE, lw=0.9, ls=":")
    ax.axhline(corpus.UNIFORM_IC, color=vs.INK_3, lw=0.9, ls="--")
    ax.text(lengths[-1], corpus.UNIFORM_IC + 0.0015, "$1/26$", ha="right",
            fontsize=7.5, color=vs.INK_3)
    ax.set_xlabel("message length (letters)")
    ax.set_ylabel("index of coincidence")
    vs.title(ax, "b  Coincidence", "the cipher reaches the uniform value")
    ax.legend(loc="center right")
    vs.despine(ax)

    ax = axes[2]
    bins = np.linspace(0.030, 0.085, 44)
    ax.hist(red["wrong"], bins=bins, color=vs.ORANGE, alpha=0.85,
            label="wrong trajectory", density=True)
    ax.hist(red["true"], bins=bins, color=vs.BLUE, alpha=0.85,
            label="correct trajectory", density=True)
    ax.axvline(corpus.UNIFORM_IC, color=vs.INK_3, lw=0.9, ls="--")
    ax.set_xlabel("index of coincidence of the reduced stream")
    ax.set_ylabel("density")
    vs.title(ax, "c  The plugboard is invisible",
             f"separation {stats['reduced_separation_sigma']:.1f}$\\sigma$, "
             "any plugboard")
    ax.legend(loc="upper left")
    vs.despine(ax)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_statistics.pdf"))
    fig.savefig(os.path.join(OUT, "fig_statistics.png"))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
