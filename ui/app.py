"""Real Mogul — Kivy desktop app (Phase 3 vertical slice).

One playable campaign level with placeholder art: an isometric board, a live
deal/finance panel, build timers, and the "Explain this deal" overlay showing
real engine numbers. The views are thin — every decision routes through
``GameController`` (Kivy-free, tested).

Play:      python -m ui
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

Window.size = (1120, 700)
Window.clearcolor = theme.BG


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
    def build(self):
        root = FloatLayout()
        main = BoxLayout(orientation="vertical", size_hint=(1, 1))
        root.add_widget(main)

        # HUD bar
        self.hud_bar = _panel(
            BoxLayout(
                orientation="horizontal", size_hint=(1, None), height=64, padding=12, spacing=18
            ),
            theme.PANEL_BG_ALT,
        )
        self.lbl_month = _hud_label("", bold=True)
        self.lbl_cash = _hud_label("", color=theme.GOLD, bold=True)
        self.lbl_networth = _hud_label("", bold=True)
        self.lbl_objective = _hud_label("", color=theme.TEXT_MUTED, size=13)
        self.progress = ProgressBar(max=1.0, size_hint=(0.5, None), height=18)
        obj_box = BoxLayout(orientation="vertical", spacing=2)
        obj_box.add_widget(self.lbl_objective)
        obj_box.add_widget(self.progress)
        for w in (self.lbl_month, self.lbl_cash, self.lbl_networth, obj_box):
            self.hud_bar.add_widget(w)
        self.lbl_crews = _hud_label("", color=theme.TEXT_MUTED, size=12)
        self.hud_bar.add_widget(self.lbl_crews)
        btn_hire = Button(
            text="Hire crew", size_hint=(None, 1), width=90, background_color=theme.ACCENT_DIM
        )
        btn_hire.bind(on_release=lambda *_: self._on_hire())
        self.hud_bar.add_widget(btn_hire)
        self.btn_deals = Button(
            text="Deals", size_hint=(None, 1), width=100, background_color=theme.GOLD
        )
        self.btn_deals.bind(on_release=lambda *_: self.open_opportunities())
        self.hud_bar.add_widget(self.btn_deals)
        btn_advisors = Button(
            text="Advisors", size_hint=(None, 1), width=100, background_color=theme.ACCENT_DIM
        )
        btn_advisors.bind(on_release=lambda *_: self.open_advisors())
        self.hud_bar.add_widget(btn_advisors)
        self.lbl_mastery = _hud_label("", color=theme.TEXT_MUTED, size=12)
        self.hud_bar.add_widget(self.lbl_mastery)
        btn_store = Button(
            text="Store", size_hint=(None, 1), width=80, background_color=theme.ACCENT_DIM
        )
        btn_store.bind(on_release=lambda *_: self.open_store())
        self.hud_bar.add_widget(btn_store)
        btn_glossary = Button(
            text="The Closet", size_hint=(None, 1), width=110, background_color=theme.ACCENT_DIM
        )
        btn_glossary.bind(on_release=lambda *_: self.open_glossary())
        btn_explain = Button(
            text="Explain deal", size_hint=(None, 1), width=120, background_color=theme.ACCENT_DIM
        )
        btn_explain.bind(on_release=lambda *_: self.open_explain())
        btn_next = Button(
            text="Advance month", size_hint=(None, 1), width=140, background_color=theme.ACCENT
        )
        btn_next.bind(on_release=lambda *_: self.on_advance())
        self.hud_bar.add_widget(btn_glossary)
        self.hud_bar.add_widget(btn_explain)
        self.hud_bar.add_widget(btn_next)
        main.add_widget(self.hud_bar)

        # Middle: board + deal panel
        mid = BoxLayout(orientation="horizontal", size_hint=(1, 1))
        self.board = BoardWidget(on_tile=self.on_tile, size_hint=(0.62, 1))
        mid.add_widget(self.board)

        self.deal_panel = _panel(
            BoxLayout(orientation="vertical", size_hint=(0.38, 1), padding=14, spacing=8),
            theme.PANEL_BG,
        )
        mid.add_widget(self.deal_panel)
        main.add_widget(mid)

        # Coach bar — mentor tips and status messages live here.
        self.lbl_coach = _hud_label("", color=theme.TEXT, size=13)
        coach_bar = _panel(
            BoxLayout(size_hint=(1, None), height=52, padding=(14, 6)), theme.PANEL_BG_ALT
        )
        coach_bar.add_widget(self.lbl_coach)
        main.add_widget(coach_bar)

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
        self.lbl_cash.text = f"Cash ${self._cash_shown:,.0f}"

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
        self.lbl_month.text = f"Month {h.month}/{h.month_limit}"
        self._cash_target = float(h.cash_value)  # animated by _tick_cash
        self.btn_deals.text = f"Deals ({h.deals})" if h.deals else "Deals"
        self.lbl_networth.text = f"Net worth {h.net_worth}"
        self.lbl_objective.text = h.objective
        self.progress.value = h.progress
        self.lbl_mastery.text = f"Mastery {self.controller.mastery():.0%}"
        self.lbl_crews.text = f"Crews {h.crews}"
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

    def _refresh_deal(self):
        self.deal_panel.clear_widgets()
        deal = self.controller.selected_deal()
        if deal is None:
            self.deal_panel.add_widget(
                _hud_label("Tap a lot to scout a deal.", color=theme.TEXT_MUTED)
            )
            return
        title = _hud_label(deal.title, size=20, bold=True)
        title.size_hint_y = None
        title.height = 28
        sub = _hud_label(deal.subtitle, color=theme.TEXT_MUTED, size=13)
        sub.size_hint_y = None
        sub.height = 20
        self.deal_panel.add_widget(title)
        self.deal_panel.add_widget(sub)

        grid = GridLayout(cols=2, size_hint=(1, None), spacing=4)
        grid.bind(minimum_height=grid.setter("height"))
        for label, value in deal.rows:
            term = self.controller.term_for_metric(label)
            if term is not None:
                # Tappable metric -> opens its glossary term (every metric explained).
                lk = Button(
                    text=label + "  ?",
                    size_hint_y=None,
                    height=24,
                    halign="left",
                    valign="middle",
                    background_color=(0, 0, 0, 0),
                    color=theme.ACCENT,
                    font_size=13,
                )
                lk.bind(size=lk.setter("text_size"))
                lk.bind(on_release=partial(self._open_term, term.id))
            else:
                lk = _hud_label(label, color=theme.TEXT_MUTED, size=13)
                lk.size_hint_y = None
                lk.height = 24
            lv = _hud_label(value, color=theme.TEXT, size=13, bold=True)
            lv.halign = "right"
            lv.size_hint_y = None
            lv.height = 24
            grid.add_widget(lk)
            grid.add_widget(lv)
        self.deal_panel.add_widget(grid)

        for action in deal.actions:
            btn = Button(
                text=action.label + ("" if action.enabled else f"  · {action.hint}"),
                size_hint=(1, None),
                height=42,
                disabled=not action.enabled,
                background_color=theme.ACCENT if action.enabled else theme.PANEL_BG_ALT,
            )
            btn.bind(on_release=partial(self._on_action, action.action_id))
            self.deal_panel.add_widget(btn)

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
