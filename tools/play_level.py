"""Headless campaign driver — proves levels are playable start -> win.

A deterministic greedy agent general enough for every level type: it buys the most
affordable listed deal (any asset class), adds value by renovating, develops vacant
land it owns, and periodically refinances to recycle equity. Used to verify that
each handcrafted level is winnable within its time limit.

    python -m tools.play_level            # level 1
    python -m tools.play_level --all      # every campaign level
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from engine.assets.asset_class import AssetClassId
from engine.assets.upgrades import UPGRADE_CATALOG
from engine.progression.campaign import CampaignLevel, build_level_one, campaign_levels, new_session
from engine.progression.session import GameSession
from engine.world.zoning import Zoning

CASH_BUFFER = 15_000
DEV_BUFFER = 70_000  # keep a fat reserve before tying cash up in a build
REFI_MIN_PROCEEDS = 25_000
MAX_BOUGHT = 3  # cap churn — transaction friction (premium + closing) is ~8% a pop


@dataclass
class PlayResult:
    level_id: str
    won: bool
    months_played: int
    final_net_worth: float
    holdings: int
    log: list[str]


def _try_upgrade(session: GameSession) -> bool:
    """Renovate an owned, un-renovated, finished property when affordable."""
    cost = UPGRADE_CATALOG["renovate"].cost
    for lot_id, h in session.holdings.items():
        if h.property_ is None or h.pending or "renovate" in h.property_.upgrades:
            continue
        if cost + CASH_BUFFER <= session.cash:
            return session.upgrade(lot_id, "renovate")
    return False


def _try_acquire(session: GameSession, bought: list[int]) -> bool:
    """Buy the most affordable listed property, up to the churn cap."""
    if bought[0] >= MAX_BOUGHT:
        return False
    listed = [lot for lot in session.town.lots_for_sale() if lot.property_ is not None]
    listed.sort(key=lambda lot: lot.property_.value(session.market))
    for lot in listed:
        if session.acquire(lot.id):
            bought[0] += 1
            return True
    return False


def _try_develop(session: GameSession) -> bool:
    """Build on owned, empty, zoned land when there's cash to spare."""
    for lot_id, lot in session.town.lots.items():
        if not lot.owned or not lot.is_empty:
            continue
        holding = session.holdings.get(lot_id)
        if holding is not None and holding.pending:
            continue  # already building
        asset = AssetClassId.MIXED_USE if lot.zoning is Zoning.MIXED else AssetClassId.SFR
        if session.develop(lot_id, asset, 1):
            return True
    return False


def _try_refinance(session: GameSession, refinanced: set[str]) -> bool:
    """Refinance each property at most once — repeated refis just stack fees/debt."""
    for lot_id, h in session.holdings.items():
        if h.property_ is None or h.pending or lot_id in refinanced:
            continue
        proceeds = session.refinance(lot_id)
        if proceeds is not None and proceeds >= REFI_MIN_PROCEEDS:
            refinanced.add(lot_id)
            return True
    return False


def _listings_remain(session: GameSession) -> bool:
    return any(lot.property_ is not None for lot in session.town.lots_for_sale())


def play(level: CampaignLevel) -> PlayResult:
    session = new_session(level)
    bought = [0]
    refinanced: set[str] = set()
    while session.status == "playing":
        # 1) Value-add: best risk-adjusted return on cash.
        if _try_upgrade(session):
            session.advance_month()
            continue
        # 2) Recycle equity (once per property) ONLY while still buying — once the
        #    portfolio is built, hold and let it appreciate rather than re-lever.
        if (
            bought[0] < MAX_BOUGHT
            and session.month > 0
            and session.month % 12 == 0
            and _try_refinance(session, refinanced)
        ):
            session.advance_month()
            continue
        # 3) Acquire while keeping a buffer, up to the churn cap.
        if session.cash >= CASH_BUFFER and _try_acquire(session, bought):
            session.advance_month()
            continue
        # 4) Only build once nothing's left to buy and reserves are healthy.
        if not _listings_remain(session) and session.cash >= DEV_BUFFER and _try_develop(session):
            session.advance_month()
            continue
        session.advance_month()

    return PlayResult(
        level_id=level.id,
        won=session.won,
        months_played=session.month,
        final_net_worth=session.net_worth(),
        holdings=len(session.holdings),
        log=session.log,
    )


def _print(result: PlayResult) -> None:
    status = "WON" if result.won else "LOST"
    print(
        f"  {result.level_id:<9} {status:<4} month {result.months_played:>3}  "
        f"net worth ${result.final_net_worth:>12,.0f}  holdings {result.holdings}"
    )


def main() -> int:
    if "--all" in sys.argv:
        print("=" * 60)
        print("  REAL MOGUL - campaign playthroughs")
        print("=" * 60)
        results = [play(level) for level in campaign_levels()]
        for r in results:
            _print(r)
        print("=" * 60)
        return 0 if all(r.won for r in results) else 1

    result = play(build_level_one())
    for line in result.log:
        print("  " + line)
    _print(result)
    return 0 if result.won else 1


if __name__ == "__main__":
    raise SystemExit(main())
