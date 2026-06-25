"""Flet spike: the same isometric board via Flet's Canvas + native finance cards.

Run desktop:  python -m spikes.flet_slice
Run web:      python -m spikes.flet_slice --web   (serves on http://localhost:8552)

The point of the spike: Flet's strength is polished *native widgets* (the cards,
buttons, the "Explain" panel). The open question is whether its Canvas can carry a
clickable isometric board. This draws the diamonds as Canvas paths with a
GestureDetector for hit-testing — same real engine numbers as the Kivy slice.
"""

from __future__ import annotations

import sys

import flet as ft
import flet.canvas as cv

from spikes.board_data import Tile, board_tiles, explain_deal

TILE_W, TILE_H = 150, 86
ORIGIN_X, ORIGIN_Y = 300, 120


def iso(col: int, row: int) -> tuple[float, float]:
    return ORIGIN_X + (col - row) * TILE_W / 2, ORIGIN_Y + (col + row) * TILE_H / 2


def _diamond_path(cx: float, cy: float, fill: str) -> cv.Path:
    return cv.Path(
        [
            cv.Path.MoveTo(cx, cy - TILE_H / 2),
            cv.Path.LineTo(cx + TILE_W / 2, cy),
            cv.Path.LineTo(cx, cy + TILE_H / 2),
            cv.Path.LineTo(cx - TILE_W / 2, cy),
            cv.Path.Close(),
        ],
        paint=ft.Paint(color=fill, style=ft.PaintingStyle.FILL),
    )


def _diamond_outline(cx: float, cy: float) -> cv.Path:
    return cv.Path(
        [
            cv.Path.MoveTo(cx, cy - TILE_H / 2),
            cv.Path.LineTo(cx + TILE_W / 2, cy),
            cv.Path.LineTo(cx, cy + TILE_H / 2),
            cv.Path.LineTo(cx - TILE_W / 2, cy),
            cv.Path.Close(),
        ],
        paint=ft.Paint(color="#dfe8df", stroke_width=1.5, style=ft.PaintingStyle.STROKE),
    )


def _hit(tiles: list[Tile], x: float, y: float) -> Tile | None:
    for t in tiles:
        cx, cy = iso(t.col, t.row)
        if abs(x - cx) / (TILE_W / 2) + abs(y - cy) / (TILE_H / 2) <= 1.0:
            return t
    return None


def main(page: ft.Page):
    page.title = "Real Mogul — Flet spike"
    page.bgcolor = "#1a1f29"
    tiles = board_tiles()

    shapes: list[cv.Shape] = []
    for t in tiles:
        cx, cy = iso(t.col, t.row)
        heat = min(1.0, t.value / 180_000)
        g = int(0x55 + 0x55 * heat)
        shapes.append(_diamond_path(cx, cy, f"#{0x33:02x}{g:02x}{0x44:02x}"))
        shapes.append(_diamond_outline(cx, cy))
        shapes.append(
            cv.Text(
                cx - 26, cy - 9, f"${t.value/1000:.0f}k", ft.TextStyle(size=14, color="#ffffff")
            )
        )

    canvas = cv.Canvas(shapes, width=620, height=380)

    # --- native widgets: the finance panel (Flet's real strength) ---
    panel_title = ft.Text("Tap a lot", size=18, weight=ft.FontWeight.BOLD, color="#ffffff")
    panel_body = ft.Text("Inspect the deal →", size=14, color="#b8c2cc", selectable=True)
    panel = ft.Container(
        content=ft.Column([panel_title, ft.Divider(height=8), panel_body]),
        bgcolor="#252c38",
        border_radius=12,
        padding=18,
        width=280,
    )

    def on_tap(e: ft.TapEvent):
        # Flet 0.85: tap coords live on a single local_position Offset (.x/.y).
        pos = getattr(e, "local_position", None)
        if pos is None:
            return
        t = _hit(tiles, pos.x, pos.y)
        if t is None:
            return
        panel_title.value = t.lot_id.upper()
        panel_body.value = explain_deal(t)
        page.update()

    board = ft.GestureDetector(content=canvas, on_tap_down=on_tap)

    page.add(
        ft.Text(
            "REAL MOGUL — deal board (Flet)", size=20, weight=ft.FontWeight.BOLD, color="#eaf0f6"
        ),
        ft.Row([board, panel], alignment=ft.MainAxisAlignment.START, spacing=24),
    )


def run() -> None:
    if "--web" in sys.argv:
        ft.run(main, view=ft.AppView.WEB_BROWSER, port=8552)
    else:
        ft.run(main)


if __name__ == "__main__":
    run()
