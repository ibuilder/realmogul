"""Google Play Billing bridge (pyjnius) — implements BillingProvider.

Scaffold for Phase 6. The flow on-device:

1. Connect a ``BillingClient`` (Play Billing Library) via pyjnius.
2. ``purchase(product_id)`` launches the billing flow and, on success, returns a
   ``Receipt`` carrying the Play **purchase token** (platform="google").
3. The client sends that receipt to the FastAPI verify service, which calls the
   Google Play Developer API to confirm it server-side before entitling.

pyjnius is only available inside a python-for-android build, so the import is
lazy: this module imports fine everywhere, but constructing the provider off
Android raises a clear error.
"""

from __future__ import annotations

from monetization.billing import BillingProvider, PurchaseResult, Receipt


class AndroidBillingProvider(BillingProvider):
    def __init__(self) -> None:
        try:
            from jnius import autoclass  # noqa: F401  (presence check)
        except ImportError as exc:  # pragma: no cover - desktop/CI path
            raise RuntimeError(
                "AndroidBillingProvider requires pyjnius on an Android (p4a) build."
            ) from exc
        # TODO(phase6): autoclass BillingClient/PurchaseParams; connect; cache.
        self._connected = False

    def purchase(self, product_id: str) -> PurchaseResult:  # pragma: no cover - device only
        # TODO(phase6): launchBillingFlow, await onPurchasesUpdated, build Receipt
        # with platform="google" and the Play purchase token as `token`.
        raise NotImplementedError("Play Billing purchase flow is wired on-device in Phase 6.")

    def restore(self) -> list[Receipt]:  # pragma: no cover - device only
        # TODO(phase6): queryPurchasesAsync(INAPP + SUBS) -> receipts.
        raise NotImplementedError("Play Billing restore is wired on-device in Phase 6.")
