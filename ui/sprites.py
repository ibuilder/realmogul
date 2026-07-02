"""Procedural isometric building art, drawn to the style bible.

No raster assets yet — buildings are extruded iso prisms with three flat tones
(lit top, mid-left, dark-right), windows, and per-class silhouettes. This both
gives the slice a cozy-tycoon look now and pins down the target for the eventual
sprite-atlas hand-off (assets_src/STYLE_BIBLE.md).

Every function assumes it's called inside an active ``with canvas:`` block — Kivy
graphics instructions attach to whatever canvas is open.
"""

from __future__ import annotations

from kivy.graphics import Color, Line, Mesh

from ui import theme

Point = tuple[float, float]


def _shade(rgb: tuple[float, float, float], factor: float, alpha: float = 1.0):
    return (
        min(1.0, rgb[0] * factor),
        min(1.0, rgb[1] * factor),
        min(1.0, rgb[2] * factor),
        alpha,
    )


def _lerp(a: Point, b: Point, t: float) -> Point:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _quad(p0: Point, p1: Point, p2: Point, p3: Point, color) -> None:
    Color(*color)
    Mesh(
        vertices=[p0[0], p0[1], 0, 0, p1[0], p1[1], 0, 0, p2[0], p2[1], 0, 0, p3[0], p3[1], 0, 0],
        indices=[0, 1, 2, 0, 2, 3],
        mode="triangles",
    )


def _diamond(cx: float, cy: float, hw: float, hh: float) -> tuple[Point, Point, Point, Point]:
    """Return (back, right, front, left) corners of an iso tile diamond."""
    return (cx, cy + hh), (cx + hw, cy), (cx, cy - hh), (cx - hw, cy)


def draw_ground(cx: float, cy: float, for_sale: bool) -> None:
    """A raised plot: a grass/earth top diamond with visible dirt sides, so each
    lot reads as a little 3D tile rather than a flat decal."""
    hw, hh = theme.TILE_FOOT_W / 2, theme.TILE_FOOT_H / 2
    h = theme.GROUND_H
    back, right, front, left = _diamond(cx, cy, hw, hh)
    # Dirt sides (the two faces of the plot the camera sees), extruded downward.
    _quad(
        left, front, (front[0], front[1] - h), (left[0], left[1] - h), _shade(theme.EARTH[:3], 0.9)
    )
    _quad(
        front,
        right,
        (right[0], right[1] - h),
        (front[0], front[1] - h),
        _shade(theme.EARTH[:3], 0.7),
    )
    # Grass/asphalt top.
    base = theme.GROUND_FORSALE if for_sale else theme.GROUND
    _quad(back, right, front, left, base)
    Color(*_shade(base[:3], 0.78))
    Line(points=[*back, *right, *front, *left, *back], width=1.1)
    Color(*theme.OUTLINE)
    # Bottom silhouette of the raised plot.
    Line(
        points=[left[0], left[1] - h, front[0], front[1] - h, right[0], right[1] - h],
        width=1.0,
    )


def draw_shadow(cx: float, cy: float, scale: float = 1.0) -> None:
    hw, hh = theme.TILE_FOOT_W / 2 * 1.02 * scale, theme.TILE_FOOT_H / 2 * 1.02 * scale
    back, right, front, left = _diamond(cx, cy - 3, hw, hh)
    _quad(back, right, front, left, theme.SHADOW)


def _face_point(a: Point, b: Point, height: float, u: float, v: float) -> Point:
    bp = _lerp(a, b, u)
    return (bp[0], bp[1] + height * v)


def _windows(a: Point, b: Point, height: float, storeys: int, lit: bool) -> None:
    """Tile a face (base edge a->b, extruded up by ``height``) with framed windows."""
    color = theme.WINDOW_LIT if lit else theme.WINDOW_DARK
    cols = 2
    pad_u, pad_v = 0.16, 0.18
    for s in range(storeys):
        v0 = (s + pad_v) / storeys
        v1 = (s + 1 - pad_v) / storeys
        for c in range(cols):
            u0 = (c + pad_u) / cols
            u1 = (c + 1 - pad_u) / cols
            p0 = _face_point(a, b, height, u0, v0)
            p1 = _face_point(a, b, height, u1, v0)
            p2 = _face_point(a, b, height, u1, v1)
            p3 = _face_point(a, b, height, u0, v1)
            _quad(p0, p1, p2, p3, color)
            Color(*theme.OUTLINE)  # window frame
            Line(points=[*p0, *p1, *p2, *p3, *p0], width=1.0)


