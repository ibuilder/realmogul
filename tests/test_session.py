"""GameSession actions and the turn loop."""

from engine.assets.asset_class import AssetClassId
from engine.progression.campaign import build_level_one, new_session
from engine.world.events import TwistEvent, TwistKind


def test_acquire_spends_cash_and_records_holding():
    s = new_session(build_level_one())
    before = s.cash
    assert s.acquire("sfr-0")
    assert "sfr-0" in s.holdings
    assert s.cash < before
    assert s.town.lots["sfr-0"].owned


def test_cannot_acquire_what_you_cannot_afford():
    s = new_session(build_level_one())
    s.cash = 1_000  # not enough for a down payment + closing
    assert not s.acquire("sfr-0")
    assert "sfr-0" not in s.holdings


def test_upgrade_applies_after_build_months():
    s = new_session(build_level_one())
    s.acquire("sfr-0")
    noi_before = s.holdings["sfr-0"].property_.annual_noi(s.market)
    assert s.upgrade("sfr-0", "renovate")
    # Pending until the renovation finishes (3 months).
    assert s.holdings["sfr-0"].pending
    for _ in range(3):
        s.advance_month()
    h = s.holdings["sfr-0"]
    assert not h.pending
    assert "renovate" in h.property_.upgrades
    assert h.property_.annual_noi(s.market) > noi_before


def test_owned_lot_drops_listing_so_holding_is_single_source():
    """Once a lot is owned, its property lives only in the holding. The town lot
    must not keep advertising a (now stale) listing snapshot — renovation mutates
    the holding, and reading via the town lot must never disagree with it."""
    s = new_session(build_level_one())
    s.acquire("sfr-0")
    # Acquisition strips the listing off the town lot.
    assert s.town.lots["sfr-0"].owned
    assert s.town.lots["sfr-0"].property_ is None
    assert s.holdings["sfr-0"].property_ is not None

    s.upgrade("sfr-0", "renovate")
    for _ in range(3):  # renovation completes after 3 months
        s.advance_month()

    holding_prop = s.holdings["sfr-0"].property_
    assert "renovate" in holding_prop.upgrades
    # The town lot still claims nothing: there is no stale copy to diverge.
    assert s.town.lots["sfr-0"].property_ is None


def test_refinance_pulls_cash_after_value_rises():
    s = new_session(build_level_one())
    s.acquire("sfr-0")
    s.upgrade("sfr-0", "renovate")
    for _ in range(12):
        s.advance_month()
    cash_before = s.cash
    proceeds = s.refinance("sfr-0")
    assert proceeds is not None and proceeds > 0
    assert s.cash > cash_before


def test_sell_removes_holding_and_returns_proceeds():
    s = new_session(build_level_one())
    s.acquire("sfr-0")
    proceeds = s.sell("sfr-0")
    assert proceeds is not None
    assert "sfr-0" not in s.holdings


def test_develop_builds_a_property_on_empty_land():
    s = new_session(build_level_one())
    assert s.develop("land-0", AssetClassId.SFR, 2)
    h = s.holdings["land-0"]
    assert h.property_ is None  # under construction
    for _ in range(8):  # SFR build_months
        s.advance_month()
    h = s.holdings["land-0"]
    assert h.property_ is not None
    assert h.property_.units == 2
    assert h.property_.leased


def test_anchor_leaves_stops_income_until_relet():
    from engine.assets.property import Property
    from engine.progression.session import Holding
    from engine.world.lot import Lot
    from engine.world.zoning import Zoning

    s = new_session(build_level_one())
    # Place a leased retail asset we own, then schedule its anchor to vacate.
    retail = Property(asset_class=AssetClassId.RETAIL, units=2, condition=1.0)
    s.town = s.town.with_lot(
        Lot(id="shop", zoning=Zoning.COMMERCIAL, property_=retail, owned=True, for_sale=False)
    )
    s.holdings["shop"] = Holding(lot_id="shop", property_=retail, loan=None, cash_basis=0.0)
    s.events = [TwistEvent(1, TwistKind.ANCHOR_LEAVES, lot_id="shop", message="Anchor leaves")]

    assert s.holdings["shop"].property_.annual_noi(s.market) > 0
    s.advance_month()
    assert not s.holdings["shop"].property_.leased
    assert s.holdings["shop"].property_.annual_noi(s.market) == 0.0


def test_bankruptcy_is_a_loss():
    s = new_session(build_level_one())
    s.cash = -1.0
    s.advance_month()
    assert s.status == "lost"
