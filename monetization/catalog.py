"""The IAP catalog — what's for sale, and crucially what it can and cannot grant.

Ethical by construction (CLAUDE.md): products grant **cosmetics, convenience, or
education** — never an edge that beats a non-paying player on a fixed-seed
challenge. Every product carries ``affects_fairness=False``; a test asserts the
whole catalog stays that way, and the engine can't even see entitlements, so
pay-to-win is structurally impossible, not just policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Kind(str, Enum):
    CONSUMABLE = "consumable"  # spent (Keys packs)
    NON_CONSUMABLE = "non_consumable"  # owned forever (cosmetics, founders, ad-free)
    SUBSCRIPTION = "subscription"  # time-limited (education pass)


class Category(str, Enum):
    COSMETIC = "cosmetic"
    CURRENCY = "currency"
    PASS = "pass"
    SUBSCRIPTION = "subscription"
    AD_REMOVAL = "ad_removal"
    FOUNDERS = "founders"


@dataclass(frozen=True)
class Grant:
    """What a purchase confers. None of these touch deterministic gameplay."""

    keys: int = 0
    cosmetics: tuple[str, ...] = ()
    ad_free: bool = False
    education_unlocked: bool = False
    pass_premium: bool = False
    subscription_days: int = 0


@dataclass(frozen=True)
class Product:
    id: str
    title: str
    kind: Kind
    category: Category
    price_usd: float
    grant: Grant
    # Hard invariant: no product may affect a fixed-seed/challenge outcome.
    affects_fairness: bool = field(default=False)


CATALOG: dict[str, Product] = {
    # --- cosmetics (highest-trust revenue; pure vanity) ---
    "skin_brick": Product(
        "skin_brick",
        "Classic Brick façade",
        Kind.NON_CONSUMABLE,
        Category.COSMETIC,
        1.99,
        Grant(cosmetics=("skin_brick",)),
    ),
    "skin_artdeco": Product(
        "skin_artdeco",
        "Art Deco façade",
        Kind.NON_CONSUMABLE,
        Category.COSMETIC,
        2.99,
        Grant(cosmetics=("skin_artdeco",)),
    ),
    "firm_logo_gold": Product(
        "firm_logo_gold",
        "Gold firm logo",
        Kind.NON_CONSUMABLE,
        Category.COSMETIC,
        0.99,
        Grant(cosmetics=("firm_logo_gold",)),
    ),
    # --- convenience currency (Keys); campaign fully completable without ---
    "keys_small": Product(
        "keys_small",
        "Pouch of 50 Keys",
        Kind.CONSUMABLE,
        Category.CURRENCY,
        0.99,
        Grant(keys=50),
    ),
    "keys_large": Product(
        "keys_large",
        "Vault of 600 Keys",
        Kind.CONSUMABLE,
        Category.CURRENCY,
        7.99,
        Grant(keys=600),
    ),
    # --- Mogul Pass (season track, premium tier) ---
    "mogul_pass_s1": Product(
        "mogul_pass_s1",
        "Mogul Pass — Season 1",
        Kind.NON_CONSUMABLE,
        Category.PASS,
        9.99,
        Grant(pass_premium=True, keys=100),
    ),
    # --- subscription: ad-free + full Academy + monthly Keys stipend ---
    "edu_sub_monthly": Product(
        "edu_sub_monthly",
        "Education Pass (monthly)",
        Kind.SUBSCRIPTION,
        Category.SUBSCRIPTION,
        4.99,
        Grant(ad_free=True, education_unlocked=True, subscription_days=30, keys=100),
    ),
    # --- one-time premium unlock for F2P-haters ---
    "founders_pack": Product(
        "founders_pack",
        "Founder's Pack",
        Kind.NON_CONSUMABLE,
        Category.FOUNDERS,
        14.99,
        Grant(ad_free=True, education_unlocked=True, cosmetics=("skin_founder",), keys=300),
    ),
}


def get_product(product_id: str) -> Product | None:
    return CATALOG.get(product_id)


def all_products() -> list[Product]:
    return list(CATALOG.values())
