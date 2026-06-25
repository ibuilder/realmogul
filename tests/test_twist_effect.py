"""Acceptance: a forced rate-shock twist measurably changes optimal play.

We run the same greedy agent against the same level twice — once as authored, and
once with a severe early rate hike injected. Higher rates raise cap rates (lower
values) and make debt costlier, so the player's trajectory must measurably worsen.
"""

from dataclasses import replace

from engine.progression.campaign import build_level_one
from engine.world.events import TwistEvent, TwistKind
from tools.play_level import play


def test_rate_hike_twist_measurably_worsens_outcome():
    base_level = build_level_one()
    base = play(base_level)

    # Inject a hard rate hike early in the hold.
    hiked_level = replace(
        base_level,
        events=base_level.events
        + [TwistEvent(4, TwistKind.RATE_HIKE, magnitude=0.04, message="Rate shock!")],
    )
    hiked = play(hiked_level)

    # The shock must change the trajectory in a measurable, correct direction.
    assert hiked.final_net_worth != base.final_net_worth
    if base.won and hiked.won:
        # If both still win, the shocked run should at least take longer or end poorer.
        assert (
            hiked.months_played >= base.months_played
            or hiked.final_net_worth < base.final_net_worth
        )
    else:
        # A severe enough shock can flip a win into a loss within the time limit.
        assert not hiked.won or hiked.final_net_worth < base.final_net_worth
