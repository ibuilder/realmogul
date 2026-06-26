"""GameController: the thin presenter between GameSession and the Kivy views.

Deliberately Kivy-free so it can be unit-tested headlessly and so the views stay
dumb (they render view-models and forward taps). Imports engine + education only —
never Kivy. This is what keeps "UI is thin" honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from education.assessment import ConceptTracker
from education.explain import ExplainLine, explain_financing, explain_valuation
from education.glossary import GlossaryTerm, all_terms, get_term, search
from education.mentors import MentorTip, tip_for
from education.mistakes import (
    LessonCard,
    bankruptcy_card,
    dscr_denial_card,
    negative_cashflow_card,
    time_up_card,
    underwater_card,
)
from engine.assets.asset_class import AssetClassId
from engine.finance.loans import LoanDecision, annual_debt_service, underwrite
from engine.progression.campaign import CampaignLevel, new_session
from engine.progression.session import CLOSING_COST_RATE, GameSession
from engine.world.events import TwistKind

# Deal-panel row labels (which may carry a parenthetical) -> glossary concept id,
# so tapping any metric opens its plain-English term.
_METRIC_TERMS: dict[str, str] = {
    "Cap rate": "cap_rate",
    "NOI / yr": "noi",
    "Value": "value",
    "Asking price": "value",
    "Loan": "leverage",
    "Cash to close": "leverage",
    "Cash flow / mo": "cash_on_cash",
    "Loan balance": "amortization",
    "Equity": "equity",
    "Condition": "value_add",
    "Upgrades": "value_add",
    "Zoning": "zoning",
}


def money(x: float) -> str:
    return f"${x:,.0f}"


def pct(x: float) -> str:
    return f"{x:.2%}"


@dataclass(frozen=True)
class TileView:
    lot_id: str
    col: int
    row: int
    top_label: str
    owned: bool
    for_sale: bool
    empty: bool
    selected: bool
    pending_label: str
    heat: float  # 0..1, drives fill brightness
    asset_class: str | None = None  # e.g. "sfr" (None for empty land)
    condition: float = 1.0
    storeys: int = 1
    lit: bool = True  # leased/occupied -> windows glow
    value: float = 0.0


@dataclass(frozen=True)
class HudView:
    month: int
    month_limit: int
    cash: str
    net_worth: str
    objective: str
    progress: float  # 0..1 toward the (first) objective
    status: str  # playing | won | lost
    message: str
    crews: str = ""  # "free/total" worker crews


@dataclass(frozen=True)
class ActionView:
    action_id: str
    label: str
    enabled: bool
    hint: str = ""


@dataclass(frozen=True)
class DealView:
    title: str
    subtitle: str
    rows: list[tuple[str, str]] = field(default_factory=list)
    actions: list[ActionView] = field(default_factory=list)


@dataclass(frozen=True)
class FinancePreview:
    price: float
    decision: LoanDecision
    loan: float
    annual_ds: float
    cash_needed: float
    monthly_cash_flow: float


class GameController:
    def __init__(self, level: CampaignLevel) -> None:
        self.level = level
        self.session: GameSession = new_session(level)
        self.selected_lot_id: str | None = None
        self.message: str = "Tap a lot to scout a deal."
        # --- education state ---
        self.tracker = ConceptTracker()
        self.coach: MentorTip | None = None
        self.lesson: LessonCard | None = None
        self._seen_first_deal = False
        self._bought_any = False
        self._celebrated_renovations: set[str] = set()
        self._flagged_negative: set[str] = set()

    def _display_property(self, lot):
        """The property to *show* for a lot.

        For an owned lot the holding is the single source of truth (renovations
        mutate the holding, not the original town listing). For an unowned lot the
        town's listing is what's for sale.
        """
        holding = self.session.holdings.get(lot.id)
        if lot.owned and holding is not None and holding.property_ is not None:
            return holding.property_
        return lot.property_

    # -------------------------------------------------------------- layout
    def _layout(self) -> dict[str, tuple[int, int]]:
        """Assign each lot a grid position deterministically (3 columns)."""
        positions: dict[str, tuple[int, int]] = {}
        for i, lot_id in enumerate(sorted(self.session.town.lots)):
            positions[lot_id] = (i % 3, i // 3)
        return positions

    def board(self) -> list[TileView]:
        positions = self._layout()
        tiles: list[TileView] = []
        market = self.session.effective_market
        for lot_id, lot in sorted(self.session.town.lots.items()):
            col, row = positions[lot_id]
            holding = self.session.holdings.get(lot_id)
            pending_label = ""
            if holding and holding.pending:
                months_left = max(p.complete_month for p in holding.pending) - self.session.month
                pending_label = f"build {months_left}mo"

            display_prop = self._display_property(lot)
            asset_class: str | None = None
            condition = 1.0
            storeys = 1
            lit = True
            value = 0.0
            if display_prop is not None:
                value = display_prop.value(market)
                top = money(value)
                heat = min(1.0, value / 220_000)
                empty = False
                asset_class = display_prop.asset_class.value
                condition = display_prop.condition
                storeys = self._storeys(display_prop)
                lit = display_prop.leased
            elif holding is not None:  # owned land under construction
                top = pending_label or "building"
                heat = 0.4
                empty = True
            else:
                top = "land"
                heat = 0.2
                empty = True

            tiles.append(
                TileView(
                    lot_id=lot_id,
                    col=col,
                    row=row,
                    top_label=top,
                    owned=lot.owned,
                    for_sale=lot.for_sale and not lot.owned,
                    empty=empty,
                    selected=(lot_id == self.selected_lot_id),
                    pending_label=pending_label,
                    heat=heat,
                    asset_class=asset_class,
                    condition=condition,
                    storeys=storeys,
                    lit=lit,
                    value=value,
                )
            )
        return tiles

    @staticmethod
    def _storeys(prop) -> int:
        base = {
            "sfr": 1,
            "multifamily": 3,
            "retail": 1,
            "office": 4,
            "industrial": 1,
            "mixed_use": 3,
        }.get(prop.asset_class.value, 1)
        return base + len(prop.upgrades)  # upgrades add visible height

    # -------------------------------------------------------------- hud
    def hud(self) -> HudView:
        s = self.session
        obj = s.objectives[0] if s.objectives else None
        m = s.metrics()
        progress = 0.0
        objective = "—"
        if obj is not None:
            objective = obj.description or f"{obj.kind.value}: {money(obj.target)}"
            progress = max(0.0, min(1.0, m.net_worth / obj.target)) if obj.target else 0.0
        return HudView(
            month=s.month,
            month_limit=s.month_limit,
            cash=money(s.cash),
            net_worth=money(m.net_worth),
            objective=objective,
            progress=progress,
            status=s.status,
            message=self.message,
            crews=f"{s.free_crews}/{s.crews}",
        )

    @staticmethod
    def _work_hint(busy: bool, free_crew: bool) -> str:
        if busy:
            return "already working here"
        if not free_crew:
            return "no free crew"
        return ""

    # -------------------------------------------------------------- finance preview
    def _finance_preview(self, lot_id: str) -> FinancePreview | None:
        lot = self.session.town.lots.get(lot_id)
        if lot is None or lot.property_ is None:
            return None
        prop = lot.property_
        market = self.session.market
        lending = self.session.lending
        value = prop.value(market)
        price = value * (1.0 + lot.list_price_premium)
        noi = prop.annual_noi(market)
        rate = market.interest_rate + lending.base_spread
        decision = underwrite(
            requested_loan=price * 0.9,
            property_value=value,
            noi=noi,
            annual_rate=rate,
            term_months=lending.term_months,
            max_ltv=lending.max_ltv,
            min_dscr=lending.min_dscr,
        )
        loan = decision.max_loan if decision.approved else 0.0
        ds = annual_debt_service(loan, rate, lending.term_months) if loan > 0 else 0.0
        cash_needed = (price - loan) + price * CLOSING_COST_RATE
        return FinancePreview(
            price=price,
            decision=decision,
            loan=loan,
            annual_ds=ds,
            cash_needed=cash_needed,
            monthly_cash_flow=noi / 12.0 - ds / 12.0,
        )

    # -------------------------------------------------------------- deal panel
    def selected_deal(self) -> DealView | None:
        lid = self.selected_lot_id
        if lid is None:
            return None
        lot = self.session.town.lots.get(lid)
        if lot is None:
            return None
        market = self.session.effective_market  # includes amenity-driven demand
        holding = self.session.holdings.get(lid)

        # Owned, built property.
        if lot.owned and holding is not None and holding.property_ is not None:
            prop = holding.property_
            balance = holding.loan.balance_at(self.session.month) if holding.loan else 0.0
            value = prop.value(market)
            ds = holding.loan.monthly_payment * 12 if holding.loan else 0.0
            rows = [
                ("Asset", f"{prop.asset_class.value.upper()} · {prop.units} unit(s)"),
                ("Condition", f"{prop.condition:.0%}"),
                ("Upgrades", ", ".join(sorted(prop.upgrades)) or "none"),
                ("NOI / yr", money(prop.annual_noi(market))),
                ("Value", money(value)),
                ("Loan balance", money(balance)),
                ("Equity", money(value - balance)),
                ("Cash flow / mo", money(prop.annual_noi(market) / 12 - ds / 12)),
            ]
            busy = bool(holding.pending)
            free_crew = self.session.free_crews > 0
            ready = not busy and free_crew
            can_renovate = ready and "renovate" in self._affordable_upgrades(prop)
            worn = prop.condition < 0.94
            can_repair = ready and worn and self.session.cash >= 9_000
            actions = [
                ActionView(
                    "renovate",
                    "Renovate ($25k, 3mo)",
                    can_renovate,
                    self._work_hint(busy, free_crew),
                ),
                ActionView(
                    "repair",
                    "Repair ($9k, 1mo)",
                    can_repair,
                    "" if worn else "in good shape",
                ),
                ActionView("refinance", "Cash-out refi", True),
                ActionView("sell", "Sell", True),
            ]
            return DealView(
                title=lid.upper(),
                subtitle="You own this",
                rows=rows,
                actions=actions,
            )

        # Owned vacant land.
        if self.session._is_vacant_land(lid):
            free_crew = self.session.free_crews > 0
            return DealView(
                title=lid.upper(),
                subtitle=f"Vacant land · {lot.zoning.value}",
                rows=[("Zoning", lot.zoning.value), ("Status", "ready to build")],
                actions=[
                    ActionView(
                        "develop", "Build 1 SFR", free_crew, self._work_hint(False, free_crew)
                    ),
                    ActionView(
                        "amenity_park",
                        "Build park ($35k)",
                        free_crew and self.session.cash >= 35_000,
                        "lifts demand portfolio-wide",
                    ),
                ],
            )

        # For-sale property.
        if lot.for_sale and lot.property_ is not None:
            prop = lot.property_
            fp = self._finance_preview(lid)
            assert fp is not None
            rows = [
                ("Asset", f"{prop.asset_class.value.upper()} · {prop.units} unit(s)"),
                ("Condition", f"{prop.condition:.0%}"),
                ("NOI / yr", money(prop.annual_noi(market))),
                ("Cap rate", pct(prop.market_cap_rate(market))),
                ("Value", money(prop.value(market))),
                ("Asking price", money(fp.price)),
                (f"Loan ({fp.decision.binding_constraint})", money(fp.loan)),
                ("Cash to close", money(fp.cash_needed)),
                ("Cash flow / mo", money(fp.monthly_cash_flow)),
            ]
            affordable = fp.cash_needed <= self.session.cash
            actions = [
                ActionView(
                    "buy",
                    f"Buy ({money(fp.cash_needed)} down)",
                    affordable,
                    "" if affordable else "not enough cash",
                )
            ]
            return DealView(
                title=lid.upper(),
                subtitle="For sale",
                rows=rows,
                actions=actions,
            )
        return None

    def _affordable_upgrades(self, prop) -> set[str]:
        from engine.assets.upgrades import UPGRADE_CATALOG

        out = set()
        for uid, up in UPGRADE_CATALOG.items():
            affordable = up.cost <= self.session.cash
            if up.allowed_for(prop.asset_class) and uid not in prop.upgrades and affordable:
                out.add(uid)
        return out

    # -------------------------------------------------------------- explain
    def explain_lines(self) -> list[ExplainLine]:
        lid = self.selected_lot_id
        if lid is None:
            return []
        lot = self.session.town.lots.get(lid)
        if lot is None:
            return []
        prop = self._display_property(lot)
        if prop is None:
            return []
        lines = explain_valuation(prop, self.session.market)
        fp = self._finance_preview(lid)
        if fp is not None and not lot.owned:
            lines = lines + explain_financing(
                fp.decision,
                price=fp.price,
                noi=prop.annual_noi(self.session.market),
                annual_debt_service=fp.annual_ds,
                cash_invested=fp.cash_needed,
            )
        return lines

    # -------------------------------------------------------------- education access
    def coach_tip(self) -> MentorTip | None:
        return self.coach

    def current_lesson(self) -> LessonCard | None:
        return self.lesson

    def dismiss_lesson(self) -> None:
        self.lesson = None

    def mastery(self) -> float:
        return self.tracker.mastery_fraction()

    def next_concept_term(self) -> GlossaryTerm | None:
        nxt = self.tracker.next_concept()
        return get_term(nxt) if nxt else None

    def glossary(self, query: str = "") -> list[GlossaryTerm]:
        return search(query) if query else all_terms()

    def term_for_metric(self, row_label: str) -> GlossaryTerm | None:
        """Map a deal-panel row label (e.g. 'Loan (dscr)') to its glossary term."""
        key = row_label.split(" (")[0].strip()
        term_id = _METRIC_TERMS.get(key)
        # A parenthetical like 'Loan (dscr)' should prefer the more specific term.
        if "(" in row_label and "dscr" in row_label:
            term_id = "dscr"
        elif "(" in row_label and "ltv" in row_label:
            term_id = "ltv"
        return get_term(term_id) if term_id else None

    # -------------------------------------------------------------- commands
    def select(self, lot_id: str) -> None:
        self.selected_lot_id = lot_id
        lot = self.session.town.lots.get(lot_id)
        if not self._seen_first_deal and lot is not None and lot.for_sale and lot.property_:
            self.coach = tip_for("first_deal")
            self._seen_first_deal = True

    def hire_crew(self) -> None:
        if self.session.hire_crew():
            self.message = f"Hired a crew — now {self.session.crews}."
        else:
            self.message = "Can't afford another crew."

    def do_action(self, action_id: str) -> None:
        lid = self.selected_lot_id
        if lid is None:
            return
        if action_id == "buy":
            self._do_buy(lid)
        elif action_id == "repair":
            self.message = (
                "Repair started — restoring condition."
                if self.session.repair(lid)
                else "Can't repair now."
            )
        elif action_id == "amenity_park":
            if self.session.build_amenity(lid, "park"):
                self.tracker.record("demand")
                self.coach = tip_for("boom_town")
                self.message = "Park underway — it'll lift demand everywhere."
            else:
                self.message = "Can't build a park here."
        elif action_id == "renovate":
            if self.session.upgrade(lid, "renovate"):
                self.tracker.record("value_add")
                self.message = "Renovation started — forcing NOI up."
            else:
                self.message = "Can't renovate now."
        elif action_id == "refinance":
            proceeds = self.session.refinance(lid)
            if proceeds:
                self.tracker.record("refinance", "cash_out_refi", "equity")
                self.coach = tip_for("refi_available")
                self.message = f"Pulled {money(proceeds)} tax-deferred."
            else:
                self.message = "Refi not available."
        elif action_id == "sell":
            proceeds = self.session.sell(lid)
            if proceeds is not None:
                self.tracker.record("irr")
                self.message = f"Sold for {money(proceeds)} net."
                self.selected_lot_id = None
        elif action_id == "develop":
            if self.session.develop(lid, AssetClassId.SFR, 1):
                self.tracker.record("construction_loan", "interest_reserve")
                self.coach = tip_for("developing")
                self.message = "Broke ground on 1 SFR."
            else:
                self.message = "Can't build here."

    def _do_buy(self, lid: str) -> None:
        fp = self._finance_preview(lid)
        if self.session.acquire(lid):
            self.tracker.record("noi", "cap_rate", "value")
            if fp and fp.loan > 0:
                self.tracker.record("leverage", "dscr")
            if not self._bought_any:
                self.coach = tip_for("bought_first")
                self._bought_any = True
            self.message = "Bought the property."
        elif fp is not None and not fp.decision.approved:
            noi = self.session.town.lots[lid].property_.annual_noi(self.session.market)
            self.lesson = dscr_denial_card(noi, noi / self.session.lending.min_dscr)
            self.coach = tip_for("dscr_denied")
            self.message = "Loan denied."
        else:
            self.message = "Can't afford that."

    def advance_month(self) -> None:
        next_month = self.session.month + 1
        fired = [e for e in self.session.events if e.month == next_month]
        self.session.advance_month()
        self._coach_from_events(fired)
        self._coach_from_completions()
        self._detect_problems()
        self._resolve_endgame_coaching()

    def _coach_from_events(self, fired) -> None:
        for e in fired:
            if e.kind is TwistKind.RATE_HIKE:
                self.coach = tip_for("rate_spike")
            elif e.kind is TwistKind.BOOM_TOWN:
                self.coach = tip_for("boom_town")

    def _coach_from_completions(self) -> None:
        for lot_id, h in self.session.holdings.items():
            if (
                h.property_ is not None
                and "renovate" in h.property_.upgrades
                and lot_id not in self._celebrated_renovations
            ):
                self._celebrated_renovations.add(lot_id)
                self.coach = tip_for("renovation_done")

    def _detect_problems(self) -> None:
        market = self.session.market
        month = self.session.month
        for lot_id, h in self.session.holdings.items():
            if h.property_ is None or h.loan is None:
                continue
            monthly = h.property_.annual_noi(market) / 12 - h.loan.monthly_payment
            if monthly < -1 and lot_id not in self._flagged_negative:
                self._flagged_negative.add(lot_id)
                self.lesson = negative_cashflow_card(lot_id, monthly)
                self.coach = tip_for("negative_cashflow")
                return
            value = h.property_.value(market)
            balance = h.loan.balance_at(month)
            if value < balance:
                self.lesson = underwater_card(lot_id, value, balance)
                return

    def _resolve_endgame_coaching(self) -> None:
        s = self.session
        if s.status == "won":
            self.coach = tip_for("won")
            self.message = "You hit the objective — level complete!"
        elif s.status == "lost":
            self.coach = tip_for("lost")
            obj = s.objectives[0] if s.objectives else None
            target = obj.target if obj else 0.0
            self.lesson = bankruptcy_card() if s.cash < 0 else time_up_card(s.net_worth(), target)
            self.message = "Out of time or bankrupt. Level over."
        else:
            self.message = f"Month {s.month}."

    @property
    def status(self) -> str:
        return self.session.status
