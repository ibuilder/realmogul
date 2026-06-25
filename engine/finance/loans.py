"""Debt: amortizing mortgages, LTV/DSCR gates, and construction loans.

The construction loan with a financed interest reserve is the single best "you
actually learned something" mechanic in the game — it models the interest-on-
interest circularity from a real development proforma. See
:func:`construction_loan_schedule`.
"""

from __future__ import annotations

from dataclasses import dataclass


def monthly_payment(principal: float, annual_rate: float, term_months: int) -> float:
    """Standard fully-amortizing payment.

    ``M = P * r * (1+r)^n / ((1+r)^n - 1)`` where ``r`` is the monthly rate.
    Handles the zero-interest edge case (straight-line principal).
    """
    if term_months <= 0:
        raise ValueError("term_months must be positive")
    if principal < 0:
        raise ValueError("principal must be non-negative")
    r = annual_rate / 12.0
    if r == 0:
        return principal / term_months
    growth = (1.0 + r) ** term_months
    return principal * r * growth / (growth - 1.0)


def annual_debt_service(principal: float, annual_rate: float, term_months: int) -> float:
    """Twelve monthly payments — the figure DSCR and cash-on-cash use."""
    return monthly_payment(principal, annual_rate, term_months) * 12.0


def remaining_balance(
    principal: float,
    annual_rate: float,
    term_months: int,
    payments_made: int,
) -> float:
    """Outstanding principal after ``payments_made`` payments.

    Drives refinance/cash-out math: equity = value - remaining_balance.
    """
    if payments_made < 0:
        raise ValueError("payments_made must be non-negative")
    if payments_made >= term_months:
        return 0.0
    r = annual_rate / 12.0
    if r == 0:
        return principal * (1.0 - payments_made / term_months)
    pmt = monthly_payment(principal, annual_rate, term_months)
    growth = (1.0 + r) ** payments_made
    return principal * growth - pmt * (growth - 1.0) / r


def max_loan_by_ltv(property_value: float, max_ltv: float) -> float:
    """Largest loan a lender allows by loan-to-value. ``max_ltv`` is a decimal."""
    return property_value * max_ltv


def dscr(noi: float, annual_debt_service_amount: float) -> float:
    """DSCR = NOI / annual debt service. Below ~1.20-1.25, commercial lenders balk."""
    if annual_debt_service_amount == 0:
        raise ValueError("annual_debt_service must be non-zero to compute DSCR")
    return noi / annual_debt_service_amount


def max_loan_by_dscr(
    noi: float,
    annual_rate: float,
    term_months: int,
    min_dscr: float,
) -> float:
    """Largest loan whose debt service keeps DSCR >= ``min_dscr``.

    Inverts the payment formula: find principal such that
    ``NOI / (12 * payment(principal)) == min_dscr``. Since payment is linear in
    principal, this is a direct division.
    """
    if min_dscr <= 0:
        raise ValueError("min_dscr must be positive")
    allowed_annual_ds = noi / min_dscr
    # annual_debt_service is linear in principal, so scale a unit loan's payment.
    unit_ds = annual_debt_service(1.0, annual_rate, term_months)
    return allowed_annual_ds / unit_ds


@dataclass(frozen=True)
class LoanDecision:
    """The lender's verdict, with the binding constraint made explicit so the
    education layer can explain *why* a deal was denied or capped."""

    approved: bool
    max_loan: float
    binding_constraint: str  # "ltv", "dscr", or "denied"


def underwrite(
    *,
    requested_loan: float,
    property_value: float,
    noi: float,
    annual_rate: float,
    term_months: int,
    max_ltv: float,
    min_dscr: float,
) -> LoanDecision:
    """Run both gates and return the most restrictive outcome.

    The player should *feel* a DSCR denial — this surfaces which limit bit.
    """
    ltv_cap = max_loan_by_ltv(property_value, max_ltv)
    dscr_cap = max_loan_by_dscr(noi, annual_rate, term_months, min_dscr)
    ceiling = min(ltv_cap, dscr_cap)
    binding = "ltv" if ltv_cap <= dscr_cap else "dscr"

    if ceiling <= 0:
        return LoanDecision(approved=False, max_loan=0.0, binding_constraint="denied")
    approved_amount = min(requested_loan, ceiling)
    return LoanDecision(approved=True, max_loan=approved_amount, binding_constraint=binding)


@dataclass(frozen=True)
class ConstructionMonth:
    month: int
    draw: float  # hard-cost draw funded this month
    interest: float  # interest accrued this month
    balance: float  # outstanding loan balance at month end


@dataclass(frozen=True)
class ConstructionLoanResult:
    schedule: list[ConstructionMonth]
    total_draws: float  # sum of hard-cost draws
    total_interest: float  # the interest reserve actually consumed
    final_balance: float  # what converts to permanent debt at completion


def construction_loan_schedule(
    draws: list[float],
    annual_rate: float,
    *,
    capitalize_interest: bool = True,
) -> ConstructionLoanResult:
    """Simulate a construction draw schedule with a financed interest reserve.

    The circularity: during construction the project earns nothing, so interest is
    paid from an *interest reserve* that is itself part of the loan. Each month's
    interest is therefore added to the balance and accrues interest next month —
    interest on interest. We resolve it the way a real proforma does: march month
    by month, capitalizing interest as we go.

    Convention: a month's draw is funded at the start of the month, and interest
    accrues on the resulting end-of-month balance.

    Set ``capitalize_interest=False`` to model a borrower paying interest in cash
    each month (no reserve) — useful for teaching the contrast.
    """
    monthly_rate = annual_rate / 12.0
    balance = 0.0
    total_interest = 0.0
    total_draws = 0.0
    schedule: list[ConstructionMonth] = []

    for i, draw in enumerate(draws, start=1):
        balance += draw
        total_draws += draw
        interest = balance * monthly_rate
        total_interest += interest
        if capitalize_interest:
            balance += interest
        schedule.append(ConstructionMonth(month=i, draw=draw, interest=interest, balance=balance))

    return ConstructionLoanResult(
        schedule=schedule,
        total_draws=total_draws,
        total_interest=total_interest,
        final_balance=balance,
    )


@dataclass(frozen=True)
class RefinanceResult:
    new_loan: float
    payoff_old_balance: float
    cash_out: float  # tax-deferred proceeds to the player (can be negative => cash in)


def cash_out_refinance(
    *,
    new_property_value: float,
    old_loan_balance: float,
    max_ltv: float,
    costs: float = 0.0,
) -> RefinanceResult:
    """Pull equity out when value rises. Teaches leverage *and* its risk.

    new_loan = value x max_ltv; cash_out = new_loan - old_balance - costs.
    """
    new_loan = max_loan_by_ltv(new_property_value, max_ltv)
    cash_out = new_loan - old_loan_balance - costs
    return RefinanceResult(
        new_loan=new_loan,
        payoff_old_balance=old_loan_balance,
        cash_out=cash_out,
    )
