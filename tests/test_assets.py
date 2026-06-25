"""Asset economics: NOI/value derivation, upgrades, and demand effects."""

import pytest

from engine.assets.asset_class import AssetClassId
from engine.assets.property import Property
from engine.economy.market import MarketState


def _base_market():
    return MarketState.at_base()


def test_sfr_noi_matches_hand_computation():
    # SFR, 1 unit, condition 1.0, base market (cap 0.06, demand 1.0).
    # gpr = 1600*12 = 19,200; vacancy 0.05 -> egi 18,240; opex 38% -> 6,931.2;
    # NOI = 11,308.8.
    prop = Property(asset_class=AssetClassId.SFR, units=1, condition=1.0)
    assert prop.annual_noi(_base_market()) == pytest.approx(11_308.8, abs=0.1)


def test_value_is_noi_over_cap():
    prop = Property(asset_class=AssetClassId.SFR, units=1, condition=1.0)
    m = _base_market()
    assert prop.value(m) == pytest.approx(prop.annual_noi(m) / m.cap_rate, rel=1e-9)


def test_renovation_raises_rent_and_value():
    base = Property(asset_class=AssetClassId.SFR, units=1, condition=0.85)
    renovated = base.with_upgrade("renovate")
    m = _base_market()
    assert renovated.annual_noi(m) > base.annual_noi(m)
    assert renovated.value(m) > base.value(m)
    assert renovated.condition == 1.0  # renovation resets condition


def test_hot_demand_lifts_noi():
    prop = Property(asset_class=AssetClassId.SFR, units=4, condition=0.9)
    soft = MarketState(interest_rate=0.065, cap_rate=0.06, demand_index=1.0)
    hot = MarketState(interest_rate=0.065, cap_rate=0.06, demand_index=1.5)
    assert prop.annual_noi(hot) > prop.annual_noi(soft)


def test_unleased_property_produces_no_income_but_holds_value():
    prop = Property(asset_class=AssetClassId.RETAIL, units=3, leased=False)
    m = _base_market()
    assert prop.annual_noi(m) == 0.0
    # Still worth something on stabilized income (a built, empty asset has value).
    assert prop.value(m) > 0.0


def test_operating_breakdown_is_single_source_of_truth():
    # operating() must reconcile internally and equal annual_noi (no drift).
    prop = Property(asset_class=AssetClassId.MULTIFAMILY, units=6, condition=0.9)
    m = _base_market()
    op = prop.operating(m)
    assert op.gpr > op.egi > 0
    assert op.egi - op.opex == pytest.approx(op.noi)
    assert op.noi == pytest.approx(prop.annual_noi(m))


def test_unleased_operating_is_all_zero():
    prop = Property(asset_class=AssetClassId.OFFICE, units=2, leased=False)
    op = prop.operating(_base_market())
    assert (op.gpr, op.egi, op.opex, op.noi) == (0.0, 0.0, 0.0, 0.0)


def test_commercial_trades_at_a_wider_cap():
    m = _base_market()
    sfr = Property(asset_class=AssetClassId.SFR, units=1)
    office = Property(asset_class=AssetClassId.OFFICE, units=1)
    assert office.market_cap_rate(m) > sfr.market_cap_rate(m)
