"""GameSession: the turn-based engine that ties the world to player decisions.

Holds mutable game state (cash, month, town, holdings) and exposes the player's
verbs: acquire, upgrade, refinance, sell, develop, and advance_month. All money
math defers to ``engine.finance``; all randomness routes through ``GameRNG``; the
whole session is deterministic given a seed, which is what lets a headless script
play a level to victory and what makes saves replayable.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from engine.assets.asset_class import AssetClassId
from engine.assets.property import Property
from engine.assets.upgrades import get_upgrade
from engine.economy.market import MarketState
from engine.economy_balance.asset_economics import economics_for
from engine.economy_balance.constants import (
    DEFAULT_AMENITIES,
    DEFAULT_LENDING,
    DEFAULT_OPPORTUNITIES,
    DEFAULT_UPKEEP,
    DEFAULT_WORKFORCE,
    LendingTerms,
)
from engine.finance.loans import (
    construction_loan_schedule,
    monthly_payment,
    remaining_balance,
    underwrite,
)
from engine.progression.advisors import AdvisorId, get_advisor
from engine.progression.career import Career
from engine.progression.objectives import GameMetrics, Objective, all_met
from engine.progression.opportunities import Opportunity
from engine.rng import GameRNG
from engine.world.events import TwistEvent, TwistKind
from engine.world.lot import Lot
from engine.world.town import Town
from engine.world.zoning import Zoning

CLOSING_COST_RATE = 0.03
SELLING_COST_RATE = 0.06
REFI_COST_RATE = 0.02

# amenity name -> (cash cost, build months, permanent appeal added)
AMENITY_CATALOG: dict[str, tuple[float, int, float]] = {
    name: (cost, months, bonus) for name, cost, months, bonus in DEFAULT_AMENITIES.catalog
}


@dataclass(frozen=True)
class LoanPosition:
    principal: float
    annual_rate: float
    term_months: int
    origination_month: int

    @property
    def monthly_payment(self) -> float:
        return monthly_payment(self.principal, self.annual_rate, self.term_months)

    def balance_at(self, month: int) -> float:
        return remaining_balance(
            self.principal,
            self.annual_rate,
            self.term_months,
            max(0, month - self.origination_month),
        )


@dataclass(frozen=True)
class PendingWork:
    """Construction or upgrade in flight; applied when the month arrives."""

    complete_month: int
    kind: str  # "upgrade" | "build" | "repair" | "amenity"
    upgrade_id: str | None = None
    asset_class: AssetClassId | None = None
    units: int = 0
    amenity_type: str | None = None


@dataclass(frozen=True)
class Holding:
    lot_id: str
    property_: Property | None  # None while under construction
    loan: LoanPosition | None
    cash_basis: float  # equity the player has put in
    pending: tuple[PendingWork, ...] = ()


class GameSession:
    """Mutable game state. Actions return a bool/float and append to the log."""

    def __init__(
        self,
        *,
        cash: float,
        town: Town,
        objectives: list[Objective],
        month_limit: int,
        events: list[TwistEvent] | None = None,
        rng: GameRNG,
        lending: LendingTerms = DEFAULT_LENDING,
        career: Career | None = None,
        starting_crews: int = DEFAULT_WORKFORCE.starting_crews,
    ) -> None:
        self.cash = cash
        self.town = town
        self.crews = starting_crews
        self.objectives = objectives
        self.month_limit = month_limit
        self.events = sorted(events or [], key=lambda e: e.month)
        self.rng = rng
        self.career = career
        # Apply career perks to session-level levers (convenience-shaped, not pay-to-win).
        if career is not None:
            lending = replace(
                lending,
                max_ltv=lending.max_ltv + career.ltv_bonus,
                min_dscr=max(1.0, lending.min_dscr - career.dscr_relief),
            )
        self.lending = lending
        self.selling_cost_rate = career.selling_cost_rate if career else SELLING_COST_RATE
        self.build_speed = career.build_speed if career else 1.0
        self.month = 0
        self.holdings: dict[str, Holding] = {}
        self.log: list[str] = []
        self.won = False
        self.lost = False
        # Random opportunities run on their OWN rng stream so they never perturb
        # the deterministic market path the campaign is balanced against.
        self.opp_rng = rng.fork("opportunities")
        self.opportunities: list[Opportunity] = []
        self._opp_counter = 0
        self.opportunity_rate = 1.0  # advisors can scale how often deals appear
        self.decay_mult = 1.0  # advisors can slow condition decay
        self.advisors: set[AdvisorId] = set()

    # ------------------------------------------------------------------ metrics
    @property
    def market(self) -> MarketState:
        return self.town.market

    @property
    def effective_market(self) -> MarketState:
        """The market that properties actually experience: the live market plus the
        permanent demand lift the player has built via amenities (town.appeal)."""
        if self.town.appeal == 0.0:
            return self.town.market
        return replace(
            self.town.market, demand_index=self.town.market.demand_index + self.town.appeal
        )

    @property
    def busy_crews(self) -> int:
        return sum(len(h.pending) for h in self.holdings.values())

    @property
    def free_crews(self) -> int:
        return max(0, self.crews - self.busy_crews)

    def hire_crew(self) -> bool:
        """Hire another crew so more work can run in parallel. Cost scales with size."""
        cost = DEFAULT_WORKFORCE.hire_cost_base * self.crews
        if cost > self.cash:
            return False
        self.cash -= cost
        self.crews += 1
        self.log.append(f"m{self.month}: hired a crew (now {self.crews})")
        return True

    def hire_advisor(self, advisor_id: AdvisorId) -> bool:
        """Bring a specialist on staff for a one-time fee, applying their perk."""
        if advisor_id in self.advisors:
            return False
        adv = get_advisor(advisor_id)
        if adv.hire_cost > self.cash:
            return False
        self.cash -= adv.hire_cost
        self.advisors.add(advisor_id)
        self.lending = replace(self.lending, max_ltv=self.lending.max_ltv + adv.ltv_bonus)
        self.build_speed *= adv.build_speed_mult
        self.decay_mult *= adv.decay_mult
        self.opportunity_rate *= adv.opportunity_mult
        self.log.append(f"m{self.month}: hired {adv.name} ({adv.role})")
        return True

    def net_worth(self) -> float:
        market = self.effective_market
        equity = 0.0
        for h in self.holdings.values():
            if h.property_ is None:
                equity += h.cash_basis  # building: count the equity put in
                continue
            value = h.property_.value(market)
            balance = h.loan.balance_at(self.month) if h.loan else 0.0
            equity += value - balance
        return self.cash + equity

    def portfolio_noi(self) -> float:
        market = self.effective_market
        return sum(
            h.property_.annual_noi(market)
            for h in self.holdings.values()
            if h.property_ is not None
        )

    def units_owned(self) -> int:
        return sum(h.property_.units for h in self.holdings.values() if h.property_ is not None)

    def metrics(self) -> GameMetrics:
        return GameMetrics(
            cash=self.cash,
            net_worth=self.net_worth(),
            units_owned=self.units_owned(),
            portfolio_noi=self.portfolio_noi(),
            month=self.month,
        )

    @property
    def status(self) -> str:
        if self.won:
            return "won"
        if self.lost:
            return "lost"
        return "playing"

    # ------------------------------------------------------------------ actions
    def acquire(self, lot_id: str) -> bool:
        """Buy a listed property, financed up to the lender's gates."""
        lot = self.town.lots.get(lot_id)
        if lot is None or lot.owned or not lot.for_sale or lot.property_ is None:
            return False
        prop = lot.property_
        value = prop.value(self.effective_market)
        price = value * (1.0 + lot.list_price_premium)
        noi = prop.annual_noi(self.effective_market)
        loan_rate = self.market.interest_rate + self.lending.base_spread

        decision = underwrite(
            requested_loan=price * 0.9,
            property_value=value,  # the lender appraises intrinsic value, not the ask
            noi=noi,
            annual_rate=loan_rate,
            term_months=self.lending.term_months,
            max_ltv=self.lending.max_ltv,
            min_dscr=self.lending.min_dscr,
        )
        loan_amount = decision.max_loan if decision.approved else 0.0
        cash_needed = (price - loan_amount) + price * CLOSING_COST_RATE
        if cash_needed > self.cash:
            return False

        self.cash -= cash_needed
        loan = (
            LoanPosition(loan_amount, loan_rate, self.lending.term_months, self.month)
            if loan_amount > 0
            else None
        )
        self.holdings[lot_id] = Holding(
            lot_id=lot_id, property_=prop, loan=loan, cash_basis=cash_needed
        )
        self.town = self.town.with_lot(lot.acquired())
        self.log.append(
            f"m{self.month}: acquired {lot_id} for {price:,.0f} (loan {loan_amount:,.0f})"
        )
        return True

    def upgrade(self, lot_id: str, upgrade_id: str) -> bool:
        h = self.holdings.get(lot_id)
        if h is None or h.property_ is None:
            return False
        up = get_upgrade(upgrade_id)
        if not up.allowed_for(h.property_.asset_class) or upgrade_id in h.property_.upgrades:
            return False
        if up.cost > self.cash or self.free_crews <= 0:  # needs a free crew
            return False
        self.cash -= up.cost
        work = PendingWork(
            complete_month=self.month + up.build_months, kind="upgrade", upgrade_id=upgrade_id
        )
        self.holdings[lot_id] = replace(h, pending=h.pending + (work,))
        self.log.append(f"m{self.month}: started upgrade '{upgrade_id}' on {lot_id}")
        return True

    def refinance(self, lot_id: str) -> float | None:
        h = self.holdings.get(lot_id)
        if h is None or h.property_ is None:
            return None
        market = self.effective_market
        value_now = h.property_.value(market)
        noi = h.property_.annual_noi(market)
        loan_rate = self.market.interest_rate + self.lending.base_spread
        # A refi is underwritten like any loan: capped by BOTH LTV and DSCR, so the
        # new payment can't exceed what the income covers (no negative-cashflow trap).
        decision = underwrite(
            requested_loan=value_now * self.lending.max_ltv,
            property_value=value_now,
            noi=noi,
            annual_rate=loan_rate,
            term_months=self.lending.term_months,
            max_ltv=self.lending.max_ltv,
            min_dscr=self.lending.min_dscr,
        )
        new_loan_amount = decision.max_loan if decision.approved else 0.0
        old_balance = h.loan.balance_at(self.month) if h.loan else 0.0
        cash_out = new_loan_amount - old_balance - value_now * REFI_COST_RATE
        if cash_out < 0 and -cash_out > self.cash:
            return None
        new_loan = (
            LoanPosition(new_loan_amount, loan_rate, self.lending.term_months, self.month)
            if new_loan_amount > 0
            else None
        )
        self.holdings[lot_id] = replace(h, loan=new_loan)
        self.cash += cash_out
        self.log.append(f"m{self.month}: refinanced {lot_id}, pulled {cash_out:,.0f}")
        return cash_out

    def sell(self, lot_id: str) -> float | None:
        h = self.holdings.get(lot_id)
        if h is None or h.property_ is None:
            return None
        value_now = h.property_.value(self.effective_market)
        payoff = h.loan.balance_at(self.month) if h.loan else 0.0
        proceeds = value_now * (1.0 - self.selling_cost_rate) - payoff
        self.cash += proceeds
        lot = self.town.lots[lot_id]
        self.town = self.town.with_lot(replace(lot, owned=False, for_sale=False))
        del self.holdings[lot_id]
        self.log.append(f"m{self.month}: sold {lot_id} for net {proceeds:,.0f}")
        return proceeds

    def _is_vacant_land(self, lot_id: str) -> bool:
        """Owned land with nothing on it and no work queued.

        Note: an owned lot's town-side ``property_`` is always None (the asset
        lives in the holding), so emptiness is determined by the *absence of a
        holding* plus no amenity — not by ``lot.is_empty``.
        """
        lot = self.town.lots.get(lot_id)
        return lot is not None and lot.owned and lot.amenity is None and lot_id not in self.holdings

    def develop(self, lot_id: str, asset_class: AssetClassId, units: int) -> bool:
        """Start a ground-up build on an owned, empty, correctly-zoned lot.

        Uses a construction loan with a financed interest reserve; the player puts
        down equity equal to (1 - max_ltv) of hard cost.
        """
        lot = self.town.lots.get(lot_id)
        if lot is None or not self._is_vacant_land(lot_id):
            return False
        if not lot.zoning.allows(asset_class):
            return False
        if self.free_crews <= 0:  # construction needs a free crew
            return False
        econ = economics_for(asset_class)
        build_months = max(1, round(econ.build_months * self.build_speed))  # career: build speed
        build_cost = units * econ.build_cost_per_unit
        equity = build_cost * (1.0 - self.lending.max_ltv)
        if equity > self.cash:
            return False
        self.cash -= equity

        loan_rate = self.market.interest_rate + self.lending.base_spread
        financed = build_cost * self.lending.max_ltv
        draws = [financed / build_months] * build_months
        schedule = construction_loan_schedule(draws, loan_rate)
        # The permanent loan at completion equals the construction balance (incl. reserve).
        perm_loan = LoanPosition(
            schedule.final_balance,
            loan_rate,
            self.lending.term_months,
            self.month + build_months,
        )
        work = PendingWork(
            complete_month=self.month + build_months,
            kind="build",
            asset_class=asset_class,
            units=units,
        )
        self.holdings[lot_id] = Holding(
            lot_id=lot_id, property_=None, loan=perm_loan, cash_basis=equity, pending=(work,)
        )
        self.log.append(f"m{self.month}: broke ground on {units}x {asset_class.value} at {lot_id}")
        return True

    def repair(self, lot_id: str) -> bool:
        """Restore a worn building's condition. Cheap and quick, but needs a crew."""
        h = self.holdings.get(lot_id)
        if h is None or h.property_ is None or h.pending:
            return False
        if DEFAULT_UPKEEP.repair_cost > self.cash or self.free_crews <= 0:
            return False
        self.cash -= DEFAULT_UPKEEP.repair_cost
        work = PendingWork(complete_month=self.month + DEFAULT_UPKEEP.repair_months, kind="repair")
        self.holdings[lot_id] = replace(h, pending=h.pending + (work,))
        self.log.append(f"m{self.month}: started repair on {lot_id}")
        return True

    def build_amenity(self, lot_id: str, amenity_type: str) -> bool:
        """Build a civic structure (park/transit/plaza) on owned, empty land.

        On completion it permanently lifts the neighborhood's appeal — firming
        rents and easing vacancy across the whole portfolio. The player's own
        lever on demand (Build-a-Lot's 'appeal', made real)."""
        spec = AMENITY_CATALOG.get(amenity_type)
        lot = self.town.lots.get(lot_id)
        if spec is None or lot is None or not self._is_vacant_land(lot_id):
            return False
        cost, months, _bonus = spec
        if cost > self.cash or self.free_crews <= 0:
            return False
        self.cash -= cost
        work = PendingWork(
            complete_month=self.month + months, kind="amenity", amenity_type=amenity_type
        )
        self.holdings[lot_id] = Holding(
            lot_id=lot_id, property_=None, loan=None, cash_basis=cost, pending=(work,)
        )
        self.log.append(f"m{self.month}: broke ground on a {amenity_type} at {lot_id}")
        return True

    # ------------------------------------------------------------ opportunities
    def _generate_opportunity(self) -> None:
        cfg = DEFAULT_OPPORTUNITIES
        if not self.opp_rng.chance(cfg.per_month_prob * self.opportunity_rate):
            return
        eligible = [
            lid for lid, h in self.holdings.items() if h.property_ is not None and not h.pending
        ]
        self._opp_counter += 1
        oid = f"opp-{self._opp_counter}"
        expires = self.month + cfg.expires_in_months

        if eligible and self.opp_rng.chance(0.5):  # an unsolicited buyout offer
            lot_id = self.opp_rng.choice(eligible)
            premium = self.opp_rng.uniform(*cfg.buyout_premium)
            opp = Opportunity(
                id=oid,
                kind="buyout",
                expires_month=expires,
                headline=f"Buyer offers {premium:.0%} over market for {lot_id}",
                lot_id=lot_id,
                premium=premium,
            )
        else:  # a distressed listing comes to market cheap
            asset_class, units, zoning = self.opp_rng.choice(
                [
                    (AssetClassId.SFR, 1, Zoning.RESIDENTIAL),
                    (AssetClassId.MULTIFAMILY, 4, Zoning.RESIDENTIAL),
                    (AssetClassId.RETAIL, 3, Zoning.COMMERCIAL),
                ]
            )
            condition = self.opp_rng.uniform(0.6, 0.85)
            discount = self.opp_rng.uniform(*cfg.distressed_discount)
            prop = Property(asset_class=asset_class, units=units, condition=condition, age_years=25)
            self.town = self.town.with_lot(
                Lot(id=oid, zoning=zoning, property_=prop, list_price_premium=-discount)
            )
            opp = Opportunity(
                id=oid,
                kind="distressed",
                expires_month=expires,
                headline=f"Distressed {asset_class.value} listed {discount:.0%} below market",
                lot_id=oid,
                discount=discount,
                asset_class=asset_class.value,
                units=units,
                condition=condition,
            )
        self.opportunities.append(opp)
        self.log.append(f"m{self.month}: opportunity — {opp.headline}")

    def accept_opportunity(self, opp_id: str) -> bool:
        opp = next((o for o in self.opportunities if o.id == opp_id), None)
        if opp is None:
            return False
        ok = (
            self.acquire(opp.lot_id)
            if opp.kind == "distressed"
            else self._sell_at_premium(opp.lot_id, opp.premium)
        )
        if ok:
            self.opportunities = [o for o in self.opportunities if o.id != opp_id]
        return ok

    def _sell_at_premium(self, lot_id: str, premium: float) -> bool:
        h = self.holdings.get(lot_id)
        if h is None or h.property_ is None:
            return False
        value = h.property_.value(self.effective_market)
        payoff = h.loan.balance_at(self.month) if h.loan else 0.0
        proceeds = value * (1.0 + premium) - payoff  # a direct offer: no broker fee
        self.cash += proceeds
        lot = self.town.lots[lot_id]
        self.town = self.town.with_lot(replace(lot, owned=False, for_sale=False))
        del self.holdings[lot_id]
        self.log.append(f"m{self.month}: accepted buyout on {lot_id} for {proceeds:,.0f}")
        return True

    def _expire_opportunities(self) -> None:
        still: list[Opportunity] = []
        for o in self.opportunities:
            if o.expires_month > self.month:
                still.append(o)
                continue
            # An unbought distressed listing leaves the market.
            if o.kind == "distressed":
                lot = self.town.lots.get(o.lot_id)
                if lot is not None and not lot.owned:
                    lots = dict(self.town.lots)
                    lots.pop(o.lot_id, None)
                    self.town = replace(self.town, lots=lots)
        self.opportunities = still

    # ------------------------------------------------------------------ turn
    def _apply_events_for(self, month: int) -> tuple[float, float]:
        """Fire events scheduled for ``month``; return aggregate market perturbation."""
        rate_shock = 0.0
        demand_delta = 0.0
        for ev in (e for e in self.events if e.month == month):
            rs, dd = ev.market_perturbation()
            rate_shock += rs
            demand_delta += dd
            if ev.mutates_town:
                self._apply_town_mutation(ev)
            if ev.message:
                self.log.append(f"m{month}: TWIST — {ev.message}")
        return rate_shock, demand_delta

    def _apply_town_mutation(self, ev: TwistEvent) -> None:
        if ev.lot_id is None:
            return
        lot = self.town.lots.get(ev.lot_id)
        if lot is None:
            return
        if ev.kind is TwistKind.ZONING_CHANGE and ev.new_zoning is not None:
            self.town = self.town.with_lot(lot.rezoned(ev.new_zoning))
        elif ev.kind is TwistKind.ANCHOR_LEAVES:
            # Income stops until the space is re-leased (sign a new anchor upgrade).
            # For an owned lot the property lives in the holding (the town lot no
            # longer carries it); an unowned listing keeps its property on the lot.
            h = self.holdings.get(ev.lot_id)
            if h is not None and h.property_ is not None:
                self.holdings[ev.lot_id] = replace(h, property_=replace(h.property_, leased=False))
            if lot.property_ is not None:
                self.town = self.town.with_lot(
                    lot.with_property(replace(lot.property_, leased=False))
                )

    def _complete_due_work(self) -> None:
        for lot_id, h in list(self.holdings.items()):
            if not h.pending:
                continue
            still_pending: list[PendingWork] = []
            prop = h.property_
            completed_amenity: str | None = None
            for work in h.pending:
                if work.complete_month > self.month:
                    still_pending.append(work)
                    continue
                if work.kind == "upgrade" and prop is not None and work.upgrade_id:
                    prop = prop.with_upgrade(work.upgrade_id).leased_up()
                elif work.kind == "build" and work.asset_class is not None:
                    prop = Property(
                        asset_class=work.asset_class,
                        units=work.units,
                        condition=1.0,
                        age_years=0,
                        leased=True,
                    )
                    self.log.append(f"m{self.month}: completed build at {lot_id}")
                elif work.kind == "repair" and prop is not None:
                    prop = replace(prop, condition=DEFAULT_UPKEEP.repair_restores_to)
                    self.log.append(f"m{self.month}: repair complete at {lot_id}")
                elif work.kind == "amenity" and work.amenity_type:
                    completed_amenity = work.amenity_type

            if completed_amenity is not None:
                self._open_amenity(lot_id, completed_amenity)
                continue  # amenity holding is consumed into appeal, not kept
            self.holdings[lot_id] = replace(h, property_=prop, pending=tuple(still_pending))

    def _open_amenity(self, lot_id: str, amenity_type: str) -> None:
        _cost, _months, bonus = AMENITY_CATALOG[amenity_type]
        lot = self.town.lots.get(lot_id)
        if lot is not None:
            self.town = self.town.with_lot(lot.with_amenity(amenity_type))
        self.town = self.town.with_appeal(self.town.appeal + bonus)
        del self.holdings[lot_id]
        self.log.append(f"m{self.month}: {amenity_type} opened — neighborhood appeal up")

    def _decay_conditions(self) -> None:
        for lot_id, h in self.holdings.items():
            if h.property_ is None or h.pending or not h.property_.leased:
                continue
            worn = max(
                DEFAULT_UPKEEP.condition_floor,
                h.property_.condition - DEFAULT_UPKEEP.condition_decay_per_month * self.decay_mult,
            )
            if worn != h.property_.condition:
                self.holdings[lot_id] = replace(h, property_=replace(h.property_, condition=worn))

    def advance_month(self) -> None:
        if self.won or self.lost:
            return
        next_month = self.month + 1
        rate_shock, demand_delta = self._apply_events_for(next_month)

        self.town = self.town.with_market(
            self.market.stepped(self.rng, rate_shock=rate_shock, demand_delta=demand_delta)
        )
        self.month = next_month
        self._complete_due_work()

        # Accrue this month's operating cash flow (demand includes built amenities).
        market = self.effective_market
        for h in self.holdings.values():
            if h.property_ is None:
                continue
            monthly_noi = h.property_.annual_noi(market) / 12.0
            monthly_ds = h.loan.monthly_payment if h.loan else 0.0
            self.cash += monthly_noi - monthly_ds

        self._decay_conditions()
        self._expire_opportunities()
        self._generate_opportunity()
        self._resolve_endgame()

    def _resolve_endgame(self) -> None:
        if self.cash < 0:
            self.lost = True
            self.log.append(f"m{self.month}: BANKRUPT (cash {self.cash:,.0f})")
            return
        if all_met(self.objectives, self.metrics()):
            self.won = True
            self.log.append(f"m{self.month}: WON — objectives met")
            return
        if self.month >= self.month_limit:
            self.lost = True
            self.log.append(f"m{self.month}: TIME UP — objectives not met")
