"""Seeded, deterministic RNG for the Real Mogul engine.

Determinism is non-negotiable (see CLAUDE.md): same seed + same inputs => same
outcome. This underpins tests, replays, fairness, and anti-cheat. Nothing in
``engine/`` should call the bare ``random`` module, ``secrets``, or wall-clock
time for game logic — route it all through this class.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


class GameRNG:
    """A thin, explicit wrapper over a seeded ``random.Random``.

    Kept deliberately small so its behaviour is obvious and fully testable. Each
    instance owns its own stream; pass instances around rather than using module
    globals so two parallel simulations never interfere.
    """

    __slots__ = ("_seed", "_random")

    def __init__(self, seed: int) -> None:
        self._seed = int(seed)
        self._random = random.Random(self._seed)

    @property
    def seed(self) -> int:
        return self._seed

    def getstate(self) -> tuple:
        """Internal RNG state, for saving mid-game so a reload continues identically."""
        return self._random.getstate()

    def setstate(self, state: tuple) -> None:
        self._random.setstate(state)

    @classmethod
    def from_state(cls, seed: int, state: tuple) -> GameRNG:
        rng = cls(seed)
        rng.setstate(state)
        return rng

    def fork(self, label: str) -> GameRNG:
        """Derive a child stream deterministically from this one and a label.

        Use this to isolate subsystems (market vs. events vs. tenant behaviour)
        so adding a draw in one place does not shift every other stream.
        """
        derived = (hash((self._seed, label)) & 0x7FFFFFFF) ^ 0x5DEECE66
        return GameRNG(derived & 0x7FFFFFFF)

    def randint(self, low: int, high: int) -> int:
        """Inclusive integer in ``[low, high]``."""
        return self._random.randint(low, high)

    def uniform(self, low: float, high: float) -> float:
        return self._random.uniform(low, high)

    def random(self) -> float:
        """Float in ``[0.0, 1.0)``."""
        return self._random.random()

    def chance(self, probability: float) -> bool:
        """True with the given probability (clamped to ``[0, 1]``)."""
        p = min(1.0, max(0.0, probability))
        return self._random.random() < p

    def choice(self, items: Sequence[T]) -> T:
        return self._random.choice(items)
