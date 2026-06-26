"""Wave 1 gameplay: worker crews, condition decay/repair, amenities, plus the
engine fixes (DSCR-gated refinance, regime rate model)."""

from engine.economy.market import MarketState
from engine.economy_balance.constants import DEFAULT_UPKEEP
from engine.finance.loans import dscr
from engine.progression.campaign import build_level_one, new_session
from engine.progression.objectives import Objective, ObjectiveKind
from engine.rng import GameRNG


def _sandbox():
    """A session that won't auto-win/lose mid-test (so advance_month keeps going)."""
    s = new_session(build_level_one())
    s.cash = 500_000  # plenty of room to act
    s.objectives = [Objective(ObjectiveKind.NET_WORTH, 1e18, "sandbox")]  # unreachable
    s.month_limit = 10_000
    return s


def _owned_sfr_session():
    s = _sandbox()
    s.acquire("sfr-2")
    return s


# ---------------- worker crews ----------------
def test_crews_gate_concurrent_work():
    s = _sandbox()
    s.crews = 1
    s.acquire("sfr-0")
    s.acquire("sfr-1")
    assert s.upgrade("sfr-0", "renovate")  # uses the one crew
    assert s.free_crews == 0
    assert not s.upgrade("sfr-1", "renovate")  # no crew free -> blocked


def test_hire_crew_unblocks_and_costs_cash():
    s = _sandbox()
    s.crews = 1
    s.acquire("sfr-0")
    s.acquire("sfr-1")
    s.upgrade("sfr-0", "renovate")
    cash_before = s.cash
    assert s.hire_crew()
    assert s.crews == 2
    assert s.cash < cash_before
    assert s.upgrade("sfr-1", "renovate")  # now there's a free crew


# ---------------- condition decay + repair ----------------
def test_condition_decays_over_time():
    s = _owned_sfr_session()
    start = s.holdings["sfr-2"].property_.condition
    for _ in range(24):
        s.advance_month()
    assert s.holdings["sfr-2"].property_.condition < start


def test_repair_restores_condition():
    s = _owned_sfr_session()
    # Wear it down first.
    for _ in range(40):
        s.advance_month()
    worn = s.holdings["sfr-2"].property_.condition
    assert s.repair("sfr-2")
    for _ in range(DEFAULT_UPKEEP.repair_months):
        s.advance_month()
    assert s.holdings["sfr-2"].property_.condition > worn


# ---------------- amenities -> demand ----------------
def test_amenity_lifts_appeal_and_consumes_the_lot():
    s = _sandbox()
    assert s.town.appeal == 0.0
    assert s.build_amenity("land-0", "park")
    # Park takes a few months; advance until it opens.
    for _ in range(4):
        s.advance_month()
    assert s.town.appeal > 0.0
    assert s.town.lots["land-0"].amenity == "park"
    assert "land-0" not in s.holdings  # amenity holding consumed into appeal


def test_amenity_raises_effective_demand():
    s = _sandbox()
    base_demand = s.effective_market.demand_index
    s.build_amenity("land-0", "park")
    for _ in range(4):
        s.advance_month()
    assert s.effective_market.demand_index > base_demand


def test_cannot_build_amenity_on_owned_built_lot():
    s = _owned_sfr_session()  # owns sfr-2 (built); its town lot.property_ is None now
    assert not s.build_amenity("sfr-2", "park")  # not vacant land


# ---------------- DSCR-gated refinance ----------------
def test_refinance_respects_dscr():
    s = _owned_sfr_session()
    for _ in range(18):  # build some equity
        s.advance_month()
    proceeds = s.refinance("sfr-2")
    assert proceeds is not None
    h = s.holdings["sfr-2"]
    noi = h.property_.annual_noi(s.effective_market)
    annual_ds = h.loan.monthly_payment * 12
    # The refinanced loan can't push coverage below the lender's floor.
    assert dscr(noi, annual_ds) >= s.lending.min_dscr - 1e-6


# ---------------- regime rate model ----------------
def test_rate_cut_shifts_regime_permanently():
    rng = GameRNG(1)
    m = MarketState.at_base()
    base_regime = m.regime
    m = m.stepped(rng, rate_shock=-0.02)  # a cut
    assert m.regime < base_regime
    cut_regime = m.regime
    for _ in range(40):  # let the walk run with no further events
        m = m.stepped(rng)
    # Rate stays anchored near the NEW regime, not the original base.
    assert abs(m.interest_rate - cut_regime) < abs(m.interest_rate - base_regime)
