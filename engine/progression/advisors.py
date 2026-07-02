"""Advisors — hire specialists for passive perks (a light REIT-Tycoon C-suite).

Layered on top of careers: a career is your specialty; advisors are staff you add
mid-game for one-time cash. Perks are convenience-shaped (more leverage, faster
builds, slower decay, more deal flow) — they change strategy, never make the
campaign unbeatable. Pure data; the session applies the effects on hire.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AdvisorId(str, Enum):
    SCOUT = "scout"
    BANKER = "banker"
    GC = "gc"
    MANAGER = "manager"


@dataclass(frozen=True)
class Advisor:
    id: AdvisorId
    name: str
    role: str
    blurb: str
    hire_cost: float
    ltv_bonus: float = 0.0  # added to max LTV
    build_speed_mult: float = 1.0  # <1 = faster builds
    decay_mult: float = 1.0  # <1 = buildings wear slower
    opportunity_mult: float = 1.0  # >1 = more deals surface


ADVISORS: dict[AdvisorId, Advisor] = {
    AdvisorId.SCOUT: Advisor(
        AdvisorId.SCOUT,
        "Priya Anand",
        "Deal Scout",
        "Works her network — more off-market deals cross your desk.",
        hire_cost=40_000,
        opportunity_mult=1.9,
    ),
    AdvisorId.BANKER: Advisor(
        AdvisorId.BANKER,
        "Marcus Vale",
        "Relationship Banker",
        "Gets you a little more leverage on every loan.",
        hire_cost=55_000,
        ltv_bonus=0.04,
    ),
    AdvisorId.GC: Advisor(
        AdvisorId.GC,
        "Lena Ortiz",
        "General Contractor",
        "Runs tight sites — builds and renovations finish faster.",
        hire_cost=45_000,
        build_speed_mult=0.8,
    ),
    AdvisorId.MANAGER: Advisor(
        AdvisorId.MANAGER,
        "Sam Cho",
        "Property Manager",
        "Proactive upkeep — your buildings wear down more slowly.",
        hire_cost=35_000,
        decay_mult=0.5,
    ),
}


def get_advisor(advisor_id: AdvisorId) -> Advisor:
    return ADVISORS[advisor_id]
