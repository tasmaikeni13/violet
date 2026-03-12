"""Core implementation of the Violet cascade electromechanical cipher machine.

The engine models the machine described in the research paper as the cascade

    E_t = sigma_t o rho_t

where the rotor stage rho_t evolves over Z_26^r and the stepping-switch stage
sigma_t evolves independently over Z_25^k.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ALPHABET_SIZE = 26
SWITCH_POSITIONS = 25
CANONICAL_AVAILABLE_ROTORS = 8
CANONICAL_INSTALLED_ROTORS = 5
CANONICAL_SWITCHES = 6
CANONICAL_PLUGBOARD_PAIRS = 10
CANONICAL_WIRING_SEED = 42


def _as_permutation(values: Sequence[int], modulus: int = ALPHABET_SIZE) -> np.ndarray:
    """Validate and return a permutation array."""

    permutation = np.asarray(values, dtype=np.int16)
    if permutation.shape != (modulus,):
        raise ValueError(f"Expected permutation of length {modulus}, got {permutation.shape}.")
    if set(permutation.tolist()) != set(range(modulus)):
        raise ValueError("Array is not a valid permutation.")
    return permutation.copy()


def _compose(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Return the permutation left o right using array lookup semantics."""

    return left[right]


def _invert(permutation: np.ndarray) -> np.ndarray:
    """Return the inverse permutation."""

    return np.argsort(permutation).astype(np.int16)


def _char_to_index(char: str) -> int:
    return ord(char) - ord("A")


def _index_to_char(index: int) -> str:
    return ALPHABET[index]


def _normalize_message(message: str) -> str:
    return "".join(char for char in message.upper() if char.isalpha())


@dataclass(frozen=True)
class VioletKey:
    """Serializable key container for a Violet machine instance."""

    rotors: List[List[int]]
    rotor_positions: List[int]
    plugboard_pairs: List[Tuple[str, str]]
    switch_wirings: List[List[List[int]]]
    switch_positions: List[int]

    def as_dict(self) -> Dict[str, object]:
        return {
            "rotors": self.rotors,
            "rotor_positions": self.rotor_positions,
            "plugboard_pairs": [list(pair) for pair in self.plugboard_pairs],
            "switch_wirings": self.switch_wirings,
            "switch_positions": self.switch_positions,
        }


