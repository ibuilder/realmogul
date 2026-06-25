"""Consumer-protection guardrails, baked in from day one (CLAUDE.md / brief §7).

Spending limits, parental lock, purchase confirmation, and probability disclosure.
These protect players (and the store rating, and long-term revenue) and are not
optional polish.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from monetization.catalog import Product


@dataclass
class SpendingGuard:
    daily_cap_usd: float = 50.0
    parental_lock: bool = False  # when on, purchases require an out-of-band code
    require_confirmation: bool = True  # the UI must confirm price before charging
    _spent_today: float = field(default=0.0)
    _day: int = field(default=-1)

    def _roll_day(self, now: float) -> None:
        day = int(now // 86_400)
        if day != self._day:
            self._day = day
            self._spent_today = 0.0

    def check(self, product: Product, now: float, *, parental_code_ok: bool = False) -> str | None:
        """Return None if the purchase may proceed, else a refusal reason."""
        self._roll_day(now)
        if self.parental_lock and not parental_code_ok:
            return "parental_lock"
        if self._spent_today + product.price_usd > self.daily_cap_usd:
            return "daily_cap_reached"
        return None

    def record(self, product: Product, now: float) -> None:
        self._roll_day(now)
        self._spent_today += product.price_usd


def probability_disclosure() -> str:
    """Real Mogul sells no randomized items, so disclosure is simple and honest."""
    return "Real Mogul has no loot boxes or randomized purchases. Every item is exactly as shown."
