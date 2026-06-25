"""IRR / XIRR / NPV against closed-form hand checks, plus solver edge paths."""

from datetime import date

import pytest

from engine.finance.returns import (
    DatedCashflow,
    _has_sign_change,
    _solve_rate,
    irr,
    npv,
    xirr,
)


def test_npv_zero_rate_is_sum():
    assert npv(0.0, [-1000, 500, 700]) == pytest.approx(200)


def test_irr_simple_doubling():
    # -1000 today, +1100 next period -> 10%.
    assert irr([-1000, 1100]) == pytest.approx(0.10, abs=1e-6)


def test_irr_two_period_compound():
    # -1000 now, +1210 in two periods -> 10% (1.1^2 = 1.21).
    assert irr([-1000, 0, 1210]) == pytest.approx(0.10, abs=1e-6)


def test_irr_npv_is_zero_at_solution():
    flows = [-50_000, 12_000, 13_000, 14_000, 30_000]
    rate = irr(flows)
    assert rate is not None
    assert npv(rate, flows) == pytest.approx(0.0, abs=1e-4)


def test_irr_none_without_sign_change():
    assert irr([100, 200, 300]) is None
    assert irr([-100, -200]) is None


def test_has_sign_change_helper():
    assert _has_sign_change([-1, 1])
    assert not _has_sign_change([1, 2, 3])
    assert not _has_sign_change([0, 0])


def test_solver_falls_back_to_bisection_when_newton_stalls():
    # Force Newton to break immediately (derivative 0), exercising the bisection
    # branch deterministically. Root of (x - 0.25) is 0.25, well inside the range.
    root = _solve_rate(lambda r: r - 0.25, lambda r: 0.0, guess=0.1)
    assert root == pytest.approx(0.25, abs=1e-6)


def test_solver_returns_none_when_not_bracketed():
    # Strictly positive everywhere in range -> no root to bracket.
    assert _solve_rate(lambda r: 5.0, lambda r: 0.0, guess=0.1) is None


def test_solver_hits_exact_endpoint():
    # value_fn is zero exactly at the low bracket endpoint.
    assert _solve_rate(lambda r: r - (-0.9999), lambda r: 0.0, guess=0.0) == pytest.approx(-0.9999)


def test_xirr_one_year_matches_irr():
    flows = [
        DatedCashflow(date(2026, 1, 1), -1000),
        DatedCashflow(date(2027, 1, 1), 1100),
    ]
    assert xirr(flows) == pytest.approx(0.10, abs=1e-3)


def test_xirr_needs_two_flows_and_a_sign_change():
    assert xirr([DatedCashflow(date(2026, 1, 1), -1000)]) is None
    assert (
        xirr(
            [
                DatedCashflow(date(2026, 1, 1), 1000),
                DatedCashflow(date(2027, 1, 1), 1100),
            ]
        )
        is None
    )


def test_xirr_irregular_dates_zeroes_npv():
    flows = [
        DatedCashflow(date(2026, 1, 1), -100_000),
        DatedCashflow(date(2026, 6, 15), 20_000),
        DatedCashflow(date(2027, 3, 1), 30_000),
        DatedCashflow(date(2028, 1, 10), 70_000),
    ]
    rate = xirr(flows)
    assert rate is not None
    t0 = flows[0].when
    val = sum(f.amount / (1 + rate) ** ((f.when - t0).days / 365.0) for f in flows)
    assert val == pytest.approx(0.0, abs=1e-2)
