"""'While you were away' offline earnings + save timestamp metadata."""

import json

from engine.economy_balance.constants import OfflineDefaults
from engine.progression.campaign import build_level_one, new_session
from engine.progression.offline import compute_offline_earnings
from engine.save.store import load_from_dict, save_to_dict, save_to_json, saved_at_of

CFG = OfflineDefaults(real_seconds_per_game_month=3600.0, max_months_credited=6.0)


def _owning_session():
    s = new_session(build_level_one())
    s.acquire("sfr-2")
    return s


def test_no_time_away_no_earnings():
    s = _owning_session()
    assert compute_offline_earnings(s, 0.0, CFG).amount == 0.0


def test_earnings_scale_with_time_and_cash_flow():
    s = _owning_session()
    monthly = s.monthly_cash_flow()
    assert monthly > 0
    # Two hours away == two game months of rent (below the cap).
    result = compute_offline_earnings(s, 2 * 3600.0, CFG)
    assert result.months_credited == 2.0
    assert result.amount == monthly * 2.0
    assert result.worthwhile


def test_earnings_are_capped():
    s = _owning_session()
    monthly = s.monthly_cash_flow()
    # A week away still only credits the 6-month cap.
    result = compute_offline_earnings(s, 7 * 24 * 3600.0, CFG)
    assert result.months_credited == 6.0
    assert result.amount == monthly * 6.0


def test_no_holdings_means_no_offline_income():
    s = new_session(build_level_one())  # nothing bought
    assert compute_offline_earnings(s, 10 * 3600.0, CFG).amount == 0.0


def test_negative_cash_flow_never_punishes():
    s = _owning_session()
    # Force the holding underwater on cash flow; offline income floors at zero.
    h = next(iter(s.holdings.values()))
    from dataclasses import replace

    from engine.progression.session import LoanPosition

    s.holdings[h.lot_id] = replace(h, loan=LoanPosition(5_000_000, 0.2, 360, 0))
    assert s.monthly_cash_flow() < 0
    assert compute_offline_earnings(s, 10 * 3600.0, CFG).amount == 0.0


# ----- save timestamp metadata -----
def test_saved_at_recorded_and_outside_checksum():
    s = _owning_session()
    env = save_to_dict(s, saved_at=1_700_000_000.0)
    assert saved_at_of(env) == 1_700_000_000.0
    # saved_at lives outside the checksummed state, so the integrity check still holds.
    assert load_from_dict(env).cash == s.cash


def test_saved_at_optional():
    env = save_to_dict(_owning_session())
    assert saved_at_of(env) is None
    assert "saved_at" in json.loads(save_to_json(_owning_session(), saved_at=123.0))
