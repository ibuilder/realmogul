"""StoreKit billing bridge (pyobjus) — implements BillingProvider.

Scaffold for Phase 6. On-device flow:

1. Use StoreKit via pyobjus: load products, add an ``SKPayment`` to the queue.
2. ``purchase`` returns a ``Receipt`` referencing the App Store receipt /
   transaction (platform="apple").
3. The verify service validates against the App Store Server API before entitling.

pyobjus only exists inside a kivy-ios build, so the import is lazy; this module
imports fine on desktop/CI and only raises when instantiated off iOS.
"""

from __future__ import annotations

from monetization.billing import BillingProvider, PurchaseResult, Receipt


class IosBillingProvider(BillingProvider):
    def __init__(self) -> None:
        try:
            from pyobjus import autoclass  # noqa: F401  (presence check)
        except ImportError as exc:  # pragma: no cover - desktop/CI path
            raise RuntimeError("IosBillingProvider requires pyobjus on a kivy-ios build.") from exc
        # TODO(phase6): SKProductsRequest; SKPaymentQueue observer.
        self._ready = False

    def purchase(self, product_id: str) -> PurchaseResult:  # pragma: no cover - device only
        # TODO(phase6): add SKPayment, observe transaction, return Receipt with
        # platform="apple" and the transaction/receipt data as `token`.
        raise NotImplementedError("StoreKit purchase flow is wired on-device in Phase 6.")

    def restore(self) -> list[Receipt]:  # pragma: no cover - device only
        # TODO(phase6): restoreCompletedTransactions -> receipts.
        raise NotImplementedError("StoreKit restore is wired on-device in Phase 6.")
