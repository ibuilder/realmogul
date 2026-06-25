"""The upgrade tree: spend cash + time to improve a property's economics.

Each upgrade nudges one of the levers the NOI formula already exposes — rent,
vacancy, or opex — so the education layer can explain exactly why an upgrade
paid off. A small, legible catalog for Phase 2; expand per asset class later.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.assets.asset_class import AssetClassId


@dataclass(frozen=True)
class Upgrade:
    """One improvement. Bonuses are multiplicative/additive deltas applied to the
    property's operating math while the upgrade is owned."""

    id: str
    name: str
    cost: float
    build_months: int
    rent_multiplier_bonus: float = 0.0  # +0.10 => +10% rent
    vacancy_delta: float = 0.0  # negative => fewer empty units
    opex_ratio_delta: float = 0.0  # negative => cheaper to run
    condition_set: float | None = None  # renovation can reset condition to e.g. 1.0
    allowed_classes: frozenset[AssetClassId] | None = None  # None => all classes

    def allowed_for(self, asset_class: AssetClassId) -> bool:
        return self.allowed_classes is None or asset_class in self.allowed_classes


_RESIDENTIAL = frozenset({AssetClassId.SFR, AssetClassId.MULTIFAMILY, AssetClassId.MIXED_USE})
_COMMERCIAL = frozenset(
    {AssetClassId.RETAIL, AssetClassId.OFFICE, AssetClassId.INDUSTRIAL, AssetClassId.MIXED_USE}
)

UPGRADE_CATALOG: dict[str, Upgrade] = {
    "renovate": Upgrade(
        id="renovate",
        name="Full Renovation",
        cost=25_000,
        build_months=3,
        rent_multiplier_bonus=0.12,
        condition_set=1.0,
    ),
    "kitchens_baths": Upgrade(
        id="kitchens_baths",
        name="Kitchens & Baths",
        cost=15_000,
        build_months=2,
        rent_multiplier_bonus=0.08,
        allowed_classes=_RESIDENTIAL,
    ),
    "energy_retrofit": Upgrade(
        id="energy_retrofit",
        name="Energy Retrofit",
        cost=20_000,
        build_months=2,
        opex_ratio_delta=-0.05,
    ),
    "amenities": Upgrade(
        id="amenities",
        name="Amenity Package",
        cost=30_000,
        build_months=3,
        vacancy_delta=-0.02,
        rent_multiplier_bonus=0.05,
        allowed_classes=_RESIDENTIAL,
    ),
    "anchor_tenant": Upgrade(
        id="anchor_tenant",
        name="Sign an Anchor Tenant",
        cost=40_000,
        build_months=4,
        vacancy_delta=-0.05,
        rent_multiplier_bonus=0.10,
        allowed_classes=_COMMERCIAL,
    ),
}


def get_upgrade(upgrade_id: str) -> Upgrade:
    return UPGRADE_CATALOG[upgrade_id]
