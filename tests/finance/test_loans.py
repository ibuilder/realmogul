"""Financing math: amortization, LTV/DSCR gates, construction loan, refi."""

import pytest

from engine.finance.loans import (
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


def test_monthly_payment_30yr_6pct():
    # $100,000 at 6% over 360 months -> ~$599.55 (well-known figure).
    assert monthly_payment(100_000, 0.06, 360) == pytest.approx(599.55, abs=0.01)


def test_monthly_payment_zero_interest_is_straight_line():
    assert monthly_payment(120_000, 0.0, 12) == pytest.approx(10_000)


def test_remaining_balance_endpoints():
    # No payments -> full principal; all payments -> zero.
    assert remaining_balance(100_000, 0.06, 360, 0) == pytest.approx(100_000)
    assert remaining_balance(100_000, 0.06, 360, 360) == pytest.approx(0.0)


def test_remaining_balance_decreases():
    bal_12 = remaining_balance(100_000, 0.06, 360, 12)
    bal_24 = remaining_balance(100_000, 0.06, 360, 24)
    assert 0 < bal_24 < bal_12 < 100_000


def test_max_loan_by_ltv():
    assert max_loan_by_ltv(1_000_000, 0.75) == pytest.approx(750_000)


def test_dscr():
    assert dscr(120_000, 100_000) == pytest.approx(1.2)


def test_max_loan_by_dscr_roundtrips():
    # The loan sized to exactly min_dscr should produce that DSCR back.
    noi = 120_000
    loan = max_loan_by_dscr(noi, 0.06, 360, 1.25)
    ds = annual_debt_service(loan, 0.06, 360)
    assert dscr(noi, ds) == pytest.approx(1.25, rel=1e-6)


def test_underwrite_dscr_binds_when_income_is_thin():
    # Generous value (high LTV ceiling) but weak NOI -> DSCR is the binding gate.
    decision = underwrite(
        requested_loan=900_000,
        property_value=1_000_000,
        noi=60_000,
        annual_rate=0.07,
        term_months=360,
        max_ltv=0.80,
        min_dscr=1.25,
    )
    assert decision.approved
    assert decision.binding_constraint == "dscr"
    assert decision.max_loan < 800_000  # capped below the LTV ceiling


def test_underwrite_ltv_binds_when_income_is_strong():
    decision = underwrite(
        requested_loan=900_000,
        property_value=1_000_000,
        noi=200_000,
        annual_rate=0.07,
        term_months=360,
        max_ltv=0.75,
        min_dscr=1.25,
    )
    assert decision.approved
    assert decision.binding_constraint == "ltv"
    assert decision.max_loan == pytest.approx(750_000)


def test_construction_interest_reserve_circularity():
    # Four monthly draws of 100k at 12% annual (1%/mo), interest capitalized.
    # Month 1: balance 100,000; interest 1,000.000; -> 101,000.000
    # Month 2: +100,000 = 201,000; interest 2,010.000; -> 203,010.000
    # Month 3: +100,000 = 303,010; interest 3,030.100; -> 306,040.100
    # Month 4: +100,000 = 406,040.10; interest 4,060.401; -> 410,100.501
    result = construction_loan_schedule([100_000] * 4, 0.12, capitalize_interest=True)
    assert result.total_draws == pytest.approx(400_000)
    assert result.schedule[0].balance == pytest.approx(101_000.0)
    assert result.schedule[1].balance == pytest.approx(203_010.0)
    assert result.schedule[2].balance == pytest.approx(306_040.10, abs=0.01)
    assert result.final_balance == pytest.approx(410_100.501, abs=0.01)
    assert result.total_interest == pytest.approx(10_100.501, abs=0.01)


def test_construction_capitalized_costs_more_than_paid_in_cash():
    capitalized = construction_loan_schedule([100_000] * 6, 0.12, capitalize_interest=True)
    paid_cash = construction_loan_schedule([100_000] * 6, 0.12, capitalize_interest=False)
    # Interest-on-interest makes the financed reserve more expensive.
    assert capitalized.total_interest > paid_cash.total_interest
    assert paid_cash.final_balance == pytest.approx(600_000)


def test_cash_out_refi_pulls_equity_when_value_rises():
    # Value 1.2M, 75% LTV -> 900k new loan; pay off 600k old -> 300k out (minus costs).
    refi = cash_out_refinance(
        new_property_value=1_200_000,
        old_loan_balance=600_000,
        max_ltv=0.75,
        costs=10_000,
    )
    assert refi.new_loan == pytest.approx(900_000)
    assert refi.cash_out == pytest.approx(290_000)
