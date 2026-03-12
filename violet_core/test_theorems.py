"""Empirical validation suite for the Violet cipher machine.

Run directly with:

    python violet_core/test_theorems.py
"""

from __future__ import annotations

import copy
import math
import time
from collections import Counter
from typing import Callable, Dict, Iterable, List, Sequence

import numpy as np
from scipy.stats import chisquare

from violet_engine import ALPHABET, VioletMachine

DEFAULT_SEED = 42
IDENTITY = np.arange(26, dtype=np.int16)


def make_machine(seed: int = DEFAULT_SEED) -> VioletMachine:
    """Create a reproducible canonical Violet machine."""

    return VioletMachine.from_key(VioletMachine.generate_random_key(seed=seed))


def machine_to_key(machine: VioletMachine) -> Dict[str, object]:
    """Serialize a live machine back into a key dictionary."""

    return {
        "rotors": [rotor.tolist() for rotor in machine.rotors],
        "rotor_positions": machine.initial_rotor_positions.copy(),
        "plugboard_pairs": [list(pair) for pair in machine.plugboard_pairs],
        "switch_wirings": [[permutation.tolist() for permutation in switch] for switch in machine.switch_wirings],
        "switch_positions": machine.initial_switch_positions.copy(),
    }


def deep_copy_key(key: Dict[str, object]) -> Dict[str, object]:
    return copy.deepcopy(key)


def set_random_state(machine: VioletMachine, rng: np.random.Generator) -> None:
    machine.rotor_positions = rng.integers(0, 26, size=machine.rotor_count).tolist()
    machine.switch_positions = rng.integers(0, 25, size=machine.switch_count).tolist()


def permutation_at_random_state(machine: VioletMachine, rng: np.random.Generator) -> np.ndarray:
    set_random_state(machine, rng)
    return machine.get_state()["E_t"]


def state_signature(machine: VioletMachine) -> tuple:
    return tuple(machine.rotor_positions), tuple(machine.switch_positions)


