"""Career paths — pick a specialty for distinct perks, so replays feel different.

Each career nudges a few session-level levers (leverage, financing strictness,
selling cost, build speed). Perks are deliberately modest and *convenience-shaped*
— they change strategy, not whether the campaign is beatable. Pure data; the
session applies them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CareerId(str, Enum):
    FLIPPER = "flipper"
    LANDLORD = "landlord"
    DEVELOPER = "developer"
    SYNDICATOR = "syndicator"


@dataclass(frozen=True)
class Career:
    id: CareerId
    name: str
    blurb: str
    ltv_bonus: float = 0.0  # added to max LTV (more leverage)
    dscr_relief: float = 0.0  # subtracted from min DSCR (easier approval)
    selling_cost_rate: float = 0.06  # transaction cost on a sale
    build_speed: float = 1.0  # multiplier on construction months (<1 = faster)


CAREERS: dict[CareerId, Career] = {
    CareerId.FLIPPER: Career(
        CareerId.FLIPPER,
        "Flipper",
        "Buys low, sells fast. Low transaction costs on exits.",
        selling_cost_rate=0.03,
    ),
    CareerId.LANDLORD: Career(
        CareerId.LANDLORD,
        "Landlord",
        "Operations-first. Lenders cut you slack on coverage.",
        dscr_relief=0.10,
    ),
    CareerId.DEVELOPER: Career(
        CareerId.DEVELOPER,
        "Developer",
        "Ground-up specialist. Builds finish faster.",
        build_speed=0.75,
    ),
    CareerId.SYNDICATOR: Career(
        CareerId.SYNDICATOR,
        "Syndicator",
        "Raises capital. Access to higher leverage.",
        ltv_bonus=0.05,
    ),
}


def get_career(career_id: CareerId) -> Career:
    return CAREERS[career_id]
