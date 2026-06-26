"""Save migrations: never wipe a player's save on a schema change.

Each migration upgrades a state dict from version N to N+1. The store applies them
in sequence until the save reaches ``SCHEMA_VERSION``. Keep them pure and total:
given any valid version-N state, produce a valid version-(N+1) state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def migrate_1_to_2(state: dict[str, Any]) -> dict[str, Any]:
    """v1 -> v2: the live market gained a ``demand_index`` and sessions gained a
    ``log``. Backfill both with sane defaults so old saves load cleanly."""
    market = state.get("town", {}).get("market", {})
    market.setdefault("demand_index", 1.0)
    state.setdefault("log", [])
    return state


def migrate_2_to_3(state: dict[str, Any]) -> dict[str, Any]:
    """v2 -> v3: owned lots no longer carry their own property snapshot.

    The owned asset is now authoritative only in the holding
    (``holdings[id].property``); the town lot keeping a copy could go stale after
    a renovation/build. Null the listing on every owned lot so old saves obey the
    single-source-of-truth invariant. The holding already holds the live copy, so
    nothing is lost (net worth and income are computed from holdings)."""
    lots = state.get("town", {}).get("lots", {})
    for lot in lots.values():
        if lot.get("owned"):
            lot["property"] = None
    return state


def migrate_3_to_4(state: dict[str, Any]) -> dict[str, Any]:
    """v3 -> v4: gameplay gained worker crews, amenity-driven town appeal, and
    condition decay. Backfill the new fields with neutral defaults so old saves
    load unchanged (3 crews, no appeal, no amenities)."""
    state.setdefault("crews", 3)
    town = state.get("town", {})
    town.setdefault("appeal", 0.0)
    for lot in town.get("lots", {}).values():
        lot.setdefault("amenity", None)
    for holding in state.get("holdings", {}).values():
        for work in holding.get("pending", []):
            work.setdefault("amenity_type", None)
    return state


# version N -> (N+1) transform. Extend as the schema evolves.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    1: migrate_1_to_2,
    2: migrate_2_to_3,
    3: migrate_3_to_4,
}
