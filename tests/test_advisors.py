"""Advisors (hireable perks) and the expanded upgrade tree."""

from engine.assets.asset_class import AssetClassId
from engine.assets.property import Property
from engine.assets.upgrades import UPGRADE_CATALOG, get_upgrade
from engine.economy.market import MarketState
from engine.progression.advisors import ADVISORS, AdvisorId
from engine.progression.campaign import build_level_one, new_session
from engine.save.store import load_from_json, save_to_json


def _rich():
    s = new_session(build_level_one())
    s.cash = 500_000
    return s


def test_advisor_roster_complete():
    assert set(ADVISORS) == set(AdvisorId)


def test_manager_slows_decay():
    s = _rich()
    assert s.decay_mult == 1.0
    assert s.hire_advisor(AdvisorId.MANAGER)
    assert s.decay_mult == 0.5
    assert not s.hire_advisor(AdvisorId.MANAGER)  # already on staff


def test_banker_adds_leverage():
    s = _rich()
    before = s.lending.max_ltv
    s.hire_advisor(AdvisorId.BANKER)
    assert s.lending.max_ltv > before


def test_gc_speeds_builds_and_scout_boosts_deals():
    s = _rich()
    s.hire_advisor(AdvisorId.GC)
    assert s.build_speed < 1.0
    s.hire_advisor(AdvisorId.SCOUT)
    assert s.opportunity_rate > 1.0


def test_cannot_afford_advisor():
    s = new_session(build_level_one())
    s.cash = 1_000
    assert not s.hire_advisor(AdvisorId.BANKER)
    assert not s.advisors


def test_advisor_perks_survive_save_load():
    s = _rich()
    s.hire_advisor(AdvisorId.MANAGER)
    s.hire_advisor(AdvisorId.BANKER)
    restored = load_from_json(save_to_json(s))
    assert restored.advisors == {AdvisorId.MANAGER, AdvisorId.BANKER}
    assert restored.decay_mult == 0.5
    assert restored.lending.max_ltv == s.lending.max_ltv


# ----- deeper upgrade tree -----
def test_new_upgrades_are_class_restricted():
    assert not get_upgrade("signage").allowed_for(AssetClassId.SFR)
    assert get_upgrade("signage").allowed_for(AssetClassId.RETAIL)
    assert get_upgrade("co_working").allowed_for(AssetClassId.OFFICE)
    assert not get_upgrade("co_working").allowed_for(AssetClassId.RETAIL)
    assert get_upgrade("loading_dock").allowed_for(AssetClassId.INDUSTRIAL)
    # façade and solar apply to everything
    assert get_upgrade("facade").allowed_for(AssetClassId.SFR)
    assert get_upgrade("solar").allowed_for(AssetClassId.OFFICE)


def test_solar_lowers_opex_and_lifts_noi():
    m = MarketState.at_base()
    base = Property(asset_class=AssetClassId.MULTIFAMILY, units=4, condition=1.0)
    solar = base.with_upgrade("solar")
    assert "solar" in UPGRADE_CATALOG
    assert solar.annual_noi(m) > base.annual_noi(m)  # cheaper to run -> higher NOI
