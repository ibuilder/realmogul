"""Entitlement state — what the player owns. The client's source of truth, but it
is only ever updated from *verified* grants (the client never trusts itself).

Pure data + JSON round-trip so it persists across relaunch. Time is injected (a
``now`` epoch) so tests are deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from monetization.catalog import Kind, Product


@dataclass
class Entitlements:
    keys: int = 0
    cosmetics: set[str] = field(default_factory=set)
    ad_free: bool = False
    education_unlocked: bool = False
    pass_premium: bool = False
    subscription_until: float | None = None  # epoch seconds

    def subscription_active(self, now: float) -> bool:
        return self.subscription_until is not None and now < self.subscription_until

    def has_cosmetic(self, cosmetic_id: str) -> bool:
        return cosmetic_id in self.cosmetics

    def grant(self, product: Product, now: float) -> None:
        """Apply a verified purchase. Consumables stack; everything else is set."""
        g = product.grant
        self.keys += g.keys
        self.cosmetics.update(g.cosmetics)
        if g.ad_free:
            self.ad_free = True
        if g.education_unlocked:
            self.education_unlocked = True
        if g.pass_premium:
            self.pass_premium = True
        if g.subscription_days:
            base = max(now, self.subscription_until or now)
            self.subscription_until = base + g.subscription_days * 86_400

    def spend_keys(self, amount: int) -> bool:
        """Convenience spend (speed a timer, etc.). Never used in challenge mode."""
        if amount <= 0 or self.keys < amount:
            return False
        self.keys -= amount
        return True

    # ---- persistence ----
    def to_dict(self) -> dict[str, Any]:
        return {
            "keys": self.keys,
            "cosmetics": sorted(self.cosmetics),
            "ad_free": self.ad_free,
            "education_unlocked": self.education_unlocked,
            "pass_premium": self.pass_premium,
            "subscription_until": self.subscription_until,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Entitlements:
        return cls(
            keys=d.get("keys", 0),
            cosmetics=set(d.get("cosmetics", [])),
            ad_free=d.get("ad_free", False),
            education_unlocked=d.get("education_unlocked", False),
            pass_premium=d.get("pass_premium", False),
            subscription_until=d.get("subscription_until"),
        )


# Kinds that should be re-granted when restoring purchases on a fresh device.
RESTORABLE_KINDS = {Kind.NON_CONSUMABLE, Kind.SUBSCRIPTION}
