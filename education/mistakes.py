"""Mistake-as-lesson cards: turn a bad outcome into a short, kind lesson.

When a deal goes wrong — a DSCR denial, a property bleeding cash, getting caught
overleveraged in a rate spike, or running out of road — we surface a card that
says plainly *what happened* and *how pros avoid it*, linked to the concept. The
goal is "oh, I get it now," never "you failed."

Pure: takes plain facts, returns a card. The caller (controller) decides when to
detect; this module decides what to say.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LessonCard:
    title: str
    what_happened: str
    how_pros_avoid: str
    concept: str  # glossary id


def dscr_denial_card(noi: float, needed_noi: float) -> LessonCard:
    return LessonCard(
        title="Loan denied — DSCR too low",
        what_happened=(
            f"The property's NOI (${noi:,.0f}) didn't cover the payment with the cushion "
            f"the lender requires (it wanted about ${needed_noi:,.0f})."
        ),
        how_pros_avoid=(
            "Buy at a price where the income carries the debt, put more cash down, or raise "
            "NOI first. Stretching leverage past DSCR is how good deals become denials."
        ),
        concept="dscr",
    )


def negative_cashflow_card(lot_id: str, monthly: float) -> LessonCard:
    return LessonCard(
        title="This property bleeds cash",
        what_happened=(
            f"{lot_id} runs about ${monthly:,.0f} a month after debt service — money out "
            f"of your pocket every month you hold it."
        ),
        how_pros_avoid=(
            "Either fix the NOI (raise rent via value-add, cut expenses) or refinance to a "
            "lower payment. Negative cash-on-cash only works if appreciation clearly outruns it."
        ),
        concept="cash_on_cash",
    )


def underwater_card(lot_id: str, value: float, loan: float) -> LessonCard:
    return LessonCard(
        title="Underwater after a rate spike",
        what_happened=(
            f"Rates rose, cap rates followed, and {lot_id}'s value (${value:,.0f}) fell below "
            f"its loan (${loan:,.0f}). Leverage cuts both ways."
        ),
        how_pros_avoid=(
            "Keep a margin of safety on leverage and don't assume cheap rates last. Lower LTV "
            "going in means a rate shock dents you instead of drowning you."
        ),
        concept="leverage",
    )


def bankruptcy_card() -> LessonCard:
    return LessonCard(
        title="Out of cash",
        what_happened="Spending and debt service outran your income and reserves.",
        how_pros_avoid=(
            "Hold a cash buffer for vacancies and surprises, and don't tie every dollar up in "
            "down payments. Liquidity is what lets you survive to the next deal."
        ),
        concept="cash_on_cash",
    )


def time_up_card(net_worth: float, target: float) -> LessonCard:
    return LessonCard(
        title="Time's up",
        what_happened=(
            f"The level ended at ${net_worth:,.0f} net worth, short of the ${target:,.0f} goal."
        ),
        how_pros_avoid=(
            "Compounding needs tempo: add value early, refinance to recycle equity, and keep "
            "your capital working instead of parked."
        ),
        concept="equity",
    )
