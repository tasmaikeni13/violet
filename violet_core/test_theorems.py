"""Executable checks of every claim the Violet paper makes about the machine.

Each check corresponds to a numbered statement in the paper; the structural ones
are also machine-checked in Lean, and this suite is the computational witness
that the Lean statements are about the implemented object.

    python violet_core/test_theorems.py
"""

from __future__ import annotations

import os
import sys
import unittest
from math import factorial, gcd, log2

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from violet import (ALPHABET, Enigma, FIELD, M, Mode, N, Purple, STRATEGIC,
                    VioletMachine, compose, cycle_type, displace, fixed_points,
                    identity, invert, involution_from_pairs, is_permutation,
                    odometer_advance, odometer_step, open_loop_period, sign,
                    state_space_bits, text_to_indices)


class Correctness(unittest.TestCase):
    """Proposition: decryption inverts encryption, in both regimes."""

    def test_roundtrip(self):
        for mode in (Mode.OPEN, Mode.CLOSED):
            for cfg in (FIELD, STRATEGIC):
                machine = VioletMachine.canonical(cfg, mode=mode, key_seed=7)
                for message in ("ATTACKATDAWN", "A", ALPHABET * 3,
                                "THEENEMYISLISTENING" * 5):
                    with self.subTest(mode=mode.value, rotors=cfg["num_rotors"],
                                      n=len(message)):
                        self.assertEqual(machine.decrypt(machine.encrypt(message)),
                                         message)

    def test_permutation_at_every_step(self):
        machine = VioletMachine.canonical(FIELD, mode=Mode.CLOSED, key_seed=3)
        stream = machine.permutation_stream(200, xs=np.zeros(200, dtype=np.int64))
        for t in range(200):
            self.assertTrue(is_permutation(stream[t], N))

    def test_output_alphabet(self):
        machine = VioletMachine.canonical(FIELD, mode=Mode.CLOSED, key_seed=4)
        cipher = machine.encrypt_indices(text_to_indices("A" * 500))
        self.assertEqual(len(cipher), 500)
        self.assertTrue(np.all((cipher >= 0) & (cipher < N)))


class Odometers(unittest.TestCase):
    """Lemma (odometer linearisation) and the period theorems."""

    def test_odometer_is_a_counter(self):
        for base, width in ((26, 3), (25, 4)):
            state = np.array([base - 1] * width, dtype=np.int64)
            for t in range(1, 200):
                state = odometer_step(state, base)
                expected = odometer_advance([base - 1] * width, base, t)
                self.assertTrue(np.array_equal(state, expected))

    def test_period_is_the_product_of_coprime_moduli(self):
        for r, k in ((2, 2), (3, 2), (5, 6), (14, 14)):
            self.assertEqual(gcd(N ** r, M ** k), 1)
            self.assertEqual(open_loop_period(r, k), N ** r * M ** k)

    def test_open_loop_state_is_a_function_of_time(self):
        machine = VioletMachine.canonical(FIELD, mode=Mode.OPEN, key_seed=5)
        a = machine.permutation_stream(120, xs=np.zeros(120, dtype=np.int64))
        b = machine.permutation_stream(120, xs=np.arange(120) % N)
        self.assertTrue(np.array_equal(a, b))

    def test_closed_loop_state_depends_on_the_message(self):
        machine = VioletMachine.canonical(FIELD, mode=Mode.CLOSED, key_seed=5)
        a = machine.permutation_stream(120, xs=np.zeros(120, dtype=np.int64))
        b = machine.permutation_stream(120, xs=np.arange(120) % N)
        self.assertFalse(np.array_equal(a, b))

    def test_closed_loop_period_floor(self):
        """The autonomous switch clock forbids a repeat inside 25^k steps."""
        machine = VioletMachine.canonical(FIELD, mode=Mode.CLOSED, key_seed=9)
        machine.reset()
        seen = set()
        rng = np.random.default_rng(0)
        for _ in range(4000):
            state = (tuple(machine.p.tolist()), tuple(machine.q.tolist()))
            self.assertNotIn(state, seen)
            seen.add(state)
            machine.encrypt_symbol(int(rng.integers(0, N)))


