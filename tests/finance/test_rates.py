"""The rate curve must be deterministic and economically sane."""

from engine.economy.rates import simulate_rate_path
from engine.economy_balance.constants import DEFAULT_MARKET
from engine.rng import GameRNG


def test_rate_path_is_deterministic():
    a = simulate_rate_path(GameRNG(42), 120)
    b = simulate_rate_path(GameRNG(42), 120)
    assert [r.interest_rate for r in a] == [r.interest_rate for r in b]
    assert [r.cap_rate for r in a] == [r.cap_rate for r in b]


def test_rates_stay_positive_and_bounded():
    path = simulate_rate_path(GameRNG(7), 600)
    assert all(r.interest_rate >= 0.005 for r in path)
    assert all(r.cap_rate >= 0.01 for r in path)


def test_cap_rate_tracks_interest_rate():
    # When interest equals the base, cap equals the base cap (1:1 linkage).
    market = DEFAULT_MARKET
    first = simulate_rate_path(GameRNG(1), 1)[0]
    expected = market.base_cap_rate + (first.interest_rate - market.base_interest_rate)
    assert first.cap_rate == max(0.01, expected)


def test_length_matches_request():
    assert len(simulate_rate_path(GameRNG(3), 0)) == 0
    assert len(simulate_rate_path(GameRNG(3), 250)) == 250
