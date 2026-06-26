# Real Mogul — Gameplay Roadmap

Grounded in research on what makes tycoon/time-management games fun (sources at
bottom). The current build has a correct, well-tested economy but a **mechanical
loop**: buy → renovate → refinance → advance. The research points at three gaps:

1. **No time-management tension.** Build-a-Lot's fun came from juggling *workers,
   materials, time, and budget* against a clock. We have build timers but no
   constraint that forces prioritization.
2. **The player can't build "appeal."** Demand only moves via scripted events.
   Build-a-Lot let you place parks/civic buildings to lift a neighborhood — the
   brief explicitly calls this out as the thing to fix.
3. **Assets never age and there's no reason to return.** No upkeep loop, no
   offline/idle reward — both are top retention drivers (idle games hit 10–15% D7
   vs ~8% baseline by rewarding return + showing visible momentum).

## Wave 1 — Make the core loop tense & strategic ✅ DONE

- **1.1 Worker crews.** ✅ A pool of crews (start 3); each build/renovation/repair/
  amenity ties up a crew for its duration; hire more for escalating cash. You now
  *choose* what to work on — the Build-a-Lot squeeze. (`GameSession.crews`,
  `free_crews`, `hire_crew`; HUD shows `Crews free/total`.)
- **1.2 Amenities → demand.** ✅ Build a park/transit/plaza on owned vacant land;
  on completion it permanently raises `town.appeal`, lifting rents and easing
  vacancy across every holding (via `effective_market`). The player drives the heat.
- **1.3 Condition decay + repair.** ✅ Buildings wear ~1.8%/yr; low condition drags
  NOI/value; a cheap quick `repair` restores them. Ongoing upkeep, not buy-and-forget.

Two engine fixes fell out of tuning this: a **regime rate model** (a scripted rate
cut now permanently shifts the baseline rates revert toward, so the lesson lasts
instead of reverting in a few months) and **DSCR-gated refinance** (a cash-out refi
is now capped by coverage, not just LTV — no more negative-cashflow over-leverage
spiral). Campaign targets were recalibrated to a robust reference agent.

## Wave 2 — Retention & pacing

- **2.1 Offline catch-up.** On load, accrue capped earnings for time away
  ("while you were away, your portfolio earned $X"). Reward returning, never punish leaving.
- **2.2 Fast early hook + visible momentum.** Front-load the first win; animate
  bars filling and cash piling so progress is always legible.

## Wave 3 — Depth & variety ✅ DONE

- **3.1 Advisors.** ✅ Hire 4 specialists for passive perks — Deal Scout (more
  deal flow), Banker (+LTV), GC (faster builds), Property Manager (slower decay).
  Layered on careers; one-time cash; effects persisted in saves.
- **3.2 Random opportunities.** ✅ Distressed deals + buyout offers on a *separate*
  RNG stream (never perturbs the balanced market). Persisted in saves.
- **3.3 Deeper, per-class upgrade trees.** ✅ Added façade, solar, smart-home,
  signage (retail), co-working (office), loading dock (industrial); a per-property
  "Upgrades" picker surfaces what each building can still take.

## Wave 4 — Juice & feel

- **4.1 Cash counter roll-up.** ✅ The HUD cash readout eases toward its target.
- **4.2 Audio hooks.** ✅ Real synthesized SFX (`tools/gen_audio.py` → tick / cash /
  build-complete / win / lose) loaded via SDL2; defensive no-op if no audio backend.
- **4.3 Win/lose flourishes.** ✅ Win/lose stings play on the endgame popup.
  (Visual flourish — confetti/shake — still todo.)

## Execution order

Wave 1 first (it defines the fun), then Wave 4 juice on top of it, then as much of
Wave 2/3 as fits. After every change: re-run `tools/play_level.py --all` (all
campaign levels must stay winnable) and the balance sim (must stay non-degenerate).

## Sources

- [How to Make a Tycoon Game like AdVenture Capitalist — Mind Studios](https://themindstudios.com/blog/make-a-tycoon-game-like-adventure-capitalist/)
- [Build-a-lot series — GameHouse](https://www.gamehouse.com/series/build-a-lot-games-for-windows)
- [Top 20 Tycoon Games (REIT Tycoon, executives/specializations) — Playgama](https://playgama.com/blog/top-games/tycoon-games-top-%E2%80%91-20-august-2025/)
- [A Guide to Idle Games (offline progression, retention) — Apptrove](https://apptrove.com/a-guide-to-idle-games/)
- [Juice in Game Design — Blood Moon Interactive](https://www.bloodmooninteractive.com/articles/juice.html)
