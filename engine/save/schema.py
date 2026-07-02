"""Versioned save schema: convert a live session to/from JSON-safe dicts.

The save captures everything needed to resume a game *identically* — including the
RNG's internal state — so a reload is indistinguishable from never having stopped.
Bump ``SCHEMA_VERSION`` and add a migration (see ``engine/save/migrations``)
whenever this shape changes; never wipe a player's save.
"""

from __future__ import annotations

from typing import Any

from engine.assets.asset_class import AssetClassId
from engine.assets.property import Property
from engine.economy.market import MarketState
from engine.economy_balance.constants import LendingTerms
from engine.progression.advisors import AdvisorId
from engine.progression.objectives import Objective, ObjectiveKind
from engine.progression.opportunities import Opportunity
from engine.progression.session import (
    GameSession,
    Holding,
    LoanPosition,
    PendingWork,
)
from engine.rng import GameRNG
from engine.world.events import TwistEvent, TwistKind
from engine.world.lot import Lot
from engine.world.town import Town
from engine.world.zoning import Zoning

SCHEMA_VERSION = 6


# --------------------------------------------------------------------- encode
def _market_to(m: MarketState) -> dict[str, Any]:
    return {
        "interest_rate": m.interest_rate,
        "cap_rate": m.cap_rate,
        "demand_index": m.demand_index,
        "base_rate": m.base_rate,
    }


def _property_to(p: Property | None) -> dict[str, Any] | None:
    if p is None:
        return None
    return {
        "asset_class": p.asset_class.value,
        "units": p.units,
        "condition": p.condition,
        "age_years": p.age_years,
        "upgrades": sorted(p.upgrades),
        "leased": p.leased,
    }


def _lot_to(lot: Lot) -> dict[str, Any]:
    return {
        "id": lot.id,
        "zoning": lot.zoning.value,
        "property": _property_to(lot.property_),
        "owned": lot.owned,
        "for_sale": lot.for_sale,
        "list_price_premium": lot.list_price_premium,
        "amenity": lot.amenity,
    }


def _loan_to(loan: LoanPosition | None) -> dict[str, Any] | None:
    if loan is None:
        return None
    return {
        "principal": loan.principal,
        "annual_rate": loan.annual_rate,
        "term_months": loan.term_months,
        "origination_month": loan.origination_month,
    }


def _pending_to(w: PendingWork) -> dict[str, Any]:
    return {
        "complete_month": w.complete_month,
        "kind": w.kind,
        "upgrade_id": w.upgrade_id,
        "asset_class": w.asset_class.value if w.asset_class else None,
        "units": w.units,
        "amenity_type": w.amenity_type,
    }


def _holding_to(h: Holding) -> dict[str, Any]:
    return {
        "lot_id": h.lot_id,
        "property": _property_to(h.property_),
        "loan": _loan_to(h.loan),
        "cash_basis": h.cash_basis,
        "pending": [_pending_to(w) for w in h.pending],
    }


def _objective_to(o: Objective) -> dict[str, Any]:
    return {"kind": o.kind.value, "target": o.target, "description": o.description}


def _event_to(e: TwistEvent) -> dict[str, Any]:
    return {
        "month": e.month,
        "kind": e.kind.value,
        "magnitude": e.magnitude,
        "lot_id": e.lot_id,
        "new_zoning": e.new_zoning.value if e.new_zoning else None,
        "message": e.message,
    }


def _rng_to(rng) -> dict[str, Any]:
    version, internal, gauss = rng.getstate()
    return {"seed": rng.seed, "version": version, "internal": list(internal), "gauss_next": gauss}


def _opportunity_to(o: Opportunity) -> dict[str, Any]:
    return {
        "id": o.id,
        "kind": o.kind,
        "expires_month": o.expires_month,
        "headline": o.headline,
        "lot_id": o.lot_id,
        "discount": o.discount,
        "premium": o.premium,
        "asset_class": o.asset_class,
        "units": o.units,
        "condition": o.condition,
    }


def session_to_state(session: GameSession) -> dict[str, Any]:
    """Serialize the full session into a plain dict (the schema body)."""
    rng_version, internal, gauss = session.rng.getstate()
    return {
        "cash": session.cash,
        "month": session.month,
        "month_limit": session.month_limit,
        "crews": session.crews,
        "won": session.won,
        "lost": session.lost,
        "log": list(session.log),
        "opportunities": [_opportunity_to(o) for o in session.opportunities],
        "opportunity_rate": session.opportunity_rate,
        "opp_counter": session._opp_counter,
        "opp_rng": _rng_to(session.opp_rng),
        # Derived levers (career + advisors bake into these) so a reload matches
        # exactly without re-deriving from career/advisor effects.
        "advisors": sorted(a.value for a in session.advisors),
        "decay_mult": session.decay_mult,
        "build_speed": session.build_speed,
        "selling_cost_rate": session.selling_cost_rate,
        "lending": {
            "max_ltv": session.lending.max_ltv,
            "min_dscr": session.lending.min_dscr,
            "term_months": session.lending.term_months,
            "base_spread": session.lending.base_spread,
        },
        "town": {
            "name": session.town.name,
            "market": _market_to(session.town.market),
            "appeal": session.town.appeal,
            "lots": {lid: _lot_to(lot) for lid, lot in session.town.lots.items()},
        },
        "holdings": {lid: _holding_to(h) for lid, h in session.holdings.items()},
        "objectives": [_objective_to(o) for o in session.objectives],
        "events": [_event_to(e) for e in session.events],
        "rng": {
            "seed": session.rng.seed,
            "version": rng_version,
            "internal": list(internal),
            "gauss_next": gauss,
        },
    }


