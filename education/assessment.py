"""Stealth assessment: track which concepts the player demonstrably *uses*.

Not a quiz — we watch what they actually do (financed a deal -> leverage; renovated
-> value-add; pulled a cash-out refi -> refinance) and build a quiet picture of
mastery. That drives gentle "here's the next idea" nudges and, later, the
education-pack analytics.

Pure, in-memory, serializable to a plain set for saves.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# A sensible teaching order — earlier concepts unlock the later ones.
LEARNING_ORDER: tuple[str, ...] = (
    "noi",
    "cap_rate",
    "value",
    "leverage",
    "dscr",
    "value_add",
    "cash_on_cash",
    "refinance",
    "cash_out_refi",
    "construction_loan",
    "interest_reserve",
    "irr",
)


@dataclass
class ConceptTracker:
    demonstrated: set[str] = field(default_factory=set)

    def record(self, *concepts: str) -> None:
        self.demonstrated.update(concepts)

    def has(self, concept: str) -> bool:
        return concept in self.demonstrated

    def mastery_fraction(self) -> float:
        if not LEARNING_ORDER:
            return 0.0
        known = sum(1 for c in LEARNING_ORDER if c in self.demonstrated)
        return known / len(LEARNING_ORDER)

    def next_concept(self) -> str | None:
        """The first concept in the learning order they haven't shown yet."""
        for concept in LEARNING_ORDER:
            if concept not in self.demonstrated:
                return concept
        return None

    # save/load helpers (plain JSON-friendly)
    def to_list(self) -> list[str]:
        return sorted(self.demonstrated)

    @classmethod
    def from_list(cls, items: list[str]) -> ConceptTracker:
        return cls(demonstrated=set(items))