def proper_divisors(value: int) -> List[int]:
    divisors = set()
    for candidate in range(1, int(math.isqrt(value)) + 1):
        if value % candidate == 0:
            divisors.add(candidate)
            divisors.add(value // candidate)
    divisors.discard(value)
    return sorted(divisors)


def random_message(rng: np.random.Generator, length: int) -> str:
    return "".join(rng.choice(list(ALPHABET), size=length))


def hamming_distance(left: str, right: str) -> int:
    return sum(a != b for a, b in zip(left, right))


def format_report(result: Dict[str, object]) -> str:
    evidence = result["evidence"]
    if not evidence:
        return "-"
    parts = []
    for key, value in evidence.items():
        if isinstance(value, float):
            parts.append(f"{key}={value:.4f}")
        else:
            parts.append(f"{key}={value}")
    return "; ".join(parts)


def test_theorem_9_1_closure(machine: VioletMachine, n_trials: int = 500) -> Dict[str, object]:
    """Theorem 9.1: every E_t is a permutation in S_26."""

    rng = np.random.default_rng(DEFAULT_SEED)
    valid = 0
    for _ in range(n_trials):
        permutation = permutation_at_random_state(machine, rng)
        is_bijection = np.array_equal(np.sort(permutation), IDENTITY)
        if is_bijection and len(set(permutation.tolist())) == 26:
            valid += 1

    closure_rate = valid / n_trials
    return {
        "theorem": "Theorem 9.1 Closure",
        "passed": valid == n_trials,
        "details": f"Closure held for {valid}/{n_trials} sampled machine states.",
        "evidence": {"closure_rate": closure_rate, "trials": n_trials},
    }


def test_theorem_9_2_non_reciprocity(machine: VioletMachine, n_trials: int = 500) -> Dict[str, object]:
    """Theorem 9.2: the cipher is generically non-involutory."""

    rng = np.random.default_rng(DEFAULT_SEED)
    non_involutions = 0
    fixed_point_steps = 0
    for _ in range(n_trials):
        permutation = permutation_at_random_state(machine, rng)
        if not np.array_equal(permutation[permutation], IDENTITY):
            non_involutions += 1
        if np.any(permutation == IDENTITY):
            fixed_point_steps += 1

    non_involution_rate = non_involutions / n_trials
    fixed_point_step_rate = fixed_point_steps / n_trials
    return {
        "theorem": "Theorem 9.2 Non-Reciprocity",
        "passed": non_involution_rate > 0.95,
        "details": (
            f"Observed non-involution on {non_involutions}/{n_trials} sampled states; "
            f"fixed points appeared on {fixed_point_steps}/{n_trials} states."
        ),
        "evidence": {
            "non_involution_rate": non_involution_rate,
            "fixed_point_step_rate": fixed_point_step_rate,
        },
    }


def test_theorem_9_3_corollary(machine: VioletMachine, n_trials: int = 1000) -> Dict[str, object]:
    """Corollary 9.3: Violet can encrypt a letter to itself."""

    rng = np.random.default_rng(DEFAULT_SEED)
    histogram = Counter({letter: 0 for letter in ALPHABET})
    observed = 0
    for _ in range(n_trials):
        permutation = permutation_at_random_state(machine, rng)
        fixed_points = np.where(permutation == IDENTITY)[0]
        if fixed_points.size:
            observed += 1
        for index in fixed_points:
            histogram[ALPHABET[int(index)]] += 1

    return {
        "theorem": "Corollary 9.3 Self-Encryption",
        "passed": observed > 0,
        "details": f"Observed self-encryption on {observed}/{n_trials} sampled states.",
        "evidence": {
            "states_with_self_encryption": observed,
            "top_letters": dict(histogram.most_common(5)),
        },
    }


def test_theorem_9_4_fixed_point_distribution(machine: VioletMachine, n_samples: int = 10000) -> Dict[str, object]:
    """Theorem 9.4: fixed-point counts approximate Poisson(1)."""

    rng = np.random.default_rng(DEFAULT_SEED)
    samples = np.empty(n_samples, dtype=np.int16)
    for index in range(n_samples):
        permutation = permutation_at_random_state(machine, rng)
        samples[index] = int(np.sum(permutation == IDENTITY))

    empirical_mean = float(samples.mean())
    empirical_variance = float(samples.var())

    observed = np.array([(samples == j).sum() for j in range(4)] + [(samples >= 4).sum()], dtype=float)
    poisson_mass = np.array(
        [math.exp(-1), math.exp(-1), math.exp(-1) / 2, math.exp(-1) / 6],
        dtype=float,
    )
    poisson_mass = np.append(poisson_mass, 1.0 - poisson_mass.sum())
    expected = poisson_mass * n_samples
    chi2 = chisquare(observed, expected)

    pmf = {f"P(X={j})": float((samples == j).mean()) for j in range(5)}
    result = {
        "theorem": "Theorem 9.4 Fixed Point Distribution",
        "passed": abs(empirical_mean - 1.0) < 0.12 and abs(empirical_variance - 1.0) < 0.15 and chi2.pvalue > 0.05,
        "details": (
            f"Empirical mean={empirical_mean:.4f}, variance={empirical_variance:.4f}, "
            f"chi-squared p-value={chi2.pvalue:.4f}."
        ),
        "evidence": {
            "mean": empirical_mean,
            "variance": empirical_variance,
            "chi2_pvalue": float(chi2.pvalue),
            **pmf,
        },
    }
    return result


def test_theorem_9_5_period(machine: VioletMachine, r: int = 2, k: int = 2) -> Dict[str, object]:
    """Theorem 9.5: the machine period is 26^r * 25^k for reduced parameters."""

    base_key = machine_to_key(machine)
    reduced_key = {
        "rotors": base_key["rotors"][:r],
        "rotor_positions": base_key["rotor_positions"][:r],
        "plugboard_pairs": base_key["plugboard_pairs"],
        "switch_wirings": base_key["switch_wirings"][:k],
        "switch_positions": base_key["switch_positions"][:k],
    }
    reduced_machine = VioletMachine.from_key(reduced_key)

    period = (26**r) * (25**k)
    divisors = set(proper_divisors(period))
    initial_signature = state_signature(reduced_machine)
    premature_cycle = None
    start = time.perf_counter()

    for step in range(1, period + 1):
        reduced_machine._step_rotors()
        reduced_machine._step_switches()
        signature = state_signature(reduced_machine)
        if step in divisors and signature == initial_signature:
            premature_cycle = step
            break

    runtime_seconds = time.perf_counter() - start
    final_signature = state_signature(reduced_machine)
    passed = premature_cycle is None and final_signature == initial_signature
    return {
        "theorem": "Theorem 9.5 Machine Period",
        "passed": passed,
        "details": (
            f"Reduced machine returned to its initial state after {period} steps; "
            f"premature cycle={premature_cycle}."
        ),
        "evidence": {
            "confirmed_period": period,
            "premature_cycle": premature_cycle,
            "runtime_seconds": runtime_seconds,
        },
    }


def test_theorem_9_6_temporal_diffusion(machine: VioletMachine, n_trials: int = 200) -> Dict[str, object]:
    """Theorem 9.6: ciphertext depends on all initial-state components."""

    rng = np.random.default_rng(DEFAULT_SEED)
    base_key = machine_to_key(machine)
    distances: Dict[str, List[float]] = {f"rotor_{index + 1}": [] for index in range(machine.rotor_count)}
    distances.update({f"switch_{index + 1}": [] for index in range(machine.switch_count)})

    for _ in range(n_trials):
        message = random_message(rng, 64)
        baseline = VioletMachine.from_key(base_key).encrypt(message)

        for index in range(machine.rotor_count):
            mutated_key = deep_copy_key(base_key)
            mutated_key["rotor_positions"][index] = (mutated_key["rotor_positions"][index] + 1) % 26
            candidate = VioletMachine.from_key(mutated_key).encrypt(message)
            distances[f"rotor_{index + 1}"].append(hamming_distance(baseline, candidate) / len(baseline))

        for index in range(machine.switch_count):
            mutated_key = deep_copy_key(base_key)
            mutated_key["switch_positions"][index] = (mutated_key["switch_positions"][index] + 1) % 25
            candidate = VioletMachine.from_key(mutated_key).encrypt(message)
            distances[f"switch_{index + 1}"].append(hamming_distance(baseline, candidate) / len(baseline))

    averages = {key: float(np.mean(values)) for key, values in distances.items()}
    grand_average = float(np.mean(list(averages.values())))
    return {
        "theorem": "Theorem 9.6 Temporal Diffusion",
        "passed": all(value > 0.45 for value in averages.values()),
        "details": f"Single-component perturbations changed {grand_average:.2%} of ciphertext symbols on average.",
        "evidence": {"average_hamming_ratio": grand_average, **averages},
    }


def test_theorem_9_7_statistical_mixing(machine: VioletMachine, message_length: int = 5000) -> Dict[str, object]:
    """Theorem 9.7: long ciphertexts approach uniform output statistics."""

    rng = np.random.default_rng(DEFAULT_SEED)
    plaintext = random_message(rng, message_length)
    ciphertext = machine.encrypt(plaintext)
    counts = np.array([ciphertext.count(letter) for letter in ALPHABET], dtype=float)
    ic = float(np.sum(counts * (counts - 1)) / (message_length * (message_length - 1)))
    expected = np.full(26, message_length / 26, dtype=float)
    chi2 = chisquare(counts, expected)
    return {
        "theorem": "Theorem 9.7 Statistical Mixing",
        "passed": 0.034 <= ic <= 0.043 and chi2.pvalue > 0.05,
        "details": f"Ciphertext IC={ic:.5f}; chi-squared p-value={chi2.pvalue:.4f} against uniform output.",
        "evidence": {"IC": ic, "chi2_pvalue": float(chi2.pvalue)},
    }


def test_period_theorem_proposition_10_1() -> Dict[str, object]:
    """Proposition 10.1: coprime periods multiply exactly."""

    rotor_period = 26**5
    switch_period = 25**6
    gcd_value = math.gcd(rotor_period, switch_period)
    lcm_value = math.lcm(rotor_period, switch_period)
    all_coprime = all(math.gcd(26**r, 25**k) == 1 for r in range(1, 11) for k in range(1, 11))
    return {
        "theorem": "Proposition 10.1 Coprimality",
        "passed": gcd_value == 1 and lcm_value == rotor_period * switch_period and all_coprime,
        "details": "Verified GCD and LCM identities for canonical and reduced exponent ranges.",
        "evidence": {"gcd": gcd_value, "lcm_equals_product": lcm_value == rotor_period * switch_period},
    }


def test_keyspace_theorem_11_1() -> Dict[str, object]:
    """Theorem 11.1: validate the closed-form keyspace formula."""

    n, r, m, k = 8, 5, 10, 6
    n_order = math.factorial(n) // math.factorial(n - r)
    n_pos = 26**r
    n_plug = math.factorial(26) // (math.factorial(26 - 2 * m) * (2**m) * math.factorial(m))
    n_switch = 25**k
    total = n_order * n_pos * n_plug * n_switch
    entropy_bits = math.log2(total)

    return {
        "theorem": "Theorem 11.1 Keyspace",
        "passed": (
            n_order == 6720
            and n_pos == 11_881_376
            and n_plug == 150_738_274_937_250
            and n_switch == 244_140_625
            and entropy_bits > 111.0
        ),
        "details": f"Computed total keyspace={total} with entropy={entropy_bits:.4f} bits.",
        "evidence": {
            "N_order": n_order,
            "N_pos": n_pos,
            "N_plug": n_plug,
            "N_switch": n_switch,
            "entropy_bits": entropy_bits,
            "enigma_bits": 77,
            "purple_bits": 60,
        },
    }


def test_encrypt_decrypt_roundtrip(machine: VioletMachine, n_trials: int = 100) -> Dict[str, object]:
    """Core correctness test: encrypt then decrypt recovers the plaintext."""

    rng = np.random.default_rng(DEFAULT_SEED)
    successes = 0
    alphabet_with_noise = list(ALPHABET) + [" ", "-", "?", ".", "1"]
    for _ in range(n_trials):
        length = int(rng.integers(10, 101))
        message = "".join(rng.choice(alphabet_with_noise, size=length))
        normalized = "".join(character for character in message.upper() if character.isalpha())
        ciphertext = machine.encrypt(message)
        recovered = machine.decrypt(ciphertext)
        if recovered == normalized:
            successes += 1

    return {
        "theorem": "Core Roundtrip Correctness",
        "passed": successes == n_trials,
        "details": f"Recovered the exact normalized plaintext in {successes}/{n_trials} trials.",
        "evidence": {"roundtrip_rate": successes / n_trials, "trials": n_trials},
    }


def run_all_tests() -> List[Dict[str, object]]:
    """Run the full theorem validation suite and print a formatted summary table."""

    machine = make_machine()
    tests: List[Callable[..., Dict[str, object]]] = [
        test_encrypt_decrypt_roundtrip,
        test_theorem_9_1_closure,
        test_theorem_9_2_non_reciprocity,
        test_theorem_9_3_corollary,
        test_theorem_9_4_fixed_point_distribution,
        test_theorem_9_5_period,
        test_theorem_9_6_temporal_diffusion,
        test_theorem_9_7_statistical_mixing,
        test_period_theorem_proposition_10_1,
        test_keyspace_theorem_11_1,
    ]

    results: List[Dict[str, object]] = []
    for test in tests:
        start = time.perf_counter()
        if test in {test_period_theorem_proposition_10_1, test_keyspace_theorem_11_1}:
            result = test()
        else:
            result = test(machine)
        result["runtime_seconds"] = time.perf_counter() - start
        results.append(result)

    header = ["Test", "Status", "Key Metrics", "Runtime (s)"]
    rows = [
        [
            result["theorem"],
            "PASS" if result["passed"] else "FAIL",
            format_report(result),
            f"{result['runtime_seconds']:.3f}",
        ]
        for result in results
    ]
    widths = [max(len(str(row[index])) for row in [header] + rows) for index in range(len(header))]

    def line(left: str, fill: str, join: str, right: str) -> str:
        return left + join.join(fill * (width + 2) for width in widths) + right

    def render(row: Sequence[str]) -> str:
        return "│ " + " │ ".join(str(value).ljust(width) for value, width in zip(row, widths)) + " │"

    print(line("┌", "─", "┬", "┐"))
    print(render(header))
    print(line("├", "─", "┼", "┤"))
    for row in rows:
        print(render(row))
    print(line("└", "─", "┴", "┘"))

    passed = sum(bool(result["passed"]) for result in results)
    total = len(results)
    overall = "PASS" if passed == total else "FAIL"
    print()
    print(f"Overall result: {overall} ({passed}/{total} tests passed)")
    for result in results:
        print(f"- {result['theorem']}: {result['details']}")
    return results


if __name__ == "__main__":
    run_all_tests()
