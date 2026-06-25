"""Billing provider interface + a dev MockBillingProvider.

The engine/UI never import platform billing code — they depend on this
``BillingProvider`` interface. Real bridges (Play Billing via pyjnius, StoreKit
via pyobjus) live in ``platform/`` and implement it in Phase 6. On desktop/web we
ship ``MockBillingProvider`` so the whole purchase + verify + entitle flow is
exercisable without a store.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Receipt:
    """Proof of purchase the client sends to the verification server. The client
    never trusts this itself — only the server's verdict grants entitlements."""

    product_id: str
    token: str
    platform: str  # "mock" | "google" | "apple"
    signature: str


@dataclass(frozen=True)
class PurchaseResult:
    success: bool
    receipt: Receipt | None = None
    error: str = ""


def sign(secret: str, platform: str, product_id: str, token: str) -> str:
    msg = f"{platform}|{product_id}|{token}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


class BillingProvider(ABC):
    @abstractmethod
    def purchase(self, product_id: str) -> PurchaseResult: ...

    @abstractmethod
    def restore(self) -> list[Receipt]:
        """Receipts for non-consumables/subscriptions already owned (new device)."""


class MockBillingProvider(BillingProvider):
    """A fake store for dev. Signs receipts with a shared dev secret so the mock
    verifier accepts them, and remembers purchases so ``restore`` works."""

    def __init__(self, secret: str, *, fail_product_ids: set[str] | None = None) -> None:
        self._secret = secret
        self._fail = fail_product_ids or set()
        self._issued: list[Receipt] = []

    def purchase(self, product_id: str) -> PurchaseResult:
        if product_id in self._fail:
            return PurchaseResult(success=False, error="user_cancelled")
        token = uuid.uuid4().hex
        receipt = Receipt(
            product_id=product_id,
            token=token,
            platform="mock",
            signature=sign(self._secret, "mock", product_id, token),
        )
        self._issued.append(receipt)
        return PurchaseResult(success=True, receipt=receipt)

    def restore(self) -> list[Receipt]:
        return list(self._issued)