def _door(a: Point, b: Point, height: float) -> None:
    """A door on the brighter (left) face, centred at the base."""
    p0 = _face_point(a, b, height, 0.40, 0.0)
    p1 = _face_point(a, b, height, 0.60, 0.0)
    p2 = _face_point(a, b, height, 0.60, min(0.5, 14.0 / height))
    p3 = _face_point(a, b, height, 0.40, min(0.5, 14.0 / height))
    _quad(p0, p1, p2, p3, theme.DOOR)
    Color(*theme.OUTLINE)
    Line(points=[*p0, *p1, *p2, *p3, *p0], width=1.0)


def draw_building(
    cx: float,
    cy: float,
    asset_class: str,
    storeys: int,
    condition: float,
    lit: bool,
    scale: float = 1.0,
    tint: float = 0.0,
) -> None:
    hw = theme.TILE_FOOT_W / 2 * (1 + (scale - 1) * 0.5)
    hh = theme.TILE_FOOT_H / 2 * (1 + (scale - 1) * 0.5)
    height = max(1, storeys) * theme.STOREY_PX * scale

    base_rgb = theme.CLASS_COLOR.get(asset_class, (0.7, 0.7, 0.7))
    if condition < 0.85:  # tired/run-down reads darker
        base_rgb = tuple(c * (0.7 + 0.3 * condition) for c in base_rgb)
    if tint:  # subtle per-building variation so a row of houses isn't identical
        base_rgb = tuple(min(1.0, max(0.0, c * (1.0 + tint))) for c in base_rgb)

    back, right, front, left = _diamond(cx, cy, hw, hh)

    # Vertical walls (left face brighter than right; light from upper-left).
    _quad(
        left,
        front,
        (front[0], front[1] + height),
        (left[0], left[1] + height),
        _shade(base_rgb, 0.92),
    )
    _quad(
        front,
        right,
        (right[0], right[1] + height),
        (front[0], front[1] + height),
        _shade(base_rgb, 0.72),
    )

    _windows(left, front, height, storeys, lit)
    _windows(front, right, height, storeys, lit)
    _door(left, front, height)

    # Roof / top.
    top = [(p[0], p[1] + height) for p in (back, right, front, left)]
    if asset_class in ("sfr", "mixed_use"):
        _draw_gable(top, base_rgb)
    else:
        _quad(top[0], top[1], top[2], top[3], _shade(base_rgb, 1.18))
        Color(*_shade(base_rgb, 1.35))  # top highlight rim
        Line(points=[*top[3], *top[0], *top[1]], width=1.0)

    if asset_class == "retail":  # awning stripe along the base
        _awning(left, front, right, height)

    # Storybook outline on the silhouette.
    Color(*theme.OUTLINE)
    Line(points=[*left, *front, *right], width=1.4)
    Line(points=[*front, front[0], front[1] + height], width=1.4)
    Line(points=[*top[3], *top[2], *top[1]], width=1.2)


def _draw_gable(top: list[Point], base_rgb) -> None:
    back, right, front, left = top
    ridge_h = 16
    ridge_back = (back[0], back[1] + ridge_h)
    ridge_front = (front[0], front[1] + ridge_h)
    # Two roof slopes.
    _quad(left, back, ridge_back, ridge_front, _shade(base_rgb, 1.25))
    _quad(front, right, ridge_back, ridge_front, _shade(base_rgb, 1.05))
    # Ridge highlight.
    Color(*_shade(base_rgb, 1.45))
    Line(points=[*ridge_back, *ridge_front], width=1.3)


def _awning(left: Point, front: Point, right: Point, height: float) -> None:
    band = 0.16
    for a, b in ((left, front), (front, right)):
        p0 = a
        p1 = b
        p2 = (b[0], b[1] + height * band)
        p3 = (a[0], a[1] + height * band)
        _quad(p0, p1, p2, p3, (0.95, 0.95, 0.92, 1))


def draw_selection_ring(cx: float, cy: float, pulse: float) -> None:
    """A gold ring around the tile footprint; ``pulse`` 0..1 modulates width."""
    hw, hh = theme.TILE_FOOT_W / 2 + 6, theme.TILE_FOOT_H / 2 + 4
    back, right, front, left = _diamond(cx, cy, hw, hh)
    Color(theme.SELECT_RING[0], theme.SELECT_RING[1], theme.SELECT_RING[2], 0.6 + 0.4 * pulse)
    Line(points=[*back, *right, *front, *left, *back], width=1.6 + 1.4 * pulse)


def draw_land_marker(cx: float, cy: float) -> None:
    """A dashed footprint for an empty/buildable lot."""
    hw, hh = theme.TILE_FOOT_W / 2, theme.TILE_FOOT_H / 2
    back, right, front, left = _diamond(cx, cy, hw, hh)
    Color(0.85, 0.80, 0.55, 0.8)
    Line(points=[*back, *right, *front, *left, *back], width=1.2, dash_offset=4, dash_length=6)
