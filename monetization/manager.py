"""MonetizationManager — the client-side coordinator (no UI, no platform import).

Ties together flags, guardrails, a BillingProvider, server-side verification, and
entitlement persistence. The purchase flow is deliberately strict:

    flag enabled? -> guardrail ok? -> provider.purchase -> SERVER verify -> grant -> persist

Entitlements are only ever updated from a verified grant, and they survive
relaunch (persisted to JSON). On launch, ``reconcile`` restores non-consumables
and subscriptions so a reinstall or new device recovers purchases.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from monetization.billing import BillingProvider
from monetization.catalog import Category, all_products, get_product
from monetization.entitlements import RESTORABLE_KINDS, Entitlements
from monetization.flags import DEFAULT_FLAGS, FeatureFlags
from monetization.guardrails import SpendingGuard
from monetization.verify import verify_receipt


@dataclass(frozen=True)
class PurchaseOutcome:
    ok: bool
    product_id: str
    error: str = ""


class MonetizationManager:
    def __init__(
        self,
        provider: BillingProvider,
        *,
        mock_secret: str,
        flags: FeatureFlags = DEFAULT_FLAGS,
        guard: SpendingGuard | None = None,
        save_path: Path | None = None,
        clock=time.time,
    ) -> None:
        self.provider = provider
        self._secret = mock_secret
        self.flags = flags
        self.guard = guard or SpendingGuard()
        self.save_path = save_path
        self._clock = clock
        self.entitlements = self._load()

    # ------------------------------------------------------------------ buy
    def purchase(self, product_id: str, *, parental_code_ok: bool = False) -> PurchaseOutcome:
        product = get_product(product_id)
        if product is None:
            return PurchaseOutcome(False, product_id, "unknown_product")
        if not self.flags.category_enabled(product.category):
            return PurchaseOutcome(False, product_id, "feature_disabled")

        now = self._clock()
        refusal = self.guard.check(product, now, parental_code_ok=parental_code_ok)
        if refusal is not None:
            return PurchaseOutcome(False, product_id, refusal)

        result = self.provider.purchase(product_id)
        if not result.success or result.receipt is None:
            return PurchaseOutcome(False, product_id, result.error or "purchase_failed")

        verdict = verify_receipt(result.receipt, mock_secret=self._secret)
        if not verdict.valid:
            return PurchaseOutcome(False, product_id, verdict.reason or "verification_failed")

        self.entitlements.grant(product, now)
        self.guard.record(product, now)
        self._save()
        return PurchaseOutcome(True, product_id)

    # ------------------------------------------------------------- reconcile
    def reconcile(self) -> int:
        """Restore owned non-consumables/subscriptions on launch. Returns count granted."""
        now = self._clock()
        granted = 0
        for receipt in self.provider.restore():
            verdict = verify_receipt(receipt, mock_secret=self._secret)
            if not verdict.valid:
                continue
            product = get_product(receipt.product_id)
            if product is None or product.kind not in RESTORABLE_KINDS:
                continue
            self.entitlements.grant(product, now)
            granted += 1
        if granted:
            self._save()
        return granted

    # ------------------------------------------------------------- queries
    def is_ad_free(self) -> bool:
        return self.entitlements.ad_free or self.entitlements.subscription_active(self._clock())

    def education_unlocked(self) -> bool:
        return self.entitlements.education_unlocked or self.entitlements.subscription_active(
            self._clock()
        )

    def visible_products(self):
        return [
            p
            for p in all_products()
            if self.flags.category_enabled(p.category)
            and not (p.category == Category.AD_REMOVAL and self.is_ad_free())
        ]

    # ------------------------------------------------------------- persistence
    def _load(self) -> Entitlements:
        if self.save_path and self.save_path.exists():
            return Entitlements.from_dict(json.loads(self.save_path.read_text()))
        return Entitlements()

    def _save(self) -> None:
        if self.save_path:
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            self.save_path.write_text(json.dumps(self.entitlements.to_dict(), indent=2))
