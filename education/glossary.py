"""The Closet — a searchable glossary of the real terms the game teaches.

Every term ties to where it shows up in play (``appears_in``) so the UI can make
metrics tappable -> explained. Pure data + search; imports nothing from the engine
so it can't drift, and nothing from the UI.

Term ids double as *concept ids* for the stealth-assessment tracker
(``education.assessment``), so the same key threads glossary, mentors, and mastery.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GlossaryTerm:
    id: str
    term: str
    short: str  # one-line definition
    detail: str  # a sentence or two of plain-English depth
    appears_in: str  # where the player meets it
    see_also: tuple[str, ...] = field(default_factory=tuple)


GLOSSARY: dict[str, GlossaryTerm] = {
    "gpr": GlossaryTerm(
        "gpr",
        "Gross potential rent",
        "Every unit's rent at 100% occupancy — the ceiling.",
        "What you'd collect if no unit ever sat empty and everyone paid. Real life "
        "subtracts vacancy from here.",
        "Explain deal → Gross potential rent",
        ("vacancy", "egi"),
    ),
    "vacancy": GlossaryTerm(
        "vacancy",
        "Vacancy rate",
        "The share of potential rent lost to empty units.",
        "Hot demand pulls vacancy down; overbuilding pushes it up. Amenity upgrades "
        "and a strong neighborhood reduce it.",
        "Explain deal → Effective gross income",
        ("gpr", "demand"),
    ),
    "egi": GlossaryTerm(
        "egi",
        "Effective gross income",
        "GPR minus vacancy, plus other income.",
        "The rent you actually expect to collect. Everything operational is paid out "
        "of this number.",
        "Explain deal → Effective gross income",
        ("gpr", "opex", "noi"),
    ),
    "opex": GlossaryTerm(
        "opex",
        "Operating expenses",
        "The recurring cost of running the property (not the mortgage).",
        "Taxes, insurance, maintenance, management, and capital reserves. Debt service "
        "is deliberately excluded — that's financing, not operations.",
        "Explain deal → Operating expenses",
        ("noi", "egi"),
    ),
    "noi": GlossaryTerm(
        "noi",
        "Net operating income",
        "EGI minus operating expenses. The engine of value.",
        "The property's profit before debt and taxes. Commercial real estate lives and "
        "dies by NOI because value is derived directly from it.",
        "Explain deal → Net operating income",
        ("cap_rate", "egi", "opex"),
    ),
    "cap_rate": GlossaryTerm(
        "cap_rate",
        "Capitalization rate",
        "NOI ÷ value — the market's required yield on the asset.",
        "Flip it and it values the deal: value = NOI ÷ cap rate. When interest rates "
        "rise, cap rates usually rise too, so the same NOI is worth less.",
        "Deal panel → Cap rate",
        ("noi", "value", "interest_rate"),
    ),
    "value": GlossaryTerm(
        "value",
        "Property value",
        "NOI ÷ cap rate — income capitalized at the market rate.",
        "Two ways to grow it: raise NOI (rents up, expenses down) or buy/hold while cap "
        "rates compress. Value-add does the first; a falling-rate market gives the second.",
        "Deal panel → Value",
        ("noi", "cap_rate", "value_add"),
    ),
    "cash_on_cash": GlossaryTerm(
        "cash_on_cash",
        "Cash-on-cash return",
        "(NOI − debt service) ÷ the cash you actually invested.",
        "The first-year levered yield on your own money. Negative means the property "
        "doesn't cover its mortgage from operations.",
        "Explain deal → Cash-on-cash",
        ("leverage", "noi", "dscr"),
    ),
    "ltv": GlossaryTerm(
        "ltv",
        "Loan-to-value",
        "How much a lender will lend against the property's value.",
        "75% LTV on a $200k asset caps the loan at $150k. It's one of the two gates a "
        "lender applies; the other is DSCR.",
        "Explain deal → Lender's max loan",
        ("dscr", "leverage", "value"),
    ),
    "dscr": GlossaryTerm(
        "dscr",
        "Debt-service coverage ratio",
        "NOI ÷ annual debt service. Below ~1.25, lenders balk.",
        "It asks: does the income cover the mortgage with room to spare? Thin NOI means "
        "a small loan — or a flat denial. Feel a DSCR denial once and you'll never forget it.",
        "Deal panel → Loan (dscr)",
        ("noi", "ltv", "leverage"),
    ),
    "leverage": GlossaryTerm(
        "leverage",
        "Leverage",
        "Using borrowed money to control a bigger asset.",
        "It magnifies returns on the way up and losses on the way down. A rate spike on "
        "an overleveraged deal is how investors get wiped out.",
        "Deal panel → Loan",
        ("ltv", "dscr", "cash_on_cash"),
    ),
    "amortization": GlossaryTerm(
        "amortization",
        "Amortization",
        "Paying a loan down over time in level payments.",
        "Early payments are mostly interest; later ones mostly principal. Each payment "
        "quietly builds equity by shrinking the balance.",
        "Owned panel → Loan balance",
        ("equity", "leverage"),
    ),
    "equity": GlossaryTerm(
        "equity",
        "Equity",
        "Value minus what you owe — your real stake.",
        "Grows three ways: appreciation, NOI gains, and loan paydown. Cash-out refis let "
        "you tap it without selling.",
        "Owned panel → Equity",
        ("value", "amortization", "cash_out_refi"),
    ),
    "appreciation": GlossaryTerm(
        "appreciation",
        "Appreciation",
        "Value rising over time.",
        "In this game it comes from NOI growth or cap-rate compression (often a falling-"
        "rate market). Patient, leveraged holders capture the most of it.",
        "Board → tile value rising",
        ("value", "cap_rate"),
    ),
    "refinance": GlossaryTerm(
        "refinance",
        "Refinance",
        "Replacing an old loan with a new one.",
        "Usually to lower the rate or pull equity out. A cash-out refi hands you tax-"
        "deferred cash to redeploy into the next deal.",
        "Owned panel → Cash-out refi",
        ("cash_out_refi", "leverage", "equity"),
    ),
    "cash_out_refi": GlossaryTerm(
        "cash_out_refi",
        "Cash-out refinance",
        "Refinancing for more than you owe and pocketing the difference.",
        "Tax-deferred leverage: great for compounding, dangerous if values then fall and "
        "you're suddenly underwater.",
        "Owned panel → Cash-out refi",
        ("refinance", "leverage", "equity"),
    ),
    "irr": GlossaryTerm(
        "irr",
        "Internal rate of return",
        "The annualized return across a deal's whole cash-flow timeline.",
        "It accounts for timing, not just totals — $1 today beats $1 next year. Shown on "
        "every exit so you can compare flipping vs. holding honestly.",
        "Exit summary → IRR",
        ("cash_on_cash", "value"),
    ),
    "construction_loan": GlossaryTerm(
        "construction_loan",
        "Construction loan",
        "A loan that funds a build in draws as work progresses.",
        "It carries an interest reserve so the project can pay interest before it earns "
        "any rent — and that reserve is itself financed.",
        "Build → ground-up development",
        ("interest_reserve", "leverage"),
    ),
    "interest_reserve": GlossaryTerm(
        "interest_reserve",
        "Interest reserve",
        "Borrowed money set aside to pay a construction loan's own interest.",
        "Because the reserve is part of the loan, it accrues interest too — interest on "
        "interest. This circularity is exactly how a real development proforma works.",
        "Build → ground-up development",
        ("construction_loan",),
    ),
    "demand": GlossaryTerm(
        "demand",
        "Demand / neighborhood heat",
        "How badly tenants want space here.",
        "Jobs, amenities, and your own improvements raise it; it firms rents and cuts "
        "vacancy. The thing Build-a-Lot ignored, made real.",
        "Twist → boom town / bust",
        ("vacancy", "appreciation"),
    ),
    "zoning": GlossaryTerm(
        "zoning",
        "Zoning",
        "What you're allowed to build on a lot.",
        "A rezoning twist can open a more valuable use — or kill a plan. Mixed-use zoning "
        "is the most flexible.",
        "Lot → zoning",
        ("demand",),
    ),
    "interest_rate": GlossaryTerm(
        "interest_rate",
        "Interest rate",
        "The price of borrowing — the variable that cascades through everything.",
        "Up rates mean costlier debt AND higher cap rates (lower values). One number "
        "moves your financing and your valuation at the same time.",
        "HUD → market",
        ("cap_rate", "leverage"),
    ),
    "value_add": GlossaryTerm(
        "value_add",
        "Value-add",
        "Forcing value up by improving the property.",
        "Renovate to raise rent or cut expenses; NOI rises and, at the same cap rate, so "
        "does value. The most reliable lever you control directly.",
        "Owned panel → Renovate",
        ("noi", "value", "appreciation"),
    ),
}


def get_term(term_id: str) -> GlossaryTerm | None:
    return GLOSSARY.get(term_id)


def all_terms() -> list[GlossaryTerm]:
    return sorted(GLOSSARY.values(), key=lambda t: t.term.lower())


def search(query: str) -> list[GlossaryTerm]:
    """Case-insensitive match over term, short, and detail. Empty query -> all."""
    q = query.strip().lower()
    if not q:
        return all_terms()
    hits = [
        t
        for t in GLOSSARY.values()
        if q in t.term.lower() or q in t.short.lower() or q in t.detail.lower()
    ]
    return sorted(hits, key=lambda t: (not t.term.lower().startswith(q), t.term.lower()))
