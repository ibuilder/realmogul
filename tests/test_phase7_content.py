"""Phase 7 content: campaign winnability, careers, challenges, prestige."""

import pytest

from engine.progression.campaign import CAMPAIGN, campaign_levels, level_by_id, new_session
from engine.progression.career import CAREERS, CareerId, get_career
from engine.progression.challenge import (
    Leaderboard,
    daily_challenge,
    final_score,
    weekly_challenge,
)
from engine.progression.prestige import PRESTIGE_THRESHOLD, PrestigeState
from tools.play_level import play


# ---------------- campaign ----------------
def test_campaign_has_multiple_levels_with_unique_ids():
    ids = [lvl.id for lvl in CAMPAIGN]
    assert len(ids) >= 4
    assert len(ids) == len(set(ids))
    assert level_by_id("level-3").name == "Market Street"
    assert level_by_id("nope") is None


@pytest.mark.parametrize("level", campaign_levels(), ids=lambda lvl: lvl.id)
def test_every_campaign_level_is_winnable(level):
    # The reference agent must beat each handcrafted level within its time limit.
    result = play(level)
    assert (
        result.won
    ), f"{level.id} unwinnable: {result.final_net_worth:,.0f} in {result.months_played}mo"


def test_playthroughs_are_deterministic():
    a = play(level_by_id("level-2"))
    b = play(level_by_id("level-2"))
    assert (a.won, a.months_played, a.final_net_worth) == (
        b.won,
        b.months_played,
        b.final_net_worth,
    )


# ---------------- careers ----------------
def test_career_perks_apply_to_session():
    base = level_by_id("level-1")
    flipper = new_session(base)  # level 1 is the Flipper
    assert flipper.career.id is CareerId.FLIPPER
    assert flipper.selling_cost_rate == 0.03  # flipper perk: cheap exits

    syndicator = get_career(CareerId.SYNDICATOR)
    assert syndicator.ltv_bonus > 0
    assert get_career(CareerId.DEVELOPER).build_speed < 1.0
    assert get_career(CareerId.LANDLORD).dscr_relief > 0


def test_developer_builds_faster():
    from engine.assets.asset_class import AssetClassId
    from engine.progression.campaign import build_level_four

    s = new_session(build_level_four())  # developer career
    assert s.develop("land-0", AssetClassId.SFR, 1)
    pending = s.holdings["land-0"].pending[0]
    # SFR base build is 8 months; developer ×0.75 -> 6.
    assert pending.complete_month == 6


def test_all_careers_present():
    assert set(CAREERS) == set(CareerId)


# ---------------- challenges ----------------
def test_daily_challenge_is_deterministic_and_scored():
    c1 = daily_challenge(20260625)
    c2 = daily_challenge(20260625)
    assert c1.seed == c2.seed
    assert daily_challenge(20260626).seed != c1.seed
    # A fixed-seed run yields a reproducible score.
    s1 = new_session(c1)
    s2 = new_session(c2)
    for _ in range(c1.month_limit):
        s1.advance_month()
        s2.advance_month()
    assert final_score(s1) == final_score(s2)


def test_weekly_challenge_distinct_from_daily():
    assert weekly_challenge(1).seed != daily_challenge(1).seed


def test_leaderboard_ranks_and_keeps_best():
    lb = Leaderboard("daily-1")
    lb.submit("rosa", 500_000)
    lb.submit("dex", 750_000)
    lb.submit("rosa", 900_000)  # improves
    lb.submit("rosa", 100_000)  # ignored (worse)
    ranked = lb.ranked()
    assert [e.name for e in ranked] == ["rosa", "dex"]
    assert ranked[0].score == 900_000
    assert lb.rank_of("dex") == 2
    assert lb.rank_of("ghost") is None


# ---------------- prestige ----------------
def test_prestige_requires_threshold_and_grows_multiplier():
    p = PrestigeState()
    assert p.starting_cash_multiplier == 1.0
    assert not p.can_prestige(PRESTIGE_THRESHOLD - 1)

    p2 = p.go_national(PRESTIGE_THRESHOLD + 50_000)
    assert p2.level == 1 and p2.region == 1
    assert p2.starting_cash_multiplier > 1.0
    assert p2.apply_starting_cash(160_000) > 160_000


def test_prestige_no_op_below_threshold():
    p = PrestigeState()
    assert p.go_national(1_000) == p


def test_prestige_multiplier_is_capped():
    p = PrestigeState(level=100)  # absurd
    assert p.starting_cash_multiplier <= 2.5  # 1.0 + capped 1.5


def test_prestige_round_trips():
    p = PrestigeState(level=3, region=3, best_net_worth=1_000_000)
    assert PrestigeState.from_dict(p.to_dict()) == p
