"""FastAPI receipt-verification service — the server the client must trust.

A thin wrapper over ``verify.verify_receipt``; the real Apple/Google API calls
land here in Phase 6. The dev secret comes from the environment so it never ships
in the client. Run:

    uvicorn monetization.verify_service:app --port 8000
"""

# NOTE: intentionally no `from __future__ import annotations` here — FastAPI must
# resolve the request-model annotation to a real class, not a string.

import os

from monetization.billing import Receipt
from monetization.verify import verify_receipt


def _make_app():
    # Imported lazily so the rest of monetization has no hard FastAPI dependency.
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI(title="Real Mogul — receipt verification")
    secret = os.environ.get("REALMOGUL_MOCK_SECRET", "dev-secret-change-me")

    class ReceiptIn(BaseModel):
        product_id: str
        token: str
        platform: str
        signature: str

    class VerdictOut(BaseModel):
        valid: bool
        product_id: str
        platform: str
        reason: str = ""

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/verify", response_model=VerdictOut)
    def verify(receipt: ReceiptIn) -> VerdictOut:
        result = verify_receipt(
            Receipt(
                product_id=receipt.product_id,
                token=receipt.token,
                platform=receipt.platform,
                signature=receipt.signature,
            ),
            mock_secret=secret,
        )
        return VerdictOut(
            valid=result.valid,
            product_id=result.product_id,
            platform=result.platform,
            reason=result.reason,
        )

    return app


# Created at import only if FastAPI is installed; tests build it via _make_app().
try:  # pragma: no cover - trivial import guard
    app = _make_app()
except ImportError:  # pragma: no cover
    app = None
