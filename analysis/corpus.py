"""English plaintext source for the statistical and cryptanalytic experiments."""

from __future__ import annotations

import os
import numpy as np

WORDS_PATH = "/usr/share/dict/words"

# Frequencies of the 26 letters in English prose (Norvig, Google Books corpus).
ENGLISH_FREQ = np.array([
    0.0804, 0.0148, 0.0334, 0.0382, 0.1249, 0.0240, 0.0187, 0.0505, 0.0757,
    0.0016, 0.0054, 0.0407, 0.0251, 0.0723, 0.0764, 0.0214, 0.0012, 0.0628,
    0.0651, 0.0928, 0.0273, 0.0105, 0.0168, 0.0023, 0.0166, 0.0009])
ENGLISH_FREQ = ENGLISH_FREQ / ENGLISH_FREQ.sum()

#: Index of coincidence of English text with the above unigram distribution.
ENGLISH_IC = float((ENGLISH_FREQ ** 2).sum())
UNIFORM_IC = 1.0 / 26.0


def english_words(seed: int = 0) -> list[str]:
    if os.path.exists(WORDS_PATH):
        with open(WORDS_PATH, encoding="utf-8", errors="ignore") as fh:
            words = [w.strip().upper() for w in fh]
        words = [w for w in words if w.isalpha() and w.isascii() and 2 <= len(w) <= 11]
        return words
    return ["THE", "ENEMY", "IS", "LISTENING", "ATTACK", "AT", "DAWN"]


def english_text(length: int, seed: int = 0) -> np.ndarray:
    """A stream of `length` letter indices built from real English words."""
    rng = np.random.default_rng(seed)
    words = english_words()
    # Sample words with a Zipf-like preference so common short words dominate,
    # which reproduces realistic letter statistics and repeated-letter density.
    weights = 1.0 / np.arange(1, len(words) + 1) ** 0.6
    weights /= weights.sum()
    order = rng.permutation(len(words))
    picks = rng.choice(len(words), size=length // 4 + 8, p=weights)
    text = "".join(words[order[p]] for p in picks)
    idx = np.frombuffer(text.encode(), dtype=np.uint8).astype(np.int64) - 65
    return idx[:length]


def index_of_coincidence(idx: np.ndarray, n: int = 26) -> float:
    counts = np.bincount(idx, minlength=n).astype(float)
    total = counts.sum()
    if total < 2:
        return float("nan")
    return float((counts * (counts - 1)).sum() / (total * (total - 1)))


def chi_square_uniform(idx: np.ndarray, n: int = 26) -> float:
    counts = np.bincount(idx, minlength=n).astype(float)
    expected = counts.sum() / n
    return float(((counts - expected) ** 2 / expected).sum())
