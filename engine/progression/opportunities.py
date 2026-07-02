"""Random opportunities — surprise deals that break the optimization monotony.

Two kinds:
- **distressed**: a property comes to market below value for a few months — grab it
  cheap or let it pass.
- **buyout**: an unsolicited offer to buy one of your buildings *above* market —
  take the premium or hold.

Generated on a *separate* RNG stream (``session.opp_rng``) so they never perturb
the deterministic market path the campaign is balanced against. Pure data; the
session generates, applies, and expires them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Opportunity:
    id: str
    kind: str  # "distressed" | "buyout"
    expires_month: int
    headline: str
    lot_id: str  # distressed: the new listing's lot; buyout: the holding offered
    discount: float = 0.0  # distressed: fraction below market
    premium: float = 0.0  # buyout: fraction above market
    # distressed property spec (so the session can mint the listing):
    asset_class: str | None = None
    units: int = 1
    condition: float = 0.8
