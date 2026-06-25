"""Tuned per-asset-class economics — designer-owned balance data.

Starting values for Phase 2. The balance simulator is the tool for tuning these
until each class has a distinct, fair role. Residential is steady and cheap to
run; commercial trades at wider cap rates with thinner vacancy tolerance and
bigger swings.
"""

from __future__ import annotations

from engine.assets.asset_class import AssetClassId, AssetEconomics

ASSET_ECONOMICS: dict[AssetClassId, AssetEconomics] = {
    AssetClassId.SFR: AssetEconomics(
        base_monthly_rent_per_unit=1_600,
        base_vacancy=0.05,
        opex_ratio=0.38,
        cap_spread=0.0,
        build_cost_per_unit=130_000,
        build_months=8,
        demand_sensitivity=0.6,
    ),
    AssetClassId.MULTIFAMILY: AssetEconomics(
        base_monthly_rent_per_unit=1_350,
        base_vacancy=0.06,
        opex_ratio=0.42,
        cap_spread=0.005,
        build_cost_per_unit=92_000,
        build_months=14,
        demand_sensitivity=0.7,
    ),
    AssetClassId.RETAIL: AssetEconomics(
        base_monthly_rent_per_unit=2_400,
        base_vacancy=0.09,
        opex_ratio=0.30,
        cap_spread=0.015,
        build_cost_per_unit=165_000,
        build_months=12,
        demand_sensitivity=1.1,
    ),
    AssetClassId.OFFICE: AssetEconomics(
        base_monthly_rent_per_unit=3_000,
        base_vacancy=0.12,
        opex_ratio=0.35,
        cap_spread=0.02,
        build_cost_per_unit=175_000,
        build_months=18,
        demand_sensitivity=1.3,
    ),
    AssetClassId.INDUSTRIAL: AssetEconomics(
        base_monthly_rent_per_unit=2_000,
        base_vacancy=0.07,
        opex_ratio=0.22,
        cap_spread=0.01,
        build_cost_per_unit=120_000,
        build_months=10,
        demand_sensitivity=0.9,
    ),
    AssetClassId.MIXED_USE: AssetEconomics(
        base_monthly_rent_per_unit=2_100,
        base_vacancy=0.08,
        opex_ratio=0.33,
        cap_spread=0.0125,
        build_cost_per_unit=150_000,
        build_months=16,
        demand_sensitivity=1.0,
    ),
}


def economics_for(asset_class: AssetClassId) -> AssetEconomics:
    return ASSET_ECONOMICS[asset_class]
