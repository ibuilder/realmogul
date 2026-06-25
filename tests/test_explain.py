"""The education layer's explanations must tie out to the engine's own numbers."""

from education.explain import explain_financing, explain_valuation
from engine.assets.asset_class import AssetClassId
from engine.assets.property import Property
from engine.economy.market import MarketState
from engine.finance.loans import LoanDecision


def test_valuation_explanation_ties_to_engine():
    prop = Property(asset_class=AssetClassId.SFR, units=1, condition=0.9)
    market = MarketState.at_base()
    lines = explain_valuation(prop, market)

    by_label = {ln.label: ln for ln in lines}
    # The final "Value" line must equal the engine's value to the dollar.
    assert by_label["Value"].result == f"${prop.value(market):,.0f}"
    assert by_label["Net operating income"].result == f"${prop.annual_noi(market):,.0f}"
    # Every line carries a formula and plugged-in numbers (it's a teaching artifact).
    assert all(ln.formula and ln.plugged for ln in lines)


def test_financing_explanation_includes_dscr_when_levered():
    decision = LoanDecision(approved=True, max_loan=80_000, binding_constraint="dscr")
    lines = explain_financing(
        decision, price=170_000, noi=10_000, annual_debt_service=8_000, cash_invested=95_000
    )
    labels = {ln.label for ln in lines}
    assert {"Lender's max loan", "Down payment", "DSCR", "Cash-on-cash"} <= labels
    dscr_line = next(ln for ln in lines if ln.label == "DSCR")
    assert dscr_line.result == "1.25×"  # 10,000 / 8,000
