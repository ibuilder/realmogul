# real mogul

*The real-estate tycoon that actually teaches you the deal.*

> Buy low. Build smart. Learn the game while you play it.

A cross-platform (iOS, Android, Windows, macOS, Linux, web) real-estate tycoon
game in the spirit of *Build-a-Lot*, with two things that genre lacks:

1. **Real financial fidelity** — cap rate, NOI, IRR, cash-on-cash, LTV, DSCR,
   draw schedules, refinancing, and 1031 exchanges, learned by using them to win,
   across residential **and** commercial asset classes.
2. **A dynamic market** — prices and rents move with an interest-rate curve,
   supply/demand, and local events instead of static price tags.

Free-to-play with ethical, non-pay-to-win monetization.

## Architecture in one line

A pure-Python, fully-tested **simulation core** (`engine/`) with a thin,
swappable UI. Read [`CLAUDE.md`](CLAUDE.md) before contributing — the layer
boundaries are enforced.

```
engine/          pure deterministic simulation (the product's real value)
education/        glossary, lesson triggers, "explain this deal" generators
monetization/     IAP catalog + entitlements behind interfaces (no platform code)
ui/               thin presentation layer (Kivy primary)
platform/         the only place native code lives (billing, ads, analytics)
tools/            headless dev tooling (balance sim, atlas packer, deal replay)
tests/            pytest; engine coverage target >= 90%
```

## Quick start (dev)

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Git Bash:           source .venv/Scripts/activate
pip install -e ".[dev]"
pre-commit install
pytest

# Watch the engine play itself (headless):
python -m tools.balance_sim --deals 10000 --seed 1   # economy audit
python -m tools.play_level                           # campaign level 1 start->win
python -m tools.play_level --all                     # all campaign levels start->win

# Play the Kivy desktop slice (needs a display):
pip install kivy
python -m ui                                         # play level 1
python -m ui --shot                                  # capture screenshots to ui/_shots/

# Run the receipt-verification server (Phase 5):
pip install -e ".[server]"
uvicorn monetization.verify_service:app --port 8000
```

## Build phases

See [`REAL_MOGUL_build_plan.md`](REAL_MOGUL_build_plan.md) Section 10. Current
status:

- [x] **Phase 0** — Scaffold & guardrails
- [x] **Phase 1** — Engine: finance & economy (no UI)
- [x] **Phase 2** — Engine: world, assets, progression, save
- [x] **Phase 3** — UI vertical slice (one playable level) · Kivy (see [spike](spikes/SPIKE_FINDINGS.md))
- [x] **Phase 4** — Education layer (glossary, mentors, mistake cards, stealth assessment) + art pass (style bible + procedural isometric buildings, juice). 5-levels-art-complete gated on Phase 7 content.
- [x] **Phase 5** — Monetization (catalog, entitlements, MockBillingProvider, feature flags, guardrails, FastAPI receipt-verify; zero-spend completable; no pay-to-win)
- [ ] **Phase 6** — Mobile packaging & native bridges (needs Android SDK / macOS / signing — environment-gated)
- [~] **Phase 7** — Content & balance: 4-level campaign (all verifiably winnable), career paths, daily/weekly challenges + leaderboard, prestige, tuned economy. Soft-launch retention metrics need real users.

Do not start UI (Phase 3) until Phase 1 & 2 acceptance criteria pass.

## License

Proprietary — all rights reserved (placeholder; update before any distribution).