# --------------------------------------------------------------------- decode
def _market_from(d: dict[str, Any]) -> MarketState:
    return MarketState(
        interest_rate=d["interest_rate"],
        cap_rate=d["cap_rate"],
        demand_index=d.get("demand_index", 1.0),
        base_rate=d.get("base_rate"),
    )


def _property_from(d: dict[str, Any] | None) -> Property | None:
    if d is None:
        return None
    return Property(
        asset_class=AssetClassId(d["asset_class"]),
        units=d["units"],
        condition=d["condition"],
        age_years=d["age_years"],
        upgrades=frozenset(d["upgrades"]),
        leased=d["leased"],
    )


def _lot_from(d: dict[str, Any]) -> Lot:
    return Lot(
        id=d["id"],
        zoning=Zoning(d["zoning"]),
        property_=_property_from(d["property"]),
        owned=d["owned"],
        for_sale=d["for_sale"],
        list_price_premium=d["list_price_premium"],
        amenity=d.get("amenity"),
    )


def _loan_from(d: dict[str, Any] | None) -> LoanPosition | None:
    if d is None:
        return None
    return LoanPosition(
        principal=d["principal"],
        annual_rate=d["annual_rate"],
        term_months=d["term_months"],
        origination_month=d["origination_month"],
    )


def _pending_from(d: dict[str, Any]) -> PendingWork:
    ac = d["asset_class"]
    return PendingWork(
        complete_month=d["complete_month"],
        kind=d["kind"],
        upgrade_id=d["upgrade_id"],
        asset_class=AssetClassId(ac) if ac else None,
        units=d["units"],
        amenity_type=d.get("amenity_type"),
    )


def _holding_from(d: dict[str, Any]) -> Holding:
    return Holding(
        lot_id=d["lot_id"],
        property_=_property_from(d["property"]),
        loan=_loan_from(d["loan"]),
        cash_basis=d["cash_basis"],
        pending=tuple(_pending_from(w) for w in d["pending"]),
    )


def _objective_from(d: dict[str, Any]) -> Objective:
    return Objective(
        kind=ObjectiveKind(d["kind"]), target=d["target"], description=d["description"]
    )


def _event_from(d: dict[str, Any]) -> TwistEvent:
    nz = d["new_zoning"]
    return TwistEvent(
        month=d["month"],
        kind=TwistKind(d["kind"]),
        magnitude=d["magnitude"],
        lot_id=d["lot_id"],
        new_zoning=Zoning(nz) if nz else None,
        message=d["message"],
    )


def _opportunity_from(d: dict[str, Any]) -> Opportunity:
    return Opportunity(
        id=d["id"],
        kind=d["kind"],
        expires_month=d["expires_month"],
        headline=d["headline"],
        lot_id=d["lot_id"],
        discount=d.get("discount", 0.0),
        premium=d.get("premium", 0.0),
        asset_class=d.get("asset_class"),
        units=d.get("units", 1),
        condition=d.get("condition", 0.8),
    )


def state_to_session(state: dict[str, Any]) -> GameSession:
    """Rebuild a live session from a (current-version) state dict."""
    town_d = state["town"]
    town = Town(
        name=town_d["name"],
        market=_market_from(town_d["market"]),
        lots={lid: _lot_from(lot) for lid, lot in town_d["lots"].items()},
        appeal=town_d.get("appeal", 0.0),
    )
    rng_d = state["rng"]
    rng = GameRNG.from_state(
        rng_d["seed"],
        (rng_d["version"], tuple(rng_d["internal"]), rng_d["gauss_next"]),
    )
    session = GameSession(
        cash=state["cash"],
        town=town,
        objectives=[_objective_from(o) for o in state["objectives"]],
        month_limit=state["month_limit"],
        events=[_event_from(e) for e in state["events"]],
        rng=rng,
    )
    session.month = state["month"]
    session.crews = state.get("crews", session.crews)
    session.won = state["won"]
    session.lost = state["lost"]
    session.log = list(state["log"])
    session.holdings = {lid: _holding_from(h) for lid, h in state["holdings"].items()}
    session.opportunities = [_opportunity_from(o) for o in state.get("opportunities", [])]
    session.opportunity_rate = state.get("opportunity_rate", 1.0)
    session._opp_counter = state.get("opp_counter", 0)
    opp = state.get("opp_rng")
    if opp is not None:
        session.opp_rng = GameRNG.from_state(
            opp["seed"], (opp["version"], tuple(opp["internal"]), opp["gauss_next"])
        )
    # Restore derived levers (career + advisor effects already baked in).
    session.advisors = {AdvisorId(a) for a in state.get("advisors", [])}
    session.decay_mult = state.get("decay_mult", session.decay_mult)
    session.build_speed = state.get("build_speed", session.build_speed)
    session.selling_cost_rate = state.get("selling_cost_rate", session.selling_cost_rate)
    lend = state.get("lending")
    if lend is not None:
        session.lending = LendingTerms(
            max_ltv=lend["max_ltv"],
            min_dscr=lend["min_dscr"],
            term_months=lend["term_months"],
            base_spread=lend["base_spread"],
        )
    return session
