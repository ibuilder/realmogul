"""World layer: zoning rules, lot/town transforms, and event perturbations."""

from engine.assets.asset_class import AssetClassId
from engine.economy.market import MarketState
from engine.world.events import TwistEvent, TwistKind
from engine.world.lot import Lot
from engine.world.town import Town
from engine.world.zoning import Zoning


def test_zoning_allows():
    assert Zoning.RESIDENTIAL.allows(AssetClassId.SFR)
    assert not Zoning.RESIDENTIAL.allows(AssetClassId.OFFICE)
    assert Zoning.COMMERCIAL.allows(AssetClassId.RETAIL)
    assert not Zoning.COMMERCIAL.allows(AssetClassId.SFR)
    assert Zoning.MIXED.allows(AssetClassId.SFR)
    assert Zoning.MIXED.allows(AssetClassId.OFFICE)


def test_lot_transforms_are_immutable():
    lot = Lot(id="a", zoning=Zoning.RESIDENTIAL)
    rezoned = lot.rezoned(Zoning.MIXED)
    assert lot.zoning is Zoning.RESIDENTIAL  # original unchanged
    assert rezoned.zoning is Zoning.MIXED
    assert lot.is_empty


def test_town_with_lot_replaces_and_filters():
    town = Town(name="T", market=MarketState.at_base())
    town = town.with_lot(Lot(id="x", zoning=Zoning.RESIDENTIAL, for_sale=True))
    town = town.with_lot(Lot(id="y", zoning=Zoning.COMMERCIAL, owned=True, for_sale=False))
    assert {lot.id for lot in town.lots_for_sale()} == {"x"}
    assert {lot.id for lot in town.owned_lots()} == {"y"}


def test_event_market_perturbations():
    assert TwistEvent(1, TwistKind.RATE_HIKE, magnitude=0.02).market_perturbation() == (0.02, 0.0)
    assert TwistEvent(1, TwistKind.RATE_CUT, magnitude=0.02).market_perturbation() == (-0.02, 0.0)
    assert TwistEvent(1, TwistKind.BOOM_TOWN, magnitude=0.3).market_perturbation() == (0.0, 0.3)
    assert TwistEvent(1, TwistKind.BUST, magnitude=0.3).market_perturbation() == (0.0, -0.3)


def test_zoning_change_event_mutates_town_flag():
    assert TwistEvent(1, TwistKind.ZONING_CHANGE, new_zoning=Zoning.MIXED).mutates_town
    assert not TwistEvent(1, TwistKind.RATE_HIKE).mutates_town
