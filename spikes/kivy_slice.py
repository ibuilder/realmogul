"""Kivy spike: an isometric board drawn on the GL canvas + a finance panel.

Run interactively:   python -m spikes.kivy_slice
Capture a screenshot: python -m spikes.kivy_slice --shot

The board is hand-drawn diamonds (isometric tiles) on a Canvas — Kivy's home turf.
Tapping a tile shows the "Explain this deal" numbers, computed by the engine.
"""

from __future__ import annotations

import os
import sys

# Headless-friendly window config must be set before other kivy imports.
os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.app import App  # noqa: E402
from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.graphics import Color, Line, Mesh  # noqa: E402
from kivy.uix.label import Label  # noqa: E402
from kivy.uix.widget import Widget  # noqa: E402

from spikes.board_data import Tile, board_tiles, explain_deal  # noqa: E402

Window.size = (900, 600)
Window.clearcolor = (0.10, 0.12, 0.16, 1)

TILE_W, TILE_H = 150, 86
ORIGIN_X, ORIGIN_Y = 360, 420


def iso(col: int, row: int) -> tuple[float, float]:
    x = ORIGIN_X + (col - row) * TILE_W / 2
    y = ORIGIN_Y - (col + row) * TILE_H / 2
    return x, y


class Board(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tiles = board_tiles()
        self.panel = Label(
            text="Tap a lot to inspect the deal",
            pos=(580, 40),
            size=(300, 200),
            halign="left",
            valign="top",
            font_size=16,
        )
        self.add_widget(self.panel)
        Clock.schedule_once(lambda dt: self.redraw(), 0)
        Window.bind(on_touch_down=self._on_touch)

    def _diamond(self, cx: float, cy: float, color, outline=False):
        pts = [
            cx,
            cy + TILE_H / 2,
            cx + TILE_W / 2,
            cy,
            cx,
            cy - TILE_H / 2,
            cx - TILE_W / 2,
            cy,
        ]
        if outline:
            Color(*color)
            Line(points=pts + [pts[0], pts[1]], width=1.4)
        else:
            Color(*color)
            # two triangles -> diamond
            Mesh(
                vertices=[
                    pts[0],
                    pts[1],
                    0,
                    0,
                    pts[2],
                    pts[3],
                    0,
                    0,
                    pts[4],
                    pts[5],
                    0,
                    0,
                    pts[6],
                    pts[7],
                    0,
                    0,
                ],
                indices=[0, 1, 2, 0, 2, 3],
                mode="triangles",
            )

    def redraw(self):
        self.canvas.before.clear()
        with self.canvas.before:
            for t in self.tiles:
                cx, cy = iso(t.col, t.row)
                # value drives the fill brightness (a cheap "heat" read)
                heat = min(1.0, t.value / 180_000)
                self._diamond(cx, cy, (0.25 + 0.45 * heat, 0.55, 0.40, 1))
                self._diamond(cx, cy, (0.85, 0.9, 0.85, 1), outline=True)
        # value labels on top of each tile
        for child in list(self.children):
            if isinstance(child, Label) and child is not self.panel:
                self.remove_widget(child)
        for t in self.tiles:
            cx, cy = iso(t.col, t.row)
            lbl = Label(
                text=f"${t.value/1000:.0f}k",
                pos=(cx - 50, cy - 12),
                size=(100, 24),
                font_size=14,
                bold=True,
            )
            self.add_widget(lbl)

    def _hit(self, x: float, y: float) -> Tile | None:
        for t in self.tiles:
            cx, cy = iso(t.col, t.row)
            # diamond hit test in tile-space
            dx = abs(x - cx) / (TILE_W / 2)
            dy = abs(y - cy) / (TILE_H / 2)
            if dx + dy <= 1.0:
                return t
        return None

    def _on_touch(self, _window, touch):
        t = self._hit(touch.x, touch.y)
        if t is not None:
            self.panel.text = explain_deal(t)
            return True
        return False


class KivySpike(App):
    def __init__(self, shot: bool = False, **kwargs):
        super().__init__(**kwargs)
        self._shot = shot

    def build(self):
        return Board()

    def on_start(self):
        if self._shot:
            # Wait for several real frames to flip before grabbing the buffer.
            Clock.schedule_once(self._capture, 2.5)

    def _capture(self, _dt):
        Window.canvas.ask_update()
        path = Window.screenshot(name="spikes/_kivy_shot.png")
        print(f"SHOT:{path}")
        Clock.schedule_once(lambda dt: self.stop(), 0.5)


def main() -> int:
    shot = "--shot" in sys.argv
    KivySpike(shot=shot).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
