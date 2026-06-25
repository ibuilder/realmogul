"""Input-guard and edge-branch coverage for the finance engine."""

import pytest

from engine.finance.loans import (
    construction_loan_schedule,
    dscr,
    max_loan_by_dscr,
    monthly_payment,
    remaining_balance,
    underwrite,
)
from engine.finance.operating import (
    OperatingExpenses,
    monthly_to_annual,
    operating_statement,
)


def test_monthly_payment_rejects_bad_term():
    with pytest.raises(ValueError):
        monthly_payment(100_000, 0.06, 0)


def test_monthly_payment_rejects_negative_principal():
    with pytest.raises(ValueError):
        monthly_payment(-1, 0.06, 360)


def test_remaining_balance_rejects_negative_payments():
    with pytest.raises(ValueError):
        remaining_balance(100_000, 0.06, 360, -1)


def test_remaining_balance_zero_interest_path():
    # Half the term paid on a 0% loan -> half the principal remains.
    assert remaining_balance(120_000, 0.0, 360, 180) == pytest.approx(60_000)


def test_dscr_zero_debt_service_raises():
    with pytest.raises(ValueError):
        dscr(100_000, 0)


def test_max_loan_by_dscr_rejects_nonpositive():
    with pytest.raises(ValueError):
        max_loan_by_dscr(100_000, 0.06, 360, 0)


def test_underwrite_denies_when_no_income():
    # Zero NOI -> DSCR cap is zero -> lender denies outright.
    decision = underwrite(
        requested_loan=500_000,
        property_value=1_000_000,
        noi=0.0,
        annual_rate=0.07,
        term_months=360,
        max_ltv=0.75,
        min_dscr=1.25,
    )
    assert not decision.approved
    assert decision.binding_constraint == "denied"
    assert decision.max_loan == 0.0


def test_construction_loan_zero_rate_has_no_interest():
    result = construction_loan_schedule([50_000, 50_000], 0.0)
    assert result.total_interest == pytest.approx(0.0)
    assert result.final_balance == pytest.approx(100_000)


def test_monthly_to_annual():
    assert monthly_to_annual(1_000) == 12_000


def test_operating_statement_without_annualize_uses_values_as_is():
    stmt = operating_statement(
        unit_rents=[60_000],  # already annual
        vacancy_rate=0.05,
        expenses=OperatingExpenses(taxes=10_000),
        other_income=2_000,
        annualize=False,
    )
    # EGI = 60,000 * 0.95 + 2,000 = 59,000; NOI = 59,000 - 10,000 = 49,000.
    assert stmt.egi == pytest.approx(59_000)
    assert stmt.noi == pytest.approx(49_000)
