"""Real Mogul — Kivy desktop app.

The playable client: a status bar, an isometric board, a live deal/finance panel,
mentor coaching, a store, advisors, opportunities, and the "Explain this deal"
overlay — all rendering real engine numbers. The views stay thin; every decision
routes through ``GameController`` (Kivy-free, tested). Layout is a status bar on
top, board + deal panel in the middle, a coach strip, and an action toolbar.

Play:       python -m ui
Screenshot: python -m ui --shot   (captures a scripted sequence to ui/_shots/)
"""

from __future__ import annotations

import contextlib
import json
import os
import random
import sys
import time
from functools import partial
from pathlib import Path

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.animation import Animation  # noqa: E402
from kivy.app import App  # noqa: E402
from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.graphics import Color, Ellipse, Rectangle  # noqa: E402
from kivy.uix.boxlayout import BoxLayout  # noqa: E402
from kivy.uix.button import Button  # noqa: E402
from kivy.uix.floatlayout import FloatLayout  # noqa: E402
from kivy.uix.gridlayout import GridLayout  # noqa: E402
from kivy.uix.label import Label  # noqa: E402
from kivy.uix.popup import Popup  # noqa: E402
from kivy.uix.progressbar import ProgressBar  # noqa: E402
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager  # noqa: E402
from kivy.uix.scrollview import ScrollView  # noqa: E402
from kivy.uix.textinput import TextInput  # noqa: E402
from kivy.uix.widget import Widget  # noqa: E402

from education.glossary import get_term  # noqa: E402
from engine.assets.upgrades import UPGRADE_CATALOG  # noqa: E402
from engine.progression.campaign import build_level_one, campaign_levels  # noqa: E402
from engine.progression.challenge import daily_challenge  # noqa: E402
from engine.progression.offline import compute_offline_earnings  # noqa: E402
from engine.save.store import load_from_dict, save_to_json, saved_at_of  # noqa: E402
from monetization import (  # noqa: E402
    MockBillingProvider,
    MonetizationManager,
    probability_disclosure,
)
from ui import theme  # noqa: E402
from ui.audio import SoundBank  # noqa: E402
from ui.board import BoardWidget  # noqa: E402
from ui.controller import GameController  # noqa: E402

# Actions that are "work" (a crew starts something) vs money moving.
_WORK_ACTIONS = set(UPGRADE_CATALOG) | {"repair", "amenity_park", "develop"}

# A distinct colour per mentor for their coach-bar portrait.
_MENTOR_COLORS = {
    "flipper": theme.ACCENT,
    "broker": theme.PRIMARY,
    "banker": theme.GOLD,
    "syndicator": (0.71, 0.51, 0.55, 1),
}


