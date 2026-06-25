"""Cap-rate valuation and the cash-on-cash return.

The single most important commercial lever: ``value = NOI / cap_rate``. When market
cap rates rise (often because interest rates rose), the same NOI is worth less.
That cascade is the central lesson of the market model — keep it in one obvious
place.
"""

from __future__ import annotations


def cap_rate(noi: float, property_value: float) -> float:
    """cap_rate = NOI / value. The market's required yield on the asset."""
    if property_value == 0:
        raise ValueError("property_value must be non-zero to compute a cap rate")
    return noi / property_value


def value_from_noi(noi: float, market_cap_rate: float) -> float:
    """value = NOI / market_cap_rate. Income capitalized at the market rate."""
    if market_cap_rate <= 0:
        raise ValueError("market_cap_rate must be positive")
    return noi / market_cap_rate


def cash_on_cash(noi: float, annual_debt_service: float, cash_invested: float) -> float:
    """cash_on_cash = (NOI - debt_service) / cash_invested.

    The first-year levered yield on the actual cash the player put in. Negative
    means the property does not cover its mortgage from operations.
    """
    if cash_invested == 0:
        raise ValueError("cash_invested must be non-zero")
    return (noi - annual_debt_service) / cash_invested


def equity_multiple(total_distributions: float, cash_invested: float) -> float:
    """How many times the invested cash came back over the hold (incl. return of capital)."""
    if cash_invested == 0:
        raise ValueError("cash_invested must be non-zero")
    return total_distributions / cash_invested
