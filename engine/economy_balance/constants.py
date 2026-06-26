"""Tunable economy constants — the ONE place designers change balance.

Keep magic numbers out of logic and in here (see CLAUDE.md). These are starting
values for Phase 1; the balance simulator (tools/balance_sim.py) exists to tune
them until the economy is fun and has no infinite-money exploit.

Rates are decimals (0.06 == 6%).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LendingTerms:
    """Underwriting limits a lender applies. Vary these per market/asset class."""

    max_ltv: float = 0.75
    min_dscr: float = 1.25
    term_months: int = 360
    base_spread: float = 0.0225  # added on top of the market rate curve


@dataclass(frozen=True)
class MarketDefaults:
    """Starting market conditions before events ("twists") perturb them."""

    base_interest_rate: float = 0.065  # the rate curve's starting anchor
    base_cap_rate: float = 0.06  # market cap rate for stabilized assets
    base_vacancy_rate: float = 0.07
    # Drift kept low so scripted twists (the lessons) dominate over a long hold
    # instead of being washed out by a random walk. Tuned in Phase 7.
    rate_drift_std: float = 0.0015  # monthly drift volatility
    rate_shock_prob: float = 0.02  # chance of a rate shock event per step
    rate_shock_size: float = 0.012  # magnitude of a shock when it fires


@dataclass(frozen=True)
class OpexAssumptions:
    """Default operating-expense ratios when not specified per property."""

    management_rate: float = 0.05  # of EGI
    maintenance_rate: float = 0.08  # of EGI
    capex_reserve_rate: float = 0.05  # of EGI
    insurance_rate_of_value: float = 0.004  # annual, of property value
    tax_rate_of_value: float = 0.012  # annual property tax, of value


@dataclass(frozen=True)
class WorkforceDefaults:
    """Labor constraints — the Build-a-Lot 'juggle your crews' tension."""

    starting_crews: int = 3
    hire_cost_base: float = 28_000  # cost to hire the next crew, scales with count


@dataclass(frozen=True)
class UpkeepDefaults:
    """Buildings wear down; repairs restore them (ongoing management loop)."""

    # ~1.8%/yr drift down: a gentle nudge that rewards occasional upkeep, not a
    # treadmill that erases a renovation. Tuned in the gameplay (Wave 1) pass.
    condition_decay_per_month: float = 0.0015
    condition_floor: float = 0.55
    repair_cost: float = 9_000
    repair_months: int = 1
    repair_restores_to: float = 0.97


@dataclass(frozen=True)
class AmenityDefaults:
    """Civic builds that permanently lift neighborhood appeal (player-driven demand)."""

    # type -> (cash cost, build months, permanent appeal added to demand)
    catalog: tuple = (
        ("park", 35_000, 3, 0.12),
        ("transit", 90_000, 6, 0.25),
        ("plaza", 60_000, 4, 0.18),
    )


@dataclass(frozen=True)
class OpportunityDefaults:
    """Surprise deals that break the optimization monotony (Wave 3)."""

    per_month_prob: float = 0.07  # chance a fresh opportunity appears each month
    distressed_discount: tuple = (0.10, 0.28)  # buy below market by this fraction
    buyout_premium: tuple = (0.08, 0.22)  # an offer above market by this fraction
    expires_in_months: int = 3  # act before it's gone


# Default bundles the rest of the engine imports.
DEFAULT_LENDING = LendingTerms()
DEFAULT_MARKET = MarketDefaults()
DEFAULT_OPEX = OpexAssumptions()
DEFAULT_WORKFORCE = WorkforceDefaults()
DEFAULT_UPKEEP = UpkeepDefaults()
DEFAULT_AMENITIES = AmenityDefaults()
DEFAULT_OPPORTUNITIES = OpportunityDefaults()
