# Phase 3 framework spike — Kivy vs Flet

**Question:** which UI framework carries Real Mogul to mobile + desktop + web —
and specifically, *can Flet draw a clickable isometric game board, or does the
board force us onto Kivy's canvas?*

**Method:** built the same minimal slice in each, both importing the **real
engine** ([`board_data.py`](board_data.py)) so the tiles show live NOI/cap/value —
which also proves the thin-client architecture (UI imports engine, never the
reverse). Versions tested: **Kivy 2.3.1**, **Flet 0.85.3**, Python 3.10.

## What actually happened

| | Kivy | Flet |
|---|---|---|
| Isometric board | **Rendered cleanly** on the GL canvas — see `_kivy_shot0001.png` (real capture) | **Renders without error** via `flet.canvas` Path + GestureDetector; Flutter client booted, no API errors |
| Finance panel | Hand-drawn label (functional, unstyled) | Native Material cards — polished with ~zero effort |
| Web | via pygbag (separate path) | **Free** — it *is* a web app |
| Auto-screenshot in CI | Trivial (`Window.screenshot`) | **Hung** — Flutter web's render loop never goes idle |
| API stability | Stable since 2011 | Pre-1.0, fast-moving (hit `ft.app`→`ft.run` deprecation mid-spike) |
| Mobile packaging | buildozer / kivy-ios (finicky — the project's #1 risk) | Flutter toolchain; still needs the same native IAP bridges |

## Reading the result

Both **can** draw the board. The difference is *grain*:

- **Kivy** is canvas-first. A tycoon game *is* a custom-drawn, animated board
  (iso tiles, cash pops, build flourishes). That is Kivy's home turf, and the
  screenshot shows it working on the first try.
- **Flet** is widget-first. Its superpower is the polished native panels — which
  are the *easy* part of this game. To draw the board you drop down to a single
  Canvas control and hand-roll hit-testing/animation anyway, i.e. you take on
  Kivy-like work *and* give up Flet's main advantage exactly where it matters
  most. The screenshot tooling hanging on Flutter's render loop is a small but
  real signal that the game-canvas path is off Flet's beaten track.

## Recommendation

**Kivy as the primary shipping client** (as the brief predicted), because the core
gameplay surface is a live animated board and that is precisely what Kivy is for.

De-risking, already partly in place:

1. **Engine stays renderer-agnostic** (done — `engine/` imports no UI). The bet is
   reversible until the UI gets thick.
2. **Containerize buildozer and build in CI early** — packaging is the real risk,
   not the game logic.
3. **Keep Flet / pygbag-web in mind as a marketing/onboarding showcase**, not the
   monetized client.

**When Flet would have won:** if Real Mogul were more dashboard than board —
menus, forms, numbers — Flet's polish + free web would tip it. It's genuinely
close on UI polish; the isometric, juicy board is what tips it to Kivy.

## Artifacts

- [`kivy_slice.py`](kivy_slice.py) — `python -m spikes.kivy_slice` (or `--shot`)
- [`flet_slice.py`](flet_slice.py) — `python -m spikes.flet_slice` (or `--web`)
- [`board_data.py`](board_data.py) — shared engine-backed board data
- `_kivy_shot0001.png` — captured Kivy render
