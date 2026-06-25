"""Prestige — "Go National".

Reset the local empire for a permanent edge and a new region: classic long-tail
loop. Each prestige converts the net worth you reached into a small, permanent
starting-cash multiplier for future runs. Modest and capped so it adds tempo
without trivializing the campaign. Pure, serializable state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Each prestige adds this fraction to starting cash, capped so it never runs away.
_BONUS_PER_LEVEL = 0.15
_MAX_BONUS = 1.50  # at most +150% starting cash
# Net worth needed to qualify for a prestige (must have actually built something).
PRESTIGE_THRESHOLD = 250_000


@dataclass(frozen=True)
class PrestigeState:
    level: int = 0
    region: int = 0
    best_net_worth: float = 0.0

    @property
    def starting_cash_multiplier(self) -> float:
        return 1.0 + min(_MAX_BONUS, self.level * _BONUS_PER_LEVEL)

    def can_prestige(self, net_worth: float) -> bool:
        return net_worth >= PRESTIGE_THRESHOLD

    def go_national(self, net_worth: float) -> PrestigeState:
        """Reset for a permanent multiplier and the next region. No-op if you
        haven't cleared the threshold."""
        if not self.can_prestige(net_worth):
            return self
        return PrestigeState(
            level=self.level + 1,
            region=self.region + 1,
            best_net_worth=max(self.best_net_worth, net_worth),
        )

    def apply_starting_cash(self, base_cash: float) -> float:
        return base_cash * self.starting_cash_multiplier

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level, "region": self.region, "best_net_worth": self.best_net_worth}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PrestigeState:
        return cls(
            level=d.get("level", 0),
            region=d.get("region", 0),
            best_net_worth=d.get("best_net_worth", 0.0),
        )
