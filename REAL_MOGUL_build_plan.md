# Real Mogul — Build Plan & Engineering Brief

**Working title:** **real mogul** *(the real-estate tycoon that actually teaches you the deal)*

**Tagline:** *"Buy low. Build smart. Learn the game while you play it."*

> **How to use this document.** This is the master brief. It lives in the repo
> root alongside `CLAUDE.md`, which keeps the architecture rules in working
> memory. Build in the phase order given. Each phase has explicit **acceptance
> criteria** — do not advance until they pass.

---

## 1. The product in one paragraph

real mogul is a cross-platform (iOS, Android, Windows, macOS, Linux, and web)
real-estate tycoon game in the spirit of *Build-a-Lot*, but with two things that
genre lacks: (1) **real financial fidelity** — you learn cap rate, NOI, IRR,
cash-on-cash, LTV, DSCR, draw schedules, refinancing, and 1031 exchanges by using
them to win, across **both residential and commercial** asset classes; and (2) **a
dynamic market** that moves with interest rates, demand cycles, and local events
instead of static price tags. It is free-to-play with **ethical, non-pay-to-win
monetization**: cosmetics, a "Mogul Pass" season track, optional rewarded ads, an
ad-removal/education-pack subscription, and convenience currency that never gates
the campaign.

## 2. Improving over Build-a-Lot

| Build-a-Lot did this | real mogul does this instead |
|---|---|
| Static prices | **Live market**: prices/rents driven by an interest-rate curve, supply/demand, and neighborhood "heat" |
| All-cash or trivial loans | **Real financing**: mortgages, construction loans with interest reserves, refis, DSCR-gated lending |
| Residential only | **Residential + commercial**: SFR, multifamily, retail, office, industrial, mixed-use |
| Rent = flat number | **NOI math**: gross rent - vacancy - opex = NOI; value = NOI / cap rate |
| Linear levels | **Campaign + Sandbox + Daily/Weekly challenges + Prestige** |
| No teaching | **Mentor system + Deal Lab**: tooltips, glossary, "explain this deal" overlays |

**Core fun loop (<=90 seconds):** scout a deal -> run the numbers (assisted) ->
finance it -> build/renovate (timed, worker/material constrained) -> lease or flip
-> watch NOI/equity climb -> reinvest or refinance to pull cash out -> unlock the
next market. Each level injects an **event** (rate hike, zoning change, anchor
tenant leaves, boom town) that forces a strategy pivot.

## 3. Architecture

See `CLAUDE.md` for the enforced rules. Summary: pure-Python deterministic
`engine/`, thin `ui/`, native code isolated in `platform/`.

- **Primary UI:** Kivy + KivyMD. Android via buildozer (python-for-android), iOS
  via kivy-ios. Same build runs desktop.
- **Web:** pygbag (pygame-ce -> WASM) as a showcase/onboarding surface, not the
  monetized client.
- **Spike (timeboxed):** evaluate Flet / BeeWare in Phase 1-2 downtime. Do not
  switch after Phase 2.
- **IAP:** Android via pyjnius -> Play Billing; iOS via pyobjus -> StoreKit. Both
  behind a `BillingProvider` interface. Server-side receipt verification (FastAPI)
  is mandatory. `MockBillingProvider` for dev/desktop/web.

## 4. Simulation core — formulas (the teaching engine)

Implemented as pure functions in `engine/finance/`. Each formula is a lesson
trigger.

- `gross_potential_rent = sum(unit_rent)`
- `EGI = GPR * (1 - vacancy_rate) + other_income`
- `OpEx = taxes + insurance + maintenance + mgmt + capex_reserve`
- `NOI = EGI - OpEx`
- `cap_rate = NOI / property_value`; `value = NOI / market_cap_rate`
- `cash_on_cash = (NOI - debt_service) / cash_invested`
- Amortizing mortgage: `M = P*r*(1+r)^n / ((1+r)^n - 1)`
- Construction loan with **interest reserve** (interest-on-interest circularity)
- `LTV` gates borrowing; `DSCR = NOI / annual_debt_service` gates approval
- Refinance / cash-out refi
- `IRR` / `XIRR` via Newton's method on the deal cash-flow timeline
- Advanced: 1031 exchange, depreciation/cost-seg, JV waterfall (pref -> return of
  capital -> promote), pro-rata distributions

**Market model (`engine/economy/`):** a drifting/shocking rate curve; demand/heat
per neighborhood; seasonality and supply. **Determinism:** everything routes
through `engine/rng.py`.

## 5. Game modes

