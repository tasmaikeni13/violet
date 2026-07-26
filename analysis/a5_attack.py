"""Key recovery against the cascade, measured.

The autonomous cascade is broken by enumerating its *state space*, not its key
space: a crib of a few dozen letters plus one pass over the reachable states
recovers the trajectory, and the plugboard falls out of the arithmetic.  This
script instantiates families of scaled machines, runs the search to completion
on each, and fits the two quantities the paper claims: the work factor (linear
in the state count) and the crib length at which a single hypothesis survives.

The same search is then pointed at the tap-driven machine, where the state at
time t is no longer a function of t, and the cost of the corresponding attack is
measured as a function of the pin entropy that must be guessed alongside it.
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import time

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "violet_core"))
sys.path.insert(0, os.path.dirname(__file__))

from violet import (M, Mode, N, VioletBuild, VioletKey, VioletMachine, compose,  # noqa: E402
                    displace, identity, invert, involution_from_pairs)
import corpus  # noqa: E402
import vizstyle as vs  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "figures")
DATA = os.path.join(HERE, "results")
BIN = os.path.join(HERE, "violet_attack")
SCRATCH = os.environ.get("VIOLET_SCRATCH", "/tmp")


def build_binary() -> None:
    src = os.path.join(HERE, "violet_attack.c")
    subprocess.run(["gcc", "-O3", "-march=native", "-fopenmp", "-o", BIN, src], check=True)


def stage_tables(build: VioletBuild, order, r: int, k: int):
    A, B = N ** r, M ** k
    rho = np.empty((A, N), dtype=np.int64)
    for c in range(A):
        out = identity(N)
        for i in range(r):
            out = compose(displace(build.rotor_chest[order[i]], (c // N ** i) % N), out)
        rho[c] = out
    sig = np.empty((B, N), dtype=np.int64)
    for c in range(B):
        out = identity(N)
        for j in range(k):
            out = compose(build.switch_banks[j][(c // M ** j) % M], out)
        sig[c] = out
    return rho, sig


def make_crib(rho, sig, plug, c0, d0, plain):
    t = np.arange(len(plain))
    A, B = len(rho), len(sig)
    return sig[(d0 + t) % B, rho[(c0 + t) % A, plug[plain]]]


def run_attack(r: int, k: int, crib_len: int, pairs: int, seed: int) -> dict:
    build = VioletMachine.build_hardware(chest=r + 2, num_switches=k, seed=0x5657)
    rng = np.random.default_rng(seed)
    order = list(range(r))
    rho, sig = stage_tables(build, order, r, k)
    rho_inv = np.stack([invert(p) for p in rho]).astype(np.uint8)
    sig_inv = np.stack([invert(p) for p in sig]).astype(np.uint8)

    letters = rng.permutation(N)[: 2 * pairs].reshape(pairs, 2)
    plug = involution_from_pairs([(int(a), int(b)) for a, b in letters])
    A, B = N ** r, M ** k
    c0, d0 = int(rng.integers(0, A)), int(rng.integers(0, B))
    plain = corpus.english_text(crib_len, seed=seed + 1)
    cipher = make_crib(rho, sig, plug, c0, d0, plain)

    spec = os.path.join(SCRATCH, f"violet_spec_{r}_{k}_{seed}.bin")
    res = os.path.join(SCRATCH, f"violet_res_{r}_{k}_{seed}.bin")
    with open(spec, "wb") as fh:
        fh.write(struct.pack("7i", N, r, k, A, B, crib_len, pairs))
        fh.write(rho_inv.tobytes())
        fh.write(sig_inv.tobytes())
        fh.write(plain.astype(np.uint8).tobytes())
        fh.write(cipher.astype(np.uint8).tobytes())
    proc = subprocess.run([BIN, spec, res], capture_output=True, text=True)
    with open(res, "rb") as fh:
        total = struct.unpack("q", fh.read(8))[0]
        elapsed = struct.unpack("d", fh.read(8))[0]
        hist = np.frombuffer(fh.read((crib_len + 1) * 8), dtype=np.int64)
    os.remove(spec)
    os.remove(res)
    survivors = np.cumsum(hist[::-1])[::-1]      # survivors[L] = candidates reaching L
    return {
        "r": r, "k": k, "states": int(total), "seconds": float(elapsed),
        "survivors": survivors.tolist(), "true_state": [c0, d0],
        "stderr": proc.stderr.strip(),
    }


def tap_entropy(r: int, k: int, crib_len: int, trials: int, seed: int) -> np.ndarray:
    """Distinct tap symbols seen in the first t letters of a tap-driven run.

    Each distinct tap symbol exposes one fresh column of the pin matrix, so the
    pin entropy an attacker must resolve alongside the state is (r-1) times this
    count.
    """
    counts = np.zeros((trials, crib_len))
    for trial in range(trials):
        cfg = dict(num_rotors=r, num_switches=k, chest=r + 2, plug_pairs=10)
        machine = VioletMachine.canonical(cfg, mode=Mode.CLOSED, key_seed=seed + trial)
        plain = corpus.english_text(crib_len, seed=seed + 500 + trial)
        machine.reset()
        seen = set()
        for t, x in enumerate(plain):
            tap = int(machine.rho()[machine.plug[int(x)]])
            seen.add(tap)
            counts[trial, t] = len(seen)
            machine.encrypt_symbol(int(x))
    return counts.mean(axis=0)


def main() -> None:
    vs.use_paper_style()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    build_binary()

    crib_len = 64
    configs = [(2, 2), (3, 2), (2, 3), (3, 3), (4, 3), (3, 4), (4, 4)]
    runs = [run_attack(r, k, crib_len, pairs=10, seed=1000 + 7 * i)
            for i, (r, k) in enumerate(configs)]
    for run in runs:
        print(f"r={run['r']} k={run['k']} |Omega|={run['states']:>12,} "
              f"t={run['seconds']:8.3f}s  survivors@L={run['survivors'][-1]}")

    # Where does the survivor count reach one?
    for run in runs:
        s = np.array(run["survivors"], dtype=float)
        idx = np.argmax(s <= 1)
        run["unicity_letters"] = int(idx) if s[idx] <= 1 else -1
        run["state_bits"] = float(np.log2(run["states"]))

    taps = tap_entropy(r=4, k=4, crib_len=48, trials=24, seed=77)

    summary = {
        "runs": runs,
        "threads": int(os.environ.get("OMP_NUM_THREADS", os.cpu_count() or 1)),
        "mean_distinct_taps": taps.tolist(),
        "english_redundancy_bits_per_letter": float(np.log2(26) - 1.5),
    }


    # ---------------------------------------------------------------- figure
    fig, axes = plt.subplots(1, 3, figsize=(11.6, 3.25))

    ax = axes[0]
    states = np.array([r_["states"] for r_ in runs], dtype=float)
    secs = np.array([r_["seconds"] for r_ in runs], dtype=float)
    ordering = np.argsort(states)
    ax.loglog(states[ordering], secs[ordering], marker="o", color=vs.BLUE,
              label="measured")
    big = states > 1e7
    slope, intercept = np.polyfit(np.log(states[big]), np.log(secs[big]), 1)
    grid = np.logspace(np.log10(states.min()), np.log10(states.max()), 50)
    ax.loglog(grid, np.exp(intercept) * grid ** slope, color=vs.ORANGE, ls="--",
              lw=1.2, label=f"fit, exponent {slope:.2f}")
    summary["scaling_exponent"] = float(slope)
    summary["throughput_states_per_second"] = float(states[big].sum() / secs[big].sum())
    ax.set_xlabel("$|\\Omega|$ — reachable states")
    ax.set_ylabel("wall-clock seconds (36 threads)")
    vs.title(ax, "a  The work factor is the state count",
             "exhaustive trajectory search")
    ax.legend(loc="upper left")
    vs.despine(ax)

    ax = axes[1]
    show = [(2, 2), (3, 2), (3, 3)]
    for (r_, k_), colour in zip(show, [vs.BLUE, vs.ORANGE, vs.AQUA]):
        run = next(x for x in runs if (x["r"], x["k"]) == (r_, k_))
        s = np.array(run["survivors"], dtype=float)
        ax.semilogy(np.arange(len(s)), np.maximum(s, 0.5), color=colour,
                    label=f"$r={r_},\\ k={k_}$  ({run['state_bits']:.0f} bits)")
    ax.axhline(1, color=vs.INK_3, lw=0.9, ls="--")
    ax.text(crib_len * 0.98, 1.35, "unique key", ha="right", fontsize=7.5,
            color=vs.INK_3)
    ax.set_xlabel("crib length (letters)")
    ax.set_ylabel("surviving hypotheses")
    ax.set_xlim(0, 42)
    vs.title(ax, "b  How much crib is needed", "plugboard never searched")
    ax.legend(loc="upper right")
    vs.despine(ax)

    ax = axes[2]
    t = np.arange(1, len(taps) + 1)
    for r_, colour in zip([4, 8, 14], [vs.BLUE, vs.ORANGE, vs.AQUA]):
        ax.plot(t, (r_ - 1) * taps, color=colour, label=f"$r={r_}$ rotors")
    ax.set_xlabel("crib length (letters)")
    ax.set_ylabel("pin bits the attacker must resolve")
    vs.title(ax, "c  What feedback costs the attacker",
             "fresh pin column per new tap symbol")
    ax.legend(loc="upper left")
    vs.despine(ax)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_attack.pdf"))
    fig.savefig(os.path.join(OUT, "fig_attack.png"))
    with open(os.path.join(DATA, "attack.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    for run in runs:
        print(f"r={run['r']} k={run['k']}  bits={run['state_bits']:.1f}  "
              f"unicity={run['unicity_letters']} letters  t={run['seconds']:.2f}s")


if __name__ == "__main__":
    main()