class Invariants(unittest.TestCase):
    """The three classical obstructions, and Violet's escape from each."""

    @classmethod
    def setUpClass(cls):
        cls.violet = VioletMachine.canonical(STRATEGIC, mode=Mode.CLOSED, key_seed=11)
        rng = np.random.default_rng(1)
        cls.V = cls.violet.permutation_stream(4000, xs=rng.integers(0, N, size=4000))
        cls.E = Enigma(plug_pairs=[(0, 5), (1, 9)]).permutation_stream(2000)
        cls.P = Purple(seed=7).permutation_stream(2000)

    def test_enigma_lies_in_the_reflector_class(self):
        for t in range(0, 2000, 37):
            perm = self.E[t]
            self.assertEqual(fixed_points(perm), 0)
            self.assertTrue(np.array_equal(perm[perm], np.arange(N)))
            self.assertEqual(sign(perm), -1)
            self.assertEqual(cycle_type(perm), tuple([2] * 13))

    def test_violet_has_fixed_points_and_is_not_an_involution(self):
        fp = np.array([fixed_points(self.V[t]) for t in range(4000)])
        self.assertGreater(fp.mean(), 0.85)
        self.assertLess(fp.mean(), 1.15)
        self.assertLess(abs(fp.var() - 1.0), 0.2)          # Poisson(1)
        involutions = sum(np.array_equal(self.V[t][self.V[t]], np.arange(N))
                          for t in range(500))
        self.assertEqual(involutions, 0)

    def test_rotor_stage_signature_is_frozen(self):
        rng = np.random.default_rng(2)
        signs = {sign(self.violet.rho(rng.integers(0, N, size=self.violet.r)))
                 for _ in range(60)}
        self.assertEqual(len(signs), 1)

    def test_violet_signature_moves(self):
        frac_even = float(np.mean(np.array([sign(self.V[t]) for t in range(600)]) == 1))
        self.assertGreater(frac_even, 0.4)
        self.assertLess(frac_even, 0.6)

    def test_purple_preserves_a_block(self):
        """The input plugboard conjugates the internal 6-set into an unknown
        block; the block still exists, which is the whole weakness."""
        purple = Purple(seed=7)
        block = {int(purple.plug_inv[b]) for b in range(6)}
        images = {int(self.P[t][x]) for t in range(2000) for x in block}
        self.assertEqual(images, block)

    def test_violet_preserves_no_block(self):
        reach = np.zeros((N, N), dtype=bool)
        for perm in self.V[:2000]:
            reach[np.arange(N), perm] = True
        closure = reach.copy()
        for k in range(N):
            closure |= np.outer(closure[:, k], closure[k, :])
        self.assertTrue(closure.all())

    def test_reachable_set_generates_the_symmetric_group(self):
        from sympy.combinatorics import Permutation, PermutationGroup
        gens = [Permutation(list(map(int, self.V[t]))) for t in range(0, 400, 7)]
        self.assertEqual(PermutationGroup(gens).order(), factorial(N))


