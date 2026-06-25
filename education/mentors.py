"""Mentor characters: contextual, one-line coaching at decision points.

Four personas with distinct voices deliver a tip when the game hits a teachable
moment (a context key like ``"dscr_denied"`` or ``"first_deal"``). Each tip links
to a glossary concept so a tap can go deeper. Witty, not preachy — and never
blocking; the UI surfaces these alongside play.

Deterministic: a context maps to a fixed tip, so playthroughs and tests are stable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mentor:
    id: str
    name: str
    role: str
    voice: str  # a note on their personality, for future VO/art


MENTORS: dict[str, Mentor] = {
    "flipper": Mentor(
        "flipper", "Rosa Vega", "Scrappy flipper", "fast, street-smart, allergic to fluff"
    ),
    "broker": Mentor(
        "broker", "Dex Calloway", "Commercial broker", "polished, name-drops cap rates"
    ),
    "banker": Mentor("banker", "Miriam Osei", "Lender", "precise, risk-first, dryly funny"),
    "syndicator": Mentor("syndicator", "Theo Park", "Syndicator", "big-picture, talks in 'we'"),
}


@dataclass(frozen=True)
class MentorTip:
    mentor_id: str
    mentor_name: str
    text: str
    concept: str  # glossary id for "learn more"


# context key -> (mentor id, line, glossary concept)
_TIPS: dict[str, tuple[str, str, str]] = {
    "first_deal": (
        "flipper",
        "First one's the hardest. Buy for the numbers, not the curb appeal — what's the NOI?",
        "noi",
    ),
    "considering_leverage": (
        "banker",
        "A bigger loan means a smaller check today and a bigger payment forever. Mind the DSCR.",
        "dscr",
    ),
    "dscr_denied": (
        "banker",
        "Can't lend on that — income won't cover the payment. Thin NOI, thin loan. That's DSCR.",
        "dscr",
    ),
    "bought_first": (
        "flipper",
        "Nice. You don't own a house, you own a cash-flow stream with a roof. Go raise the rent.",
        "value_add",
    ),
    "renovation_done": (
        "broker",
        "Renovation lifted your NOI — same cap rate, so that's instant value. Forced appreciation.",
        "value_add",
    ),
    "refi_available": (
        "syndicator",
        "Value's up — refinance and pull our cash back out, tax-deferred, to buy the next one.",
        "cash_out_refi",
    ),
    "negative_cashflow": (
        "banker",
        "This one bleeds every month. Negative cash-on-cash isn't a strategy unless you love feeding it.",  # noqa: E501
        "cash_on_cash",
    ),
    "rate_spike": (
        "broker",
        "Rates jumped. Cap rates follow, so values slipped — anything overleveraged hurts now.",
        "interest_rate",
    ),
    "boom_town": (
        "syndicator",
        "Big employer's moving in. Demand surges, vacancy drops — rents have room to run here.",
        "demand",
    ),
    "developing": (
        "broker",
        "Ground-up build: the construction loan's interest reserve finances its own interest.",
        "interest_reserve",
    ),
    "won": (
        "syndicator",
        "That's the playbook — buy right, add value, recycle the equity. On to the next market.",
        "equity",
    ),
    "lost": (
        "banker",
        "Tough one. Most blowups trace to too much leverage meeting a bad month. Live to deal on.",
        "leverage",
    ),
}


def tip_for(context: str) -> MentorTip | None:
    entry = _TIPS.get(context)
    if entry is None:
        return None
    mentor_id, text, concept = entry
    return MentorTip(mentor_id, MENTORS[mentor_id].name, text, concept)


def contexts() -> list[str]:
    return list(_TIPS)
