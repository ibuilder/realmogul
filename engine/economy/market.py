"""Live, steppable market state for gameplay.

Where ``rates.simulate_rate_path`` precomputes a whole path for the balance sim,
``MarketState`` advances one turn at a time so scripted events ("twists") can
perturb it mid-game. Holds the interest rate, the implied cap rate, and a
neighborhood ``demand_index`` (Build-a-Lot's ignored "appeal", made real) that
nudges rents and vacancy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from engine.economy.rates import cap_from_rate, step_interest_rate
from engine.economy_balance.constants import DEFAULT_MARKET, MarketDefaults
from engine.rng import GameRNG


@dataclass(frozen=True)
class MarketState:
    """Immutable snapshot of market conditions for one turn.

    ``demand_index`` is centered on 1.0: above 1 means a hot neighborhood
    (rents firm, vacancy eases), below 1 means soft.
    """

    interest_rate: float
    cap_rate: float
    demand_index: float = 1.0
    base_rate: float | None = None  # the current rate regime; rates revert toward it

    @property
    def regime(self) -> float:
        return self.base_rate if self.base_rate is not None else self.interest_rate

    @classmethod
    def at_base(cls, market: MarketDefaults = DEFAULT_MARKET) -> MarketState:
        return cls(
            interest_rate=market.base_interest_rate,
            cap_rate=cap_from_rate(market.base_interest_rate, market),
            demand_index=1.0,
            base_rate=market.base_interest_rate,
        )

    def stepped(
        self,
        rng: GameRNG,
        market: MarketDefaults = DEFAULT_MARKET,
        *,
        rate_shock: float = 0.0,
        demand_delta: float = 0.0,
    ) -> MarketState:
        """Return the next turn's market.

        ``rate_shock`` and ``demand_delta`` are how events feed in: a rate-hike
        twist passes a positive ``rate_shock``; a boom-town twist passes a
        positive ``demand_delta``.

        A rate twist shifts the *regime* (``base_rate``) permanently, so the cut/
        hike lasts; the rate then wanders around that new regime. Demand is the
        opposite — a boom is transient, easing back toward 1.0 over months.
        """
        new_regime = max(0.005, self.regime + rate_shock)
        new_rate, _ = step_interest_rate(rng, self.interest_rate, new_regime, market)
        reversion = (1.0 - self.demand_index) * 0.04
        new_demand = max(0.5, min(1.8, self.demand_index + reversion + demand_delta))
        return replace(
            self,
            interest_rate=new_rate,
            cap_rate=cap_from_rate(new_rate, market),
            demand_index=new_demand,
            base_rate=new_regime,
        )
