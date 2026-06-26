# CLAUDE.md — Real Mogul architecture rules (working memory)

> This file encodes the non-negotiable architecture rules from Section 3 of
> `REAL_MOGUL_build_plan.md`. Read it before writing or changing code. If a
> change would violate a rule here, stop and flag it instead.

## The one hard rule: separate the brain from the face

The **simulation is the product**. It must stay pure, deterministic, and fully
tested. The UI is a thin, replaceable client. This is what makes "every platform"
achievable and lets us swap the renderer without rewriting the economy.

## Layer boundaries (enforced by discipline + tests)

```
engine/        PURE PYTHON. No UI, no platform, no I/O side effects beyond save/.
               Deterministic. Everything random routes through engine/rng.py.
education/      Reads from engine outputs. Generates explanations. No UI imports.
monetization/   Catalog + entitlement state behind interfaces. No platform code.
ui/             Presentation only. Imports engine/education/monetization. Thin.
nativebridge/   The ONLY place native code lives (billing bridges, ads, analytics).
                This is the brief's "platform/" layer, renamed: a package literally
                named `platform` shadows the stdlib `platform` module (Kivy imports
                it) and breaks the app. Native imports (pyjnius/pyobjus) are lazy so
                modules import on desktop; only instantiating a real bridge off-device
                raises. The provider is injected at startup (provider_for_platform).
tools/          Headless dev tooling (balance sim, atlas packer, deal replay).
tests/          pytest. Engine coverage target >= 90%.
```

### Import direction (never violate)

- `engine/` imports **nothing** from `ui/`, `platform/`, `monetization/`,
  `education/`. It is self-contained.
- `education/`, `monetization/` may import `engine/`. Not `ui/` or `platform/`.
- `ui/` may import `engine/`, `education/`, `monetization/`. Never `nativebridge/`
  directly — a provider is injected at startup (see `main.py`).
- `nativebridge/` implements interfaces declared in `monetization/` (and adapters
  for ads/analytics). Engine never knows it exists.

A unit test (`tests/test_architecture.py`) asserts these boundaries by scanning
imports. Keep it green.

## Determinism rules

- All randomness goes through `engine/rng.py` (seeded). No bare `random` /
  `numpy.random` / `secrets` inside `engine/`.
- Same seed + same inputs => identical outcome. This underpins tests, replays,
  fairness, and anti-cheat. Do not introduce wall-clock, threading, or dict-order
  dependence into engine outputs.

## Finance / economy rules

- Money math lives in `engine/finance/`. Each formula is also an education
  trigger — keep formulas expressible as plain functions so `education/` can
  render "explain this deal" with the player's own numbers, never out of sync.
- Tunable constants live ONLY in `engine/economy_balance/`. No magic numbers
  scattered through logic. Designers own that file.

## Saves

- Saves are versioned JSON + checksum (`engine/save/`). Never wipe a save on a
  schema change — add a migration in `engine/save/migrations/`. Round-trip must
  be lossless.

## Monetization guardrails (bake in from day one)

- Campaign must be fully completable with **zero spend**.
- No mechanic lets a payer beat a non-payer on a fixed-seed challenge/leaderboard.
- Every revenue stream sits behind a feature flag so it can be tuned/disabled.
- Client never trusts itself for entitlements — server-side receipt verification.

## UI layer (Kivy — decided Phase 3)

- Shipping framework is **Kivy** (spike in `spikes/`, findings in
  `spikes/SPIKE_FINDINGS.md`). Do not switch — the brief forbids it post-Phase 2.
- `ui/controller.py` (`GameController`) is the **thin presenter**: Kivy-free,
  imports engine + education only, fully unit-tested headless. Kivy widgets
  (`ui/app.py`, `ui/board.py`) are dumb — they render view-models and forward
  taps. Never put game logic or money math in a widget.
- **Owned assets: the holding is the single source of truth.** A for-sale lot
  carries its listing in `town.lots[id].property_`. On acquisition `Lot.acquired()`
  **clears** that field (sets it to `None`); from then on the owned, mutable copy
  lives only in `session.holdings[id].property_`, which is what renovations,
  builds, and anchor changes mutate. So the town lot can never serve a stale owned
  copy — reading it for an owned lot yields `None`, not old numbers. For anything
  an owned lot displays or computes, read `holdings[id].property_` (see
  `GameController._display_property`). Old saves are normalized by the v2→v3
  migration, which nulls `property` on owned lots.

## Monetization (Phase 5)

- `monetization/` is pure-Python: catalog, entitlements, a `BillingProvider`
  interface + `MockBillingProvider`, feature flags, guardrails, and a coordinator
  (`MonetizationManager`). It may import `engine`, never `ui`/`platform`.
- **Native billing lives in `platform/`** (Phase 6) and implements
  `monetization.billing.BillingProvider`. The engine/UI never import it.
- **Server-side verification is mandatory.** The client only updates entitlements
  from a verified grant. The FastAPI service is `monetization/verify_service.py`
  (pure logic in `verify.py`). `verify_service.py` deliberately omits
  `from __future__ import annotations` — FastAPI must resolve the request model to
  a real class, not a string.
- **No pay-to-win, by construction.** Because `engine/` can't import
  `monetization/`, nothing sold can touch a fixed-seed/challenge outcome. Every
  product also carries `affects_fairness=False` (a test enforces it). The campaign
  must stay completable with zero spend.

## Phase gates

Build in the phase order in `REAL_MOGUL_build_plan.md` Section 10. **Do not start
UI (Phase 3) until Phase 1 & 2 acceptance criteria pass.** Each phase has explicit
acceptance criteria — treat them as gates, not suggestions.

## Tooling

- Format/lint: `ruff` + `black`. Run `pre-commit` before committing.
- Tests: `pytest`. Engine coverage >= 90% is a release gate.
- Python: 3.10+.
