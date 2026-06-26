"""The UI controller (Kivy-free presenter) drives the game correctly.

Imports no Kivy, so it runs in plain CI. These guard the view-model the Kivy
widgets render — including the regression where a renovated property's panel read
the stale town listing instead of the owned holding.
"""

from engine.progression.campaign import build_level_one
from ui.controller import GameController


def _fresh() -> GameController:
    return GameController(build_level_one())


def test_board_and_initial_hud():
    c = _fresh()
    tiles = c.board()
    assert len(tiles) == 8
    assert any(t.for_sale for t in tiles)
    hud = c.hud()
    assert hud.status == "playing"
    assert hud.month == 0


def test_select_for_sale_deal_shows_buy_and_explain():
    c = _fresh()
    c.select("sfr-3")
    deal = c.selected_deal()
    assert deal is not None and deal.subtitle == "For sale"
    assert [a.action_id for a in deal.actions] == ["buy"]
    assert deal.actions[0].enabled
    assert len(c.explain_lines()) > 0


def test_buy_then_own_panel():
    c = _fresh()
    cash_before = c.session.cash
    c.select("sfr-3")
    c.do_action("buy")
    assert c.session.cash < cash_before
    c.select("sfr-3")
    deal = c.selected_deal()
    assert deal.subtitle == "You own this"
    assert {a.action_id for a in deal.actions} == {"renovate", "repair", "refinance", "sell"}


def test_renovation_completion_updates_the_displayed_panel():
    # Regression: the owned panel must read the holding (which renovation mutates),
    # not the stale town listing.
    c = _fresh()
    c.select("sfr-3")
    c.do_action("buy")
    c.do_action("renovate")
    for _ in range(3):  # renovation completes at month 3
        c.advance_month()
    c.select("sfr-3")
    rows = dict(c.selected_deal().rows)
    assert rows["Condition"] == "100%"
    assert rows["Upgrades"] == "renovate"
    # Renovate must now be disabled (already done).
    reno = next(a for a in c.selected_deal().actions if a.action_id == "renovate")
    assert not reno.enabled


def test_sell_clears_selection():
    c = _fresh()
    c.select("sfr-3")
    c.do_action("buy")
    c.do_action("sell")
    assert c.selected_lot_id is None
    assert "sfr-3" not in c.session.holdings


def test_develop_on_owned_land():
    c = _fresh()
    c.select("land-0")
    deal = c.selected_deal()
    assert deal.actions[0].action_id == "develop"
    c.do_action("develop")
    assert "land-0" in c.session.holdings


def test_advance_reports_endgame_when_won():
    c = _fresh()
    c.session.won = True  # force the terminal state
    c.advance_month()
    assert c.session.status == "won"


# ----- education wiring -----
def test_first_deal_and_buy_coach_and_concepts():
    c = _fresh()
    c.select("sfr-3")
    assert c.coach_tip() is not None  # first-deal coaching fires
    c.do_action("buy")
    # A financed buy demonstrates leverage + dscr + valuation concepts.
    assert {"leverage", "dscr", "noi", "cap_rate", "value"} <= c.tracker.demonstrated
    assert c.mastery() > 0


def test_renovation_completion_triggers_coach():
    c = _fresh()
    c.select("sfr-3")
    c.do_action("buy")
    c.do_action("renovate")
    for _ in range(3):
        c.advance_month()
    tip = c.coach_tip()
    assert tip is not None and tip.concept == "value_add"


def test_metric_rows_map_to_glossary_terms():
    c = _fresh()
    assert c.term_for_metric("Cap rate").id == "cap_rate"
    assert c.term_for_metric("Loan (dscr)").id == "dscr"
    assert c.term_for_metric("Cash flow / mo").id == "cash_on_cash"


def test_glossary_accessible_through_controller():
    c = _fresh()
    assert len(c.glossary()) == len(c.glossary(""))
    assert any(t.id == "dscr" for t in c.glossary("coverage"))


def test_opportunities_surface_and_can_be_taken():
    c = _fresh()
    c.session.opportunity_rate = 100.0  # force a deal to appear
    c.advance_month()
    opps = c.opportunities()
    assert opps and c.hud().deals == len(opps)
    c.accept_opportunity(opps[0].opp_id)
    assert "seized" in c.message.lower() or "couldn't" in c.message.lower()
