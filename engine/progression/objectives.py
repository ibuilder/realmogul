"""Campaign objectives and the metrics they read.

An objective is a win condition tied to a learning goal — "reach $300k net worth"
teaches equity growth; "own 30 units" teaches scaling; "portfolio NOI of $X"
teaches buying for cash flow. Pure predicates over a metrics snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ObjectiveKind(str, Enum):
    NET_WORTH = "net_worth"
    CASH = "cash"
    UNITS_OWNED = "units_owned"
    PORTFOLIO_NOI = "portfolio_noi"


@dataclass(frozen=True)
class GameMetrics:
    """A snapshot of the player's position, computed by the session each check."""

    cash: float
    net_worth: float
    units_owned: int
    portfolio_noi: float
    month: int


@dataclass(frozen=True)
class Objective:
    kind: ObjectiveKind
    target: float
    description: str = ""

    def is_met(self, m: GameMetrics) -> bool:
        value = {
            ObjectiveKind.NET_WORTH: m.net_worth,
            ObjectiveKind.CASH: m.cash,
            ObjectiveKind.UNITS_OWNED: float(m.units_owned),
            ObjectiveKind.PORTFOLIO_NOI: m.portfolio_noi,
        }[self.kind]
        return value >= self.target


def all_met(objectives: list[Objective], m: GameMetrics) -> bool:
    return all(o.is_met(m) for o in objectives)
