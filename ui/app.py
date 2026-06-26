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
import sys
import time
from functools import partial
from pathlib import Path

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.app import App  # noqa: E402
from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.graphics import Color, Rectangle  # noqa: E402
from kivy.uix.boxlayout import BoxLayout  # noqa: E402
from kivy.uix.button import Button  # noqa: E402
from kivy.uix.floatlayout import FloatLayout  # noqa: E402
from kivy.uix.gridlayout import GridLayout  # noqa: E402
from kivy.uix.label import Label  # noqa: E402
from kivy.uix.popup import Popup  # noqa: E402
from kivy.uix.progressbar import ProgressBar  # noqa: E402
from kivy.uix.scrollview import ScrollView  # noqa: E402
from kivy.uix.textinput import TextInput  # noqa: E402

from education.glossary import get_term  # noqa: E402
from engine.assets.upgrades import UPGRADE_CATALOG  # noqa: E402
from engine.progression.campaign import build_level_one  # noqa: E402
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
        self.controller = GameController(build_level_one())
        self._shot = shot
        # Monetization: a provider is injected on-device (see nativebridge); on
        # desktop/web it defaults to the mock store. Entitlements persist + reconcile.
        secret = "dev-secret-change-me"
        provider = billing_provider or MockBillingProvider(secret)
        self.monet = MonetizationManager(
            provider,
            mock_secret=secret,
            save_path=Path("ui/_entitlements.json"),
        )
        self.monet.reconcile()
        self.sounds = SoundBank()

        # Save/resume + 'while you were away'. Disabled in --shot so captures are
        # deterministic and don't pick up a stale save.
        self._persist = not shot
        self._save_path = Path("ui/_savegame.json")
        self._offline = None
        # A corrupt/incompatible save just starts a fresh game.
        if self._persist and self._save_path.exists():
            with contextlib.suppress(Exception):
                env = json.loads(self._save_path.read_text())
                session = load_from_dict(env)
                self.controller.session = session
                ts = saved_at_of(env)
                if ts is not None:
                    off = compute_offline_earnings(session, time.time() - ts)
                    if off.worthwhile:
                        session.cash += off.amount
                        self._offline = off

    def _save_game(self):
        if not self._persist:
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
        bar = _panel(
            BoxLayout(
                orientation="horizontal", size_hint=(1, None), height=50, padding=(12, 7), spacing=8
            ),
            theme.TOOLBAR_BG,
        )
        self.btn_deals = _flat_button("Deals", theme.GOLD, width=104)
        self.btn_deals.color = (0.1, 0.1, 0.1, 1)
        self.btn_deals.bind(on_release=lambda *_: self.open_opportunities())
        specs = [
            ("Hire crew", self._on_hire),
            ("Advisors", self.open_advisors),
            ("Store", self.open_store),
            ("The Closet", self.open_glossary),
            ("Explain deal", self.open_explain),
        ]
        bar.add_widget(self.btn_deals)
        for text, cb in specs:
            btn = _flat_button(text, theme.BTN_BG, width=112)
            btn.bind(on_release=lambda _w, c=cb: c())
            bar.add_widget(btn)
        bar.add_widget(BoxLayout())  # flexible spacer pushes the primary action right
        btn_next = _flat_button("Advance month  ▸", theme.PRIMARY, width=190, font_size=15)
        btn_next.bind(on_release=lambda *_: self.on_advance())
        bar.add_widget(btn_next)
        return bar

    def build(self):
        root = FloatLayout()
        main = BoxLayout(orientation="vertical", size_hint=(1, 1))
        root.add_widget(main)

        main.add_widget(self._make_status_bar())

        # Middle: board + deal panel
        mid = BoxLayout(orientation="horizontal", size_hint=(1, 1))
        self.board = BoardWidget(on_tile=self.on_tile, size_hint=(0.62, 1))
        mid.add_widget(self.board)
        self.deal_panel = _panel(
            BoxLayout(orientation="vertical", size_hint=(0.38, 1), padding=0, spacing=0),
            theme.PANEL_BG,
        )
        mid.add_widget(self.deal_panel)
        main.add_widget(mid)

        # Coach strip — mentor tips and status messages.
        self.lbl_coach = _hud_label("", color=theme.TEXT, size=13)
        coach_bar = _panel(
            BoxLayout(size_hint=(1, None), height=40, padding=(16, 6)), theme.PANEL_BG_ALT
        )
        coach_bar.add_widget(self.lbl_coach)
        main.add_widget(coach_bar)

        main.add_widget(self._make_toolbar())

        # Juice: the cash readout rolls up/down toward its target instead of jumping.
        self._cash_shown = float(self.controller.hud().cash_value)
        self._cash_target = self._cash_shown
        Clock.schedule_interval(self._tick_cash, 1 / 30.0)

        self.refresh()
        return root

    def _tick_cash(self, dt):
        if abs(self._cash_target - self._cash_shown) < 1:
            self._cash_shown = self._cash_target
        else:
            self._cash_shown += (self._cash_target - self._cash_shown) * min(1.0, dt * 7.0)
        self.lbl_cash.text = f"${self._cash_shown:,.0f}"

    def on_start(self):
        if self._shot:
            Clock.schedule_once(lambda dt: self._run_capture(), 1.0)
        elif self._offline is not None:
            Clock.schedule_once(lambda dt: self._show_offline(), 0.6)

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
            self.lbl_coach.text = f"[{tip.mentor_name}]  {tip.text}"
            self.lbl_coach.color = theme.TEXT
        else:
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
        if status != "playing":
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
        h = self.controller.hud()
        msg = "Level complete!" if h.status == "won" else "Level over."
        body = Label(
            text=f"{msg}\n\n{h.message}\n\nNet worth: {h.net_worth}\nMonth {h.month}",
            color=theme.TEXT,
            halign="center",
        )
        Popup(title=msg, content=body, size_hint=(0.5, 0.4)).open()

    # ----------------------------------------------------------------- capture
    def _run_capture(self):
        os.makedirs("ui/_shots", exist_ok=True)
        # export_to_png renders synchronously to an FBO, so each shot matches its
        # label (no double-buffer lag, unlike Window.screenshot).
        self._cap_queue = [
            ("01_initial", None),
            ("02_select_coach", lambda: self.on_tile("sfr-3")),
            ("03_explain", lambda: self.open_explain()),
            ("04_glossary", lambda: (self._dismiss_explain(), self.open_glossary())),
            ("05_bought_coach", lambda: (self._dismiss_glossary(), self._on_action("buy"))),
            ("06_renovate", lambda: self._on_action("renovate")),
            ("07_boom_coach", lambda: [self.on_advance() for _ in range(20)]),
            ("08_store", lambda: self.open_store()),
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
