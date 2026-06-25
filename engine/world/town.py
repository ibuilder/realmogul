"""A town: the board. A collection of lots plus the live market over them."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from engine.economy.market import MarketState
from engine.world.lot import Lot


@dataclass(frozen=True)
class Town:
    """The playfield. Lots are keyed by id for O(1) lookup and stable saves."""

    name: str
    market: MarketState
    lots: dict[str, Lot] = field(default_factory=dict)

    def with_market(self, market: MarketState) -> Town:
        return replace(self, market=market)

    def with_lot(self, lot: Lot) -> Town:
        new_lots = dict(self.lots)
        new_lots[lot.id] = lot
        return replace(self, lots=new_lots)

    def lots_for_sale(self) -> list[Lot]:
        return [lot for lot in self.lots.values() if lot.for_sale and not lot.owned]

    def owned_lots(self) -> list[Lot]:
        return [lot for lot in self.lots.values() if lot.owned]
