"""Feature flags — every revenue stream sits behind one (CLAUDE.md guardrail).

Lets us tune or kill any monetization surface without a code change or store
update (remote config flips these in production). All default on in dev; a flag
off means the catalog hides those products and the manager refuses to sell them.
"""

from __future__ import annotations

from dataclasses import dataclass

from monetization.catalog import Category


@dataclass(frozen=True)
class FeatureFlags:
    cosmetics: bool = True
    keys: bool = True  # convenience currency
    rewarded_ads: bool = True
    mogul_pass: bool = True
    subscription: bool = True
    founders_pack: bool = True

    def category_enabled(self, category: Category) -> bool:
        return {
            Category.COSMETIC: self.cosmetics,
            Category.CURRENCY: self.keys,
            Category.PASS: self.mogul_pass,
            Category.SUBSCRIPTION: self.subscription,
            Category.AD_REMOVAL: self.subscription or self.founders_pack,
            Category.FOUNDERS: self.founders_pack,
        }[category]


DEFAULT_FLAGS = FeatureFlags()