1. **Campaign ("Climb")** — ~40 handcrafted levels, each a learning objective + a twist.
2. **Sandbox ("Open Market")** — infinite, seed-shareable.
3. **Daily Deal / Weekly Challenge** — fixed-seed, leaderboard by IRR or net worth.
4. **Prestige ("Go National")** — reset for permanent multipliers + new region.
5. **Career path flavor** — Flipper / Landlord / Developer / Syndicator perks.

## 6. Education layer (`education/`)

Opt-in and frictionless. "Explain this deal" overlay; mentor characters; glossary
("The Closet"); mistake-as-lesson cards; stealth assessment; certification stretch
goal ("real mogul Academy").

## 7. Monetization (ethical hybrid)

Behind `monetization/` with feature flags: cosmetics; "Mogul Pass" season track;
opt-in rewarded ads; ad-removal + Education Pack subscription; convenience currency
("Keys", dual-currency with soft "Cash"); one-time "Founder's Pack". Guardrails:
clear price/value, purchase confirmation, spending limits + parental controls,
probability disclosure, no pay-to-win on leaderboards.

## 8. Art pipeline

Clean warm isometric (2:1 grid). Style bible first. ~6 lot states x 6 asset
classes x 3 tiers + mentors + UI kit. Sprite atlas (Kivy `Atlas`). AI-assisted,
human-curated, disclosed. Author @3x, ship downscaled buckets. Cheap juicy
animation. `tools/pack_atlas.py` for one-command handoff.

## 9. Cross-platform delivery & compliance

CI from day one (desktop + Dockerized buildozer Android on push; manual iOS).
Store readiness (privacy labels, data safety, age rating, COPPA). Versioned saves
+ migrations. Privacy-first analytics + remote config + feature flags.
Localization scaffolding (externalize strings).

## 10. Phased build plan (do in order)

**Phase 0 — Scaffold & guardrails.** Repo structure, `CLAUDE.md`,
`pyproject.toml`, pytest, ruff/black, pre-commit, CI skeleton.
*Accept:* `pytest` green on a trivial test; CI passes; lint clean.

**Phase 1 — Engine: finance & economy (no UI).** Section 4 formulas + full unit
tests + seeded RNG. `tools/balance_sim.py` plays 10,000 headless deals.
*Accept:* >=90% coverage on `engine/finance`; sane non-degenerate economy (no
infinite-money exploit); formulas match hand-computed fixtures.

**Phase 2 — Engine: world, assets, progression, save.** Towns/lots/zoning, res +
commercial classes, upgrade trees, twist events, campaign objectives, versioned
saves + one migration.
*Accept:* headless full level start->win; save/load round-trips; a forced
rate-shock twist measurably changes optimal play.

**Phase 3 — UI vertical slice (one playable level).** Framework spike resolved.
Isometric board, deal/finance panel, build timers, one level end-to-end on desktop.
*Accept:* a person plays one level to completion on desktop with placeholder art;
"Explain this deal" shows correct live numbers.

**Phase 4 — Education layer + art pass.** Mentors, glossary, explain-overlays,
mistake cards. Style-bible art + atlas + juice/SFX.
*Accept:* every computed metric tappable->explained; first 5 levels art-complete,
legible on a 5" screen.

**Phase 5 — Monetization.** Catalog + entitlements + `MockBillingProvider`;
FastAPI receipt-verify; cosmetics, Keys, rewarded-ad hooks, Mogul Pass,
subscription — all flagged. Spending limits/parental controls/disclosures.
*Accept:* full campaign completable with zero spend; mock purchases grant
entitlements and survive relaunch; no pay-to-win on fixed-seed challenge.

**Phase 6 — Mobile packaging & native bridges.** Android buildozer + pyjnius
billing; iOS kivy-ios + pyobjus StoreKit; ad mediation; analytics; device QA.
*Accept:* signed Android sandbox purchase end-to-end with server verification;
iOS sandbox purchase verified; pygbag web demo deploys.

**Phase 7 — Content, balance, soft launch.** 40-level campaign, daily/weekly,
prestige, Mogul Pass season 1, remote-config balance, soft launch.
*Accept:* D1 retention and crash-free rate clear pre-set thresholds.

## 11. First commands

1. Generate `CLAUDE.md`, `README.md`, Phase 0 scaffold. *(done)*
2. Implement Phase 1 `engine/finance` with pytest fixtures from hand-computed
   examples. Then build `tools/balance_sim.py`.
3. Tune `engine/economy_balance/` until no infinite-money exploit.
4. Proceed phase by phase; no UI until Phase 1-2 accept.

## 12. Risks & caveats

iOS/Android Python packaging is the riskiest part, not the game logic —
containerize buildozer, build in CI early, keep native code minimal/isolated. IAP
needs native bridges + a verification server. Scope discipline: engine + 5 polished
levels + one monetization stream is a shippable MVP. Balance is a product — invest
in the simulator.
