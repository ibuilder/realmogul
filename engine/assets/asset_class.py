"""Asset-class identity and the shape of its economics.

Six classes spanning residential and commercial. The *structure* lives here; the
tuned *numbers* live in ``engine/economy_balance/asset_economics.py`` so designers
own balance in one place (see CLAUDE.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AssetClassId(str, Enum):
    SFR = "sfr"  # single-family rental
    MULTIFAMILY = "multifamily"
    RETAIL = "retail"
    OFFICE = "office"
    INDUSTRIAL = "industrial"
    MIXED_USE = "mixed_use"

    @property
    def is_commercial(self) -> bool:
        return self in {
            AssetClassId.RETAIL,
            AssetClassId.OFFICE,
            AssetClassId.INDUSTRIAL,
            AssetClassId.MIXED_USE,
        }


@dataclass(frozen=True)
class AssetEconomics:
    """Tuned economic parameters for one asset class.

    - ``base_monthly_rent_per_unit``: starting market rent per unit.
    - ``base_vacancy``: structural vacancy before demand effects.
    - ``opex_ratio``: operating expenses as a fraction of EGI.
    - ``cap_spread``: added to the market cap rate (commercial trades wider).
    - ``build_cost_per_unit`` / ``build_months``: development economics.
    - ``demand_sensitivity``: how strongly neighborhood demand moves its rent.
    """

    base_monthly_rent_per_unit: float
    base_vacancy: float
    opex_ratio: float
    cap_spread: float
    build_cost_per_unit: float
    build_months: int
    demand_sensitivity: float