class StaticLayerTransparency(unittest.TestCase):
    """The plugboard is computed, not searched, and is invisible to the
    statistic that identifies a trajectory."""

    def _instance(self, r=2, k=2, length=400, seed=0):
        build = VioletMachine.build_hardware(chest=r + 2, num_switches=k)
        rng = np.random.default_rng(seed)
        A, B = N ** r, M ** k
        rho = np.empty((A, N), dtype=np.int64)
        for c in range(A):
            out = identity(N)
            for i in range(r):
                out = compose(displace(build.rotor_chest[i], (c // N ** i) % N), out)
            rho[c] = out
        sig = np.empty((B, N), dtype=np.int64)
        for c in range(B):
            out = identity(N)
            for j in range(k):
                out = compose(build.switch_banks[j][(c // M ** j) % M], out)
            sig[c] = out
        letters = rng.permutation(N)[:20].reshape(10, 2)
        plug = involution_from_pairs([(int(a), int(b)) for a, b in letters])
        c0, d0 = int(rng.integers(0, A)), int(rng.integers(0, B))
        plain = rng.integers(0, N, size=length)
        t = np.arange(length)
        cipher = sig[(d0 + t) % B, rho[(c0 + t) % A, plug[plain]]]
        rho_inv = np.stack([invert(p) for p in rho])
        sig_inv = np.stack([invert(p) for p in sig])
        z = rho_inv[(c0 + t) % A, sig_inv[(d0 + t) % B, cipher]]
        return plug, plain, z

    def test_plugboard_is_read_off(self):
        plug, plain, z = self._instance(seed=1)
        self.assertTrue(np.array_equal(z, plug[plain]))

    def test_repeated_letter_test_is_plugboard_free(self):
        plug, plain, z = self._instance(seed=2)
        for a in range(N):
            idx = np.flatnonzero(plain == a)
            if len(idx) > 1:
                self.assertEqual(len(set(z[idx].tolist())), 1)

    def test_coincidence_count_is_plugboard_independent(self):
        def coincidences(z):
            counts = np.bincount(z, minlength=N).astype(float)
            return float((counts * (counts - 1)).sum())

        rng = np.random.default_rng(3)
        plain = rng.integers(0, N, size=600)
        base = coincidences(plain)
        for _ in range(20):
            letters = rng.permutation(N)[:20].reshape(10, 2)
            plug = involution_from_pairs([(int(a), int(b)) for a, b in letters])
            self.assertEqual(coincidences(plug[plain]), base)


class Feedback(unittest.TestCase):
    """Error propagation and the destruction of depth."""

    def test_open_loop_confines_a_change(self):
        machine = VioletMachine.canonical(FIELD, mode=Mode.OPEN, key_seed=13)
        plain = np.arange(200) % N
        base = machine.encrypt_indices(plain)
        edited = plain.copy()
        edited[0] = (edited[0] + 1) % N
        alt = machine.encrypt_indices(edited)
        self.assertEqual(int(np.sum(base[1:] != alt[1:])), 0)

    def test_closed_loop_propagates_a_change(self):
        machine = VioletMachine.canonical(FIELD, mode=Mode.CLOSED, key_seed=13)
        rng = np.random.default_rng(4)
        rates = []
        for _ in range(20):
            plain = rng.integers(0, N, size=300)
            base = machine.encrypt_indices(plain)
            edited = plain.copy()
            edited[0] = (edited[0] + 1 + rng.integers(0, N - 1)) % N
            alt = machine.encrypt_indices(edited)
            rates.append(float(np.mean(base[1:] != alt[1:])))
        mean = float(np.mean(rates))
        self.assertGreater(mean, 0.93)
        self.assertLess(abs(mean - (N - 1) / N), 0.03)

    def test_depth_survives_open_loop_and_dies_closed_loop(self):
        rng = np.random.default_rng(5)
        a, b = rng.integers(0, N, size=150), rng.integers(0, N, size=150)
        opened = VioletMachine.canonical(FIELD, mode=Mode.OPEN, key_seed=17)
        self.assertTrue(np.array_equal(opened.permutation_stream(150, xs=a),
                                       opened.permutation_stream(150, xs=b)))
        closed = VioletMachine.canonical(FIELD, mode=Mode.CLOSED, key_seed=17)
        sa = closed.permutation_stream(150, xs=a)
        sb = closed.permutation_stream(150, xs=b)
        self.assertLess(sum(np.array_equal(sa[t], sb[t]) for t in range(150)), 8)


class Accounting(unittest.TestCase):
    """The stated sizes."""

    def test_state_space_bits(self):
        self.assertAlmostEqual(state_space_bits(14, 14), 130.82, places=2)
        self.assertAlmostEqual(state_space_bits(8, 8), 74.75, places=2)

    def test_strategic_period(self):
        self.assertEqual(open_loop_period(14, 14), 650 ** 14)
        self.assertGreater(open_loop_period(14, 14), 2 ** 130)

    def test_sizing_rule(self):
        """r log2 26 + k log2 25 >= 128 first holds at r = k = 14."""
        need = lambda r: r * log2(N) + r * log2(M)
        self.assertLess(need(13), 128)
        self.assertGreaterEqual(need(14), 128)


class StudioAdapter(unittest.TestCase):
    """The interface Violet Studio uses still round-trips."""

    def test_dictionary_key_roundtrip(self):
        from violet_engine import VioletMachine as Studio, generate_random_key
        key = generate_random_key(seed=42)
        machine = Studio.from_key(key)
        message = "VIOLETSTUDIOROUNDTRIP"
        self.assertEqual(machine.decrypt(machine.encrypt(message)), message)
        state = machine.get_state()
        self.assertEqual(len(state["rotor_positions"]), 5)
        self.assertEqual(len(state["switch_positions"]), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
