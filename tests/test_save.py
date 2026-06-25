"""Acceptance: saves round-trip losslessly, detect tampering, and migrate."""

import json

import pytest

from engine.progression.campaign import build_level_one, new_session
from engine.save.schema import SCHEMA_VERSION
from engine.save.store import (
    SaveIntegrityError,
    load_from_dict,
    load_from_json,
    save_to_dict,
    save_to_json,
)


def _mid_game_session():
    s = new_session(build_level_one())
    for _ in range(6):
        s.advance_month()
    s.acquire("sfr-0")
    s.upgrade("sfr-0", "renovate")
    for _ in range(4):
        s.advance_month()
    return s


def test_round_trip_preserves_state():
    s = _mid_game_session()
    restored = load_from_json(save_to_json(s))
    assert restored.cash == s.cash
    assert restored.month == s.month
    assert restored.net_worth() == s.net_worth()
    assert set(restored.holdings) == set(s.holdings)
    assert restored.town.market.demand_index == s.town.market.demand_index


def test_round_trip_preserves_rng_so_future_is_identical():
    s = _mid_game_session()
    restored = load_from_json(save_to_json(s))
    for _ in range(10):
        s.advance_month()
        restored.advance_month()
    assert restored.cash == s.cash
    assert restored.net_worth() == s.net_worth()
    assert restored.log == s.log


def test_envelope_has_version_and_checksum():
    env = save_to_dict(new_session(build_level_one()))
    assert env["version"] == SCHEMA_VERSION
    assert isinstance(env["checksum"], str) and len(env["checksum"]) == 64


def test_tampered_save_is_rejected():
    env = save_to_dict(_mid_game_session())
    env["state"]["cash"] += 1_000_000  # cheat attempt
    with pytest.raises(SaveIntegrityError):
        load_from_dict(env)


def test_v2_save_drops_owned_lot_listing_on_migrate():
    # v2 kept a property snapshot on owned lots; v3 makes the holding the single
    # source of truth. Build a current save (owns + renovated sfr-0), then fake a
    # v2 body where the owned lot still carries a stale listing, and migrate it.
    s = _mid_game_session()
    env = save_to_dict(s)
    state = env["state"]
    assert state["holdings"]["sfr-0"]["property"] is not None
    # Re-introduce the old invariant: a stale listing back on the owned lot.
    state["town"]["lots"]["sfr-0"]["property"] = {
        "asset_class": "sfr",
        "units": 1,
        "condition": 0.5,
        "age_years": 30,
        "upgrades": [],
        "leased": True,
    }
    import hashlib

    canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
    v2_env = {
        "version": 2,
        "checksum": hashlib.sha256(canonical.encode()).hexdigest(),
        "state": state,
    }
    session = load_from_dict(v2_env)
    # Migration nulled the town lot's copy; the holding still has the live one.
    assert session.town.lots["sfr-0"].property_ is None
    assert session.holdings["sfr-0"].property_ is not None


def test_v1_save_migrates_to_current():
    # Build a current save, then strip it back to a plausible v1 shape:
    # no market demand_index, no log. Re-checksum at v1 and load.
    env = save_to_dict(new_session(build_level_one()))
    state = env["state"]
    del state["town"]["market"]["demand_index"]
    state.pop("log", None)
    # Recompute the checksum for the v1 body so integrity passes pre-migration.
    import hashlib

    canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
    v1_env = {
        "version": 1,
        "checksum": hashlib.sha256(canonical.encode()).hexdigest(),
        "state": state,
    }
    session = load_from_dict(v1_env)
    assert session.town.market.demand_index == 1.0  # backfilled by migration
    assert session.log == []
