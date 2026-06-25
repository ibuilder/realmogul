"""Twists: scheduled market/world events that force a strategy pivot.

This is where the learning sticks (Section 2 of the brief): a rate hike, a zoning
change, an anchor tenant leaving, a boom town. Events are pure data with a fixed
trigger month so a level is deterministic and replayable. The session interprets
them when it advances a turn — events stay free of any session import.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from engine.world.zoning import Zoning


class TwistKind(str, Enum):
    RATE_HIKE = "rate_hike"  # rates spike -> values fall, debt costs more
    RATE_CUT = "rate_cut"  # rates fall -> values rise
    BOOM_TOWN = "boom_town"  # demand surges -> rents firm, vacancy eases
    BUST = "bust"  # demand craters
    ZONING_CHANGE = "zoning_change"  # a lot is rezoned
    ANCHOR_LEAVES = "anchor_leaves"  # a commercial tenant vacates -> income stops


@dataclass(frozen=True)
class TwistEvent:
    month: int
    kind: TwistKind
    magnitude: float = 0.0
    lot_id: str | None = None
    new_zoning: Zoning | None = None
    message: str = ""

    def market_perturbation(self) -> tuple[float, float]:
        """Return ``(rate_shock, demand_delta)`` this event feeds to the market step."""
        if self.kind is TwistKind.RATE_HIKE:
            return (self.magnitude, 0.0)
        if self.kind is TwistKind.RATE_CUT:
            return (-self.magnitude, 0.0)
        if self.kind is TwistKind.BOOM_TOWN:
            return (0.0, self.magnitude)
        if self.kind is TwistKind.BUST:
            return (0.0, -self.magnitude)
        return (0.0, 0.0)

    @property
    def mutates_town(self) -> bool:
        return self.kind in {TwistKind.ZONING_CHANGE, TwistKind.ANCHOR_LEAVES}
