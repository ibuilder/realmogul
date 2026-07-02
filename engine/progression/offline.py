"""'While you were away' catch-up earnings (Wave 2).

A session-based retention nudge: when you reopen the game, credit a bounded slice
of the rent your portfolio would have collected while you were gone. Reshaped for
our turn-based game so it stays a small reward — capped, and never negative (time
away can't bankrupt you).

Pure and clock-free: the caller passes ``elapsed_seconds`` (the UI owns the wall
clock, never the engine), so the deterministic simulation is untouched.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.economy_balance.constants import DEFAULT_OFFLINE, OfflineDefaults


@dataclass(frozen=True)
class OfflineEarnings:
    amount: float
    hours_away: float
    months_credited: float

    @property
    def worthwhile(self) -> bool:
        return self.amount >= 1.0


def compute_offline_earnings(
    session,
    elapsed_seconds: float,
    cfg: OfflineDefaults = DEFAULT_OFFLINE,
) -> OfflineEarnings:
    """How much catch-up rent to credit for ``elapsed_seconds`` away.

    Only positive operating cash flow counts, scaled by elapsed time and capped at
    ``max_months_credited`` so a long absence can't trivialize the campaign.
    """
    if elapsed_seconds <= 0:
        return OfflineEarnings(0.0, 0.0, 0.0)
    monthly = max(0.0, session.monthly_cash_flow())
    months = min(cfg.max_months_credited, elapsed_seconds / cfg.real_seconds_per_game_month)
    return OfflineEarnings(
        amount=monthly * months,
        hours_away=elapsed_seconds / 3600.0,
        months_credited=months,
    )
