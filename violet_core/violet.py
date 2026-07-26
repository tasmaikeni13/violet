"""Violet: a coprime-cascade electromechanical cipher.

This module is the reference implementation of the Violet cipher machine and of
the two historical machines it is measured against (Enigma and Purple).  It is
written to be read alongside the accompanying paper: every object here has a
name and a symbol in the formal development.

Notation
--------
The alphabet is ``A = Z_n`` with ``n = 26``.  Permutations are stored as numpy
arrays ``f`` with ``f[x]`` the image of ``x``; composition ``f o g`` is the numpy
expression ``f[g]``.  The cyclic shift is ``tau(x) = x + 1 (mod n)``.

Architecture
------------
Violet has two permutation stages that live on coprime moduli:

* a **rotor bank** of ``r`` reflectorless rotors over ``Z_n`` (``n = 26``),
* a **switch bank** of ``k`` stepping switches over ``Z_m`` (``m = 25``),

composed with a static plugboard involution ``P``:

    E_t = sigma(q_t) o rho(p_t) o P.

The rotor stage is
``rho(p) = W_{r-1}^<p_{r-1}> o ... o W_0^<p_0>`` where ``W^<p> = tau^-p o W o tau^p``
is the displaced wiring of a rotor, and the switch stage is
``sigma(q) = U_{k-1}(q_{k-1}) o ... o U_0(q_0)`` where each switch ``U_j`` is an
*independent family* of ``m`` unrelated permutations (a Strowger bank), not a
conjugacy orbit of one wiring.

Two stepping regimes are implemented:

``Mode.OPEN``
    Both banks advance as autonomous odometers (base ``n`` and base ``m``).  This
    is the historically faithful composition of the two paradigms and is the
    object of the cryptanalysis in the paper.

``Mode.CLOSED``
    The switch bank remains an autonomous base-``m`` odometer -- this is what
    buys the provable period floor -- while the rotor bank steps *irregularly*
    under control of the inter-stage tap
    ``g_t = rho(p_t)(P(x_t)) = sigma(q_t)^{-1}(y_t)``, gated by key-settable pin
    rings.  The tap is a physically available wire between the two stages, so the
    feedback is realisable with 1940s relay logic, and it is available to the
    receiver before it is needed, so decryption stays deterministic.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# --------------------------------------------------------------------------
# Alphabet and global constants
# --------------------------------------------------------------------------

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
N = 26                       # alphabet size, rotor modulus
M = 25                       # stepping-switch level count

#: Canonical strategic configuration (rack mounted): 14 rotors, 14 switches.
STRATEGIC = dict(num_rotors=14, num_switches=14, chest=18, plug_pairs=10)
#: Canonical field configuration (portable): 8 rotors, 8 switches.
FIELD = dict(num_rotors=8, num_switches=8, chest=12, plug_pairs=10)


class Mode(enum.Enum):
    """Stepping regime of the machine."""

    OPEN = "open"      # both banks autonomous odometers
    CLOSED = "closed"  # autonomous switch clock + tap-controlled rotor bank


# --------------------------------------------------------------------------
# Permutation helpers
# --------------------------------------------------------------------------


def identity(n: int = N) -> np.ndarray:
    return np.arange(n, dtype=np.int64)


def compose(f: np.ndarray, g: np.ndarray) -> np.ndarray:
    """Return ``f o g``, i.e. ``x -> f(g(x))``."""
    return f[g]


def invert(f: np.ndarray) -> np.ndarray:
    inv = np.empty_like(f)
    inv[f] = np.arange(len(f), dtype=f.dtype)
    return inv


def is_permutation(f: np.ndarray, n: Optional[int] = None) -> bool:
    n = len(f) if n is None else n
    return len(f) == n and np.array_equal(np.sort(f), np.arange(n))


def sign(f: np.ndarray) -> int:
    """Signature of a permutation: ``+1`` if even, ``-1`` if odd."""
    n = len(f)
    seen = np.zeros(n, dtype=bool)
    parity = 0
    for start in range(n):
        if seen[start]:
            continue
        length = 0
        x = start
        while not seen[x]:
            seen[x] = True
            x = int(f[x])
            length += 1
        parity += length - 1
    return -1 if parity % 2 else 1


def cycle_type(f: np.ndarray) -> Tuple[int, ...]:
    n = len(f)
    seen = np.zeros(n, dtype=bool)
    lengths: List[int] = []
    for start in range(n):
        if seen[start]:
            continue
        length = 0
        x = start
        while not seen[x]:
            seen[x] = True
            x = int(f[x])
            length += 1
        lengths.append(length)
    return tuple(sorted(lengths, reverse=True))


def fixed_points(f: np.ndarray) -> int:
    return int(np.sum(f == np.arange(len(f))))


def shift(s: int, n: int = N) -> np.ndarray:
    """The permutation ``tau^s : x -> x + s (mod n)``."""
    return (np.arange(n, dtype=np.int64) + s) % n


def displace(wiring: np.ndarray, offset: int, n: int = N) -> np.ndarray:
    """Return ``W^<s> = tau^-s o W o tau^s``, the rotor wiring at offset ``s``."""
    idx = (np.arange(n, dtype=np.int64) + offset) % n
    return (wiring[idx] - offset) % n


def text_to_indices(text: str) -> np.ndarray:
    return np.array([ord(c) - 65 for c in text.upper() if c.isalpha() and c.isascii()],
                    dtype=np.int64)


def indices_to_text(idx: Sequence[int]) -> str:
    return "".join(ALPHABET[int(i)] for i in idx)


def involution_from_pairs(pairs: Sequence[Tuple[int, int]], n: int = N) -> np.ndarray:
    """Build the plugboard involution determined by disjoint transpositions."""
    perm = identity(n)
    used: set = set()
    for a, b in pairs:
        a, b = int(a), int(b)
        if a == b:
            raise ValueError("plugboard pairs must swap distinct letters")
        if a in used or b in used:
            raise ValueError("each letter may appear in at most one plugboard pair")
        used.update((a, b))
        perm[a], perm[b] = b, a
    return perm


# --------------------------------------------------------------------------
# Odometers
# --------------------------------------------------------------------------


def odometer_step(state: np.ndarray, base: int) -> np.ndarray:
    """One tick of a strict base-``b`` odometer (least significant digit first)."""
    out = state.copy()
    for i in range(len(out)):
        out[i] = (out[i] + 1) % base
        if out[i] != 0:
            break
    return out


def odometer_value(state: Sequence[int], base: int) -> int:
    """The integer whose base-``b`` digits are ``state`` (little endian)."""
    value = 0
    for digit in reversed(list(state)):
        value = value * base + int(digit)
    return value


def odometer_digits(value: int, base: int, width: int) -> np.ndarray:
    out = np.empty(width, dtype=np.int64)
    for i in range(width):
        out[i] = value % base
        value //= base
    return out


def odometer_advance(state: Sequence[int], base: int, steps: int) -> np.ndarray:
    """Advance an odometer by ``steps`` ticks in O(width) time.

    This is Lemma "odometer linearisation": a strict base-``b`` odometer is the
    base-``b`` digit representation of an integer counter, so ``steps`` ticks add
    ``steps`` to that counter.
    """
    width = len(state)
    return odometer_digits((odometer_value(state, base) + steps) % base**width, base, width)


# --------------------------------------------------------------------------
# Machine description: public wiring ("the build") and secret key
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class VioletBuild:
    """Public, long-term hardware of a Violet machine (Kerckhoffs' component)."""

    rotor_chest: List[np.ndarray]           # C rotors, each a permutation of Z_n
    switch_banks: List[List[np.ndarray]]    # k switches, each m unrelated permutations
    n: int = N
    m: int = M

    @property
    def chest_size(self) -> int:
        return len(self.rotor_chest)

    @property
    def num_switches(self) -> int:
        return len(self.switch_banks)

    def validate(self) -> None:
        for w in self.rotor_chest:
            if not is_permutation(w, self.n):
                raise ValueError("rotor wiring is not a permutation")
        for bank in self.switch_banks:
            if len(bank) != self.m:
                raise ValueError(f"each switch must expose exactly {self.m} levels")
            for level in bank:
                if not is_permutation(level, self.n):
                    raise ValueError("switch level is not a permutation")


@dataclass
class VioletKey:
    """Secret, per-message key of a Violet machine."""

    rotor_order: List[int]          # which chest rotors are installed, in order
    rotor_positions: List[int]      # p in Z_n^r
    switch_positions: List[int]     # q in Z_m^k
    plug_pairs: List[Tuple[int, int]]
    pins: np.ndarray                # (r-1, n) binary pin rings for rotors 1..r-1

    @property
    def num_rotors(self) -> int:
        return len(self.rotor_order)

    def as_dict(self) -> Dict[str, object]:
        return {
            "rotor_order": list(self.rotor_order),
            "rotor_positions": list(self.rotor_positions),
            "switch_positions": list(self.switch_positions),
            "plug_pairs": [list(p) for p in self.plug_pairs],
            "pins": np.asarray(self.pins).tolist(),
        }


# --------------------------------------------------------------------------
# The machine
# --------------------------------------------------------------------------


class VioletMachine:
    """A Violet cipher machine: a build, a key, and a stepping regime."""

    def __init__(self, build: VioletBuild, key: VioletKey, mode: Mode = Mode.CLOSED):
        build.validate()
        self.build = build
        self.key = key
        self.mode = mode
        self.n = build.n
        self.m = build.m
        self.r = key.num_rotors
        self.k = build.num_switches

        self.rotors = [np.asarray(build.rotor_chest[i], dtype=np.int64) for i in key.rotor_order]
        self.plug = involution_from_pairs(key.plug_pairs, self.n)
        self.plug_inv = self.plug  # an involution is its own inverse
        self.pins = np.asarray(key.pins, dtype=np.int64).reshape(max(self.r - 1, 0), self.n)

        # Precompute every displaced rotor wiring and cache stage products.
        self._disp = [np.stack([displace(w, s, self.n) for s in range(self.n)])
                      for w in self.rotors]
        self._switch = [[np.asarray(level, dtype=np.int64) for level in bank]
                        for bank in build.switch_banks]

        self.reset()

    # -- state ------------------------------------------------------------

    def reset(self) -> None:
        self.p = np.array(self.key.rotor_positions, dtype=np.int64) % self.n
        self.q = np.array(self.key.switch_positions, dtype=np.int64) % self.m

    def rho(self, p: Optional[Sequence[int]] = None) -> np.ndarray:
        """Rotor-stage permutation ``rho(p)``."""
        p = self.p if p is None else p
        out = identity(self.n)
        for i in range(self.r):
            out = compose(self._disp[i][int(p[i]) % self.n], out)
        return out

    def sigma(self, q: Optional[Sequence[int]] = None) -> np.ndarray:
        """Switch-stage permutation ``sigma(q)``."""
        q = self.q if q is None else q
        out = identity(self.n)
        for j in range(self.k):
            out = compose(self._switch[j][int(q[j]) % self.m], out)
        return out

    def E(self) -> np.ndarray:
        """The current full encryption permutation ``E_t = sigma o rho o P``."""
        return compose(compose(self.sigma(), self.rho()), self.plug)

    # -- stepping ---------------------------------------------------------

    def _step_open(self) -> None:
        self.p = odometer_step(self.p, self.n)
        self.q = odometer_step(self.q, self.m)

    def _step_closed(self, tap: int) -> None:
        self.q = odometer_step(self.q, self.m)
        self.p[0] = (self.p[0] + 1) % self.n
        if self.r > 1:
            self.p[1:] = (self.p[1:] + self.pins[:, tap % self.n]) % self.n

    # -- primitive transforms --------------------------------------------

    def encrypt_symbol(self, x: int) -> int:
        rho = self.rho()
        sigma = self.sigma()
        tap = int(rho[self.plug[x]])       # inter-stage wire g_t
        y = int(sigma[tap])
        if self.mode is Mode.OPEN:
            self._step_open()
        else:
            self._step_closed(tap)
        return y

    def decrypt_symbol(self, y: int) -> int:
        rho = self.rho()
        sigma = self.sigma()
        tap = int(invert(sigma)[y])        # the same wire, reached from the far end
        x = int(self.plug_inv[invert(rho)[tap]])
        if self.mode is Mode.OPEN:
            self._step_open()
        else:
            self._step_closed(tap)
        return x

    # -- messages ---------------------------------------------------------

    def encrypt_indices(self, xs: Sequence[int]) -> np.ndarray:
        self.reset()
        return np.array([self.encrypt_symbol(int(x)) for x in xs], dtype=np.int64)

    def decrypt_indices(self, ys: Sequence[int]) -> np.ndarray:
        self.reset()
        return np.array([self.decrypt_symbol(int(y)) for y in ys], dtype=np.int64)

    def encrypt(self, message: str) -> str:
        return indices_to_text(self.encrypt_indices(text_to_indices(message)))

    def decrypt(self, message: str) -> str:
        return indices_to_text(self.decrypt_indices(text_to_indices(message)))

    # -- introspection ----------------------------------------------------

    def permutation_stream(self, length: int, xs: Optional[Sequence[int]] = None) -> np.ndarray:
        """Return ``E_0, ..., E_{length-1}`` along the trajectory driven by ``xs``.

        In ``Mode.OPEN`` the trajectory is message independent and ``xs`` is
        ignored; in ``Mode.CLOSED`` it is required.
        """
        self.reset()
        out = np.empty((length, self.n), dtype=np.int64)
        for t in range(length):
            out[t] = self.E()
            if self.mode is Mode.OPEN:
                self._step_open()
            else:
                x = 0 if xs is None else int(xs[t])
                tap = int(self.rho()[self.plug[x]])
                self._step_closed(tap)
        return out

    def state(self) -> Tuple[np.ndarray, np.ndarray]:
        return self.p.copy(), self.q.copy()

    # -- key generation ---------------------------------------------------

    @staticmethod
    def build_hardware(chest: int, num_switches: int, seed: int = 0x5657,
                       n: int = N, m: int = M) -> VioletBuild:
        """Deterministically generate a machine build (rotor chest + switch banks)."""
        rng = np.random.default_rng(seed)
        chest_rotors: List[np.ndarray] = []
        seen: set = set()
        while len(chest_rotors) < chest:
            cand = rng.permutation(n).astype(np.int64)
            key = tuple(cand.tolist())
            if key in seen:
                continue
            # reject rotors that are pure shifts: tau^a commutes with displacement
            # and would contribute no offset dependence at all.
            if any(np.array_equal(cand, shift(a, n)) for a in range(n)):
                continue
            seen.add(key)
            chest_rotors.append(cand)
        banks = [[rng.permutation(n).astype(np.int64) for _ in range(m)]
                 for _ in range(num_switches)]
        return VioletBuild(rotor_chest=chest_rotors, switch_banks=banks, n=n, m=m)

    @staticmethod
    def random_key(build: VioletBuild, num_rotors: int, plug_pairs: int = 10,
                   seed: Optional[int] = None) -> VioletKey:
        rng = np.random.default_rng(seed)
        order = rng.choice(build.chest_size, size=num_rotors, replace=False).tolist()
        p = rng.integers(0, build.n, size=num_rotors).tolist()
        q = rng.integers(0, build.m, size=build.num_switches).tolist()
        letters = rng.permutation(build.n)[: 2 * plug_pairs].reshape(plug_pairs, 2)
        pairs = [(int(a), int(b)) for a, b in letters]
        pins = rng.integers(0, 2, size=(max(num_rotors - 1, 0), build.n))
        return VioletKey(rotor_order=[int(i) for i in order],
                         rotor_positions=[int(v) for v in p],
                         switch_positions=[int(v) for v in q],
                         plug_pairs=pairs, pins=pins)

    @staticmethod
    def canonical(config: Optional[Dict[str, int]] = None, seed: int = 0x5657,
                  key_seed: Optional[int] = 1, mode: Mode = Mode.CLOSED) -> "VioletMachine":
        cfg = dict(STRATEGIC if config is None else config)
        build = VioletMachine.build_hardware(cfg["chest"], cfg["num_switches"], seed=seed)
        key = VioletMachine.random_key(build, cfg["num_rotors"], cfg["plug_pairs"], seed=key_seed)
        return VioletMachine(build, key, mode=mode)


# --------------------------------------------------------------------------
# Structural quantities of the design
# --------------------------------------------------------------------------


def state_space_bits(num_rotors: int, num_switches: int, n: int = N, m: int = M) -> float:
    """``log2 |Omega|`` where ``Omega = Z_n^r x Z_m^k`` is the reachable state set."""
    return num_rotors * np.log2(n) + num_switches * np.log2(m)


def nominal_key_bits(chest: int, num_rotors: int, num_switches: int,
                     plug_pairs: int = 10, pins: bool = True,
                     n: int = N, m: int = M) -> float:
    """``log2`` of the naive key count, including material the paper shows is inert."""
    from math import lgamma, log2

    order = sum(np.log2(chest - i) for i in range(num_rotors))
    positions = num_rotors * np.log2(n) + num_switches * np.log2(m)
    # number of involutions on n points with exactly `plug_pairs` transpositions
    plug = (lgamma(n + 1) - lgamma(n - 2 * plug_pairs + 1)
            - lgamma(plug_pairs + 1) - plug_pairs * np.log(2)) / np.log(2)
    pin_bits = (num_rotors - 1) * n if pins else 0
    return order + positions + plug + pin_bits


def guaranteed_period(num_switches: int, m: int = M) -> int:
    """Provable period floor of the closed-loop machine: the autonomous clock."""
    return m ** num_switches


def open_loop_period(num_rotors: int, num_switches: int, n: int = N, m: int = M) -> int:
    """Exact period of the open-loop machine (the two moduli are coprime)."""
    from math import gcd
    a, b = n ** num_rotors, m ** num_switches
    return a * b // gcd(a, b)


# --------------------------------------------------------------------------
# Reference models of the historical machines
# --------------------------------------------------------------------------


class Enigma:
    """Three-rotor Wehrmacht Enigma with plugboard, reflector, and ring settings.

    Included for the structural comparison: what matters here is the reflector,
    an involution without fixed points, which forces every ``E_t`` into a single
    conjugacy class of ``S_26``.
    """

    ROTORS = {
        "I":    ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", "Q"),
        "II":   ("AJDKSIRUXBLHWTMCQGZNPYFVOE", "E"),
        "III":  ("BDFHJLCPRTXVZNYEIWGAKMUSQO", "V"),
        "IV":   ("ESOVPZJAYQUIRHXLNFTGKDCMWB", "J"),
        "V":    ("VZBRGITYUPSDNHLXAWMJQOFECK", "Z"),
    }
    REFLECTOR_B = "YRUHQSLDPXNGOKMIEBFZCWVJAT"

    def __init__(self, rotor_names: Sequence[str] = ("I", "II", "III"),
                 positions: Sequence[int] = (0, 0, 0),
                 rings: Sequence[int] = (0, 0, 0),
                 plug_pairs: Sequence[Tuple[int, int]] = ()):
        self.wirings = [text_to_indices(self.ROTORS[name][0]) for name in rotor_names]
        self.notches = [ord(self.ROTORS[name][1]) - 65 for name in rotor_names]
        self.reflector = text_to_indices(self.REFLECTOR_B)
        self.rings = list(rings)
        self.init_positions = list(positions)
        self.plug = involution_from_pairs(plug_pairs)
        self.reset()

    def reset(self) -> None:
        self.pos = list(self.init_positions)

    def _step(self) -> None:
        # right rotor always; middle on its own notch (double step) or right notch
        if self.pos[1] == self.notches[1]:
            self.pos[1] = (self.pos[1] + 1) % N
            self.pos[2] = (self.pos[2] + 1) % N
        elif self.pos[0] == self.notches[0]:
            self.pos[1] = (self.pos[1] + 1) % N
        self.pos[0] = (self.pos[0] + 1) % N

    def permutation(self) -> np.ndarray:
        """Return the current ``E_t`` as a permutation array."""
        out = self.plug.copy()
        for w, p, ring in zip(self.wirings, self.pos, self.rings):
            out = compose(displace(w, (p - ring) % N), out)
        out = compose(self.reflector, out)
        for w, p, ring in reversed(list(zip(self.wirings, self.pos, self.rings))):
            out = compose(invert(displace(w, (p - ring) % N)), out)
        return compose(self.plug, out)

    def encrypt_indices(self, xs: Sequence[int]) -> np.ndarray:
        self.reset()
        out = []
        for x in xs:
            self._step()
            out.append(int(self.permutation()[int(x)]))
        return np.array(out, dtype=np.int64)

    def permutation_stream(self, length: int) -> np.ndarray:
        self.reset()
        out = np.empty((length, N), dtype=np.int64)
        for t in range(length):
            self._step()
            out[t] = self.permutation()
        return out


class Purple:
    """Structural model of the Japanese Type-B machine ("Purple").

    Faithful in the property that decides its fate: the alphabet is partitioned
    into a 6-set and a 20-set, each permuted by its own stepping-switch cascade,
    and the partition is invariant under every ``E_t``.  The input plugboard is a
    fixed permutation of the 26 letters, so the invariant partition an attacker
    sees is a conjugate of the internal one, not the internal one itself.
    """

    def __init__(self, seed: int = 7, sixes_size: int = 6):
        rng = np.random.default_rng(seed)
        self.plug = rng.permutation(N).astype(np.int64)
        self.plug_inv = invert(self.plug)
        self.sixes = np.arange(sixes_size)
        self.twenties = np.arange(sixes_size, N)
        s = sixes_size
        self.sixes_bank = [rng.permutation(s).astype(np.int64) for _ in range(M)]
        self.twenties_banks = [[rng.permutation(N - s).astype(np.int64) for _ in range(M)]
                               for _ in range(3)]
        self.init_pos = [int(v) for v in rng.integers(0, M, size=4)]
        self.sixes_size = s
        self.reset()

    def reset(self) -> None:
        self.pos = list(self.init_pos)

    def _step(self) -> None:
        # sixes switch steps every character; the three twenties switches form a
        # cascade whose stepping is gated by the sixes switch position.
        self.pos[0] = (self.pos[0] + 1) % M
        if self.pos[0] == 0:
            self.pos[1] = (self.pos[1] + 1) % M
            if self.pos[1] == 0:
                self.pos[2] = (self.pos[2] + 1) % M
                if self.pos[2] == 0:
                    self.pos[3] = (self.pos[3] + 1) % M

    def permutation(self) -> np.ndarray:
        s = self.sixes_size
        inner = identity(N)
        six = self.sixes_bank[self.pos[0]]
        inner[:s] = six
        twenty = identity(N - s)
        for bank, p in zip(self.twenties_banks, self.pos[1:]):
            twenty = compose(bank[p], twenty)
        inner[s:] = twenty + s
        return compose(self.plug_inv, compose(inner, self.plug))

    def permutation_stream(self, length: int) -> np.ndarray:
        self.reset()
        out = np.empty((length, N), dtype=np.int64)
        for t in range(length):
            self._step()
            out[t] = self.permutation()
        return out

    def encrypt_indices(self, xs: Sequence[int]) -> np.ndarray:
        self.reset()
        out = []
        for x in xs:
            self._step()
            out.append(int(self.permutation()[int(x)]))
        return np.array(out, dtype=np.int64)


__all__ = [
    "ALPHABET", "N", "M", "Mode", "STRATEGIC", "FIELD",
    "VioletBuild", "VioletKey", "VioletMachine", "Enigma", "Purple",
    "identity", "compose", "invert", "sign", "cycle_type", "fixed_points",
    "displace", "shift", "involution_from_pairs", "is_permutation",
    "text_to_indices", "indices_to_text",
    "odometer_step", "odometer_value", "odometer_digits", "odometer_advance",
    "state_space_bits", "nominal_key_bits", "guaranteed_period", "open_loop_period",
]
