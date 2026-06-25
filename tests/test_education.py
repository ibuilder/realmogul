"""The education layer: glossary, mentors, mistake cards, stealth assessment."""

from education.assessment import LEARNING_ORDER, ConceptTracker
from education.glossary import GLOSSARY, all_terms, get_term, search
from education.mentors import MENTORS, contexts, tip_for
from education.mistakes import (
    dscr_denial_card,
    negative_cashflow_card,
    underwater_card,
)


# ----- glossary -----
def test_glossary_terms_are_well_formed():
    for term in GLOSSARY.values():
        assert term.term and term.short and term.detail and term.appears_in
        # see_also must point at real terms
        for ref in term.see_also:
            assert ref in GLOSSARY, f"{term.id} -> unknown see_also {ref}"


def test_glossary_search_prefers_term_name_matches():
    hits = search("dscr")
    assert hits and hits[0].id == "dscr"


def test_glossary_empty_search_returns_all_sorted():
    assert search("") == all_terms()
    assert get_term("noi").term == "Net operating income"


# ----- mentors -----
def test_every_context_yields_a_known_mentor():
    for ctx in contexts():
        tip = tip_for(ctx)
        assert tip is not None
        assert tip.mentor_id in MENTORS
        assert tip.concept in GLOSSARY  # links to a real term


def test_unknown_context_is_none():
    assert tip_for("not_a_real_context") is None


# ----- mistakes -----
def test_mistake_cards_link_to_concepts_and_speak_plainly():
    cards = [
        dscr_denial_card(9_000, 11_250),
        negative_cashflow_card("sfr-1", -250),
        underwater_card("ret-2", 180_000, 200_000),
    ]
    for card in cards:
        assert card.title and card.what_happened and card.how_pros_avoid
        assert card.concept in GLOSSARY


# ----- assessment -----
def test_concept_tracker_mastery_and_next():
    t = ConceptTracker()
    assert t.mastery_fraction() == 0.0
    assert t.next_concept() == LEARNING_ORDER[0]
    t.record("noi", "cap_rate")
    assert 0.0 < t.mastery_fraction() < 1.0
    assert t.next_concept() not in {"noi", "cap_rate"}


def test_concept_tracker_round_trips():
    t = ConceptTracker()
    t.record("noi", "leverage")
    restored = ConceptTracker.from_list(t.to_list())
    assert restored.demonstrated == t.demonstrated
