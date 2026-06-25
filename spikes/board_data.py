"""Shared spike data: turn campaign level 1 into a small board of tiles.

Both the Kivy and Flet spikes import this so they render the *same real numbers*
straight from the engine — proving the thin-client architecture (UI imports
engine, never the reverse). Nothing here is shipping code; it's exploratory.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.progression.campaign import build_level_one


@dataclass(frozen=True)
class Tile:
    col: int
    row: int
    lot_id: str
    label: str
    value: float
    noi: float
    cap_rate: float
    owned: bool


def board_tiles() -> list[Tile]:
    """Lay the level's SFR lots out on a small isometric grid."""
    level = build_level_one()
    market = level.town.market
    tiles: list[Tile] = []
    sfr_lots = [lot for lid, lot in sorted(level.town.lots.items()) if lid.startswith("sfr-")]
    # Arrange 6 lots into a 3x2 grid.
    for i, lot in enumerate(sfr_lots):
        prop = lot.property_
        assert prop is not None
        tiles.append(
            Tile(
                col=i % 3,
                row=i // 3,
                lot_id=lot.id,
                label=f"SFR · cond {prop.condition:.0%}",
                value=prop.value(market),
                noi=prop.annual_noi(market),
                cap_rate=prop.market_cap_rate(market),
                owned=lot.owned,
            )
        )
    return tiles


def explain_deal(tile: Tile) -> str:
    """The 'Explain this deal' overlay text — generated from real engine numbers."""
    return (
        f"{tile.lot_id}\n"
        f"NOI  = ${tile.noi:,.0f} / yr\n"
        f"Cap  = {tile.cap_rate:.2%}\n"
        f"Value = NOI / Cap = ${tile.value:,.0f}"
    )


if __name__ == "__main__":
    for t in board_tiles():
        print(f"{t.lot_id}: value ${t.value:,.0f}  NOI ${t.noi:,.0f}  cap {t.cap_rate:.2%}")
