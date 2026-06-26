"""Random opportunities: distressed buys + buyout offers on a separate RNG stream."""

from engine.progression.campaign import build_level_one, new_session
from engine.progression.objectives import Objective, ObjectiveKind


def _sandbox(rate: float = 100.0):
    s = new_session(build_level_one())
    s.cash = 1_000_000
    s.objectives = [Objective(ObjectiveKind.NET_WORTH, 1e18, "sandbox")]
    s.month_limit = 10_000
    s.opportunity_rate = rate  # crank generation for deterministic testing
    return s


def test_opportunities_appear():
    s = _sandbox()
    s.advance_month()
    assert s.opportunities  # something showed up


def test_distressed_deal_can_be_grabbed_cheap():
    s = _sandbox()
    s.advance_month()
    distressed = next(o for o in s.opportunities if o.kind == "distressed")
    lot = s.town.lots[distressed.lot_id]
    intrinsic = lot.property_.value(s.effective_market)
    assert lot.list_price_premium < 0  # priced below value
    assert s.accept_opportunity(distressed.id)
    assert distressed.lot_id in s.holdings  # now owned
    assert distressed not in s.opportunities
    # The lender appraised intrinsic value; we paid a discount to it.
    assert lot.property_.value(s.effective_market) == intrinsic


def test_buyout_offer_sells_above_market():
    s = _sandbox(rate=0.0)  # no random gen; we own a property and force a buyout
    s.acquire("sfr-2")
    s.opportunity_rate = 100.0
    # Advance until a buyout (needs an eligible holding) shows up.
    buyout = None
    for _ in range(40):
        s.advance_month()
        buyout = next((o for o in s.opportunities if o.kind == "buyout"), None)
        if buyout:
            break
    assert buyout is not None
    cash_before = s.cash
    assert s.accept_opportunity(buyout.id)
    assert buyout.lot_id not in s.holdings  # sold
    assert s.cash > cash_before


def test_opportunities_expire():
    s = _sandbox()
    s.advance_month()
    opp = s.opportunities[0]
    lot_id = opp.lot_id
    for _ in range(5):  # past the expiry window
        s.advance_month()
    assert opp not in s.opportunities
    # An expired, unbought distressed listing leaves the market.
    if opp.kind == "distressed":
        assert lot_id not in s.town.lots


def test_opportunity_stream_is_deterministic():
    a = _sandbox()
    b = _sandbox()
    for _ in range(6):
        a.advance_month()
        b.advance_month()
    assert [o.id for o in a.opportunities] == [o.id for o in b.opportunities]
    assert [o.kind for o in a.opportunities] == [o.kind for o in b.opportunities]


def test_opportunities_do_not_perturb_the_market():
    # Same seed, but one session has opportunities cranked and the other off.
    on = _sandbox(rate=100.0)
    off = _sandbox(rate=0.0)
    for _ in range(12):
        on.advance_month()
        off.advance_month()
    # The market (interest/cap/demand) is driven by the main rng, untouched by
    # the separate opportunity stream — so both see an identical market.
    assert on.market.interest_rate == off.market.interest_rate
    assert on.market.cap_rate == off.market.cap_rate
