"""Shared visual constants for the Kivy views (placeholder-art palette).

Centralized so the eventual style-bible art pass (Phase 4) has one place to retune.
Colors are RGBA tuples in 0..1 as Kivy expects.
"""

from __future__ import annotations

BG = (0.09, 0.11, 0.15, 1)
PANEL_BG = (0.14, 0.17, 0.22, 1)
PANEL_BG_ALT = (0.18, 0.21, 0.27, 1)

TEXT = (0.92, 0.95, 0.98, 1)
TEXT_MUTED = (0.62, 0.68, 0.75, 1)

ACCENT = (0.20, 0.70, 0.55, 1)  # teal — actions, progress
ACCENT_DIM = (0.16, 0.42, 0.38, 1)
PRIMARY = (0.22, 0.62, 0.86, 1)  # blue — the primary call-to-action
GOLD = (0.95, 0.78, 0.32, 1)  # cash / value
WARN = (0.90, 0.45, 0.40, 1)  # losses, denials

# Flat-button + status surfaces for the restructured chrome.
STATUS_BG = (0.11, 0.13, 0.18, 1)
TOOLBAR_BG = (0.13, 0.16, 0.21, 1)
BTN_BG = (0.20, 0.24, 0.31, 1)  # neutral flat button
BTN_BG_HL = (0.26, 0.31, 0.39, 1)

TILE_OWNED = (0.20, 0.55, 0.45, 1)
TILE_FORSALE = (0.30, 0.42, 0.55, 1)
TILE_LAND = (0.32, 0.30, 0.24, 1)
TILE_SELECTED = (0.95, 0.78, 0.32, 1)
TILE_OUTLINE = (0.85, 0.90, 0.92, 1)

TILE_W = 178
TILE_H = 100

# --- Style-bible palette (warm cozy isometric); see assets_src/STYLE_BIBLE.md ---
GROUND = (0.50, 0.69, 0.41, 1)  # grass
GROUND_FORSALE = (0.79, 0.65, 0.42, 1)  # bare/path for an unowned lot
SHADOW = (0, 0, 0, 0.22)
WINDOW_LIT = (1.00, 0.85, 0.55, 1)
WINDOW_DARK = (0.18, 0.22, 0.28, 1)
OUTLINE = (0.12, 0.13, 0.16, 1)
SELECT_RING = (0.95, 0.76, 0.30, 1)

# Per asset class: the wall/roof base color (top face is brightened, sides dimmed).
CLASS_COLOR = {
    "sfr": (0.88, 0.48, 0.37),
    "multifamily": (0.78, 0.36, 0.32),
    "retail": (0.24, 0.60, 0.55),
    "office": (0.36, 0.49, 0.69),
    "industrial": (0.54, 0.56, 0.59),
    "mixed_use": (0.71, 0.51, 0.55),
}

STOREY_PX = 22  # screen height per storey
TILE_FOOT_W = 104  # building footprint (2:1 iso), smaller than the tile so ground shows
TILE_FOOT_H = 52
