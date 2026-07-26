"""Violet Studio adapter.

The Studio drives a five-rotor, six-switch machine through a dictionary key.
This module presents that interface on top of the engine in ``violet.py``: keys
are dictionaries of wirings and positions, the pin rings that gate the rotor
stepping are derived deterministically from the installed wirings so that the
Studio's key format needs no extra field, and the machine runs in the
tap-driven regime described in the paper.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Sequence, Tuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from violet import (ALPHABET, M as SWITCH_POSITIONS, Mode, N as ALPHABET_SIZE,  # noqa: E402
                    VioletBuild, VioletKey, VioletMachine as _Core,
                    indices_to_text, text_to_indices)

STUDIO_ROTORS = 5
STUDIO_SWITCHES = 6
STUDIO_CHEST = 8
STUDIO_PLUG_PAIRS = 10
CANONICAL_WIRING_SEED = 0x5657


def _pins_from_wirings(rotors: Sequence[Sequence[int]]) -> np.ndarray:
    """Derive the pin rings from the installed wirings.

    Rotor ``i`` steps when the tap symbol falls on a pin; the pin pattern is the
    parity of the wiring's displacement at that letter, which gives a balanced
    ring that changes whenever the rotor order changes.
    """
    rings = []
    for wiring in rotors[1:]:
        w = np.asarray(wiring, dtype=np.int64)
        rings.append(((w - np.arange(len(w))) % ALPHABET_SIZE) & 1)
    if not rings:
        return np.zeros((0, ALPHABET_SIZE), dtype=np.int64)
    return np.stack(rings)


class VioletMachine:
    """Dictionary-keyed façade over the engine."""

    def __init__(self, rotors, rotor_positions, plugboard_pairs,
                 switch_wirings, switch_positions, mode: Mode = Mode.CLOSED):
        rotors = [list(map(int, r)) for r in rotors]
        build = VioletBuild(
            rotor_chest=[np.asarray(r, dtype=np.int64) for r in rotors],
            switch_banks=[[np.asarray(level, dtype=np.int64) for level in switch]
                          for switch in switch_wirings])
        pairs = [(ord(a.upper()) - 65, ord(b.upper()) - 65)
                 for a, b in plugboard_pairs]
        key = VioletKey(rotor_order=list(range(len(rotors))),
                        rotor_positions=[int(p) % ALPHABET_SIZE for p in rotor_positions],
                        switch_positions=[int(q) % SWITCH_POSITIONS for q in switch_positions],
                        plug_pairs=pairs,
                        pins=_pins_from_wirings(rotors))
        self._core = _Core(build, key, mode=mode)
        self.rotors = rotors
        self.plugboard_pairs = [(a.upper(), b.upper()) for a, b in plugboard_pairs]
        self.switch_wirings = switch_wirings
        self.initial_rotor_positions = list(self._core.p)
        self.initial_switch_positions = list(self._core.q)
        self.rotor_positions = list(self._core.p)
        self.switch_positions = list(self._core.q)

    # -- construction ------------------------------------------------------

    @classmethod
    def from_key(cls, key: Dict[str, object]) -> "VioletMachine":
        return cls(rotors=key["rotors"],
                   rotor_positions=key["rotor_positions"],
                   plugboard_pairs=[tuple(p) for p in key["plugboard_pairs"]],
                   switch_wirings=key["switch_wirings"],
                   switch_positions=key["switch_positions"])

    @staticmethod
    def generate_random_key(seed: int | None = None) -> Dict[str, object]:
        build = _Core.build_hardware(STUDIO_CHEST, STUDIO_SWITCHES,
                                     seed=CANONICAL_WIRING_SEED)
        rng = np.random.default_rng(seed)
        order = rng.choice(STUDIO_CHEST, size=STUDIO_ROTORS, replace=False)
        letters = rng.permutation(ALPHABET_SIZE)[: 2 * STUDIO_PLUG_PAIRS]
        pairs = [(ALPHABET[int(a)], ALPHABET[int(b)])
                 for a, b in letters.reshape(STUDIO_PLUG_PAIRS, 2)]
        return {
            "rotors": [build.rotor_chest[int(i)].tolist() for i in order],
            "rotor_positions": [int(v) for v in
                                rng.integers(0, ALPHABET_SIZE, size=STUDIO_ROTORS)],
            "plugboard_pairs": [list(p) for p in pairs],
            "switch_wirings": [[level.tolist() for level in bank]
                               for bank in build.switch_banks],
            "switch_positions": [int(v) for v in
                                 rng.integers(0, SWITCH_POSITIONS, size=STUDIO_SWITCHES)],
        }

    # -- operation ---------------------------------------------------------

    def reset(self) -> None:
        self._core.reset()
        self.rotor_positions = list(self._core.p)
        self.switch_positions = list(self._core.q)

    def encrypt(self, message: str) -> str:
        out = self._core.encrypt(message)
        self.rotor_positions = list(self._core.p)
        self.switch_positions = list(self._core.q)
        return out

    def decrypt(self, message: str) -> str:
        out = self._core.decrypt(message)
        self.rotor_positions = list(self._core.p)
        self.switch_positions = list(self._core.q)
        return out

    def encrypt_char(self, char: str) -> str:
        idx = self._core.encrypt_symbol(ord(char.upper()) - 65)
        self.rotor_positions = list(self._core.p)
        self.switch_positions = list(self._core.q)
        return ALPHABET[idx]

    def decrypt_char(self, char: str) -> str:
        idx = self._core.decrypt_symbol(ord(char.upper()) - 65)
        self.rotor_positions = list(self._core.p)
        self.switch_positions = list(self._core.q)
        return ALPHABET[idx]

    def get_state(self) -> Dict[str, object]:
        return {
            "rotor_positions": [int(v) for v in self._core.p],
            "switch_positions": [int(v) for v in self._core.q],
            "E_t": self._core.E().copy(),
        }


def generate_random_key(seed: int | None = None) -> Dict[str, object]:
    return VioletMachine.generate_random_key(seed=seed)


__all__ = ["ALPHABET", "ALPHABET_SIZE", "SWITCH_POSITIONS", "VioletMachine",
           "generate_random_key", "text_to_indices", "indices_to_text"]
