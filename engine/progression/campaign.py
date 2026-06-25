"""Campaign level definitions and a factory for fresh, deterministic sessions.

A level is immutable setup data (town template, starting cash, objectives, scripted
twists, seed). ``new_session`` builds a playable :class:`GameSession` from it; the
town template is never mutated (the session replaces its own copy), so a level can
seed many sessions — handy for A/B-ing strategies and for tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.assets.asset_class import AssetClassId
from engine.assets.property import Property
from engine.economy.market import MarketState
from engine.economy.rates import cap_from_rate
from engine.economy_balance.constants import DEFAULT_MARKET
from engine.progression.career import CareerId, get_career
from engine.progression.objectives import Objective, ObjectiveKind
from engine.progression.session import GameSession
from engine.rng import GameRNG
from engine.world.events import TwistEvent, TwistKind
from engine.world.lot import Lot
from engine.world.town import Town
from engine.world.zoning import Zoning


@dataclass(frozen=True)
class CampaignLevel:
    id: str
    name: str
    description: str
    starting_cash: float
    month_limit: int
    town: Town
    objectives: list[Objective]
    seed: int
    events: list[TwistEvent] = field(default_factory=list)
    career: CareerId | None = None  # suggested specialty / its perks apply


def new_session(level: CampaignLevel) -> GameSession:
    """Construct a fresh session from a level (repeatable for the same level)."""
    return GameSession(
        cash=level.starting_cash,
        town=level.town,
        objectives=list(level.objectives),
        month_limit=level.month_limit,
        events=list(level.events),
        rng=GameRNG(level.seed),
        career=get_career(level.career) if level.career else None,
    )


def _sfr(condition: float) -> Property:
    return Property(asset_class=AssetClassId.SFR, units=1, condition=condition, age_years=18)


def _market_at(interest_rate: float, demand: float = 1.0) -> MarketState:
    return MarketState(
        interest_rate=interest_rate,
        cap_rate=cap_from_rate(interest_rate, DEFAULT_MARKET),
        demand_index=demand,
    )


def build_level_one() -> CampaignLevel:
    """Level 1 — "Sleepy Pines": flip and hold single-family homes.

    Learning goal: leverage, value-add via renovation, and refinancing to redeploy
    equity as a falling-rate market lifts values. A handful of SFR lots plus two
    residentially-zoned vacant lots to develop. The twist is a mid-game rate cut
    that rewards patient, leveraged holders.
    """
    market = MarketState.at_base()
    lots: dict[str, Lot] = {}
    for i, cond in enumerate([0.78, 0.82, 0.85, 0.88, 0.80, 0.84]):
        lot = Lot(id=f"sfr-{i}", zoning=Zoning.RESIDENTIAL, property_=_sfr(cond))
        lots[lot.id] = lot
    # Two buildable residential lots for the develop path.
    for i in range(2):
        lot = Lot(
            id=f"land-{i}", zoning=Zoning.RESIDENTIAL, property_=None, for_sale=False, owned=True
        )
        lots[lot.id] = lot

    town = Town(name="Sleepy Pines", market=market, lots=lots)

    objectives = [
        Objective(ObjectiveKind.NET_WORTH, 320_000, "Grow net worth to $320k"),
    ]
    events = [
        TwistEvent(
            8, TwistKind.RATE_CUT, magnitude=0.010, message="The Fed cuts rates — values tick up."
        ),
        TwistEvent(
            20,
            TwistKind.BOOM_TOWN,
            magnitude=0.25,
            message="A big employer moves to town — demand surges.",
        ),
        TwistEvent(
            34,
            TwistKind.RATE_CUT,
            magnitude=0.010,
            message="Another rate cut — cap rates compress.",
        ),
    ]

    return CampaignLevel(
        id="level-1",
        name="Sleepy Pines",
        description="Flip and hold SFRs in a quiet town as rates fall.",
        starting_cash=160_000,
        month_limit=60,
        town=town,
        objectives=objectives,
        seed=20260601,
        events=events,
        career=CareerId.FLIPPER,
    )


def _prop(asset_class: AssetClassId, units: int, condition: float) -> Property:
    return Property(asset_class=asset_class, units=units, condition=condition, age_years=15)


def build_level_two() -> CampaignLevel:
    """Level 2 — "Maple Heights": small multifamily value-add as a Landlord.

    Bigger buildings, bigger NOI, thinner coverage — the Landlord's DSCR relief
    matters here. Renovate to push rents, then ride a boom.
    """
    lots: dict[str, Lot] = {}
    for i, cond in enumerate([0.76, 0.80, 0.84, 0.78]):
        lots[f"mf-{i}"] = Lot(
            id=f"mf-{i}",
            zoning=Zoning.RESIDENTIAL,
            property_=_prop(AssetClassId.MULTIFAMILY, 4, cond),
        )
    for i, cond in enumerate([0.82, 0.86]):
        lots[f"sfr-{i}"] = Lot(id=f"sfr-{i}", zoning=Zoning.RESIDENTIAL, property_=_sfr(cond))
    lots["land-0"] = Lot(
        id="land-0", zoning=Zoning.RESIDENTIAL, property_=None, for_sale=False, owned=True
    )

    town = Town(name="Maple Heights", market=_market_at(0.062, 1.0), lots=lots)
    events = [
        TwistEvent(10, TwistKind.RATE_CUT, magnitude=0.012, message="Rates ease — values firm up."),
        TwistEvent(
            30,
            TwistKind.BOOM_TOWN,
            magnitude=0.40,
            message="Transit line announced — demand jumps.",
        ),
        TwistEvent(54, TwistKind.RATE_CUT, magnitude=0.014, message="Cap rates compress further."),
        TwistEvent(
            76, TwistKind.BOOM_TOWN, magnitude=0.25, message="The neighborhood is officially hot."
        ),
    ]
    return CampaignLevel(
        id="level-2",
        name="Maple Heights",
        description="Value-add small multifamily as a Landlord.",
        starting_cash=320_000,
        month_limit=96,
        town=town,
        objectives=[Objective(ObjectiveKind.NET_WORTH, 480_000, "Grow net worth to $480k")],
        seed=20260602,
        events=events,
        career=CareerId.LANDLORD,
    )


def build_level_three() -> CampaignLevel:
    """Level 3 — "Market Street": commercial as a Syndicator.

    Retail, office and mixed-use trade at wider cap rates and tolerate less
    vacancy. Higher leverage (Syndicator) helps clear DSCR. Twist: an anchor
    tenant walks — re-lease it by signing a new anchor.
    """
    lots: dict[str, Lot] = {}
    for i, cond in enumerate([0.84, 0.88, 0.82]):
        lots[f"ret-{i}"] = Lot(
            id=f"ret-{i}", zoning=Zoning.COMMERCIAL, property_=_prop(AssetClassId.RETAIL, 3, cond)
        )
    lots["off-0"] = Lot(
        id="off-0", zoning=Zoning.COMMERCIAL, property_=_prop(AssetClassId.OFFICE, 4, 0.85)
    )
    lots["mix-0"] = Lot(
        id="mix-0", zoning=Zoning.MIXED, property_=_prop(AssetClassId.MIXED_USE, 4, 0.86)
    )

    town = Town(name="Market Street", market=_market_at(0.060, 1.05), lots=lots)
    events = [
        TwistEvent(
            24,
            TwistKind.ANCHOR_LEAVES,
            lot_id="ret-0",
            message="Anchor tenant at ret-0 walks — income stops until you re-lease.",
        ),
        TwistEvent(
            40,
            TwistKind.BOOM_TOWN,
            magnitude=0.30,
            message="Downtown revival — foot traffic surges.",
        ),
        TwistEvent(
            64, TwistKind.RATE_CUT, magnitude=0.012, message="Rates fall — commercial values rise."
        ),
    ]
    return CampaignLevel(
        id="level-3",
        name="Market Street",
        description="Commercial portfolio as a Syndicator; survive an anchor exit.",
        starting_cash=520_000,
        month_limit=108,
        town=town,
        objectives=[Objective(ObjectiveKind.NET_WORTH, 1_300_000, "Grow net worth to $1.3M")],
        seed=20260603,
        events=events,
        career=CareerId.SYNDICATOR,
    )


def build_level_four() -> CampaignLevel:
    """Level 4 — "Old Mill District": ground-up development as a Developer.

    Mostly vacant land you already own. Build, lease up, and let a boom reward the
    new supply. The Developer's faster builds shorten the cash-drag of construction.
    """
    lots: dict[str, Lot] = {}
    for i in range(4):
        zoning = Zoning.MIXED if i == 3 else Zoning.RESIDENTIAL
        lots[f"land-{i}"] = Lot(
            id=f"land-{i}", zoning=zoning, property_=None, for_sale=False, owned=True
        )
    for i, cond in enumerate([0.80, 0.84]):
        lots[f"sfr-{i}"] = Lot(id=f"sfr-{i}", zoning=Zoning.RESIDENTIAL, property_=_sfr(cond))

    town = Town(name="Old Mill District", market=_market_at(0.060, 1.0), lots=lots)
    events = [
        TwistEvent(
            24,
            TwistKind.BOOM_TOWN,
            magnitude=0.35,
            message="New campus breaks ground — demand soars.",
        ),
        TwistEvent(
            52,
            TwistKind.RATE_CUT,
            magnitude=0.012,
            message="Rates fall — your new builds revalue up.",
        ),
    ]
    return CampaignLevel(
        id="level-4",
        name="Old Mill District",
        description="Develop vacant land into income as a Developer.",
        starting_cash=300_000,
        month_limit=120,
        town=town,
        objectives=[Objective(ObjectiveKind.NET_WORTH, 600_000, "Grow net worth to $600k")],
        seed=20260604,
        events=events,
        career=CareerId.DEVELOPER,
    )


# Ordered campaign. Index = unlock order.
CAMPAIGN: list = [
    build_level_one(),
    build_level_two(),
    build_level_three(),
    build_level_four(),
]


def campaign_levels() -> list:
    return list(CAMPAIGN)


def level_by_id(level_id: str):
    for lvl in CAMPAIGN:
        if lvl.id == level_id:
            return lvl
    return None
