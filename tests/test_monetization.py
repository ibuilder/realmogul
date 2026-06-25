"""Monetization: catalog ethics, entitlements, guardrails, verify, and the
purchase/reconcile flow — including the brief's hard acceptance criteria."""

from pathlib import Path

import pytest

from monetization.billing import MockBillingProvider, Receipt
from monetization.catalog import CATALOG, Kind, all_products, get_product
from monetization.entitlements import RESTORABLE_KINDS, Entitlements
from monetization.flags import FeatureFlags
from monetization.guardrails import SpendingGuard, probability_disclosure
from monetization.manager import MonetizationManager
from monetization.verify import verify_receipt

SECRET = "test-secret"
NOW = 1_700_000_000.0


def _manager(tmp_path, *, flags=None, guard=None, provider=None, secret=SECRET):
    return MonetizationManager(
        provider or MockBillingProvider(SECRET),
        mock_secret=secret,
        flags=flags or FeatureFlags(),
        guard=guard,
        save_path=tmp_path / "ent.json",
        clock=lambda: NOW,
    )


# ---------------- catalog ethics (no pay-to-win, by construction) ----------------
def test_no_product_affects_fairness():
    # The headline guardrail: nothing sold can tilt a fixed-seed/challenge outcome.
    assert all(p.affects_fairness is False for p in all_products())


def test_catalog_is_well_formed():
    assert CATALOG, "catalog must not be empty"
    for pid, product in CATALOG.items():
        assert product.id == pid
        assert product.price_usd > 0


def test_grants_only_touch_cosmetic_or_convenience():
    # Grants may give keys/cosmetics/ad-free/education/pass/subscription — never
    # any handle on the deterministic economy (there's no field for it to).
    allowed = {
        "keys",
        "cosmetics",
        "ad_free",
        "education_unlocked",
        "pass_premium",
        "subscription_days",
    }
    for product in all_products():
        assert set(vars(product.grant)) <= allowed


# ---------------- entitlements ----------------
def test_founders_pack_grants_bundle():
    ent = Entitlements()
    ent.grant(get_product("founders_pack"), NOW)
    assert ent.ad_free and ent.education_unlocked
    assert ent.keys == 300
    assert ent.has_cosmetic("skin_founder")


def test_subscription_activates_and_expires():
    ent = Entitlements()
    ent.grant(get_product("edu_sub_monthly"), NOW)
    assert ent.subscription_active(NOW)
    assert not ent.subscription_active(NOW + 31 * 86_400)  # lapsed after 30 days


def test_keys_spend():
    ent = Entitlements(keys=60)
    assert ent.spend_keys(50)
    assert ent.keys == 10
    assert not ent.spend_keys(50)  # insufficient


def test_entitlements_round_trip():
    ent = Entitlements(keys=120, cosmetics={"a", "b"}, ad_free=True, subscription_until=NOW)
    assert Entitlements.from_dict(ent.to_dict()) == ent


# ---------------- verification ----------------
def test_verify_accepts_good_and_rejects_tampered():
    prov = MockBillingProvider(SECRET)
    receipt = prov.purchase("keys_small").receipt
    assert verify_receipt(receipt, mock_secret=SECRET).valid
    tampered = Receipt(receipt.product_id, receipt.token, "mock", "deadbeef")
    assert not verify_receipt(tampered, mock_secret=SECRET).valid


def test_verify_real_stores_not_yet_implemented():
    r = Receipt("founders_pack", "tok", "apple", "sig")
    result = verify_receipt(r, mock_secret=SECRET)
    assert not result.valid and "not_implemented" in result.reason


# ---------------- guardrails ----------------
def test_daily_cap_blocks_overspend():
    guard = SpendingGuard(daily_cap_usd=5.0)
    cheap = get_product("firm_logo_gold")  # 0.99
    big = get_product("founders_pack")  # 14.99
    assert guard.check(big, NOW) == "daily_cap_reached"
    assert guard.check(cheap, NOW) is None


def test_parental_lock_requires_code():
    guard = SpendingGuard(parental_lock=True)
    product = get_product("keys_small")
    assert guard.check(product, NOW) == "parental_lock"
    assert guard.check(product, NOW, parental_code_ok=True) is None


def test_no_randomized_purchases_disclosure():
    assert "no loot boxes" in probability_disclosure().lower()


# ---------------- manager flow ----------------
def test_purchase_grants_and_persists(tmp_path: Path):
    m = _manager(tmp_path)
    assert m.purchase("founders_pack").ok
    assert m.is_ad_free()
    assert (tmp_path / "ent.json").exists()


def test_purchase_blocked_when_feature_disabled(tmp_path: Path):
    m = _manager(tmp_path, flags=FeatureFlags(cosmetics=False))
    out = m.purchase("skin_brick")
    assert not out.ok and out.error == "feature_disabled"


def test_purchase_rejected_on_bad_signature(tmp_path: Path):
    # Provider signs with one secret; the server verifies with another -> rejected.
    m = _manager(tmp_path, provider=MockBillingProvider("other-secret"))
    out = m.purchase("keys_small")
    assert not out.ok and out.error == "bad_signature"
    assert m.entitlements.keys == 0  # nothing granted


def test_relaunch_restores_from_disk(tmp_path: Path):
    m1 = _manager(tmp_path)
    m1.purchase("founders_pack")
    m1.purchase("keys_large")
    m2 = _manager(tmp_path)  # fresh manager, same save file
    assert m2.is_ad_free()
    assert m2.entitlements.keys == 900


def test_reconcile_restores_durable_but_not_consumables(tmp_path: Path):
    provider = MockBillingProvider(SECRET)
    m1 = _manager(tmp_path, provider=provider)
    m1.purchase("founders_pack")  # non-consumable
    m1.purchase("keys_small")  # consumable (50 keys)
    # New device: same store account (provider remembers), but empty local state.
    fresh = MonetizationManager(
        provider, mock_secret=SECRET, save_path=tmp_path / "new.json", clock=lambda: NOW
    )
    fresh.reconcile()
    assert fresh.is_ad_free()  # founders restored
    assert fresh.entitlements.keys == 300  # founder's 300, NOT the consumable 50 again


# ---------------- acceptance: zero-spend completable ----------------
def test_campaign_needs_no_purchases():
    # The engine can't import monetization (enforced by tests/test_architecture),
    # so the campaign is completable with zero spend by construction. Confirm a
    # level still wins with no manager anywhere in the loop.
    from engine.progression.campaign import build_level_one
    from tools.play_level import play

    assert play(build_level_one()).won


def test_restorable_kinds():
    assert Kind.NON_CONSUMABLE in RESTORABLE_KINDS
    assert Kind.CONSUMABLE not in RESTORABLE_KINDS


def test_subscription_grants_ad_free_via_active_window(tmp_path: Path):
    m = _manager(tmp_path)
    assert m.purchase("edu_sub_monthly").ok
    assert m.is_ad_free() and m.education_unlocked()


def test_unknown_product(tmp_path: Path):
    assert _manager(tmp_path).purchase("nope").error == "unknown_product"


pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")
