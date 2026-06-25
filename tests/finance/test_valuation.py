"""Cap-rate valuation and cash-on-cash, hand-checked."""

import pytest

from engine.finance.valuation import (
    cap_rate,
    cash_on_cash,
    equity_multiple,
    value_from_noi,
)


def test_cap_rate():
    # 60,000 NOI on a 1,000,000 asset = 6% cap.
    assert cap_rate(60_000, 1_000_000) == pytest.approx(0.06)


def test_value_from_noi():
    # 60,000 NOI at a 6% market cap = 1,000,000 value.
    assert value_from_noi(60_000, 0.06) == pytest.approx(1_000_000)


def test_rate_up_lowers_value():
    # The central lesson: cap rates rise -> same NOI worth less.
    low = value_from_noi(60_000, 0.06)
    high = value_from_noi(60_000, 0.08)
    assert high < low


def test_cash_on_cash():
    # NOI 60k, debt service 45k, cash invested 250k -> (15k / 250k) = 6%.
    assert cash_on_cash(60_000, 45_000, 250_000) == pytest.approx(0.06)


def test_cash_on_cash_negative_when_underwater():
    assert cash_on_cash(40_000, 50_000, 200_000) < 0


def test_equity_multiple():
    assert equity_multiple(375_000, 250_000) == pytest.approx(1.5)


def test_guards():
    with pytest.raises(ValueError):
        cap_rate(60_000, 0)
    with pytest.raises(ValueError):
        value_from_noi(60_000, 0)
    with pytest.raises(ValueError):
        cash_on_cash(60_000, 45_000, 0)
    with pytest.raises(ValueError):
        equity_multiple(100_000, 0)
