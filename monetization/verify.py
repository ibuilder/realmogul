"""Server-side receipt verification (pure core).

Mandatory for any non-consumable/subscription: the client never trusts itself.
This is the logic the FastAPI service (``verify_service.py``) wraps. For the mock
platform we recompute the HMAC; for the real stores the verdict comes from Apple/
Google's APIs (wired in Phase 6) — stubbed here so the contract is clear.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from monetization.billing import Receipt, sign


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    product_id: str
    platform: str
    reason: str = ""


def verify_receipt(receipt: Receipt, *, mock_secret: str) -> VerificationResult:
    """Validate a receipt. Returns a verdict; never raises on a bad receipt."""
    if receipt.platform == "mock":
        expected = sign(mock_secret, "mock", receipt.product_id, receipt.token)
        ok = hmac.compare_digest(expected, receipt.signature)
        return VerificationResult(
            valid=ok,
            product_id=receipt.product_id,
            platform="mock",
            reason="" if ok else "bad_signature",
        )
    if receipt.platform in ("google", "apple"):
        # Phase 6: call Play Developer API / App Store Server API here.
        return VerificationResult(
            valid=False,
            product_id=receipt.product_id,
            platform=receipt.platform,
            reason="store_verification_not_implemented",
        )
    return VerificationResult(False, receipt.product_id, receipt.platform, "unknown_platform")
