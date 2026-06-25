"""A property: the bundle of physical facts that produces NOI and a value.

Pure data + pure derivations. Given a ``MarketState`` it computes its operating
statement through ``engine.finance`` (single source of truth for the math) and its
cap-rate value. Upgrades and condition modulate the levers; demand modulates rent
and vacancy.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from engine.assets.asset_class import AssetClassId
from engine.assets.upgrades import get_upgrade
from engine.economy.market import MarketState
from engine.economy_balance.asset_economics import economics_for
from engine.finance.operating import (
    OperatingExpenses,
    OperatingStatement,
    net_operating_income,
)
from engine.finance.valuation import value_from_noi


@dataclass(frozen=True)
class Property:
    """An income-producing asset on a lot.

    ``condition`` is 0.5..1.0 and scales rent (a tired building rents for less).
    ``upgrades`` is the set of owned upgrade ids. ``leased`` gates whether it is
    actually producing income yet (a just-built asset must be leased up).
    """

    asset_class: AssetClassId
    units: int
    condition: float = 0.9
    age_years: int = 10
    upgrades: frozenset[str] = field(default_factory=frozenset)
    leased: bool = True

    # ---- derived economics ----

    def _rent_multiplier(self) -> float:
        mult = self.condition
        for uid in self.upgrades:
            mult += get_upgrade(uid).rent_multiplier_bonus
        return mult

    def _effective_vacancy(self, market: MarketState) -> float:
        econ = economics_for(self.asset_class)
        # Hot demand (index > 1) reduces vacancy; soft demand raises it.
        demand_effect = (market.demand_index - 1.0) * econ.demand_sensitivity * 0.5
        vacancy = econ.base_vacancy - demand_effect
        for uid in self.upgrades:
            vacancy += get_upgrade(uid).vacancy_delta
        return max(0.0, min(0.6, vacancy))

    def _opex_ratio(self) -> float:
        ratio = economics_for(self.asset_class).opex_ratio
        for uid in self.upgrades:
            ratio += get_upgrade(uid).opex_ratio_delta
        return max(0.05, ratio)

    def operating(self, market: MarketState) -> OperatingStatement:
        """Full GPR -> EGI -> OpEx -> NOI breakdown for this property.

        Single source of truth for the income math: ``annual_noi`` and the
        education layer's "explain this deal" both read this, so they can never
        drift apart.
        """
        if not self.leased:
            return OperatingStatement(gpr=0.0, egi=0.0, opex=0.0, noi=0.0)
        econ = economics_for(self.asset_class)
        demand_rent = 1.0 + (market.demand_index - 1.0) * econ.demand_sensitivity * 0.5
        gpr = (
            self.units
            * econ.base_monthly_rent_per_unit
            * 12.0
            * self._rent_multiplier()
            * demand_rent
        )
        egi = gpr * (1.0 - self._effective_vacancy(market))
        opex = OperatingExpenses(maintenance=egi * self._opex_ratio()).total
        return OperatingStatement(gpr=gpr, egi=egi, opex=opex, noi=net_operating_income(egi, opex))

    def annual_noi(self, market: MarketState) -> float:
        """NOI through the finance engine — never reimplement the formula here."""
        return self.operating(market).noi

    def market_cap_rate(self, market: MarketState) -> float:
        return market.cap_rate + economics_for(self.asset_class).cap_spread

    def value(self, market: MarketState) -> float:
        """Cap-rate valuation. An unleased asset is valued on stabilized NOI so a
        development still has worth before lease-up."""
        noi = self.annual_noi(market)
        if noi <= 0:
            # Value the stabilized income even pre-lease (a built, empty asset).
            stabilized = replace(self, leased=True)
            noi = stabilized.annual_noi(market)
        return value_from_noi(max(noi, 1.0), self.market_cap_rate(market))

    # ---- transforms (return new instances; Property is immutable) ----

    def with_upgrade(self, upgrade_id: str) -> Property:
        up = get_upgrade(upgrade_id)
        new_condition = up.condition_set if up.condition_set is not None else self.condition
        return replace(
            self,
            upgrades=self.upgrades | {upgrade_id},
            condition=new_condition,
        )

    def leased_up(self) -> Property:
        return replace(self, leased=True)
