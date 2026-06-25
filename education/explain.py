"""'Explain this deal' generators — the education moat, in plain Python.

Every number here is pulled straight from the engine's own computation (the
property's operating statement, the finance functions), then shown with the
formula and the player's actual numbers plugged in. Because it reads the same
source the game uses to decide, the explanation can never be out of sync with
what actually happened — that's the whole point.

Pure: imports engine only, no UI. The Kivy layer renders these lines; it does not
compute them.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.assets.property import Property
from engine.economy.market import MarketState
from engine.finance.loans import LoanDecision
from engine.finance.valuation import cash_on_cash


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _pct(x: float) -> str:
    return f"{x:.2%}"


@dataclass(frozen=True)
class ExplainLine:
    """One row of an explanation: a named quantity, its formula, the numbers
    plugged in, and the result. Designed to render as a small table."""

    label: str
    formula: str
    plugged: str
    result: str


def explain_valuation(prop: Property, market: MarketState) -> list[ExplainLine]:
    """Walk GPR -> EGI -> NOI -> cap -> value with this property's live numbers."""
    op = prop.operating(market)
    cap = prop.market_cap_rate(market)
    value = prop.value(market)
    return [
        ExplainLine(
            "Gross potential rent",
            "units × rent × 12 months",
            f"{prop.units} unit(s) at market rent, condition {prop.condition:.0%}",
            _money(op.gpr),
        ),
        ExplainLine(
            "Effective gross income",
            "GPR × (1 − vacancy)",
            f"{_money(op.gpr)} less vacancy",
            _money(op.egi),
        ),
        ExplainLine(
            "Operating expenses",
            "EGI × opex ratio",
            "taxes, insurance, maintenance, mgmt, reserves",
            _money(op.opex),
        ),
        ExplainLine(
            "Net operating income",
            "EGI − OpEx",
            f"{_money(op.egi)} − {_money(op.opex)}",
            _money(op.noi),
        ),
        ExplainLine(
            "Market cap rate",
            "market rate + class spread",
            "what buyers demand as a yield",
            _pct(cap),
        ),
        ExplainLine(
            "Value",
            "NOI ÷ cap rate",
            f"{_money(op.noi)} ÷ {_pct(cap)}",
            _money(value),
        ),
    ]


def explain_financing(
    decision: LoanDecision,
    *,
    price: float,
    noi: float,
    annual_debt_service: float,
    cash_invested: float,
) -> list[ExplainLine]:
    """Explain how the lender sized the loan and what the deal returns on cash."""
    lines = [
        ExplainLine(
            "Lender's max loan",
            "min(LTV cap, DSCR cap)",
            f"bound by {decision.binding_constraint.upper()}",
            _money(decision.max_loan),
        ),
        ExplainLine(
            "Down payment",
            "price − loan",
            f"{_money(price)} − {_money(decision.max_loan)}",
            _money(price - decision.max_loan),
        ),
    ]
    if annual_debt_service > 0:
        lines.append(
            ExplainLine(
                "DSCR",
                "NOI ÷ annual debt service",
                f"{_money(noi)} ÷ {_money(annual_debt_service)}",
                f"{noi / annual_debt_service:.2f}×",
            )
        )
    if cash_invested > 0:
        coc = cash_on_cash(noi, annual_debt_service, cash_invested)
        lines.append(
            ExplainLine(
                "Cash-on-cash",
                "(NOI − debt service) ÷ cash in",
                f"({_money(noi)} − {_money(annual_debt_service)}) ÷ {_money(cash_invested)}",
                _pct(coc),
            )
        )
    return lines