class MentorAvatar(FloatLayout):
    """A little round portrait chip (mentor's colour + initial) for the coach bar."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._initial = Label(text="", bold=True, font_size=16, color=(0.09, 0.11, 0.15, 1))
        self._initial.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        self.add_widget(self._initial)
        self._color = None
        self.bind(pos=self._redraw, size=self._redraw)

    def set_mentor(self, color, initial: str) -> None:
        self._color = color
        self._initial.text = initial
        self._redraw()

    def clear_mentor(self) -> None:
        self._color = None
        self._initial.text = ""
        self._redraw()

    def _redraw(self, *_) -> None:
        self.canvas.before.clear()
        if self._color is None:
            return
        d = max(4.0, min(self.width, self.height) - 8)
        with self.canvas.before:
            Color(*self._color)
            Ellipse(pos=(self.center_x - d / 2, self.center_y - d / 2), size=(d, d))


Window.size = (1200, 760)
Window.clearcolor = theme.BG


def _flat_button(text: str, color, *, width: int | None = None, font_size: int = 14) -> Button:
    """A flat, modern button (no default gradient texture)."""
    btn = Button(
        text=text,
        background_normal="",
        background_down="",
        background_color=color,
        font_size=font_size,
        bold=True,
        color=theme.TEXT,
    )
    if width is not None:
        btn.size_hint_x = None
        btn.width = width
    return btn


def _panel(widget: BoxLayout, color) -> BoxLayout:
    """Give a box layout a flat background rectangle."""
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda *_: setattr(rect, "pos", widget.pos),
        size=lambda *_: setattr(rect, "size", widget.size),
    )
    return widget


def _hud_label(text: str, color=theme.TEXT, size=15, bold=False) -> Label:
    lbl = Label(text=text, color=color, font_size=size, bold=bold, halign="left", valign="middle")
    lbl.bind(size=lbl.setter("text_size"))
    return lbl


class RealMogulApp(App):
    def __init__(self, shot: bool = False, billing_provider=None, **kwargs):
        super().__init__(**kwargs)
        self._shot = shot
        self.controller = None  # created when a level is started
        self._offline = None
        self._cash_scheduled = False
        # Monetization: a provider is injected on-device (see nativebridge); on
        # desktop/web it defaults to the mock store. Entitlements persist + reconcile.
        secret = "dev-secret-change-me"
        provider = billing_provider or MockBillingProvider(secret)
        self.monet = MonetizationManager(
            provider, mock_secret=secret, save_path=Path("ui/_entitlements.json")
        )
        self.monet.reconcile()
        self.sounds = SoundBank()
        self._persist = not shot
        self._save_path = Path("ui/_savegame.json")

    def _save_game(self):
        if not self._persist or self.controller is None:
            return
        with contextlib.suppress(Exception):
            self._save_path.write_text(save_to_json(self.controller.session, saved_at=time.time()))

    # ----------------------------------------------------------------- build
    def _metric(self, caption: str, width: int, value_color=theme.TEXT):
        """A status pill: a small uppercase caption over a bold value."""
        box = BoxLayout(orientation="vertical", size_hint=(None, 1), width=width, spacing=0)
        cap = Label(
            text=caption,
            font_size=10,
            bold=True,
            color=theme.TEXT_MUTED,
            halign="left",
            valign="bottom",
        )
        cap.bind(size=cap.setter("text_size"))
        val = Label(
            text="", font_size=18, bold=True, color=value_color, halign="left", valign="top"
        )
        val.bind(size=val.setter("text_size"))
        box.add_widget(cap)
        box.add_widget(val)
        return box, val

    def _make_status_bar(self):
        bar = _panel(
            BoxLayout(
                orientation="horizontal",
                size_hint=(1, None),
                height=58,
                padding=(16, 8),
                spacing=22,
            ),
            theme.STATUS_BG,
        )
        month_box, self.lbl_month = self._metric("MONTH", 78)
        cash_box, self.lbl_cash = self._metric("CASH", 130, theme.GOLD)
        nw_box, self.lbl_networth = self._metric("NET WORTH", 130)
        crews_box, self.lbl_crews = self._metric("CREWS", 60)
        mastery_box, self.lbl_mastery = self._metric("MASTERY", 78)
        for w in (month_box, cash_box, nw_box, crews_box, mastery_box):
            bar.add_widget(w)
        # Objective + progress, right-aligned and given real width.
        obj = BoxLayout(orientation="vertical", size_hint=(0.42, 1), spacing=4)
        self.lbl_objective = Label(
            text="",
            font_size=12,
            bold=True,
            color=theme.TEXT,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=20,
        )
        self.lbl_objective.bind(size=self.lbl_objective.setter("text_size"))
        prog_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=14, spacing=8)
        self.progress = ProgressBar(max=1.0)
        self.lbl_progress_pct = Label(
            text="", font_size=11, bold=True, color=theme.ACCENT, size_hint=(None, 1), width=42
        )
        prog_row.add_widget(self.progress)
        prog_row.add_widget(self.lbl_progress_pct)
        obj.add_widget(BoxLayout(size_hint=(1, None), height=4))  # top spacer to center
        obj.add_widget(self.lbl_objective)
        obj.add_widget(prog_row)
        obj.add_widget(BoxLayout())  # bottom spacer
        bar.add_widget(obj)
        return bar

    def _make_toolbar(self):
        # Horizontally scrollable so it never overflows on a narrow / phone screen.
        outer = _panel(BoxLayout(size_hint=(1, None), height=50, padding=(10, 7)), theme.TOOLBAR_BG)
        bar = BoxLayout(orientation="horizontal", size_hint=(None, 1), spacing=8)
        bar.bind(minimum_width=bar.setter("width"))

        btn_next = _flat_button("Advance month  ▸", theme.PRIMARY, width=180, font_size=15)
        btn_next.bind(on_release=lambda *_: self.on_advance())
        bar.add_widget(btn_next)
        self.btn_deals = _flat_button("Deals", theme.GOLD, width=104)
        self.btn_deals.color = (0.1, 0.1, 0.1, 1)
        self.btn_deals.bind(on_release=lambda *_: self.open_opportunities())
        bar.add_widget(self.btn_deals)
        for text, cb in (
            ("Hire crew", self._on_hire),
            ("Advisors", self.open_advisors),
            ("Store", self.open_store),
            ("The Closet", self.open_glossary),
            ("Explain deal", self.open_explain),
            ("Menu", self._to_menu),
        ):
            btn = _flat_button(text, theme.BTN_BG, width=112)
            btn.bind(on_release=lambda _w, c=cb: c())
            bar.add_widget(btn)

        scroll = ScrollView(do_scroll_x=True, do_scroll_y=False, bar_width=0)
        scroll.add_widget(bar)
        outer.add_widget(scroll)
        return outer

    def _to_menu(self):
        self._save_game()
        self.sm.current = "menu"

    def _apply_responsive(self):
        """Stack the board above the panel on narrow (phone-ish) widths."""
        narrow = Window.width < 860
        self.mid.orientation = "vertical" if narrow else "horizontal"
        self.board.size_hint = (1, 0.55) if narrow else (0.62, 1)
        self.deal_panel.size_hint = (1, 0.45) if narrow else (0.38, 1)

    def build(self):
        self.sm = ScreenManager(transition=FadeTransition(duration=0.22))
        self.sm.add_widget(self._build_menu_screen())
        if self._shot:  # capture goes straight into a fresh level 1
            self._start_game(build_level_one())
        return self.sm

    # ----------------------------------------------------------------- menu
    def _build_menu_screen(self):
        screen = Screen(name="menu")
        bg = _panel(BoxLayout(orientation="vertical"), theme.BG)
        col = BoxLayout(
            orientation="vertical", size_hint=(None, None), width=520, spacing=10, padding=(0, 40)
        )
        col.bind(minimum_height=col.setter("height"))
        col.pos_hint = {"center_x": 0.5, "center_y": 0.5}

        title = Label(
            text="REAL MOGUL",
            font_size=48,
            bold=True,
            color=theme.GOLD,
            size_hint_y=None,
            height=64,
        )
        tag = Label(
            text="Buy low. Build smart. Learn the game while you play it.",
            font_size=15,
            color=theme.TEXT_MUTED,
            size_hint_y=None,
            height=28,
        )
        col.add_widget(title)
        col.add_widget(tag)
        col.add_widget(BoxLayout(size_hint_y=None, height=14))

        has_save = self._persist and self._save_path.exists()
        if has_save:
            cont = _flat_button("▸  Continue", theme.PRIMARY, font_size=17)
            cont.size_hint_y = None
            cont.height = 52
            cont.bind(on_release=lambda *_: self._continue_game())
            col.add_widget(cont)

        col.add_widget(
            Label(
                text="CAMPAIGN",
                font_size=12,
                bold=True,
                color=theme.TEXT_MUTED,
                size_hint_y=None,
                height=24,
            )
        )
        for i, level in enumerate(campaign_levels()):
            btn = _flat_button(
                f"{i + 1}.  {level.name}   —   {level.description}",
                theme.BTN_BG if i else theme.ACCENT,
            )
            btn.size_hint_y = None
            btn.height = 46
            btn.halign = "center"
            btn.bind(on_release=lambda _w, lv=level: self._start_game(lv))
            col.add_widget(btn)

        daily = _flat_button("🗓  Daily Challenge", theme.ACCENT_DIM)
        daily.size_hint_y = None
        daily.height = 46
        daily.bind(on_release=lambda *_: self._start_game(self._todays_challenge()))
        col.add_widget(BoxLayout(size_hint_y=None, height=8))
        col.add_widget(daily)

        anchor = FloatLayout()
        anchor.add_widget(col)
        bg.add_widget(anchor)
        screen.add_widget(bg)
        return screen

    def _todays_challenge(self):
        # A stable per-day index so the day's challenge is the same for everyone.
        return daily_challenge(int(time.time() // 86_400))

    def _continue_game(self):
        with contextlib.suppress(Exception):
            env = json.loads(self._save_path.read_text())
            session = load_from_dict(env)
            ts = saved_at_of(env)
            if ts is not None:
                off = compute_offline_earnings(session, time.time() - ts)
                if off.worthwhile:
                    session.cash += off.amount
                    self._offline = off
            self._start_game(build_level_one(), resume_session=session)
            return
        self._start_game(build_level_one())  # corrupt save -> fresh

    # ----------------------------------------------------------------- game screen
    def _start_game(self, level, resume_session=None):
        self.controller = GameController(level)
        if resume_session is not None:
            self.controller.session = resume_session
        self._endgame_shown = False
        # Rebuild the game screen fresh each time (so switching levels works).
        if self.sm.has_screen("game"):
            self.sm.remove_widget(self.sm.get_screen("game"))
        game = Screen(name="game")
        game.add_widget(self._build_game_root())
        self.sm.add_widget(game)
        if not self._cash_scheduled:
            self._cash_scheduled = True
            Clock.schedule_interval(self._tick_cash, 1 / 30.0)
        self._cash_shown = float(self.controller.hud().cash_value)
        self._cash_target = self._cash_shown
        self.sm.current = "game"
        self.refresh()
        if self._offline is not None and not self._shot:
            Clock.schedule_once(lambda dt: self._show_offline(), 0.5)

    def _build_game_root(self):
        main = BoxLayout(orientation="vertical", size_hint=(1, 1))
        self.status_bar = self._make_status_bar()
        main.add_widget(self.status_bar)

        self.mid = BoxLayout(orientation="horizontal", size_hint=(1, 1))
        self.board = BoardWidget(on_tile=self.on_tile, size_hint=(0.62, 1))
        self.mid.add_widget(self.board)
        self.deal_panel = _panel(
            BoxLayout(orientation="vertical", size_hint=(0.38, 1), padding=0, spacing=0),
            theme.PANEL_BG,
        )
        self.mid.add_widget(self.deal_panel)
        main.add_widget(self.mid)

        self.lbl_coach = _hud_label("", color=theme.TEXT, size=13)
        self.coach_avatar = MentorAvatar(size_hint=(None, 1), width=40)
        coach_bar = _panel(
            BoxLayout(size_hint=(1, None), height=44, padding=(12, 5), spacing=10),
            theme.PANEL_BG_ALT,
        )
        coach_bar.add_widget(self.coach_avatar)
        coach_bar.add_widget(self.lbl_coach)
        main.add_widget(coach_bar)

        self.toolbar = self._make_toolbar()
        main.add_widget(self.toolbar)
        Window.bind(on_resize=lambda *_: self._apply_responsive())
        Clock.schedule_once(lambda dt: self._apply_responsive(), 0)

        # Overlay for floating effects (e.g. +$ on cash gains).
        self._overlay = FloatLayout()
        self._overlay.add_widget(main)
        return self._overlay

    def _float_cash(self, amount: float):
        lbl = Label(
            text=f"+${amount:,.0f}",
            font_size=20,
            bold=True,
            color=theme.GOLD,
            size_hint=(None, None),
            size=(160, 30),
            pos=(96, Window.height - 78),
        )
        self._overlay.add_widget(lbl)
        anim = Animation(y=lbl.y + 40, opacity=0.0, duration=0.9, t="out_quad")
        anim.bind(on_complete=lambda *_: self._overlay.remove_widget(lbl))
        anim.start(lbl)

    def _tick_cash(self, dt):
        if abs(self._cash_target - self._cash_shown) < 1:
            self._cash_shown = self._cash_target
        else:
            self._cash_shown += (self._cash_target - self._cash_shown) * min(1.0, dt * 7.0)
        self.lbl_cash.text = f"${self._cash_shown:,.0f}"

    def on_start(self):
        if self._shot:
            Clock.schedule_once(lambda dt: self._run_capture(), 1.2)

    def _show_offline(self):
        off = self._offline
        body = BoxLayout(orientation="vertical", padding=14, spacing=8)
        body.add_widget(
            _hud_label(f"You were away about {off.hours_away:.1f}h.", size=15, bold=True)
        )
        body.add_widget(
            _hud_label(
                f"Your portfolio collected ${off.amount:,.0f} in rent "
                f"({off.months_credited:.1f} months' worth).",
                color=theme.GOLD,
                size=14,
            )
        )
        self.sounds.play("cash")
        Popup(title="While you were away", content=body, size_hint=(0.55, 0.35)).open()

    # ----------------------------------------------------------------- refresh
    def refresh(self):
        h = self.controller.hud()
        # Float a "+$X" cue when cash jumps up (a sale, refi, deal, or offline rent).
        prev = getattr(self, "_last_cash_seen", h.cash_value)
        if h.cash_value - prev > 50:
            self._float_cash(h.cash_value - prev)
        self._last_cash_seen = h.cash_value
        self.lbl_month.text = f"{h.month}/{h.month_limit}"
        self._cash_target = float(h.cash_value)  # animated by _tick_cash
        self.btn_deals.text = f"Deals ({h.deals})" if h.deals else "Deals"
        self.lbl_networth.text = h.net_worth
        self.lbl_objective.text = f"GOAL   {h.objective}"
        self.progress.value = h.progress
        self.lbl_progress_pct.text = f"{h.progress:.0%}"
        self.lbl_mastery.text = f"{self.controller.mastery():.0%}"
        self.lbl_crews.text = h.crews
        self._refresh_coach(h.message)
        self.board.set_tiles(self.controller.board())
        self._refresh_deal()
        self._maybe_show_lesson()
        self._save_game()  # autosave after every change (records a timestamp)

    def _refresh_coach(self, fallback: str):
        tip = self.controller.coach_tip()
        if tip is not None:
            color = _MENTOR_COLORS.get(tip.mentor_id, theme.ACCENT)
            self.coach_avatar.set_mentor(color, tip.mentor_name[:1])
            self.lbl_coach.text = f"[b]{tip.mentor_name}[/b]   {tip.text}"
            self.lbl_coach.markup = True
            self.lbl_coach.color = theme.TEXT
        else:
            self.coach_avatar.clear_mentor()
            self.lbl_coach.markup = False
            self.lbl_coach.text = fallback
            self.lbl_coach.color = theme.TEXT_MUTED

    def _maybe_show_lesson(self):
        lesson = self.controller.current_lesson()
        if lesson is None:
            return
        self.controller.dismiss_lesson()
        body = BoxLayout(orientation="vertical", padding=14, spacing=8)
        body.add_widget(_hud_label(lesson.what_happened, size=14))
        body.add_widget(_hud_label("How pros avoid it:", color=theme.GOLD, size=13, bold=True))
        body.add_widget(_hud_label(lesson.how_pros_avoid, color=theme.TEXT_MUTED, size=13))
        Popup(title=lesson.title, content=body, size_hint=(0.6, 0.45)).open()

    _PRIMARY_ACTIONS = {
        "buy",
        "renovate",
        "open_upgrades",
        "develop",
        "amenity_park",
        "repair",
    }

    def _refresh_deal(self):
        self.deal_panel.clear_widgets()
        deal = self.controller.selected_deal()
        if deal is None:
            empty = BoxLayout(padding=22)
            empty.add_widget(
                _hud_label("Tap a lot on the board to scout a deal.", color=theme.TEXT_MUTED)
            )
            self.deal_panel.add_widget(empty)
            return

        # Header strip.
        header = _panel(
            BoxLayout(
                orientation="vertical", size_hint=(1, None), height=60, padding=(16, 10), spacing=2
            ),
            theme.PANEL_BG_ALT,
        )
        t = _hud_label(deal.title, size=21, bold=True)
        t.size_hint_y = None
        t.height = 27
        s = _hud_label(deal.subtitle, color=theme.GOLD, size=12, bold=True)
        s.size_hint_y = None
        s.height = 18
        header.add_widget(t)
        header.add_widget(s)
        self.deal_panel.add_widget(header)

        content = BoxLayout(orientation="vertical", padding=(16, 12), spacing=10)
        grid = GridLayout(cols=2, size_hint=(1, None), spacing=(8, 7))
        grid.bind(minimum_height=grid.setter("height"))
        for label, value in deal.rows:
            term = self.controller.term_for_metric(label)
            if term is not None:
                lk = Button(
                    text=f"{label}  ⓘ",
                    size_hint_y=None,
                    height=26,
                    halign="left",
                    valign="middle",
                    background_normal="",
                    background_down="",
                    background_color=(0, 0, 0, 0),
                    color=theme.ACCENT,
                    font_size=13,
                )
                lk.bind(size=lk.setter("text_size"))
                lk.bind(on_release=partial(self._open_term, term.id))
            else:
                lk = _hud_label(label, color=theme.TEXT_MUTED, size=13)
                lk.size_hint_y = None
                lk.height = 26
            lv = _hud_label(value, color=theme.TEXT, size=14, bold=True)
            lv.halign = "right"
            lv.size_hint_y = None
            lv.height = 26
            grid.add_widget(lk)
            grid.add_widget(lv)
        content.add_widget(grid)
        content.add_widget(BoxLayout())  # spacer pushes the action buttons to the bottom

        actions = BoxLayout(orientation="vertical", size_hint=(1, None), spacing=7)
        actions.bind(minimum_height=actions.setter("height"))
        for action in deal.actions:
            color = theme.ACCENT if action.action_id in self._PRIMARY_ACTIONS else theme.BTN_BG
            if not action.enabled:
                color = theme.PANEL_BG_ALT
            btn = _flat_button(
                action.label + ("" if action.enabled else f"  · {action.hint}"), color
            )
            btn.size_hint_y = None
            btn.height = 44
            btn.disabled = not action.enabled
            btn.bind(on_release=partial(self._on_action, action.action_id))
            actions.add_widget(btn)
        content.add_widget(actions)
        self.deal_panel.add_widget(content)

    # ----------------------------------------------------------------- events
    def on_tile(self, lot_id: str):
        self.controller.select(lot_id)
        self.refresh()
        # Quick fade so the panel feels responsive when a new lot is selected.
        self.deal_panel.opacity = 0.25
        Animation(opacity=1.0, duration=0.16).start(self.deal_panel)

    def _on_action(self, action_id: str, *_):
        if action_id == "open_upgrades":
            self.open_upgrades()
            return
        self.controller.do_action(action_id)
        self.sounds.play("build_done" if action_id in _WORK_ACTIONS else "cash")
        self.refresh()

    def open_upgrades(self):
        lid = self.controller.selected_lot_id
        if lid is None:
            return
        body = BoxLayout(orientation="vertical", spacing=6, padding=8)
        for opt in self.controller.available_upgrades(lid):
            row = BoxLayout(orientation="vertical", size_hint_y=None, height=52, padding=(2, 2))
            top = BoxLayout(orientation="horizontal", size_hint_y=None, height=30)
            top.add_widget(_hud_label(opt.label, size=14, bold=True))
            apply = Button(
                text="Build",
                size_hint=(None, 1),
                width=90,
                disabled=not opt.enabled,
                background_color=theme.ACCENT if opt.enabled else theme.PANEL_BG_ALT,
            )
            apply.bind(on_release=partial(self._apply_upgrade, opt.upgrade_id))
            top.add_widget(apply)
            row.add_widget(top)
            row.add_widget(_hud_label(opt.summary, color=theme.TEXT_MUTED, size=12))
            body.add_widget(row)
        self._upgrades_popup = Popup(
            title="Upgrades — value-add this building", content=body, size_hint=(0.7, 0.8)
        )
        self._upgrades_popup.open()

    def _apply_upgrade(self, upgrade_id: str, *_):
        self.controller.do_action(upgrade_id)
        self.sounds.play("build_done")
        popup = getattr(self, "_upgrades_popup", None)
        if popup is not None:
            popup.dismiss()
        self.refresh()

    def open_advisors(self):
        body = BoxLayout(orientation="vertical", spacing=8, padding=10)
        for adv in self.controller.advisors():
            row = BoxLayout(orientation="vertical", size_hint_y=None, height=58, padding=(2, 2))
            head = BoxLayout(orientation="horizontal", size_hint_y=None, height=30)
            head.add_widget(_hud_label(f"{adv.label}  ({adv.cost})", size=14, bold=True))
            hire = Button(
                text="Hired" if adv.hired else "Hire",
                size_hint=(None, 1),
                width=90,
                disabled=adv.hired,
                background_color=theme.PANEL_BG_ALT if adv.hired else theme.ACCENT,
            )
            hire.bind(on_release=partial(self._hire_advisor, adv.advisor_id))
            head.add_widget(hire)
            row.add_widget(head)
            row.add_widget(_hud_label(adv.blurb, color=theme.TEXT_MUTED, size=12))
            body.add_widget(row)
        self._advisors_popup = Popup(
            title="Advisors — hire specialists for passive perks",
            content=body,
            size_hint=(0.7, 0.7),
        )
        self._advisors_popup.open()

    def _hire_advisor(self, advisor_id: str, *_):
        self.controller.hire_advisor(advisor_id)
        self.sounds.play("cash")
        popup = getattr(self, "_advisors_popup", None)
        if popup is not None:
            popup.dismiss()
        self.refresh()

    def on_advance(self):
        self.controller.advance_month()
        self.sounds.play("tick")
        self.refresh()
        status = self.controller.status
        if status != "playing" and not self._endgame_shown:
            self._endgame_shown = True
            self.sounds.play("win" if status == "won" else "lose")
            self.show_endgame()

    def _on_hire(self):
        self.controller.hire_crew()
        self.sounds.play("cash")
        self.refresh()

    def _open_term(self, term_id: str, *_):
        term = get_term(term_id)
        if term is None:
            return
        body = BoxLayout(orientation="vertical", padding=14, spacing=6)
        body.add_widget(_hud_label(term.short, size=15, bold=True))
        body.add_widget(_hud_label(term.detail, color=theme.TEXT_MUTED, size=13))
        body.add_widget(_hud_label(f"Shows up: {term.appears_in}", color=theme.GOLD, size=12))
        if term.see_also:
            related = ", ".join(get_term(t).term for t in term.see_also if get_term(t) is not None)
            body.add_widget(_hud_label(f"See also: {related}", color=theme.TEXT_MUTED, size=12))
        Popup(title=term.term, content=body, size_hint=(0.55, 0.45)).open()

    def open_glossary(self):
        root = BoxLayout(orientation="vertical", spacing=8, padding=8)
        search = TextInput(
            hint_text="Search The Closet…", size_hint=(1, None), height=38, multiline=False
        )
        listing = GridLayout(cols=1, size_hint_y=None, spacing=6, padding=4)
        listing.bind(minimum_height=listing.setter("height"))

        def rebuild(query: str = ""):
            listing.clear_widgets()
            for term in self.controller.glossary(query):
                btn = Button(
                    text=f"{term.term} — {term.short}",
                    size_hint_y=None,
                    height=40,
                    halign="left",
                    valign="middle",
                    background_color=theme.PANEL_BG_ALT,
                    font_size=13,
                )
                btn.bind(size=btn.setter("text_size"))
                btn.bind(on_release=partial(self._open_term, term.id))
                listing.add_widget(btn)

        search.bind(text=lambda _inst, val: rebuild(val))
        rebuild()
        scroll = ScrollView()
        scroll.add_widget(listing)
        root.add_widget(search)
        root.add_widget(scroll)
        self._glossary_popup = Popup(
            title="The Closet — glossary", content=root, size_hint=(0.7, 0.85)
        )
        self._glossary_popup.open()

    def open_store(self):
        root = BoxLayout(orientation="vertical", spacing=8, padding=10)
        header = _hud_label(
            f"Keys: {self.monet.entitlements.keys}   ·   "
            f"{'Ad-free' if self.monet.is_ad_free() else 'Free (ads opt-in)'}",
            bold=True,
            size=14,
        )
        header.size_hint_y = None
        header.height = 24
        root.add_widget(header)
        disclosure = _hud_label(probability_disclosure(), color=theme.TEXT_MUTED, size=11)
        disclosure.size_hint_y = None
        disclosure.height = 34
        root.add_widget(disclosure)

        listing = GridLayout(cols=1, size_hint_y=None, spacing=6)
        listing.bind(minimum_height=listing.setter("height"))

        def rebuild():
            listing.clear_widgets()
            header.text = (
                f"Keys: {self.monet.entitlements.keys}   ·   "
                f"{'Ad-free' if self.monet.is_ad_free() else 'Free (ads opt-in)'}"
            )
            for p in self.monet.visible_products():
                row = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=8)
                row.add_widget(_hud_label(f"{p.title}", size=13))
                buy = Button(
                    text=f"${p.price_usd:.2f}",
                    size_hint=(None, 1),
                    width=90,
                    background_color=theme.ACCENT,
                )
                buy.bind(on_release=partial(self._buy, p.id, rebuild))
                row.add_widget(buy)
                listing.add_widget(row)

        rebuild()
        scroll = ScrollView()
        scroll.add_widget(listing)
        root.add_widget(scroll)
        self._store_popup = Popup(
            title="Real Mogul Store — cosmetics, Keys & passes (campaign is free)",
            content=root,
            size_hint=(0.72, 0.85),
        )
        self._store_popup.open()

    def _buy(self, product_id: str, rebuild, *_):
        outcome = self.monet.purchase(product_id)
        self.controller.message = (
            f"Purchased {product_id}." if outcome.ok else f"Purchase failed: {outcome.error}"
        )
        rebuild()
        self.refresh()

    def open_opportunities(self):
        opps = self.controller.opportunities()
        body = BoxLayout(orientation="vertical", spacing=8, padding=10)
        if not opps:
            body.add_widget(_hud_label("No deals on the table right now.", color=theme.TEXT_MUTED))
        else:
            for opp in opps:
                row = BoxLayout(orientation="horizontal", size_hint_y=None, height=48, spacing=8)
                row.add_widget(_hud_label(opp.headline, size=13))
                take = Button(
                    text="Take", size_hint=(None, 1), width=90, background_color=theme.ACCENT
                )
                take.bind(on_release=partial(self._take_opportunity, opp.opp_id))
                row.add_widget(take)
                body.add_widget(row)
        self._opps_popup = Popup(
            title="Opportunities — act before they're gone", content=body, size_hint=(0.7, 0.6)
        )
        self._opps_popup.open()

    def _take_opportunity(self, opp_id: str, *_):
        self.controller.accept_opportunity(opp_id)
        self.sounds.play("cash")
        popup = getattr(self, "_opps_popup", None)
        if popup is not None:
            popup.dismiss()
        self.refresh()

    def open_explain(self):
        lines = self.controller.explain_lines()
        if not lines:
            return
        content = GridLayout(cols=1, size_hint_y=None, spacing=10, padding=6)
        content.bind(minimum_height=content.setter("height"))
        for ln in lines:
            row = BoxLayout(orientation="vertical", size_hint_y=None, height=64, padding=(4, 2))
            top = _hud_label(f"{ln.label}  =  {ln.result}", bold=True, size=15)
            top.size_hint_y = None
            top.height = 24
            formula = _hud_label(ln.formula, color=theme.GOLD, size=12)
            formula.size_hint_y = None
            formula.height = 18
            plugged = _hud_label(ln.plugged, color=theme.TEXT_MUTED, size=12)
            plugged.size_hint_y = None
            plugged.height = 18
            row.add_widget(top)
            row.add_widget(formula)
            row.add_widget(plugged)
            content.add_widget(row)
        scroll = ScrollView()
        scroll.add_widget(content)
        self._explain_popup = Popup(
            title="Explain this deal", content=scroll, size_hint=(0.7, 0.85)
        )
        self._explain_popup.open()

    def show_endgame(self):
        won = self.controller.status == "won"
        h = self.controller.hud()
        s = self.controller.session

        overlay = FloatLayout(size_hint=(1, 1))
        overlay.add_widget(_panel(BoxLayout(), (0, 0, 0, 0.62)))  # scrim
        card = _panel(
            BoxLayout(
                orientation="vertical",
                padding=26,
                spacing=12,
                size_hint=(None, None),
                size=(480, 380),
            ),
            theme.PANEL_BG_ALT,
        )
        card.pos_hint = {"center_x": 0.5, "center_y": 0.5}

        title = Label(
            text="LEVEL COMPLETE!" if won else "LEVEL OVER",
            font_size=32,
            bold=True,
            color=theme.GOLD if won else theme.WARN,
            size_hint_y=None,
            height=48,
        )
        sub = _hud_label(self.controller.level.name, color=theme.TEXT_MUTED, size=14)
        sub.halign = "center"
        sub.size_hint_y = None
        sub.height = 22
        card.add_widget(title)
        card.add_widget(sub)

        stats = GridLayout(cols=2, size_hint=(1, None), spacing=(10, 8), padding=(10, 12))
        stats.bind(minimum_height=stats.setter("height"))
        rows = [
            ("Months played", f"{h.month}"),
            ("Final net worth", h.net_worth),
            ("Units owned", f"{s.units_owned()}"),
            ("Concepts mastered", f"{self.controller.mastery():.0%}"),
        ]
        for k, v in rows:
            kl = _hud_label(k, color=theme.TEXT_MUTED, size=14)
            kl.size_hint_y = None
            kl.height = 28
            vl = _hud_label(v, color=theme.TEXT, size=15, bold=True)
            vl.halign = "right"
            vl.size_hint_y = None
            vl.height = 28
            stats.add_widget(kl)
            stats.add_widget(vl)
        card.add_widget(stats)
        card.add_widget(BoxLayout())  # spacer

        buttons = BoxLayout(orientation="horizontal", size_hint=(1, None), height=48, spacing=10)
        nxt = self._next_campaign_level()
        menu_btn = _flat_button("Main menu", theme.BTN_BG)
        menu_btn.bind(on_release=lambda *_: (self._close_end(overlay), self._to_menu()))
        buttons.add_widget(menu_btn)
        if won and nxt is not None:
            next_btn = _flat_button(f"Next: {nxt.name}  ▸", theme.ACCENT)
            next_btn.bind(on_release=lambda *_: (self._close_end(overlay), self._start_game(nxt)))
            buttons.add_widget(next_btn)
        elif not won:
            retry = _flat_button("Retry", theme.ACCENT)
            retry.bind(
                on_release=lambda *_: (
                    self._close_end(overlay),
                    self._start_game(self.controller.level),
                )
            )
            buttons.add_widget(retry)
        card.add_widget(buttons)

        overlay.add_widget(card)
        self._overlay.add_widget(overlay)
        if won:
            self._confetti(overlay)

    def _close_end(self, overlay) -> None:
        with contextlib.suppress(Exception):
            self._overlay.remove_widget(overlay)

    def _next_campaign_level(self):
        levels = campaign_levels()
        cur = getattr(self.controller, "level", None)
        for i, lvl in enumerate(levels):
            if cur is not None and lvl.id == cur.id and i + 1 < len(levels):
                return levels[i + 1]
        return None

    def _confetti(self, overlay) -> None:
        colors = [theme.GOLD, theme.ACCENT, theme.PRIMARY, theme.WARN, (0.71, 0.51, 0.55, 1)]
        w, hgt = Window.width, Window.height
        for _ in range(56):
            piece = Widget(size_hint=(None, None), size=(9, 9))
            piece.pos = (random.uniform(0, w), hgt + random.uniform(0, 160))
            col = random.choice(colors)
            with piece.canvas:
                Color(*col)
                rect = Rectangle(pos=piece.pos, size=piece.size)
            piece.bind(pos=lambda inst, val, rr=rect: setattr(rr, "pos", val))
            overlay.add_widget(piece)
            anim = Animation(
                y=-20,
                x=piece.x + random.uniform(-80, 80),
                duration=random.uniform(1.4, 3.0),
                t="in_quad",
            )
            anim.bind(on_complete=lambda a, p=piece: overlay.remove_widget(p))
            anim.start(piece)

    # ----------------------------------------------------------------- capture
    def _run_capture(self):
        os.makedirs("ui/_shots", exist_ok=True)
        # export_to_png renders synchronously to an FBO, so each shot matches its
        # label (no double-buffer lag, unlike Window.screenshot).
        self._cap_queue = [
            ("00_menu", lambda: setattr(self.sm, "current", "menu")),
            ("01_initial", lambda: setattr(self.sm, "current", "game")),
            ("02_select_coach", lambda: self.on_tile("sfr-3")),
            ("03_explain", lambda: self.open_explain()),
            ("04_glossary", lambda: (self._dismiss_explain(), self.open_glossary())),
            ("05_bought_coach", lambda: (self._dismiss_glossary(), self._on_action("buy"))),
            ("06_renovate", lambda: self._on_action("renovate")),
            ("07_boom_coach", lambda: [self.on_advance() for _ in range(19)]),
            ("08_store", lambda: self.open_store()),
            ("09_win", lambda: (self._dismiss_store(), [self.on_advance() for _ in range(6)])),
        ]
        Clock.schedule_once(self._cap_tick, 1.0)

    def _dismiss_explain(self):
        popup = getattr(self, "_explain_popup", None)
        if popup is not None:
            popup.dismiss()

    def _dismiss_glossary(self):
        popup = getattr(self, "_glossary_popup", None)
        if popup is not None:
            popup.dismiss()

    def _dismiss_store(self):
        popup = getattr(self, "_store_popup", None)
        if popup is not None:
            popup.dismiss()

    def _cap_tick(self, _dt):
        if not self._cap_queue:
            Clock.schedule_once(lambda dt: self.stop(), 0.4)
            return
        name, action = self._cap_queue.pop(0)
        if action is not None:
            action()
        Clock.schedule_once(partial(self._cap_shoot, name), 0.5)

    def _cap_shoot(self, name, _dt):
        path = f"ui/_shots/{name}.png"
        explain = getattr(self, "_explain_popup", None)
        glossary = getattr(self, "_glossary_popup", None)
        store = getattr(self, "_store_popup", None)
        if name == "03_explain" and explain is not None:
            explain.content.export_to_png(path)
        elif name == "04_glossary" and glossary is not None:
            glossary.content.export_to_png(path)
        elif name == "08_store" and store is not None:
            store.content.export_to_png(path)
        else:
            self.root.export_to_png(path)
        Clock.schedule_once(self._cap_tick, 0.3)


def main() -> int:
    RealMogulApp(shot="--shot" in sys.argv).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
