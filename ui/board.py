"""The isometric board widget: draws buildings and reports taps.

A dumb view — it renders ``TileView``s from the controller and calls back on tap
with a lot id. Buildings are drawn procedurally (ui/sprites.py) to the style
bible, depth-sorted back-to-front, with two bits of juice: a value "pop" when a
tile's value rises and a gentle pulse on the selected tile.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from ui import sprites, theme
from ui.controller import TileView


def iso(col: int, row: int, ox: float, oy: float) -> tuple[float, float]:
    x = ox + (col - row) * theme.TILE_W / 2
    y = oy - (col + row) * theme.TILE_H / 2
    return x, y


class BoardWidget(Widget):
    def __init__(self, on_tile: Callable[[str], None], **kwargs):
        super().__init__(**kwargs)
        self._on_tile = on_tile
        self._tiles: list[TileView] = []
        self._labels: list[Label] = []
        self._pop: dict[str, float] = {}  # lot_id -> remaining pop time (s)
        self._last_value: dict[str, float] = {}
        self._pulse = 0.0
        self.bind(pos=lambda *_: self.redraw(), size=lambda *_: self.redraw())
        Clock.schedule_interval(self._animate, 1 / 30.0)

    def set_tiles(self, tiles: list[TileView]) -> None:
        # Trigger a "pop" on any tile whose value rose (build done, reno, boom).
        for t in tiles:
            prev = self._last_value.get(t.lot_id)
            if prev is not None and t.value > prev + 1:
                self._pop[t.lot_id] = 0.32  # seconds of pop
            self._last_value[t.lot_id] = t.value
        self._tiles = tiles
        self.redraw()

    def _animate(self, dt: float) -> None:
        self._pulse = (self._pulse + dt) % 1.0
        if self._pop:
            for lid in list(self._pop):
                self._pop[lid] -= dt
                if self._pop[lid] <= 0:
                    del self._pop[lid]
            self.redraw()

    def _origin(self) -> tuple[float, float]:
        # Center the diamond cluster: shift right to balance the iso skew, and sit
        # high enough that the 3x3 grid uses the vertical space without clipping.
        return self.x + self.width * 0.46, self.y + self.height * 0.62

    def _pop_scale(self, lot_id: str) -> float:
        t = self._pop.get(lot_id)
        if not t:
            return 1.0
        # ease-out bump: peaks early, settles to 1.0
        return 1.0 + 0.10 * (t / 0.32)

    def redraw(self) -> None:
        self.canvas.clear()
        for lbl in self._labels:
            self.remove_widget(lbl)
        self._labels.clear()
        if not self._tiles:
            return

        ox, oy = self._origin()
        pulse = 0.5 - 0.5 * math.cos(self._pulse * 2 * math.pi)

        # Depth sort: draw back tiles first so near buildings overlap far ones.
        ordered = sorted(self._tiles, key=lambda t: (t.col + t.row, t.col))

        with self.canvas:
            for t in ordered:
                cx, cy = iso(t.col, t.row, ox, oy)
                sprites.draw_shadow(cx, cy)
                sprites.draw_ground(cx, cy, for_sale=t.for_sale)
                if t.selected:
                    sprites.draw_selection_ring(cx, cy, pulse)
                if t.asset_class is not None:
                    # Deterministic subtle hue variation per lot so rows differ.
                    tint = ((hash(t.lot_id) % 13) - 6) / 100.0
                    sprites.draw_building(
                        cx,
                        cy,
                        asset_class=t.asset_class,
                        storeys=t.storeys,
                        condition=t.condition,
                        lit=t.lit,
                        scale=self._pop_scale(t.lot_id),
                        tint=tint,
                    )
                elif t.empty:
                    sprites.draw_land_marker(cx, cy)

        # Float a value label above each building, with a dark backing for
        # legibility, drawn on top of the buildings.
        lw, lh = 96, 22
        with self.canvas:
            for t in ordered:
                cx, cy = iso(t.col, t.row, ox, oy)
                height = max(1, t.storeys) * theme.STOREY_PX if t.asset_class else 0
                ly = cy + height + 14
                Color(0, 0, 0, 0.5)
                Rectangle(pos=(cx - lw / 2, ly - lh / 2), size=(lw, lh))

        for t in ordered:
            cx, cy = iso(t.col, t.row, ox, oy)
            height = max(1, t.storeys) * theme.STOREY_PX if t.asset_class else 0
            ly = cy + height + 14
            text = t.top_label
            if t.pending_label:
                text = f"{t.top_label} · {t.pending_label}"
            lbl = Label(
                text=text,
                pos=(cx - lw / 2, ly - lh / 2),
                size=(lw, lh),
                halign="center",
                valign="middle",
                font_size=12,
                bold=True,
                color=theme.TEXT,
            )
            lbl.bind(size=lbl.setter("text_size"))
            self.add_widget(lbl)
            self._labels.append(lbl)

    def on_touch_down(self, touch) -> bool:
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        ox, oy = self._origin()
        # Hit-test near tiles first (they sit in front).
        for t in sorted(self._tiles, key=lambda t: -(t.col + t.row)):
            cx, cy = iso(t.col, t.row, ox, oy)
            dx = abs(touch.x - cx) / (theme.TILE_FOOT_W / 2)
            dy = abs(touch.y - cy) / (theme.TILE_FOOT_H / 2)
            if dx + dy <= 1.0:
                self._on_tile(t.lot_id)
                return True
        return super().on_touch_down(touch)
