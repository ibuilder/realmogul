"""A lot: a buildable parcel that may hold a property and may be for sale."""

from __future__ import annotations

from dataclasses import dataclass, replace

from engine.assets.property import Property
from engine.world.zoning import Zoning


@dataclass(frozen=True)
class Lot:
    """One parcel in a town.

    A lot the player doesn't own may be ``for_sale`` (with a ``list_price``
    premium over intrinsic value). An empty lot (``property_`` is None) can be
    developed if zoning allows.
    """

    id: str
    zoning: Zoning
    property_: Property | None = None
    owned: bool = False
    for_sale: bool = True
    list_price_premium: float = 0.05  # asking price sits this far above intrinsic value
    amenity: str | None = None  # a built civic structure (park/transit/plaza)

    @property
    def is_empty(self) -> bool:
        return self.property_ is None and self.amenity is None

    def with_amenity(self, amenity: str) -> Lot:
        return replace(self, amenity=amenity)

    def rezoned(self, zoning: Zoning) -> Lot:
        return replace(self, zoning=zoning)

    def with_property(self, prop: Property | None) -> Lot:
        return replace(self, property_=prop)

    def acquired(self) -> Lot:
        """Take ownership and drop the listing snapshot.

        Once owned, the asset lives only in ``session.holdings[id].property_`` —
        the single source of truth that renovations, builds, and anchor changes
        mutate. Clearing ``property_`` here means the town lot can never serve a
        stale owned copy; readers must consult the holding (see
        ``GameController._display_property``).
        """
        return replace(self, owned=True, for_sale=False, property_=None)
