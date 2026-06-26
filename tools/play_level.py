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
from engine.economy_balance.constants import DEFAULT_UPKEEP
from engine.progression.campaign import CampaignLevel, build_level_one, campaign_levels, new_session
from engine.progression.session import GameSession
from engine.world.zoning import Zoning

CASH_BUFFER = 15_000
DEV_BUFFER = 70_000  # keep a fat reserve before tying cash up in a build
AMENITY_BUFFER = 55_000  # build appeal once there's comfortable cash
REFI_MIN_PROCEEDS = 25_000
MAX_BOUGHT = 3  # cap churn — transaction friction (premium + closing) is ~8% a pop
REPAIR_BELOW = 0.86  # repair a building once condition slips under this
MAX_CREWS = 5


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
    """Buy the most affordable listed property, up to the churn cap — but only with
    enough cash left over to keep a reserve (don't get caught cash-poor if a tenant
    leaves). The reserve scales with price, so the agent buys fewer expensive assets."""
    if bought[0] >= MAX_BOUGHT:
        return False
    listed = [lot for lot in session.town.lots_for_sale() if lot.property_ is not None]
    listed.sort(key=lambda lot: lot.property_.value(session.effective_market))
    for lot in listed:
        value = lot.property_.value(session.effective_market)
        # Down payment + a real cushion (re-leasing/vacancy can cost a lot on a
        # pricey asset). ~55% of value keeps the agent from getting cash-poor.
        if session.cash < 0.55 * value:
            continue
        if session.acquire(lot.id):
            bought[0] += 1
            return True
    return False


def _try_relet(session: GameSession) -> bool:
    """Re-lease a property whose tenant left (e.g. an anchor walked) before it
    bleeds. Signing any improvement re-leases it; prefer a new anchor for commercial."""
    for lot_id, h in session.holdings.items():
        if h.property_ is None or h.pending or h.property_.leased:
            continue
        anchor = UPGRADE_CATALOG.get("anchor_tenant")
        if (
            anchor is not None
            and anchor.allowed_for(h.property_.asset_class)
            and "anchor_tenant" not in h.property_.upgrades
            and anchor.cost + CASH_BUFFER <= session.cash
        ):
            return session.upgrade(lot_id, "anchor_tenant")
        if (
            "renovate" not in h.property_.upgrades
            and UPGRADE_CATALOG["renovate"].cost + CASH_BUFFER <= session.cash
        ):
            return session.upgrade(lot_id, "renovate")
    return False


def _try_repair(session: GameSession) -> bool:
    """Keep buildings in shape — worn condition drags NOI and value."""
    for lot_id, h in session.holdings.items():
        if h.property_ is None or h.pending:
            continue
        if h.property_.condition < REPAIR_BELOW and (
            DEFAULT_UPKEEP.repair_cost + CASH_BUFFER <= session.cash
        ):
            return session.repair(lot_id)
    return False


AMENITY_PORTFOLIO_MIN = 700_000  # appeal only pays for itself on a big portfolio


def _try_amenity(session: GameSession) -> bool:
    """Build a park on owned vacant land — but only once the portfolio is large
    enough that a demand lift outvalues the cost (small portfolios lose on it)."""
    market = session.effective_market
    portfolio_value = sum(
        h.property_.value(market) for h in session.holdings.values() if h.property_ is not None
    )
    if portfolio_value < AMENITY_PORTFOLIO_MIN:
        return False
    for lot_id in list(session.town.lots):
        if session._is_vacant_land(lot_id) and session.build_amenity(lot_id, "park"):
            return True
    return False


def _try_develop(session: GameSession) -> bool:
    """Build on owned vacant zoned land when there's cash to spare."""
    for lot_id, lot in session.town.lots.items():
        if not session._is_vacant_land(lot_id):
            continue
        asset = AssetClassId.MIXED_USE if lot.zoning is Zoning.MIXED else AssetClassId.SFR
        if session.develop(lot_id, asset, 1):
            return True
    return False


def _try_refinance(session: GameSession) -> bool:
    """Pull equity from a property that has built enough to be worth the fees.

    Only called while the agent is still buying (see play loop), so it recycles
    equity into the next deal rather than re-levering a finished portfolio."""
    for lot_id, h in session.holdings.items():
        if h.property_ is None or h.pending:
            continue
        proceeds = session.refinance(lot_id)
        if proceeds is not None and proceeds >= REFI_MIN_PROCEEDS:
            return True
    return False


def _listings_remain(session: GameSession) -> bool:
    return any(lot.property_ is not None for lot in session.town.lots_for_sale())


def play(level: CampaignLevel) -> PlayResult:
    session = new_session(level)
    bought = [0]
    built_amenity = [False]
    while session.status == "playing":
        # 0) Keep labor flowing: hire a crew if work is blocked and cash is healthy.
        if session.free_crews == 0 and session.crews < MAX_CREWS and session.cash > 90_000:
            session.hire_crew()
        # 1a) Stop the bleeding: re-lease any vacant building immediately.
        if _try_relet(session):
            session.advance_month()
            continue
        # 1b) Upkeep — protect the income you already have.
        if _try_repair(session):
            session.advance_month()
            continue
        # 2) Value-add: best risk-adjusted return on cash.
        if _try_upgrade(session):
            session.advance_month()
            continue
        # 3) Recycle equity ONLY while still buying — fund the next deal, don't
        #    re-lever a finished portfolio.
        if (
            bought[0] < MAX_BOUGHT
            and session.month > 0
            and session.month % 12 == 0
            and _try_refinance(session)
        ):
            session.advance_month()
            continue
        # 4) Acquire while keeping a buffer, up to the churn cap.
        if session.cash >= CASH_BUFFER and _try_acquire(session, bought):
            session.advance_month()
            continue
        # 5) Build one amenity to pump demand across the whole portfolio.
        if not built_amenity[0] and session.cash >= AMENITY_BUFFER and _try_amenity(session):
            built_amenity[0] = True
            session.advance_month()
            continue
        # 6) Develop remaining land once nothing's left to buy and reserves are healthy.
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
