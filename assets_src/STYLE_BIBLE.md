# Real Mogul — Style Bible (v0, placeholder→stylized)

Lock these before producing volume art. The shipping look is **clean, warm,
cozy-tycoon isometric** — readable at phone size, characterful, not photoreal.
The Phase-4b pass draws buildings *procedurally* (vector, in Kivy) to this spec so
the look is consistent and the eventual sprite-atlas hand-off has a target.

## Projection
- **2:1 isometric grid.** Tile footprint 128×64 (width:height = 2:1).
- Buildings extrude **up** from the tile (height = footprint, scaled by tier).
- Camera is fixed; no rotation. Light comes from the **upper-left**.

## Lighting / shading
- Three flat tones per surface, no gradients:
  - **Top face**: lightest (lit).
  - **Left face**: mid.
  - **Right face**: darkest (shadow side).
- One soft contact shadow (a darker diamond) under each building.

## Line / form
- **Line weight**: 1.5px outlines, slightly darker than the fill — gives the
  cozy "storybook" edge without going cartoony.
- Rounded, chunky massing. No thin spindly detail (illegible at phone size).

## Palette (warm cozy)
| Role | Hex |
|---|---|
| Ground / grass | `#7FB069` |
| Ground alt (path) | `#C9A66B` |
| Sky/bg | `#1F2630` (dark, lets warm buildings pop) |
| SFR roof | `#E07A5F` (terracotta) |
| Multifamily roof | `#C75D52` |
| Retail | `#3D9A8B` (teal awnings) |
| Office | `#5B7DB1` (blue glass) |
| Industrial | `#8A8D91` (steel) |
| Mixed-use | `#B5838D` (mauve) |
| Wall (lit) | `#F2E9DE` |
| Window glow | `#FFD98E` |
| Cash / value gold | `#F2C14E` |
| Selection ring | `#F2C14E` |

## Condition / tier read
- **Condition** scales wall brightness and adds a "for-sale/run-down" desaturation
  below ~0.85 (peeling look = darker, fewer lit windows).
- **Upgrade tier** adds storeys (height) and more lit windows. A renovated SFR is
  visibly taller/brighter than a tired one.

## Asset-class silhouette (read at a glance)
- **SFR**: 1 storey, peaked roof.
- **Multifamily**: 2–3 storeys, flat roof, many windows.
- **Retail**: wide, low, awning stripe.
- **Office**: tall, glassy grid of windows.
- **Industrial**: wide low shed, sawtooth roof.
- **Mixed-use**: retail base + residential storeys above.

## Juice (cheap + satisfying)
- **Value pop**: a tile whose value rises scales up ~8% and settles (ease-out).
- **Build complete**: a brief bounce + window-glow flash.
- **Selection**: a gold ring that gently pulses.
- Keep all tweens < 350ms. Juice > detail for retention.

## Audio (scaffolded, content later)
- UI tick, cash chime, build-complete flourish. Loopable warm ambient pad.
- Keep files small and mobile-friendly; route through one `ui/audio.py` hook.
