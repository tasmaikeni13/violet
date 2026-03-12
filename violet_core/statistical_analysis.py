"""Statistical analysis and visualization utilities for the Violet cipher."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from violet_engine import ALPHABET, VioletMachine

DEFAULT_SEED = 42
PLOTS_DIR = Path(__file__).resolve().parent / "plots"
VIOLET = "#8B2FC9"
LAVENDER = "#B57BEE"
DEEP_VIOLET = "#3A0B52"
MIDNIGHT = "#16001F"
GOLD = "#D4AF37"
MINT = "#B8FFD0"

ENGLISH_FREQUENCIES = np.array(
    [
        8.167,
        1.492,
        2.782,
        4.253,
        12.702,
        2.228,
        2.015,
        6.094,
        6.966,
        0.153,
        0.772,
        4.025,
        2.406,
        6.749,
        7.507,
        1.929,
        0.095,
        5.987,
        6.327,
        9.056,
        2.758,
        0.978,
        2.360,
        0.150,
        1.974,
        0.074,
    ],
    dtype=float,
)
ENGLISH_FREQUENCIES /= ENGLISH_FREQUENCIES.sum()


def make_machine(seed: int = DEFAULT_SEED) -> VioletMachine:
    return VioletMachine.from_key(VioletMachine.generate_random_key(seed=seed))


def random_uniform_message(rng: np.random.Generator, length: int) -> str:
    return "".join(rng.choice(list(ALPHABET), size=length))


def random_english_message(rng: np.random.Generator, length: int) -> str:
    return "".join(rng.choice(list(ALPHABET), size=length, p=ENGLISH_FREQUENCIES))


def machine_key(machine: VioletMachine) -> Dict[str, object]:
    return {
        "rotors": [rotor.tolist() for rotor in machine.rotors],
        "rotor_positions": machine.initial_rotor_positions.copy(),
        "plugboard_pairs": [list(pair) for pair in machine.plugboard_pairs],
        "switch_wirings": [[permutation.tolist() for permutation in switch] for switch in machine.switch_wirings],
        "switch_positions": machine.initial_switch_positions.copy(),
    }


def save_figure(name: str) -> Path:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    return PLOTS_DIR / name


def plot_fixed_point_distribution(n_samples: int = 10000, seed: int = DEFAULT_SEED) -> Path:
    rng = np.random.default_rng(seed)
    machine = make_machine(seed)
    identity = np.arange(26, dtype=np.int16)
    samples = np.empty(n_samples, dtype=np.int16)
    for index in range(n_samples):
        machine.rotor_positions = rng.integers(0, 26, size=machine.rotor_count).tolist()
        machine.switch_positions = rng.integers(0, 25, size=machine.switch_count).tolist()
        samples[index] = int(np.sum(machine.get_state()["E_t"] == identity))

    empirical = np.array([(samples == j).mean() for j in range(4)] + [(samples >= 4).mean()])
    theoretical = np.array(
        [math.exp(-1), math.exp(-1), math.exp(-1) / 2, math.exp(-1) / 6, 1 - math.exp(-1) * (1 + 1 + 0.5 + 1 / 6)],
        dtype=float,
    )
    labels = ["0", "1", "2", "3", "4+"]
    positions = np.arange(len(labels))

    plt.style.use("dark_background")
    fig, axis = plt.subplots(figsize=(9, 5), facecolor=MIDNIGHT)
    axis.set_facecolor(MIDNIGHT)
    axis.bar(positions - 0.18, empirical, width=0.36, color=VIOLET, label="Empirical")
    axis.bar(positions + 0.18, theoretical, width=0.36, color=LAVENDER, label="Poisson(1)")
    axis.set_title("Violet Fixed-Point Distribution", color="white", fontsize=14)
    axis.set_xlabel("Number of Fixed Points", color="white")
    axis.set_ylabel("Probability", color="white")
    axis.set_xticks(positions, labels)
    axis.grid(axis="y", alpha=0.25, color="#FFFFFF")
    axis.legend(frameon=False)

    output = save_figure("fixed_point_distribution.png")
    fig.tight_layout()
    fig.savefig(output, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return output


def plot_letter_frequency(message_length: int = 5000, seed: int = DEFAULT_SEED) -> Path:
    rng = np.random.default_rng(seed)
    machine = make_machine(seed)
    plaintext = random_english_message(rng, message_length)
    ciphertext = machine.encrypt(plaintext)
    ciphertext_frequency = np.array([ciphertext.count(letter) for letter in ALPHABET], dtype=float) / message_length

    positions = np.arange(len(ALPHABET))
    fig, axis = plt.subplots(figsize=(12, 5), facecolor=MIDNIGHT)
    axis.set_facecolor(MIDNIGHT)
    axis.bar(positions - 0.2, ENGLISH_FREQUENCIES, width=0.38, color=GOLD, label="English input")
    axis.bar(positions + 0.2, ciphertext_frequency, width=0.38, color=VIOLET, label="Violet ciphertext")
    axis.set_title("Letter Frequency Flattening Under Violet", color="white", fontsize=14)
    axis.set_xlabel("Letter", color="white")
    axis.set_ylabel("Relative Frequency", color="white")
    axis.set_xticks(positions, list(ALPHABET))
    axis.grid(axis="y", alpha=0.25, color="#FFFFFF")
    axis.legend(frameon=False)

    output = save_figure("letter_frequency.png")
    fig.tight_layout()
    fig.savefig(output, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return output


def plot_diffusion_heatmap(n_samples: int = 400, seed: int = DEFAULT_SEED) -> Path:
    rng = np.random.default_rng(seed)
    base_machine = make_machine(seed)
    base_key = machine_key(base_machine)
    perturbations: List[Tuple[str, str, int]] = []
    for index in range(len(base_key["rotor_positions"])):
        perturbations.append((f"Rotor {index + 1}", "rotor_positions", index))
    for index in range(len(base_key["switch_positions"])):
        perturbations.append((f"Switch {index + 1}", "switch_positions", index))

    matrix = np.zeros((len(perturbations), 26), dtype=float)
    letters = list(ALPHABET)
    for row, (_, bucket, index) in enumerate(perturbations):
        mutated_key = machine_key(base_machine)
        modulus = 26 if bucket == "rotor_positions" else 25
        mutated_key[bucket][index] = (mutated_key[bucket][index] + 1) % modulus
        mutated_machine = VioletMachine.from_key(mutated_key)

        changes = np.zeros(26, dtype=float)
        trials = np.zeros(26, dtype=float)
        for _ in range(n_samples):
            base_machine.rotor_positions = rng.integers(0, 26, size=base_machine.rotor_count).tolist()
            base_machine.switch_positions = rng.integers(0, 25, size=base_machine.switch_count).tolist()
            mutated_machine.rotor_positions = base_machine.rotor_positions.copy()
            mutated_machine.switch_positions = base_machine.switch_positions.copy()
            baseline = base_machine.get_state()["E_t"]
            perturbed = mutated_machine.get_state()["E_t"]
            for column, letter in enumerate(letters):
                plaintext_index = ord(letter) - ord("A")
                trials[column] += 1
                changes[column] += float(baseline[plaintext_index] != perturbed[plaintext_index])
        matrix[row] = np.divide(changes, trials, out=np.zeros_like(changes), where=trials > 0)

    fig, axis = plt.subplots(figsize=(13, 6), facecolor=MIDNIGHT)
    axis.set_facecolor(MIDNIGHT)
    image = axis.imshow(matrix, cmap="magma", aspect="auto", vmin=0.0, vmax=1.0)
    axis.set_title("Avalanche Heatmap: Output Change Probability", color="white", fontsize=14)
    axis.set_xlabel("Plaintext Letter", color="white")
    axis.set_ylabel("Key Perturbation", color="white")
    axis.set_xticks(np.arange(26), list(ALPHABET))
    axis.set_yticks(np.arange(len(perturbations)), [label for label, _, _ in perturbations])
    colorbar = fig.colorbar(image, ax=axis)
    colorbar.set_label("Probability of Output Change", color="white")
    colorbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(colorbar.ax.get_yticklabels(), color="white")

    output = save_figure("diffusion_heatmap.png")
    fig.tight_layout()
    fig.savefig(output, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return output


def plot_period_comparison() -> Path:
    labels = ["Purple", "Enigma", "Violet"]
    periods = np.array([15_625, 16_900, (26**5) * (25**6)], dtype=float)
    colors = ["#7F5AF0", GOLD, VIOLET]

    fig, axis = plt.subplots(figsize=(10, 4.5), facecolor=MIDNIGHT)
    axis.set_facecolor(MIDNIGHT)
    axis.barh(labels, periods, color=colors)
    axis.set_xscale("log")
    axis.set_title("Period Comparison of Classical Cipher Machines", color="white", fontsize=14)
    axis.set_xlabel("Period (log scale)", color="white")
    axis.grid(axis="x", which="both", alpha=0.25, color="#FFFFFF")

    output = save_figure("period_comparison.png")
    fig.tight_layout()
    fig.savefig(output, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return output


def plot_keyspace_comparison() -> Path:
    labels = ["Purple", "Enigma", "Violet"]
    entropies = np.array([60, 77, 111.1786], dtype=float)
    colors = ["#4CC9F0", GOLD, VIOLET]

    fig, axis = plt.subplots(figsize=(10, 4.5), facecolor=MIDNIGHT)
    axis.set_facecolor(MIDNIGHT)
    axis.bar(labels, entropies, color=colors, width=0.55)
    axis.set_yscale("log")
    axis.set_title("Operational Key Entropy Comparison", color="white", fontsize=14)
    axis.set_ylabel("Bits (log scale)", color="white")
    axis.grid(axis="y", which="both", alpha=0.25, color="#FFFFFF")

    output = save_figure("keyspace_comparison.png")
    fig.tight_layout()
    fig.savefig(output, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return output


def plot_index_of_coincidence(seed: int = DEFAULT_SEED) -> Path:
    rng = np.random.default_rng(seed)
    machine = make_machine(seed)
    lengths = np.arange(100, 5001, 100)
    ic_values = []
    for length in lengths:
        plaintext = random_english_message(rng, int(length))
        ciphertext = machine.encrypt(plaintext)
        counts = np.array([ciphertext.count(letter) for letter in ALPHABET], dtype=float)
        ic = np.sum(counts * (counts - 1)) / (length * (length - 1))
        ic_values.append(ic)

    fig, axis = plt.subplots(figsize=(10, 5), facecolor=MIDNIGHT)
    axis.set_facecolor(MIDNIGHT)
    axis.plot(lengths, ic_values, color=VIOLET, linewidth=2.5, label="Violet ciphertext IC")
    axis.axhline(1 / 26, color=MINT, linestyle="--", linewidth=1.5, label="Random baseline (1/26)")
    axis.axhline(0.065, color=GOLD, linestyle=":", linewidth=1.5, label="English baseline")
    axis.set_title("Index of Coincidence Convergence", color="white", fontsize=14)
    axis.set_xlabel("Message Length", color="white")
    axis.set_ylabel("Index of Coincidence", color="white")
    axis.grid(alpha=0.25, color="#FFFFFF")
    axis.legend(frameon=False)

    output = save_figure("index_of_coincidence.png")
    fig.tight_layout()
    fig.savefig(output, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return output


def main() -> None:
    outputs = [
        plot_fixed_point_distribution(),
        plot_letter_frequency(),
        plot_diffusion_heatmap(),
        plot_period_comparison(),
        plot_keyspace_comparison(),
        plot_index_of_coincidence(),
    ]
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
