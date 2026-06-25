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


# Default bundles the rest of the engine imports.
DEFAULT_LENDING = LendingTerms()
DEFAULT_MARKET = MarketDefaults()
DEFAULT_OPEX = OpexAssumptions()
