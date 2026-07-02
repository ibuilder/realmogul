"""Acceptance: a headless agent plays a full campaign level start -> win,
deterministically."""

from engine.progression.campaign import build_level_one
from tools.play_level import play


def test_level_one_is_winnable_headless():
    level = build_level_one()
    result = play(level)
    assert result.won, f"agent failed to win; net worth {result.final_net_worth:,.0f}"
    # Cleared the level's own objective (not a hardcoded number that drifts on tuning).
    assert result.final_net_worth >= level.objectives[0].target
    assert result.months_played <= level.month_limit


def test_playthrough_is_deterministic():
    a = play(build_level_one())
    b = play(build_level_one())
    assert a.won == b.won
    assert a.months_played == b.months_played
    assert a.final_net_worth == b.final_net_worth
    assert a.log == b.log
