"""Operating income math, checked against hand-computed numbers."""

import pytest

from engine.finance.operating import (
    OperatingExpenses,
    effective_gross_income,
    gross_potential_rent,
    net_operating_income,
    operating_statement,
)


def test_gross_potential_rent_sums_units():
    assert gross_potential_rent([1000, 1200, 1500]) == 3700


def test_egi_applies_vacancy_and_other_income():
    # 100,000 GPR, 7% vacancy -> 93,000, plus 2,000 other = 95,000
    assert effective_gross_income(100_000, 0.07, 2_000) == pytest.approx(95_000)


def test_opex_total():
    opex = OperatingExpenses(
        taxes=12_000, insurance=4_000, maintenance=8_000, management=5_000, capex_reserve=5_000
    )
    assert opex.total == 34_000


def test_opex_management_pct_helper():
    # management = 5% of 95,000 EGI = 4,750
    opex = OperatingExpenses.with_management_pct(95_000, 0.05, taxes=12_000)
    assert opex.management == pytest.approx(4_750)
    assert opex.total == pytest.approx(16_750)


def test_noi():
    assert net_operating_income(95_000, 34_000) == 61_000


def test_operating_statement_annualize():
    # Two units at 1,000/mo each = 2,000/mo GPR -> 24,000/yr.
    # 5% vacancy -> 22,800 EGI (no other income). OpEx 8,000 -> NOI 14,800.
    stmt = operating_statement(
        unit_rents=[1_000, 1_000],
        vacancy_rate=0.05,
        expenses=OperatingExpenses(taxes=5_000, maintenance=3_000),
        annualize=True,
    )
    assert stmt.gpr == pytest.approx(24_000)
    assert stmt.egi == pytest.approx(22_800)
    assert stmt.opex == pytest.approx(8_000)
    assert stmt.noi == pytest.approx(14_800)
