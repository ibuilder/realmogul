"""The interest-rate curve — the one variable that cascades through everything.

Higher rates -> higher cap rates -> lower values + costlier debt. The curve drifts
each step and occasionally shocks (the "twist"). Pure and seeded: pass a
``GameRNG`` so the whole path is reproducible. The single-step function
(:func:`step_interest_rate`) backs both the precomputed path used by the balance
sim and the live, event-perturbable market used in gameplay.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.economy_balance.constants import DEFAULT_MARKET, MarketDefaults
from engine.rng import GameRNG

RATE_FLOOR = 0.005
CAP_FLOOR = 0.01


@dataclass(frozen=True)
class RateState:
    """A point on the rate path plus the cap rate it implies."""

    step: int
    interest_rate: float
    cap_rate: float
    shocked: bool


def cap_from_rate(interest_rate: float, market: MarketDefaults = DEFAULT_MARKET) -> float:
    """Cap rates track interest rates with a spread anchored at the base case.

    cap = base_cap + (interest - base_interest). A simple, teachable 1:1 linkage:
    when borrowing gets more expensive, buyers demand more yield. Floored so debt
    and valuation math stays well-defined.
    """
    return max(CAP_FLOOR, market.base_cap_rate + (interest_rate - market.base_interest_rate))


def step_interest_rate(
    rng: GameRNG,
    current_rate: float,
    anchor: float,
    market: MarketDefaults = DEFAULT_MARKET,
) -> tuple[float, bool]:
    """Advance the rate one step: random drift + a chance of a discrete shock.

    ``extra_shock`` lets an external event (a scripted "twist") inject an
    additional additive move on top of the natural process. Returns the new rate
    (floored just above zero) and whether a natural shock fired this step.

    The natural process is a *fair* random walk: shocks are equally likely up or
    down (an always-up shock would rig the market against every holder), with mild
    mean-reversion toward the base so rates stay anchored and the scripted twists
    — not the noise — carry the lesson.
    """
    drift = rng.uniform(-market.rate_drift_std, market.rate_drift_std)
    # Revert toward the current regime ``anchor`` (which scripted twists move), so a
    # rate cut/hike is a lasting change while the random noise stays anchored.
    reversion = (anchor - current_rate) * 0.04
    shocked = rng.chance(market.rate_shock_prob)
    shock = 0.0
    if shocked:
        shock = market.rate_shock_size * (1.0 if rng.chance(0.5) else -1.0)
    new_rate = max(RATE_FLOOR, current_rate + drift + reversion + shock)
    return new_rate, shocked


def simulate_rate_path(
    rng: GameRNG,
    steps: int,
    market: MarketDefaults = DEFAULT_MARKET,
) -> list[RateState]:
    """Generate a reproducible rate path of ``steps`` points."""
    path: list[RateState] = []
    rate = market.base_interest_rate
    for step in range(steps):
        rate, shocked = step_interest_rate(rng, rate, market.base_interest_rate, market)
        path.append(
            RateState(
                step=step,
                interest_rate=rate,
                cap_rate=cap_from_rate(rate, market),
                shocked=shocked,
            )
        )
    return path
