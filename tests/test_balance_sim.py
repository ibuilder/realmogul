"""The balance simulator must be deterministic and report a healthy economy."""

from engine.rng import GameRNG
from tools.balance_sim import play_deal, run


def test_sim_is_deterministic():
    a = run(deals=500, seed=1)
    b = run(deals=500, seed=1)
    assert a.irr_median == b.irr_median
    assert a.approved == b.approved
    assert a.worst_net_profit == b.worst_net_profit


def test_economy_has_no_exploit_and_is_non_degenerate():
    report = run(deals=2000, seed=1)
    assert report.ok, f"exploit flags: {report.exploit_flags}"
    # Non-degenerate: there must be both winners and losers among approved deals.
    assert report.worst_net_profit < 0 < report.best_net_profit
    # IRR band should be plausible for levered real estate, not absurd.
    assert -1.0 < report.irr_p10 <= report.irr_median <= report.irr_p90 < 1.0


def test_single_deal_shapes():
    result = play_deal(GameRNG(123))
    assert result.cash_invested > 0
    # A DSCR-gated loan guarantees first-year operations cover debt service.
    assert result.annual_cash_flow >= 0
