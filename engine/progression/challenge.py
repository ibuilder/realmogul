"""Daily / weekly challenges + leaderboard.

One fixed-seed scenario per day (or week) that everyone plays on identical terms,
scored by net worth. Fairness is structural: the engine can't see entitlements, so
a fixed-seed challenge can't be bought — exactly the brief's "no pay-to-win on
leaderboards" guarantee. Pure logic; the leaderboard is in-memory/serializable.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from engine.progression.campaign import build_level_one
from engine.progression.objectives import Objective, ObjectiveKind
from engine.progression.session import GameSession

_DAILY_SALT = 0xDA117
_WEEKLY_SALT = 0x3EE17
_MIX = 2654435761  # Knuth multiplicative hash constant


def _seed_from(index: int, salt: int) -> int:
    return (salt ^ ((index * _MIX) & 0x7FFFFFFF)) & 0x7FFFFFFF


def make_challenge(seed: int, *, challenge_id: str, month_limit: int = 36):
    """A scored sandbox: the level-1 board on a given seed, no win target — you
    play the clock and post a net-worth score."""
    base = build_level_one()
    return replace(
        base,
        id=challenge_id,
        seed=seed,
        month_limit=month_limit,
        # An unreachable target turns the level into a pure score chase.
        objectives=[Objective(ObjectiveKind.NET_WORTH, float("inf"), "Maximize net worth")],
    )


def daily_challenge(day_index: int, *, month_limit: int = 36):
    return make_challenge(
        _seed_from(day_index, _DAILY_SALT),
        challenge_id=f"daily-{day_index}",
        month_limit=month_limit,
    )


def weekly_challenge(week_index: int, *, month_limit: int = 60):
    return make_challenge(
        _seed_from(week_index, _WEEKLY_SALT),
        challenge_id=f"weekly-{week_index}",
        month_limit=month_limit,
    )


def final_score(session: GameSession) -> float:
    """The score a finished challenge run posts (net worth at the buzzer)."""
    return session.net_worth()


@dataclass(frozen=True)
class LeaderboardEntry:
    name: str
    score: float


@dataclass
class Leaderboard:
    challenge_id: str
    entries: list[LeaderboardEntry] = field(default_factory=list)

    def submit(self, name: str, score: float) -> None:
        # Keep a player's best score only.
        existing = next((e for e in self.entries if e.name == name), None)
        if existing is None:
            self.entries.append(LeaderboardEntry(name, score))
        elif score > existing.score:
            self.entries.remove(existing)
            self.entries.append(LeaderboardEntry(name, score))

    def ranked(self) -> list[LeaderboardEntry]:
        return sorted(self.entries, key=lambda e: e.score, reverse=True)

    def top(self, n: int = 10) -> list[LeaderboardEntry]:
        return self.ranked()[:n]

    def rank_of(self, name: str) -> int | None:
        for i, entry in enumerate(self.ranked(), start=1):
            if entry.name == name:
                return i
        return None
