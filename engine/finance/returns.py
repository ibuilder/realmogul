"""Return metrics on a deal's cash-flow timeline: NPV, IRR, XIRR.

IRR is shown on every exit so flipping vs. holding becomes an informed choice.
A single root-finder (:func:`_solve_rate`) backs both IRR and XIRR: Newton's
method first (fast), then a bracketed bisection fallback (robust on irregular
flows). Everything here is pure and deterministic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

_MAX_ITER = 200
_TOL = 1e-9
_BISECT_LOW = -0.9999  # just above -100%, where discounting blows up
_BISECT_HIGH = 10.0  # 1000% — wider than any sane deal IRR


def npv(rate: float, cashflows: list[float]) -> float:
    """Net present value of period-indexed cashflows (index 0 = today)."""
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))


def _has_sign_change(amounts: list[float]) -> bool:
    signs = [amt > 0 for amt in amounts if amt != 0]
    return any(signs) and not all(signs)


def _solve_rate(
    value_fn: Callable[[float], float],
    deriv_fn: Callable[[float], float],
    guess: float,
) -> float | None:
    """Find ``rate`` where ``value_fn(rate) == 0``.

    Newton's method, falling back to bisection over ``[_BISECT_LOW, _BISECT_HIGH]``
    when Newton stalls (zero derivative or a step past -100%). Returns ``None``
    when the function is not bracketed in that range (no sign change => no root).
    """
    rate = guess
    for _ in range(_MAX_ITER):
        f = value_fn(rate)
        d = deriv_fn(rate)
        if d == 0:
            break
        new_rate = rate - f / d
        if new_rate <= -1.0:
            break
        if abs(new_rate - rate) < _TOL:
            return new_rate
        rate = new_rate

    low, high = _BISECT_LOW, _BISECT_HIGH
    f_low, f_high = value_fn(low), value_fn(high)
    if f_low == 0:
        return low
    if f_high == 0:
        return high
    if f_low * f_high > 0:
        return None  # not bracketed
    for _ in range(_MAX_ITER):
        mid = (low + high) / 2.0
        f_mid = value_fn(mid)
        if abs(f_mid) < _TOL:
            return mid
        if f_low * f_mid < 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2.0


def irr(cashflows: list[float], guess: float = 0.1) -> float | None:
    """Internal rate of return: the discount rate where NPV == 0.

    Returns ``None`` when there is no sign change (no solution) or the solver
    cannot bracket a root — callers should treat that as "not meaningful" rather
    than crashing the sim.
    """
    if not _has_sign_change(cashflows):
        return None

    def value_fn(rate: float) -> float:
        return npv(rate, cashflows)

    def deriv_fn(rate: float) -> float:
        return sum(-t * cf / (1.0 + rate) ** (t + 1) for t, cf in enumerate(cashflows))

    return _solve_rate(value_fn, deriv_fn, guess)


@dataclass(frozen=True)
class DatedCashflow:
    when: date
    amount: float


def xirr(flows: list[DatedCashflow], guess: float = 0.1) -> float | None:
    """IRR for cashflows on arbitrary dates (Actual/365 year fractions).

    Discounts by elapsed days from the first flow; same solver as :func:`irr`.
    """
    if len(flows) < 2:
        return None
    if not _has_sign_change([f.amount for f in flows]):
        return None

    t0 = flows[0].when
    years = [(f.when - t0).days / 365.0 for f in flows]
    amounts = [f.amount for f in flows]

    def value_fn(rate: float) -> float:
        return sum(amt / (1.0 + rate) ** yr for amt, yr in zip(amounts, years, strict=True))

    def deriv_fn(rate: float) -> float:
        return sum(
            -yr * amt / (1.0 + rate) ** (yr + 1.0) for amt, yr in zip(amounts, years, strict=True)
        )

    return _solve_rate(value_fn, deriv_fn, guess)
