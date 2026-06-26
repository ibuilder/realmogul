"""Rewarded-ad mediation bridge.

Ethics (brief §7): ads are **opt-in rewarded only** — watch to finish a build,
get a market tip, or claim bonus currency. Never forced interstitials mid-deal.
The interface lives here; the on-device implementation (AdMob / mediation SDK via
pyjnius/pyobjus) is wired in Phase 6. Desktop/CI gets a NoRewardedAds that always
reports "unavailable" so the UI simply hides the opt-in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class RewardedAdProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def show(self, on_reward: Callable[[], None], on_dismiss: Callable[[], None]) -> None:
        """Show an opt-in rewarded ad; call ``on_reward`` only if fully watched."""


class NoRewardedAds(RewardedAdProvider):
    """Desktop/CI default — no inventory, so the opt-in stays hidden."""

    def is_available(self) -> bool:
        return False

    def show(self, on_reward, on_dismiss) -> None:
        on_dismiss()


class MediatedRewardedAds(RewardedAdProvider):  # pragma: no cover - device only
    def __init__(self) -> None:
        # TODO(phase6): init AdMob/mediation SDK via pyjnius (Android) / pyobjus (iOS).
        raise RuntimeError("MediatedRewardedAds is wired on-device in Phase 6.")

    def is_available(self) -> bool:
        raise NotImplementedError

    def show(self, on_reward, on_dismiss) -> None:
        raise NotImplementedError
