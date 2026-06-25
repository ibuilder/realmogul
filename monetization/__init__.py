"""Real Mogul monetization — catalog, entitlements, billing interface, guardrails.

Ethical hybrid (brief §7): cosmetics, convenience Keys, Mogul Pass, an education
subscription, and a one-time Founder's Pack — all behind feature flags. The
campaign is completable with zero spend, and because ``engine/`` can't import this
package, nothing here can affect a fixed-seed/challenge outcome. Platform billing
bridges (Phase 6) implement ``billing.BillingProvider``; the client only ever
trusts the server-side verifier.
"""

from monetization.billing import (
    BillingProvider,
    MockBillingProvider,
    PurchaseResult,
    Receipt,
)
from monetization.catalog import CATALOG, Category, Kind, Product, all_products, get_product
from monetization.entitlements import Entitlements
from monetization.flags import DEFAULT_FLAGS, FeatureFlags
from monetization.guardrails import SpendingGuard, probability_disclosure
from monetization.manager import MonetizationManager, PurchaseOutcome
from monetization.verify import VerificationResult, verify_receipt

__all__ = [
    "BillingProvider",
    "MockBillingProvider",
    "PurchaseResult",
    "Receipt",
    "CATALOG",
    "Category",
    "Kind",
    "Product",
    "all_products",
    "get_product",
    "Entitlements",
    "DEFAULT_FLAGS",
    "FeatureFlags",
    "SpendingGuard",
    "probability_disclosure",
    "MonetizationManager",
    "PurchaseOutcome",
    "VerificationResult",
    "verify_receipt",
]
