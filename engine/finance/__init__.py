"""Real Mogul finance engine — pure, deterministic, hand-verifiable money math.

Public surface re-exported here so callers write ``from engine.finance import irr``
style imports without reaching into submodules.
"""

from engine.finance.loans import (
    ConstructionLoanResult,
    ConstructionMonth,
    LoanDecision,
    RefinanceResult,
    annual_debt_service,
    cash_out_refinance,
    construction_loan_schedule,
    dscr,
    max_loan_by_dscr,
    max_loan_by_ltv,
    monthly_payment,
    remaining_balance,
    underwrite,
)
from engine.finance.operating import (
    OperatingExpenses,
    OperatingStatement,
    effective_gross_income,
    gross_potential_rent,
    monthly_to_annual,
    net_operating_income,
    operating_statement,
)
from engine.finance.returns import DatedCashflow, irr, npv, xirr
from engine.finance.valuation import (
    cap_rate,
    cash_on_cash,
    equity_multiple,
    value_from_noi,
)

__all__ = [
    # operating
    "gross_potential_rent",
    "effective_gross_income",
    "net_operating_income",
    "operating_statement",
    "OperatingExpenses",
    "OperatingStatement",
    "monthly_to_annual",
    # valuation
    "cap_rate",
    "value_from_noi",
    "cash_on_cash",
    "equity_multiple",
    # loans
    "monthly_payment",
    "annual_debt_service",
    "remaining_balance",
    "max_loan_by_ltv",
    "dscr",
    "max_loan_by_dscr",
    "underwrite",
    "LoanDecision",
    "construction_loan_schedule",
    "ConstructionLoanResult",
    "ConstructionMonth",
    "cash_out_refinance",
    "RefinanceResult",
    # returns
    "npv",
    "irr",
    "xirr",
    "DatedCashflow",
]
