"""Zoning: what you're allowed to build on a lot.

A zoning change is one of the campaign "twists" — rezone a residential block for
mixed-use and suddenly a new, more valuable play opens up (or a planned one dies).
"""

from __future__ import annotations

from enum import Enum

from engine.assets.asset_class import AssetClassId


class Zoning(str, Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    MIXED = "mixed"

    def allows(self, asset_class: AssetClassId) -> bool:
        if self is Zoning.MIXED:
            return True
        if self is Zoning.RESIDENTIAL:
            return asset_class in {AssetClassId.SFR, AssetClassId.MULTIFAMILY}
        # commercial
        return asset_class.is_commercial
