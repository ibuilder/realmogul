"""The FastAPI receipt-verification service. Skips cleanly if FastAPI is absent."""

import os

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from monetization.billing import MockBillingProvider  # noqa: E402
from monetization.verify_service import _make_app  # noqa: E402

SECRET = "service-secret"


@pytest.fixture
def client():
    os.environ["REALMOGUL_MOCK_SECRET"] = SECRET
    return TestClient(_make_app())


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_verify_accepts_valid_receipt(client):
    receipt = MockBillingProvider(SECRET).purchase("founders_pack").receipt
    resp = client.post(
        "/verify",
        json={
            "product_id": receipt.product_id,
            "token": receipt.token,
            "platform": receipt.platform,
            "signature": receipt.signature,
        },
    )
    body = resp.json()
    assert body["valid"] is True
    assert body["product_id"] == "founders_pack"


def test_verify_rejects_tampered_receipt(client):
    receipt = MockBillingProvider(SECRET).purchase("keys_small").receipt
    resp = client.post(
        "/verify",
        json={
            "product_id": receipt.product_id,
            "token": receipt.token,
            "platform": "mock",
            "signature": "tampered",
        },
    )
    assert resp.json()["valid"] is False


def test_verify_rejects_wrong_secret():
    os.environ["REALMOGUL_MOCK_SECRET"] = "the-server-secret"
    client = TestClient(_make_app())
    # Receipt signed with a *different* secret than the server holds.
    receipt = MockBillingProvider("attacker-secret").purchase("keys_large").receipt
    resp = client.post(
        "/verify",
        json={
            "product_id": receipt.product_id,
            "token": receipt.token,
            "platform": receipt.platform,
            "signature": receipt.signature,
        },
    )
    assert resp.json()["valid"] is False