class VioletMachine:
    """Complete implementation of the Violet cascade electromechanical cipher."""

    def __init__(
        self,
        rotors: Sequence[Sequence[int]],
        rotor_positions: Sequence[int],
        plugboard_pairs: Sequence[Tuple[str, str]],
        switch_wirings: Sequence[Sequence[Sequence[int]]],
        switch_positions: Sequence[int],
    ) -> None:
        self.rotors = [_as_permutation(rotor) for rotor in rotors]
        self.rotor_count = len(self.rotors)
        if self.rotor_count == 0:
            raise ValueError("At least one rotor is required.")

        if len(rotor_positions) != self.rotor_count:
            raise ValueError("Rotor positions must match the number of installed rotors.")
        self.initial_rotor_positions = [int(position) % ALPHABET_SIZE for position in rotor_positions]
        self.rotor_positions = self.initial_rotor_positions.copy()

        self.plugboard = self._build_plugboard(plugboard_pairs)
        self.plugboard_pairs = [(a.upper(), b.upper()) for a, b in plugboard_pairs]

        self.switch_wirings = []
        for switch in switch_wirings:
            positions = [_as_permutation(permutation) for permutation in switch]
            if len(positions) != SWITCH_POSITIONS:
                raise ValueError("Each stepping switch must expose exactly 25 positions.")
            self.switch_wirings.append(positions)
        self.switch_count = len(self.switch_wirings)
        if self.switch_count == 0:
            raise ValueError("At least one stepping switch is required.")

        if len(switch_positions) != self.switch_count:
            raise ValueError("Switch positions must match the number of installed switches.")
        self.initial_switch_positions = [int(position) % SWITCH_POSITIONS for position in switch_positions]
        self.switch_positions = self.initial_switch_positions.copy()

        self.identity = np.arange(ALPHABET_SIZE, dtype=np.int16)

    @staticmethod
    def _canonical_components(seed: int = CANONICAL_WIRING_SEED) -> Tuple[List[np.ndarray], List[List[np.ndarray]]]:
        """Return deterministic canonical rotor and switch wiring inventories."""

        rng = np.random.default_rng(seed)
        rotor_inventory: List[np.ndarray] = []
        seen_rotors = set()
        while len(rotor_inventory) < CANONICAL_AVAILABLE_ROTORS:
            candidate = tuple(rng.permutation(ALPHABET_SIZE).tolist())
            if candidate in seen_rotors:
                continue
            if any(
                all(candidate[index] == (index + shift) % ALPHABET_SIZE for index in range(ALPHABET_SIZE))
                for shift in range(ALPHABET_SIZE)
            ):
                continue
            seen_rotors.add(candidate)
            rotor_inventory.append(np.asarray(candidate, dtype=np.int16))

        switch_bank: List[List[np.ndarray]] = []
        for _ in range(CANONICAL_SWITCHES):
            positions: List[np.ndarray] = []
            seen_positions = set()
            while len(positions) < SWITCH_POSITIONS:
                candidate = tuple(rng.permutation(ALPHABET_SIZE).tolist())
                if candidate in seen_positions:
                    continue
                seen_positions.add(candidate)
                positions.append(np.asarray(candidate, dtype=np.int16))
            switch_bank.append(positions)
        return rotor_inventory, switch_bank

    @classmethod
    def from_key(cls, key: Dict[str, object]) -> "VioletMachine":
        """Instantiate a machine from a serialized key dictionary."""

        return cls(
            rotors=key["rotors"],
            rotor_positions=key["rotor_positions"],
            plugboard_pairs=[tuple(pair) for pair in key["plugboard_pairs"]],
            switch_wirings=key["switch_wirings"],
            switch_positions=key["switch_positions"],
        )

    def _build_plugboard(self, pairs: Sequence[Tuple[str, str]]) -> np.ndarray:
        """Construct and validate the plugboard involution P."""

        plugboard = np.arange(ALPHABET_SIZE, dtype=np.int16)
        used_letters = set()
        for pair in pairs:
            if len(pair) != 2:
                raise ValueError("Each plugboard entry must be a pair of letters.")
            left, right = pair[0].upper(), pair[1].upper()
            if left == right:
                raise ValueError("Plugboard pairs must swap distinct letters.")
            if left not in ALPHABET or right not in ALPHABET:
                raise ValueError("Plugboard pairs must use only A-Z letters.")
            if left in used_letters or right in used_letters:
                raise ValueError("Each letter may appear in at most one plugboard pair.")
            used_letters.add(left)
            used_letters.add(right)
            left_index = _char_to_index(left)
            right_index = _char_to_index(right)
            plugboard[left_index] = right_index
            plugboard[right_index] = left_index

        if not np.array_equal(_compose(plugboard, plugboard), np.arange(ALPHABET_SIZE, dtype=np.int16)):
            raise ValueError("Plugboard wiring must be an involution.")
        return plugboard

    def _rotor_permutation(self, rotor_wiring: Sequence[int], position: int) -> np.ndarray:
        """Compute the displaced rotor permutation tau_-s o R o tau_s."""

        rotor = _as_permutation(rotor_wiring)
        offset = int(position) % ALPHABET_SIZE
        indices = (np.arange(ALPHABET_SIZE, dtype=np.int16) + offset) % ALPHABET_SIZE
        return ((rotor[indices] - offset) % ALPHABET_SIZE).astype(np.int16)

    def _compute_rho(self, rotor_state: Sequence[int]) -> np.ndarray:
        """Compute the composite rotor-stage permutation rho_t."""

        if len(rotor_state) != self.rotor_count:
            raise ValueError("Rotor state length mismatch.")

        composite = self.plugboard.copy()
        for rotor_wiring, position in zip(self.rotors, rotor_state):
            displaced = self._rotor_permutation(rotor_wiring, position)
            composite = _compose(displaced, composite)
        return composite

    def _compute_sigma(self, switch_state: Sequence[int]) -> np.ndarray:
        """Compute the composite stepping-switch permutation sigma_t."""

        if len(switch_state) != self.switch_count:
            raise ValueError("Switch state length mismatch.")

        composite = self.identity.copy()
        for switch_positions, position in zip(self.switch_wirings, switch_state):
            composite = _compose(switch_positions[int(position) % SWITCH_POSITIONS], composite)
        return composite

    def _step_rotors(self) -> None:
        """Advance the rotor odometer as a strict base-26 counter."""

        carry = True
        for index in range(self.rotor_count):
            if not carry:
                break
            self.rotor_positions[index] = (self.rotor_positions[index] + 1) % ALPHABET_SIZE
            carry = self.rotor_positions[index] == 0

    def _step_switches(self) -> None:
        """Advance the switch odometer as a strict base-25 counter."""

        carry = True
        for index in range(self.switch_count):
            if not carry:
                break
            self.switch_positions[index] = (self.switch_positions[index] + 1) % SWITCH_POSITIONS
            carry = self.switch_positions[index] == 0

    def _current_permutations(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        rho = self._compute_rho(self.rotor_positions)
        sigma = self._compute_sigma(self.switch_positions)
        return rho, sigma, _compose(sigma, rho)

    def encrypt_char(self, char: str) -> str:
        """Step the machine and encrypt a single uppercase alphabetic character."""

        if len(char) != 1 or char.upper() not in ALPHABET:
            raise ValueError("encrypt_char expects a single alphabetic character A-Z.")

        self._step_rotors()
        self._step_switches()
        _, _, full_permutation = self._current_permutations()
        return _index_to_char(int(full_permutation[_char_to_index(char.upper())]))

    def decrypt_char(self, char: str) -> str:
        """Step the machine and decrypt a single uppercase alphabetic character."""

        if len(char) != 1 or char.upper() not in ALPHABET:
            raise ValueError("decrypt_char expects a single alphabetic character A-Z.")

        self._step_rotors()
        self._step_switches()
        rho, sigma, _ = self._current_permutations()
        inverse_sigma = _invert(sigma)
        inverse_rho = _invert(rho)
        symbol = _char_to_index(char.upper())
        return _index_to_char(int(inverse_rho[inverse_sigma[symbol]]))

    def encrypt(self, message: str) -> str:
        """Encrypt a message after resetting to the initial key state."""

        self.reset()
        normalized = _normalize_message(message)
        return "".join(self.encrypt_char(char) for char in normalized)

    def decrypt(self, message: str) -> str:
        """Decrypt a message after resetting to the initial key state."""

        self.reset()
        normalized = _normalize_message(message)
        return "".join(self.decrypt_char(char) for char in normalized)

    def reset(self) -> None:
        """Restore the machine to its constructor-supplied initial state."""

        self.rotor_positions = self.initial_rotor_positions.copy()
        self.switch_positions = self.initial_switch_positions.copy()

    def get_state(self) -> Dict[str, object]:
        """Return the current state vectors and current full permutation E_t."""

        _, _, full_permutation = self._current_permutations()
        return {
            "rotor_positions": self.rotor_positions.copy(),
            "switch_positions": self.switch_positions.copy(),
            "E_t": full_permutation.copy(),
        }

    @staticmethod
    def generate_random_key(seed: int | None = None) -> Dict[str, object]:
        """Generate a valid random canonical Violet key.

        The canonical machine uses 8 available rotors, 5 installed rotors,
        6 stepping switches, and 10 plugboard pairs.
        """

        rotor_inventory, switch_bank = VioletMachine._canonical_components()
        rng = np.random.default_rng(seed)
        rotor_indices = rng.choice(CANONICAL_AVAILABLE_ROTORS, size=CANONICAL_INSTALLED_ROTORS, replace=False)
        rotors = [rotor_inventory[index].tolist() for index in rotor_indices]
        rotor_positions = rng.integers(0, ALPHABET_SIZE, size=CANONICAL_INSTALLED_ROTORS).tolist()

        letters = rng.permutation(list(ALPHABET))[: 2 * CANONICAL_PLUGBOARD_PAIRS]
        plugboard_pairs = [tuple(pair) for pair in letters.reshape(CANONICAL_PLUGBOARD_PAIRS, 2).tolist()]
        switch_positions = rng.integers(0, SWITCH_POSITIONS, size=CANONICAL_SWITCHES).tolist()

        key = VioletKey(
            rotors=rotors,
            rotor_positions=[int(value) for value in rotor_positions],
            plugboard_pairs=[(str(left), str(right)) for left, right in plugboard_pairs],
            switch_wirings=[[permutation.tolist() for permutation in switch] for switch in switch_bank],
            switch_positions=[int(value) for value in switch_positions],
        )
        return key.as_dict()


def generate_random_key(seed: int | None = None) -> Dict[str, object]:
    """Module-level convenience wrapper for VioletMachine.generate_random_key."""

    return VioletMachine.generate_random_key(seed=seed)
