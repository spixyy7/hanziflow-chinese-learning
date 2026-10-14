"""
ui/views/dashboard.py — Dashboard v4.
Novo: XP grafikon, rank/level-up animacije, streak vezan za kviz,
      modernizovani Settings, trophy sistem, achievement overlay.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta
from typing import Callable

from ..theme import (C, F, S, Card, GhostButton, XPBar, PrimaryButton,
                     SuccessButton, DangerButton, ConfirmDialog,
                     ComboOverlay, toggle_fullscreen)
from ...core import UserProfile, Database, WeaknessDetector, compute_level, get_rank, get_next_rank
from ...core import set_audio_enabled, is_audio_enabled
from ..widgets_calendar import HeatmapCalendar, StreakPanel

# ─── Rang po levelu (nova logika — odvojena od Arena skora) ───────────────────

LEVEL_RANKS = [
    {"name": "Beginner",    "min_level": 1,  "color": "#CD7F32", "icon": "🌱",
     "trophy": None},
    {"name": "Student",     "min_level": 6,  "color": "#A8A9AD", "icon": "📖",
     "trophy": {"id": "rank_student",  "name": "Student",         "icon": "📖"}},
    {"name": "Scholar",     "min_level": 11, "color": "#FFD700", "icon": "🎓",
     "trophy": {"id": "rank_scholar",  "name": "Scholar",         "icon": "🎓"}},
    {"name": "Master",      "min_level": 21, "color": "#50C8FF", "icon": "⚡",
     "trophy": {"id": "rank_master",   "name": "Master",          "icon": "⚡"}},
    {"name": "Grand Master","min_level": 35, "color": "#B44FE8", "icon": "👑",
     "trophy": {"id": "rank_grandmaster","name": "Grand Master",  "icon": "👑"}},
    {"name": "Dragon",      "min_level": 50, "color": "#FF4F4F", "icon": "🐉",
     "trophy": {"id": "rank_dragon",   "name": "Dragon",          "icon": "🐉"}},
]

# Trofej milestone leveli
LEVEL_TROPHIES = {
    5:  {"id": "trophy_5",  "name": "First Steps",       "icon": "🏆", "xp": 50},
    10: {"id": "trophy_10", "name": "Consistent Learner","icon": "🏆", "xp": 150},
    20: {"id": "trophy_20", "name": "HSK Warrior",       "icon": "🏆", "xp": 300},
    30: {"id": "trophy_30", "name": "Fluency Seeker",    "icon": "🏆", "xp": 500},
    50: {"id": "trophy_50", "name": "Dragon Scholar",    "icon": "🐉", "xp": 1000},
}


def get_level_rank(level: int) -> dict:
    r = LEVEL_RANKS[0]
    for rank in LEVEL_RANKS:
        if level >= rank["min_level"]:
            r = rank
    return r


def get_next_level_rank(level: int) -> dict | None:
    for rank in LEVEL_RANKS:
        if level < rank["min_level"]:
            return rank
    return None


_T = {
    "en": {
        "app_title": "HanziFlow 🐉",
        "level": "Level {}",
        "xp_label": "XP: {} / {}",
        "streak": "🔥 {} day streak",
        "daily": "Today: {} / {} XP",
        "rank_lv": "Rank: {} {}",
        "next_rank": "Next rank at level {}",
        "daily_bonus": "🎁 Daily Bonus! +50 XP",
        "daily_bonus_btn": "🎁 Claim Daily Bonus",
        "already_claimed": "✅ Bonus claimed today",
        "add_word": "📖 Add Word",
        "quiz": "🧠 Quiz",
        "grammar": "📝 Grammar",
        "speaking": "🎤 Speaking",
        "arena": "⚔️ Arena",
        "leaderboard": "🏆 Leaderboard",
        "mistakes": "🔴 Mistakes ({})",
        "no_mistakes": "✅ No Mistakes",
        "goal": "🎯 Goal",
        "profile": "👤 Profile",
        "writing": "✍️ Writing",
        "audio_on": "🔊",
        "audio_off": "🔇",
        "settings_btn": "⚙️",
        "settings_title": "Settings",
        "theme_light": "☀️ Light",
        "theme_dark": "🌙 Dark",
        "theme_system": "🖥 System",
        "switch_account": "🔄 Switch Account",
        "sign_out": "⎋ Sign Out",
        "theme_label": "Theme",
        "stats_title": "Progress — Last 7 Days",
        "rank_arena": "Arena Rank:",
        "trophies": "Trophies",
        "no_trophies": "Complete quizzes to earn trophies!",
        "fullscreen": "⛶",
        "fullscreen_off": "⛶",
        "rank_up_title": "New Rank!",
        "trophy_title": "Trophy Unlocked!",
        "nickname": "{} — {}",
    },
    "sr": {
        "app_title": "HanziFlow 🐉",
        "level": "Nivo {}",
        "xp_label": "XP: {} / {}",
        "streak": "🔥 {} dana streak",
        "daily": "Danas: {} / {} XP",
        "rank_lv": "Rang: {} {}",
        "next_rank": "Sledeći rang na nivou {}",
        "daily_bonus": "🎁 Dnevni bonus! +50 XP",
        "daily_bonus_btn": "🎁 Uzmi dnevni bonus",
        "already_claimed": "✅ Bonus uzet danas",
        "add_word": "📖 Dodaj reč",
        "quiz": "🧠 Kviz",
        "grammar": "📝 Gramatika",
        "speaking": "🎤 Govor",
        "arena": "⚔️ Arena",
        "leaderboard": "🏆 Tabela",
        "mistakes": "🔴 Greške ({})",
        "no_mistakes": "✅ Nema grešaka",
        "goal": "🎯 Cilj",
        "profile": "👤 Profil",
        "writing": "✍️ Writing",
        "audio_on": "🔊",
        "audio_off": "🔇",
        "settings_btn": "⚙️",
        "settings_title": "Podešavanja",
        "theme_light": "☀️ Svetla",
        "theme_dark": "🌙 Tamna",
        "theme_system": "🖥 Sistemska",
        "switch_account": "🔄 Promeni nalog",
        "sign_out": "⎋ Odjavi se",
        "theme_label": "Tema",
        "stats_title": "Napredak — poslednjih 7 dana",
        "rank_arena": "Arena rang:",
        "trophies": "Trofeji",
        "no_trophies": "Završi kvizove da zaradiš trofeje!",
        "fullscreen": "⛶",
        "fullscreen_off": "⛶",
        "rank_up_title": "Novi Rang!",
        "trophy_title": "Trofej otključan!",
        "nickname": "{} — {}",
    },
}


class DashboardView(tk.Frame):
    def __init__(self, parent, profile: UserProfile,
                 on_quiz, on_grammar, on_speaking, on_add_word,
                 on_mistakes, on_goal, on_logout,
                 on_arena=None, on_leaderboard=None, on_profile=None,
                 on_writing=None):
        super().__init__(parent, bg=C.BG)
        self._profile = profile
        self._db      = Database()
        self._lang    = profile.lang
        self._cbs = {
            "quiz": on_quiz, "grammar": on_grammar, "speaking": on_speaking,
            "add_word": on_add_word, "mistakes": on_mistakes,
            "goal": on_goal, "logout": on_logout,
            "arena": on_arena or (lambda: None),
            "leaderboard": on_leaderboard or (lambda: None),
            "profile": on_profile or (lambda: None),
            "writing":     on_writing or (lambda: None),
            "notif_bell":  None,   # set via set_notif_callback()
        }
        self._notif_count   = 0
        self._notif_bell_btn = None
        # Track last level/rank for change detection
        lvl, _, _ = compute_level(profile.xp)
        self._last_level = lvl
        self._last_rank  = get_level_rank(lvl)["name"]

        self._build()
        self.refresh()
        self._check_daily_bonus()

    def _t(self, key: str, *args) -> str:
        txt = _T[self._lang].get(key, key)
        return txt.format(*args) if args else txt

    def set_notif_callback(self, callback, initial_count: int = 0):
        """Called by App after creating dashboard. Enables bell button."""
        self._cbs["notif_bell"] = callback
        self.update_notif_count(initial_count)

    def update_notif_count(self, count: int):
        """Update the notification badge on the bell button."""
        self._notif_count = count
        if self._notif_bell_btn:
            try:
                badge = f" ({count})" if count > 0 else ""
                self._notif_bell_btn.config(
                    text=f"🔔{badge}",
                    fg="#FF9800" if count > 0 else C.TEXT_MUTED)
            except Exception:
                pass

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Top header ───────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=C.BG_SIDEBAR); hdr.pack(fill="x")

        # Left: app title
        left_hdr = tk.Frame(hdr, bg=C.BG_SIDEBAR)
        left_hdr.pack(side="left", padx=S.MD, pady=S.XS)
        tk.Label(left_hdr, text=self._t("app_title"), bg=C.BG_SIDEBAR,
                 fg=C.PRIMARY, font=(F.FAMILY, 15, "bold")).pack(side="left")

        # Right: avatar + controls
        right_hdr = tk.Frame(hdr, bg=C.BG_SIDEBAR)
        right_hdr.pack(side="right", padx=S.SM)

        # Fullscreen button
        self._fs_btn = tk.Button(right_hdr, text=self._t("fullscreen"),
                                  bg=C.BG_SIDEBAR, fg=C.TEXT_MUTED,
                                  font=(F.FAMILY, 14), relief="flat", bd=0,
                                  cursor="hand2", activebackground=C.BG_HOVER,
                                  command=self._toggle_fs)
        self._fs_btn.pack(side="left", padx=2)
        self._fs_btn.bind("<Enter>", lambda e: self._fs_btn.config(fg=C.PRIMARY))
        self._fs_btn.bind("<Leave>", lambda e: self._fs_btn.config(fg=C.TEXT_MUTED))

        # Audio toggle
        self._audio_btn = tk.Button(right_hdr, text="", bg=C.BG_SIDEBAR,
                                     fg=C.TEXT, font=(F.FAMILY, 14),
                                     relief="flat", bd=0, cursor="hand2",
                                     activebackground=C.BG_HOVER,
                                     command=self._toggle_audio)
        self._audio_btn.pack(side="left", padx=2)

        # Notification bell
        self._notif_bell_btn = tk.Button(
            right_hdr, text="🔔",
            bg=C.BG_SIDEBAR, fg=C.TEXT_MUTED,
            font=(F.FAMILY, 14), relief="flat", bd=0, cursor="hand2",
            activebackground=C.BG_HOVER,
            command=lambda: self._cbs["notif_bell"]() if self._cbs.get("notif_bell") else None)
        self._notif_bell_btn.pack(side="left", padx=2)
        self._notif_bell_btn.bind("<Enter>", lambda e: self._notif_bell_btn.config(fg=C.PRIMARY))
        self._notif_bell_btn.bind("<Leave>", lambda e: self._notif_bell_btn.config(
            fg="#FF9800" if self._notif_count > 0 else C.TEXT_MUTED))

        # Settings
        tk.Button(right_hdr, text=self._t("settings_btn"),
                  bg=C.BG_SIDEBAR, fg=C.TEXT_MUTED, font=(F.FAMILY, 14),
                  relief="flat", bd=0, cursor="hand2",
                  activebackground=C.BG_HOVER,
                  command=self._open_settings).pack(side="left", padx=2)

        # Avatar (top right, beside streak)
        self._hdr_avatar = tk.Canvas(right_hdr, width=34, height=34,
                                      bg=C.BG_SIDEBAR, highlightthickness=0)
        self._hdr_avatar.pack(side="left", padx=(S.XS, S.SM))
        self._hdr_avatar.bind("<Button-1>", lambda e: self._cbs["profile"]())
        self._hdr_avatar.config(cursor="hand2")
        self._draw_header_avatar()

        # ── Two-column body ───────────────────────────────────────────────────
        main = tk.Frame(self, bg=C.BG)
        main.pack(fill="both", expand=True, padx=S.SM, pady=S.SM)

        left  = tk.Frame(main, bg=C.BG)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(main, bg=C.BG)
        right.pack(side="right", fill="y", padx=(S.SM, 0))

        self._build_user_card(left)
        self._build_rank_card(left)
        self._build_buttons(left)
        self._build_charts(left)
        self._build_right_panel(right)

    # ── User card ─────────────────────────────────────────────────────────────

    def _build_user_card(self, parent):
        card = Card(parent); card.pack(fill="x", pady=(0, S.XS))
        b = card.body()

        row1 = tk.Frame(b, bg=C.BG_CARD); row1.pack(fill="x")
        self._lbl_user = tk.Label(row1, text="", bg=C.BG_CARD,
                                   fg=C.TEXT, font=F.H2)
        self._lbl_user.pack(side="left")
        self._lbl_diff = tk.Label(row1, text="", bg=C.BG_CARD,
                                   fg=C.TEXT_MUTED, font=F.SMALL)
        self._lbl_diff.pack(side="right")

        self._xp_bar = XPBar(b, bg=C.BG_CARD)
        self._xp_bar.pack(fill="x", pady=(S.XS, 0))

        row2 = tk.Frame(b, bg=C.BG_CARD); row2.pack(fill="x", pady=(S.XS, 0))
        self._lbl_streak = tk.Label(row2, text="", bg=C.BG_CARD,
                                     fg=C.WARNING, font=F.LABEL_B)
        self._lbl_streak.pack(side="left")
        self._lbl_daily = tk.Label(row2, text="", bg=C.BG_CARD,
                                    fg=C.PRIMARY, font=F.LABEL)
        self._lbl_daily.pack(side="right")

    # ── Rank card (level-based) ────────────────────────────────────────────────

    def _build_rank_card(self, parent):
        card = Card(parent); card.pack(fill="x", pady=(0, S.XS))
        b = card.body()

        row = tk.Frame(b, bg=C.BG_CARD); row.pack(fill="x")
        self._lbl_rank_lv = tk.Label(row, text="", bg=C.BG_CARD,
                                      fg=C.TEXT, font=F.LABEL_B)
        self._lbl_rank_lv.pack(side="left")
        self._lbl_next_rank_lv = tk.Label(row, text="", bg=C.BG_CARD,
                                           fg=C.TEXT_MUTED, font=F.TINY)
        self._lbl_next_rank_lv.pack(side="right")

        # Arena rank (separate smaller row)
        row2 = tk.Frame(b, bg=C.BG_CARD); row2.pack(fill="x", pady=(S.XS, 0))
        self._lbl_arena_rank = tk.Label(row2, text="", bg=C.BG_CARD,
                                         fg=C.TEXT_MUTED, font=F.TINY)
        self._lbl_arena_rank.pack(side="left")
        self._lbl_arena_pts = tk.Label(row2, text="", bg=C.BG_CARD,
                                        fg=C.GOLD, font=F.TINY)
        self._lbl_arena_pts.pack(side="right")

        # Level XP bar
        self._level_xp_bar = XPBar(b, bg=C.BG_CARD)
        self._level_xp_bar.pack(fill="x", pady=(S.XS, 0))

        # Trophies row
        self._trophy_frame = tk.Frame(b, bg=C.BG_CARD)
        self._trophy_frame.pack(fill="x", pady=(S.XS, 0))

    # ── Action buttons ────────────────────────────────────────────────────────

    def _build_buttons(self, parent):
        self._bonus_btn = tk.Button(parent, text="", font=F.BODY_B,
                                    bg=C.GOLD, fg=C.TEXT,
                                    relief="flat", bd=0, cursor="hand2",
                                    padx=S.LG, pady=S.XS,
                                    command=self._claim_bonus)
        self._bonus_btn.pack(fill="x", pady=(0, S.XS))

        grid = tk.Frame(parent, bg=C.BG)
        grid.pack(fill="x", pady=(0, S.XS))

        buttons = [
            ("add_word",    C.PRIMARY),  ("quiz",      C.PURPLE),
            ("grammar",     C.ORANGE),   ("speaking",  C.TEAL),
            ("arena",       "#0D0D1E"),   ("leaderboard", C.GOLD),
            ("mistakes",    C.DANGER),   ("goal",      "#27AE60"),
            ("writing",     "#E91E8C"),   ("profile",   "#8E44AD"),
        ]
        for i, (key, color) in enumerate(buttons):
            r, c = divmod(i, 3)
            lbl = self._t(key) if key != "mistakes" else self._t("no_mistakes")
            btn = tk.Button(grid, text=lbl,
                            bg=color,
                            fg=C.TEXT_WHITE if color != C.GOLD else C.TEXT,
                            font=F.BODY_B, relief="flat", bd=0,
                            cursor="hand2", padx=S.SM, pady=S.SM, width=10,
                            activebackground=color,
                            command=self._cbs.get(key, lambda: None))
            btn.grid(row=r, column=c, padx=2, pady=2, sticky="ew")
            grid.columnconfigure(c, weight=1)
            if key == "mistakes": self._btn_mistakes = btn
            # Hover lighten
            btn.bind("<Enter>", lambda e, b=btn, bg=color: _try_lighten(b, bg))
            btn.bind("<Leave>", lambda e, b=btn, bg=color: b.config(bg=bg))

    # ── XP/Progress Charts ────────────────────────────────────────────────────

    def _build_charts(self, parent):
        card = Card(parent); card.pack(fill="x", pady=(0, S.XS))
        b = card.body()
        tk.Label(b, text=self._t("stats_title"), bg=C.BG_CARD,
                 fg=C.TEXT, font=F.LABEL_B).pack(anchor="w", pady=(0, S.XS))
        self._chart_canvas = tk.Canvas(b, height=90, bg=C.BG_CARD,
                                        highlightthickness=0, bd=0)
        self._chart_canvas.pack(fill="x")
        self._chart_canvas.bind("<Configure>", lambda e: self._draw_xp_chart())

    def _draw_xp_chart(self):
        """Nacrtaj bar chart XP za poslednjih 7 dana."""
        cv = self._chart_canvas
        cv.delete("all")
        w = cv.winfo_width()
        h = cv.winfo_height()
        if not w or not h: return

        today = date.today()
        days  = [(today - timedelta(days=6-i)) for i in range(7)]
        hist  = self._profile.daily_xp_history

        values = [hist.get(d.isoformat(), 0) for d in days]
        goal   = max(self._profile.daily_goal, 1)
        max_v  = max(max(values), goal, 1)

        bar_w   = max(8, (w - 20) // 7 - 4)
        x_start = 10

        for i, (d, v) in enumerate(zip(days, values)):
            x   = x_start + i * ((w - 20) // 7)
            pct = min(1.0, v / max_v)
            bar_h = max(2, int((h - 24) * pct))
            y_top = h - 20 - bar_h

            is_today = d == today
            met_goal = v >= self._profile.daily_goal

            # Bar color
            if is_today:
                color = C.PRIMARY
            elif met_goal:
                color = C.SUCCESS
            elif v > 0:
                color = C.WARNING
            else:
                color = C.BORDER

            # Bar
            cv.create_rectangle(x, y_top, x + bar_w, h - 20,
                                 fill=color, outline="")

            # Goal line indicator
            goal_y = h - 20 - int((h - 24) * min(1.0, goal / max_v))
            if i == 0:
                cv.create_line(x, goal_y, x + bar_w * 7 + 20, goal_y,
                               fill=C.TEXT_LIGHT, dash=(3, 3))

            # Day label
            day_lbl = d.strftime("%a")[0]  # M, T, W...
            cv.create_text(x + bar_w // 2, h - 10, text=day_lbl,
                           fill=C.TEXT_MUTED if not is_today else C.PRIMARY,
                           font=(F.FAMILY, 8))

            # Value on bar if > 0
            if v > 0:
                cv.create_text(x + bar_w // 2, y_top - 6, text=str(v),
                               fill=C.TEXT_MUTED, font=(F.FAMILY, 7))

    # ── Right panel ───────────────────────────────────────────────────────────

    def _build_right_panel(self, parent):
        self._streak_panel = StreakPanel(parent, self._profile, on_quiz=None)
        self._streak_panel.pack(fill="x", pady=(0, S.XS))
        self._heatmap = HeatmapCalendar(parent, self._profile)
        self._heatmap.pack(fill="x")

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        p   = self._profile
        lvl, cur, needed = compute_level(p.xp)
        p.level = lvl  # keep in sync

        # Nickname with rank
        rank_lv = get_level_rank(lvl)
        self._lbl_user.config(
            text=self._t("nickname", p.username, rank_lv["icon"]) +
                 f"  •  {self._t('level', lvl)}")

        # XP bar
        self._xp_bar.set(cur, needed,
                         label=self._t("xp_label", cur, needed))

        # Difficulty
        try:
            wd = WeaknessDetector(p)
            self._lbl_diff.config(text=wd.difficulty_label())
        except Exception:
            pass

        self._lbl_streak.config(text=self._t("streak", p.streak))
        self._lbl_daily.config(text=self._t("daily", p.daily_xp, p.daily_goal))

        # Level rank
        self._lbl_rank_lv.config(
            text=self._t("rank_lv", rank_lv["icon"], rank_lv["name"]),
            fg=rank_lv["color"])
        nxt = get_next_level_rank(lvl)
        if nxt:
            self._lbl_next_rank_lv.config(
                text=self._t("next_rank", nxt["min_level"]))
        else:
            self._lbl_next_rank_lv.config(text="MAX RANK 🐉")

        # Arena rank (unchanged)
        arena_rank = get_rank(p.arena_score)
        nxt_arena  = get_next_rank(p.arena_score)
        self._lbl_arena_rank.config(
            text=f"{self._t('rank_arena')} {arena_rank['icon']} {arena_rank['name']}",
            fg=arena_rank["color"])
        if nxt_arena:
            self._lbl_arena_pts.config(
                text=f"Arena: {p.arena_score} / {nxt_arena['min_score']}")
        else:
            self._lbl_arena_pts.config(text=f"Arena: {p.arena_score} ✓")

        # Level XP bar (progress within current rank)
        curr_rank_lv = get_level_rank(lvl)
        nxt_rank_lv  = get_next_level_rank(lvl)
        if nxt_rank_lv:
            rank_span = nxt_rank_lv["min_level"] - curr_rank_lv["min_level"]
            rank_prog = lvl - curr_rank_lv["min_level"]
            self._level_xp_bar.set(rank_prog, rank_span,
                                   label=f"Lv {lvl} → Lv {nxt_rank_lv['min_level']}")
        else:
            self._level_xp_bar.set(1, 1, label=f"Level {lvl} MAX")

        # Trophies display
        self._refresh_trophies()

        # Mistakes button
        m = p.get_mistakes()
        total = len(m["words"]) + len(m["sentences"])
        if hasattr(self, "_btn_mistakes"):
            if total > 0:
                self._btn_mistakes.config(
                    text=self._t("mistakes", total), state="normal", bg=C.DANGER)
            else:
                self._btn_mistakes.config(
                    text=self._t("no_mistakes"), state="disabled", bg="#AAAAAA")

        # Audio
        self._update_audio_btn()

        # Check level rank-up
        self._check_rank_up(lvl, rank_lv)

        # Right panel
        self._refresh_right_panel()

        # Redraw chart
        self.after(100, self._draw_xp_chart)

    def _refresh_trophies(self):
        """Prikaži trofeje korisnika (level milestone + rank trophies)."""
        for c in self._trophy_frame.winfo_children():
            c.destroy()

        # Collect earned trophies
        earned = []
        p = self._profile
        for lvl_req, trophy in LEVEL_TROPHIES.items():
            lvl, _, _ = compute_level(p.xp)
            if lvl >= lvl_req:
                earned.append(trophy)
        for rank in LEVEL_RANKS:
            tr = rank.get("trophy")
            if tr and tr["id"] in p.achievements:
                earned.append(tr)

        if not earned:
            tk.Label(self._trophy_frame, text=self._t("no_trophies"),
                     bg=C.BG_CARD, fg=C.TEXT_LIGHT, font=F.TINY).pack(anchor="w")
            return

        tk.Label(self._trophy_frame, text=self._t("trophies") + ":",
                 bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.TINY).pack(side="left")
        for t in earned[-5:]:  # show last 5
            lbl = tk.Label(self._trophy_frame, text=t["icon"],
                           bg=C.BG_CARD, font=(F.FAMILY, 14), cursor="hand2")
            lbl.pack(side="left", padx=2)
            # Tooltip on hover
            def _enter(e, name=t["name"]):
                from ..theme import HoverTooltip
                HoverTooltip.show(self.winfo_toplevel(), name, e.x_root, e.y_root)
            def _leave(e):
                from ..theme import HoverTooltip
                HoverTooltip.hide()
            lbl.bind("<Enter>", _enter)
            lbl.bind("<Leave>", _leave)

    def _check_rank_up(self, new_level: int, new_rank: dict):
        """Prikaži rank-up animaciju ako je rang promenjen."""
        if new_rank["name"] != self._last_rank:
            old_rank = self._last_rank
            self._last_rank = new_rank["name"]
            # Award rank trophy
            trophy = new_rank.get("trophy")
            if trophy and trophy["id"] not in self._profile.achievements:
                self._profile.achievements.append(trophy["id"])
                self._profile.xp += 60
                self._db.save_user(self._profile)
                self.after(300, lambda: self._show_rank_up_overlay(new_rank, trophy=trophy))
            else:
                self.after(300, lambda: self._show_rank_up_overlay(new_rank))

        # Check level milestone trophies
        if new_level != self._last_level:
            old_level = self._last_level
            self._last_level = new_level
            for lvl_req, trophy in LEVEL_TROPHIES.items():
                if old_level < lvl_req <= new_level:
                    if trophy["id"] not in self._profile.achievements:
                        self._profile.achievements.append(trophy["id"])
                        self._profile.xp += trophy["xp"]
                        self._db.save_user(self._profile)
                        self.after(500, lambda t=trophy: self._show_trophy_overlay(t))

    def _show_rank_up_overlay(self, rank: dict, trophy=None):
        """Full-screen rank-up animacija — pauza dok traje."""
        root = self.winfo_toplevel()
        overlay = tk.Frame(root, bg="#000000")
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()

        cv = tk.Canvas(overlay, bg="#000000", highlightthickness=0)
        cv.place(relx=0, rely=0, relwidth=1, relheight=1)
        cv.create_rectangle(0, 0, 9999, 9999, fill="#000000", stipple="gray50")

        tk.Label(overlay, text="🎖️ NEW RANK!", bg="#000000",
                 fg="#FFFFFF", font=(F.FAMILY, 20, "bold")).place(relx=0.5, rely=0.33, anchor="center")
        tk.Label(overlay, text=f"{rank['icon']} {rank['name']}",
                 bg="#000000", fg=rank["color"],
                 font=(F.FAMILY, 48, "bold")).place(relx=0.5, rely=0.45, anchor="center")
        if trophy:
            tk.Label(overlay, text=f"🏆 +{trophy['icon']} {trophy['name']}",
                     bg="#000000", fg=C.GOLD,
                     font=(F.FAMILY, 18, "bold")).place(relx=0.5, rely=0.60, anchor="center")

        tk.Label(overlay, text="Tap to continue", bg="#000000",
                 fg="#888888", font=F.SMALL).place(relx=0.5, rely=0.75, anchor="center")

        def _close(e=None):
            try: overlay.destroy()
            except tk.TclError: pass

        overlay.bind("<Button-1>", _close)
        overlay.after(3500, _close)

        # Pulse animation on rank label
        sizes = [48, 56, 48, 52, 48]
        rank_lbl = overlay.winfo_children()[2]  # the big rank label
        def _pulse(i=0):
            if i >= len(sizes): return
            try:
                rank_lbl.config(font=(F.FAMILY, sizes[i], "bold"))
                overlay.after(120, lambda: _pulse(i+1))
            except tk.TclError: pass
        _pulse()

    def _show_trophy_overlay(self, trophy: dict):
        """Full-screen trophy animacija."""
        root = self.winfo_toplevel()
        overlay = tk.Frame(root, bg="#000000")
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()

        cv = tk.Canvas(overlay, bg="#000000", highlightthickness=0)
        cv.place(relx=0, rely=0, relwidth=1, relheight=1)
        cv.create_rectangle(0, 0, 9999, 9999, fill="#000000", stipple="gray50")

        tk.Label(overlay, text="🏆 TROPHY UNLOCKED!", bg="#000000",
                 fg=C.GOLD, font=(F.FAMILY, 22, "bold")).place(relx=0.5, rely=0.35, anchor="center")
        tk.Label(overlay, text=trophy["icon"], bg="#000000",
                 font=(F.FAMILY, 64)).place(relx=0.5, rely=0.48, anchor="center")
        tk.Label(overlay, text=trophy["name"], bg="#000000",
                 fg="#FFFFFF", font=(F.FAMILY, 20, "bold")).place(relx=0.5, rely=0.62, anchor="center")
        tk.Label(overlay, text="Tap to continue", bg="#000000",
                 fg="#888888", font=F.SMALL).place(relx=0.5, rely=0.75, anchor="center")

        def _close(e=None):
            try: overlay.destroy()
            except tk.TclError: pass
        overlay.bind("<Button-1>", _close)
        overlay.after(3000, _close)

    # ── Daily bonus ───────────────────────────────────────────────────────────

    def _check_daily_bonus(self):
        today = date.today().isoformat()
        if self._profile.daily_bonus_claimed == today:
            self._bonus_btn.config(text=self._t("already_claimed"),
                                   state="disabled", bg="#AAAAAA", fg=C.TEXT_WHITE)
        else:
            self._bonus_btn.config(text=self._t("daily_bonus_btn"),
                                   state="normal", bg=C.GOLD, fg=C.TEXT)

    def _claim_bonus(self):
        today = date.today().isoformat()
        if self._profile.daily_bonus_claimed == today: return
        self._profile.daily_bonus_claimed = today
        self._profile.xp       += 50
        self._profile.daily_xp += 50
        self._profile.daily_xp_history[today] = self._profile.daily_xp
        self._db.save_user(self._profile)
        self._bonus_btn.config(text=self._t("already_claimed"),
                               state="disabled", bg="#AAAAAA", fg=C.TEXT_WHITE)
        self.refresh()

    # ── Audio / fullscreen ────────────────────────────────────────────────────

    def _update_audio_btn(self):
        on = is_audio_enabled()
        self._audio_btn.config(
            text=self._t("audio_on") if on else self._t("audio_off"),
            fg=C.PRIMARY if on else C.TEXT_MUTED)

    def _toggle_audio(self):
        new_state = not is_audio_enabled()
        set_audio_enabled(new_state)
        self._profile.audio_enabled = new_state
        self._db.save_user(self._profile)
        self._update_audio_btn()

    def _toggle_fs(self):
        root = self.winfo_toplevel()
        toggle_fullscreen(root)

    def _refresh_right_panel(self):
        if hasattr(self, "_streak_panel"):
            try: self._streak_panel.refresh()
            except Exception: pass
        if hasattr(self, "_heatmap"):
            try: self._heatmap.refresh()
            except Exception: pass

    # ── Avatar ────────────────────────────────────────────────────────────────

    def _draw_header_avatar(self):
        size = 34
        c = self._hdr_avatar
        c.delete("all")
        try:
            c.config(width=size, height=size)
        except Exception:
            pass
        c.create_oval(0, 0, size, size, fill=C.PRIMARY, outline="")
        path = self._profile.avatar_path
        if path:
            try:
                from PIL import Image, ImageTk, ImageDraw
                img  = Image.open(path).resize((size-4, size-4), Image.LANCZOS)
                mask = Image.new("L", (size-4, size-4), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size-4, size-4), fill=255)
                result = Image.new("RGBA", (size-4, size-4))
                result.paste(img, mask=mask)
                self._hdr_photo = ImageTk.PhotoImage(result)
                c.create_image(2, 2, anchor="nw", image=self._hdr_photo)
                return
            except Exception:
                pass
        initial = self._profile.username[0].upper() if self._profile.username else "?"
        c.create_oval(2, 2, size-2, size-2, fill=C.PRIMARY, outline=C.PRIMARY_DARK)
        c.create_text(size//2, size//2, text=initial, fill="white",
                      font=(F.FAMILY, 12, "bold"))

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        root = self.winfo_toplevel()
        _SettingsWindow(root, self._profile, self._db,
                        on_close=self._on_settings_close,
                        on_theme_change=lambda: self.event_generate("<<ThemeChanged>>"),
                        on_logout=self._cbs["logout"],
                        lang=self._lang)

    def _on_settings_close(self):
        """Called when settings window closes — refresh dashboard."""
        self.refresh()
        self._draw_header_avatar()


# ── Settings Window ────────────────────────────────────────────────────────────

class _SettingsWindow:
    """
    Moderni Settings ekran kao Toplevel modal sa:
    fade-in efektom, card layout, zaobljeni uglovi simulacijom, scroll.
    """
    def __init__(self, root: tk.Tk, profile: UserProfile, db: Database,
                 on_close=None, on_theme_change=None, on_logout=None, lang="en"):
        self._root     = root
        self._profile  = profile
        self._db       = db
        self._on_close = on_close
        self._on_theme = on_theme_change
        self._on_logout= on_logout
        self._lang     = lang

        self._win = tk.Toplevel(root)
        self._win.title("")
        self._win.configure(bg=C.BG_CARD)
        self._win.resizable(False, False)

        root.update_idletasks()
        rw, rh = root.winfo_width(), root.winfo_height()
        rx, ry = root.winfo_rootx(), root.winfo_rooty()
        w, h   = 400, 620
        x = rx + (rw - w) // 2
        y = ry + (rh - h) // 2
        self._win.geometry(f"{w}x{h}+{x}+{y}")
        self._win.transient(root)
        self._win.grab_set()
        self._win.focus_set()
        self._win.protocol("WM_DELETE_WINDOW", self._close)

        # Fade-in: start transparent, animate to full
        try:
            self._win.attributes("-alpha", 0.0)
        except Exception:
            pass

        self._build()
        self._fade_in()

    def _fade_in(self, alpha=0.0):
        try:
            if alpha >= 1.0:
                self._win.attributes("-alpha", 1.0); return
            self._win.attributes("-alpha", alpha)
            self._win.after(20, lambda: self._fade_in(alpha + 0.12))
        except tk.TclError:
            pass

    def _close(self):
        try:
            self._win.grab_release()
            self._win.destroy()
        except tk.TclError:
            pass
        if self._on_close: self._on_close()

    def _build(self):
        win = self._win
        p   = self._profile
        lang = self._lang
        T = _T[lang]

        # Scrollable canvas
        canvas = tk.Canvas(win, bg=C.BG_CARD, highlightthickness=0)
        sb     = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=sb.set)

        content = tk.Frame(canvas, bg=C.BG_CARD)
        cid = canvas.create_window((0, 0), window=content, anchor="nw")

        def _resize(e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(cid, width=canvas.winfo_width())
        content.bind("<Configure>", _resize)
        canvas.bind("<Configure>", _resize)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        pad = S.LG

        def section(txt):
            f = tk.Frame(content, bg=C.BG_CARD)
            f.pack(fill="x", padx=pad, pady=(S.MD, 2))
            tk.Frame(f, bg=C.BORDER, height=1).pack(fill="x", pady=(0, 4))
            tk.Label(f, text=txt.upper(), bg=C.BG_CARD,
                     fg=C.TEXT_LIGHT, font=F.TINY).pack(anchor="w")

        def row_frame():
            f = tk.Frame(content, bg=C.BG_CARD)
            f.pack(fill="x", padx=pad, pady=2)
            return f

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(content, bg=C.BG_CARD)
        hdr.pack(fill="x", padx=pad, pady=(S.LG, 0))
        tk.Label(hdr, text="⚙️  " + T["settings_title"],
                 bg=C.BG_CARD, fg=C.TEXT, font=F.H2).pack(side="left")
        tk.Button(hdr, text="✕", bg=C.BG_CARD, fg=C.TEXT_MUTED,
                  font=F.BODY, relief="flat", bd=0, cursor="hand2",
                  activebackground=C.BG_HOVER,
                  command=self._close).pack(side="right")

        # ── Avatar + name ─────────────────────────────────────────────────────
        av_size = 72
        av_row = tk.Frame(content, bg=C.BG_CARD)
        av_row.pack(pady=(S.SM, S.XS))
        av_cv = tk.Canvas(av_row, width=av_size, height=av_size,
                          bg=C.BG_CARD, highlightthickness=0)
        av_cv.pack()

        def _draw_av(path=""):
            av_cv.delete("all")
            if path:
                try:
                    from PIL import Image, ImageTk, ImageDraw
                    img  = Image.open(path).resize((av_size, av_size), Image.LANCZOS)
                    mask = Image.new("L", (av_size, av_size), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, av_size, av_size), fill=255)
                    result = Image.new("RGBA", (av_size, av_size))
                    result.paste(img, mask=mask)
                    self._av_ph = ImageTk.PhotoImage(result)
                    av_cv.create_image(0, 0, anchor="nw", image=self._av_ph)
                    return
                except Exception: pass
            init = p.username[0].upper() if p.username else "?"
            av_cv.create_oval(2, 2, av_size-2, av_size-2, fill=C.PRIMARY, outline="")
            av_cv.create_text(av_size//2, av_size//2, text=init,
                              fill="white", font=(F.FAMILY, 24, "bold"))

        _draw_av(p.avatar_path)

        def _pick_avatar():
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="Choose profile picture",
                filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All", "*.*")])
            if path:
                p.avatar_path = path
                self._db.save_user(p)
                _draw_av(path)

        tk.Button(content, text="📷  Change photo",
                  bg=C.BG_CARD, fg=C.PRIMARY, font=F.SMALL,
                  relief="flat", bd=0, cursor="hand2",
                  command=_pick_avatar).pack()
        tk.Label(content, text=p.username,
                 bg=C.BG_CARD, fg=C.TEXT, font=F.LABEL_B).pack()
        tk.Label(content, text=p.email,
                 bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.TINY).pack(pady=(0, S.XS))

        # ── DISPLAY ──────────────────────────────────────────────────────────
        section("Display")

        # Fullscreen toggle
        r = row_frame()
        tk.Label(r, text="⛶  Fullscreen (F11)",
                 bg=C.BG_CARD, fg=C.TEXT, font=F.BODY).pack(side="left")
        fs_on = [self._root.attributes("-fullscreen")]
        fs_btn = tk.Button(r, text="ON" if fs_on[0] else "OFF",
                           bg=C.SUCCESS if fs_on[0] else C.BG_INPUT,
                           fg=C.TEXT_WHITE if fs_on[0] else C.TEXT_MUTED,
                           font=F.SMALL, relief="flat", bd=0, cursor="hand2",
                           padx=S.MD, pady=S.XS)
        fs_btn.pack(side="right")
        def _toggle_fs():
            toggle_fullscreen(self._root)
            new = self._root.attributes("-fullscreen")
            fs_on[0] = new
            fs_btn.config(text="ON" if new else "OFF",
                          bg=C.SUCCESS if new else C.BG_INPUT,
                          fg=C.TEXT_WHITE if new else C.TEXT_MUTED)
        fs_btn.config(command=_toggle_fs)

        # Theme
        section(T["theme_label"])
        theme_f = tk.Frame(content, bg=C.BG_CARD)
        theme_f.pack(fill="x", padx=pad, pady=2)
        theme_btns = {}
        for val, label in [("light", T["theme_light"]),
                            ("dark",  T["theme_dark"]),
                            ("system",T["theme_system"])]:
            active = val == p.theme
            b = tk.Button(theme_f, text=label,
                          bg=C.PRIMARY if active else C.BG_HOVER,
                          fg=C.TEXT_WHITE if active else C.TEXT,
                          font=F.SMALL, relief="flat", bd=0, cursor="hand2",
                          padx=S.SM, pady=S.XS)
            b.pack(side="left", padx=2, expand=True, fill="x")
            theme_btns[val] = b

            def _make_theme_cmd(v):
                def _cmd():
                    for vv, bb in theme_btns.items():
                        act = vv == v
                        bb.config(bg=C.PRIMARY if act else C.BG_HOVER,
                                  fg=C.TEXT_WHITE if act else C.TEXT)
                    C.set_theme(v)
                    from ..theme import _apply_ttk
                    _apply_ttk(self._root)
                    p.theme = v
                    self._db.save_user(p)
                    self._close()
                    if self._on_theme: self._on_theme()
                return _cmd
            b.config(command=_make_theme_cmd(val))

        # ── SOUND ────────────────────────────────────────────────────────────
        section("Sound")
        r = row_frame()
        tk.Label(r, text="🔊  Audio", bg=C.BG_CARD, fg=C.TEXT, font=F.BODY).pack(side="left")
        aud_on = [is_audio_enabled()]
        ab = tk.Button(r,
                       text="ON" if aud_on[0] else "OFF",
                       bg=C.SUCCESS if aud_on[0] else C.BG_INPUT,
                       fg=C.TEXT_WHITE if aud_on[0] else C.TEXT_MUTED,
                       font=F.SMALL, relief="flat", bd=0, cursor="hand2",
                       padx=S.MD, pady=S.XS)
        ab.pack(side="right")
        def _toggle_snd():
            new = not is_audio_enabled(); set_audio_enabled(new); aud_on[0] = new
            p.audio_enabled = new; self._db.save_user(p)
            ab.config(text="ON" if new else "OFF",
                      bg=C.SUCCESS if new else C.BG_INPUT,
                      fg=C.TEXT_WHITE if new else C.TEXT_MUTED)
        ab.config(command=_toggle_snd)

        # ── QUIZ MODES ────────────────────────────────────────────────────────
        section("Quiz Modes")
        quiz_modes = [
            ("type",    "✍  Typing"),
            ("draw",    "✏️  Drawing"),
            ("listen",  "🔊  Listening"),
            ("meaning", "❓  Meaning"),
        ]
        mode_vars = {}
        for mode_id, label in quiz_modes:
            r = row_frame()
            tk.Label(r, text=label, bg=C.BG_CARD,
                     fg=C.TEXT, font=F.BODY).pack(side="left")
            # Active if weight > 0
            weights = p.preferred_quiz_modes
            active  = weights.get(mode_id, 2) > 0
            mode_vars[mode_id] = active

            btn = tk.Button(r,
                            text="ON" if active else "OFF",
                            bg=C.SUCCESS if active else C.BG_INPUT,
                            fg=C.TEXT_WHITE if active else C.TEXT_MUTED,
                            font=F.SMALL, relief="flat", bd=0, cursor="hand2",
                            padx=S.MD, pady=S.XS)
            btn.pack(side="right")

            def _make_mode_cmd(mid, b):
                def _cmd():
                    w = p.preferred_quiz_modes
                    w[mid] = 0 if w.get(mid, 2) > 0 else 2
                    on = w[mid] > 0
                    b.config(text="ON" if on else "OFF",
                             bg=C.SUCCESS if on else C.BG_INPUT,
                             fg=C.TEXT_WHITE if on else C.TEXT_MUTED)
                    self._db.save_user(p)
                return _cmd
            btn.config(command=_make_mode_cmd(mode_id, btn))

        # ── NICKNAME / RANK VISIBILITY ────────────────────────────────────────
        section("Profile Visibility")
        vis_opts = [
            ("show_rank",     "Show Rank"),
            ("show_nickname", "Show Nickname"),
        ]
        for attr, label in vis_opts:
            r = row_frame()
            tk.Label(r, text=label, bg=C.BG_CARD,
                     fg=C.TEXT, font=F.BODY).pack(side="left")
            # Use profile attr if exists, else default True
            current = getattr(p, attr, True)
            btn = tk.Button(r,
                            text="ON" if current else "OFF",
                            bg=C.SUCCESS if current else C.BG_INPUT,
                            fg=C.TEXT_WHITE if current else C.TEXT_MUTED,
                            font=F.SMALL, relief="flat", bd=0, cursor="hand2",
                            padx=S.MD, pady=S.XS)
            btn.pack(side="right")

            def _make_vis_cmd(attr_name, b):
                def _cmd():
                    new_val = not getattr(p, attr_name, True)
                    setattr(p, attr_name, new_val)
                    b.config(text="ON" if new_val else "OFF",
                             bg=C.SUCCESS if new_val else C.BG_INPUT,
                             fg=C.TEXT_WHITE if new_val else C.TEXT_MUTED)
                    self._db.save_user(p)
                return _cmd
            btn.config(command=_make_vis_cmd(attr, btn))

        # ── ACCOUNT ──────────────────────────────────────────────────────────
        section("Account")

        def _labeled(lbl_txt, default="", show=""):
            r = tk.Frame(content, bg=C.BG_CARD)
            r.pack(fill="x", padx=pad, pady=2)
            tk.Label(r, text=lbl_txt, bg=C.BG_CARD,
                     fg=C.TEXT_MUTED, font=F.SMALL, width=14, anchor="w").pack(side="left")
            e = tk.Entry(r, bg=C.BG_INPUT, fg=C.TEXT, font=F.BODY,
                         relief="flat", highlightbackground=C.BORDER,
                         highlightthickness=1, insertbackground=C.TEXT, show=show)
            e.insert(0, default)
            e.pack(side="left", fill="x", expand=True)
            return e

        e_email = _labeled("Email:", p.email)
        e_pw    = _labeled("New password:", show="*")
        e_pw2   = _labeled("Confirm:", show="*")

        save_lbl = tk.Label(content, text="", bg=C.BG_CARD,
                            fg=C.SUCCESS, font=F.SMALL)
        save_lbl.pack()

        def _save_account():
            new_email = e_email.get().strip()
            new_pw    = e_pw.get().strip()
            new_pw2   = e_pw2.get().strip()
            if new_email and new_email != p.email:
                p.email = new_email
            if new_pw:
                if new_pw != new_pw2:
                    save_lbl.config(text="❌ Passwords don't match", fg=C.DANGER); return
                if len(new_pw) < 4:
                    save_lbl.config(text="❌ Too short", fg=C.DANGER); return
                p.password_hash = UserProfile.hash_password(new_pw)
            self._db.save_user(p)
            save_lbl.config(text="✅ Saved!", fg=C.SUCCESS)
            e_pw.delete(0, "end"); e_pw2.delete(0, "end")

        tk.Button(content, text="💾  Save changes",
                  bg=C.PRIMARY, fg=C.TEXT_WHITE, font=F.BODY_B,
                  relief="flat", bd=0, cursor="hand2",
                  padx=S.LG, pady=S.XS,
                  command=_save_account).pack(pady=S.XS)

        # ── SIGN OUT ─────────────────────────────────────────────────────────
        section("Session")
        for lbl_txt, clr, fn in [
            ("🔄 Switch Account", C.PRIMARY,
             lambda: (self._close(), self._on_logout and self._on_logout())),
            ("⎋ Sign Out", C.DANGER,
             lambda: (self._close(), self._on_logout and self._on_logout())),
        ]:
            btn = tk.Button(content, text=lbl_txt,
                            bg=C.BG_CARD, fg=clr, font=F.BODY,
                            relief="flat", bd=0, cursor="hand2",
                            pady=S.SM, anchor="w",
                            activebackground=C.BG_HOVER,
                            command=fn)
            btn.pack(fill="x", padx=pad)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=C.BG_HOVER))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=C.BG_CARD))

        # ── UPDATES ──────────────────────────────────────────────────────────
        section("Updates")

        # Version status bar
        ver_bar = tk.Frame(content, bg="#0d1526",
                           highlightbackground="#1e3a5f", highlightthickness=1)
        ver_bar.pack(fill="x", padx=pad, pady=(2, 6))
        ver_inner = tk.Frame(ver_bar, bg="#0d1526")
        ver_inner.pack(fill="x", padx=12, pady=8)

        from ...core.updater import CURRENT_VERSION
        tk.Label(ver_inner,
                 text=f"Current version:  v{CURRENT_VERSION}  •  Stable",
                 bg="#0d1526", fg="#94a3b8",
                 font=(F.FAMILY, 9)).pack(side="left")

        learn_btn = tk.Button(ver_inner, text="What's new →",
                              bg="#0d1526", fg="#3b82f6",
                              font=(F.FAMILY, 9, "underline"),
                              relief="flat", bd=0, cursor="hand2",
                              activebackground="#0d1526",
                              command=lambda: _show_whats_new(self._root))
        learn_btn.pack(side="right")

        # Check for updates button row
        upd_row = tk.Frame(content, bg=C.BG_CARD)
        upd_row.pack(fill="x", padx=pad, pady=(0, 4))

        upd_status = tk.Label(upd_row, text="",
                              bg=C.BG_CARD, fg=C.TEXT_MUTED,
                              font=(F.FAMILY, 9))
        upd_status.pack(side="right", padx=(8, 0))

        def _do_check():
            upd_btn.config(state="disabled", text="Checking...")
            upd_status.config(text="", fg=C.TEXT_MUTED)
            import threading as _th

            def _check():
                try:
                    from ...core.updater import check_for_update, download_and_apply
                    info = check_for_update()
                except Exception:
                    info = None

                def _ui():
                    upd_btn.config(state="normal", text="🔄  Check for updates")
                    if info:
                        upd_status.config(text=f"v{info['version']} available!", fg="#22c55e")
                        _ask_update(self._root, info)
                    else:
                        upd_status.config(text="✓ You are on the latest version", fg="#22c55e")

                try: upd_row.after(0, _ui)
                except Exception: pass

            _th.Thread(target=_check, daemon=True).start()

        upd_btn = tk.Button(upd_row, text="🔄  Check for updates",
                            bg="#1e3a5f", fg="#93c5fd",
                            font=(F.FAMILY, 10, "bold"),
                            relief="flat", bd=0, cursor="hand2",
                            padx=16, pady=7,
                            activebackground="#2a4a7f",
                            command=_do_check)
        upd_btn.pack(side="left")

        # Bottom padding
        tk.Frame(content, bg=C.BG_CARD, height=S.XL).pack()


# ─── Update helpers ──────────────────────────────────────────────────────────

def _ask_update(root, info: dict):
    """Dialog: new version available — install now?"""
    import tkinter as tk
    ver   = info.get("version", "?")
    notes = info.get("notes", "Bug fixes and improvements")

    win = tk.Toplevel(root)
    win.title("Update Available")
    win.configure(bg="#14172a")
    win.resizable(False, False)
    win.attributes("-topmost", True)
    W, H = 400, 200
    sx = root.winfo_screenwidth(); sy = root.winfo_screenheight()
    win.geometry(f"{W}x{H}+{(sx-W)//2}+{(sy-H)//2}")

    hdr = tk.Frame(win, bg="#1877f2", pady=10)
    hdr.pack(fill="x")
    tk.Label(hdr, text=f"🚀  Version v{ver} is available!",
             bg="#1877f2", fg="#fff",
             font=("Segoe UI", 12, "bold")).pack()

    body = tk.Frame(win, bg="#14172a", padx=20, pady=14)
    body.pack(fill="both", expand=True)
    tk.Label(body, text=notes, bg="#14172a", fg="#94a3b8",
             font=("Segoe UI", 10), wraplength=360,
             justify="left").pack(anchor="w", pady=(0, 14))

    # Progress bar
    prog_lbl = tk.Label(body, text="", bg="#14172a", fg="#94a3b8",
                        font=("Segoe UI", 9))
    prog_lbl.pack(anchor="w")
    prog_bg  = tk.Frame(body, bg="#1e2236", height=6)
    prog_bg.pack(fill="x", pady=(2, 0))
    prog_bar = tk.Frame(prog_bg, bg="#1877f2", height=6, width=0)
    prog_bar.place(x=0, y=0, height=6)

    btn_row = tk.Frame(body, bg="#14172a")
    btn_row.pack(fill="x", pady=(10, 0))

    def _start():
        btn_yes.config(state="disabled", text="Downloading...")
        btn_no.config(state="disabled")
        prog_lbl.config(text="Downloading...")
        prog_bg.pack(fill="x", pady=(2, 0))

        def _prog(pct):
            try:
                prog_bar.config(width=int(360 * pct / 100))
                prog_lbl.config(text=f"Downloading... {pct}%")
            except Exception: pass

        def _done():
            try:
                prog_bar.config(bg="#22c55e", width=360)
                prog_lbl.config(text="✅ Restarting...")
            except Exception: pass

        def _err(msg):
            try:
                prog_lbl.config(text=f"❌ {msg}", fg="#ef4444")
                btn_no.config(state="normal", text="Close")
            except Exception: pass

        try:
            from ...core.updater import download_and_apply
            download_and_apply(
                info["download_url"],
                on_progress=lambda p: win.after(0, lambda: _prog(p)),
                on_done=lambda: win.after(0, _done),
                on_error=lambda m: win.after(0, lambda: _err(m)),
            )
        except Exception as e:
            _err(str(e))

    btn_yes = tk.Button(btn_row, text="⬇  Install Now",
                        bg="#1877f2", fg="#fff",
                        font=("Segoe UI", 10, "bold"),
                        relief="flat", cursor="hand2",
                        padx=16, pady=6, command=_start)
    btn_yes.pack(side="left")

    btn_no = tk.Button(btn_row, text="Later",
                       bg="#14172a", fg="#64748b",
                       font=("Segoe UI", 10),
                       relief="flat", cursor="hand2",
                       padx=12, pady=6,
                       command=win.destroy)
    btn_no.pack(side="left", padx=(8, 0))

    tk.Button(btn_row, text="What's new →",
              bg="#14172a", fg="#3b82f6",
              font=("Segoe UI", 9, "underline"),
              relief="flat", cursor="hand2", bd=0,
              command=lambda: _show_whats_new(root)).pack(side="right")


def _show_whats_new(root):
    """What's New modal — reads changelog from GitHub or local."""
    import tkinter as tk, threading as _th

    win = tk.Toplevel(root)
    win.title("What's New")
    win.configure(bg="#0f1729")
    win.resizable(True, True)
    W, H = 500, 520
    sx = root.winfo_screenwidth(); sy = root.winfo_screenheight()
    win.geometry(f"{W}x{H}+{(sx-W)//2}+{(sy-H)//2}")
    win.attributes("-topmost", True)

    # Header
    hdr = tk.Frame(win, bg="#1877f2", pady=14)
    hdr.pack(fill="x")
    tk.Label(hdr, text="🆕  What's New",
             bg="#1877f2", fg="#fff",
             font=("Segoe UI", 15, "bold")).pack()

    # Scrollable content
    from ...core.updater import CURRENT_VERSION
    tk.Label(win, text=f"Version v{CURRENT_VERSION}",
             bg="#0f1729", fg="#64748b",
             font=("Segoe UI", 10)).pack(pady=(10, 2))

    # Canvas + scrollbar for content
    cv_frame = tk.Frame(win, bg="#0f1729")
    cv_frame.pack(fill="both", expand=True, padx=2)
    cv = tk.Canvas(cv_frame, bg="#0f1729", highlightthickness=0)
    sb = tk.Scrollbar(cv_frame, orient="vertical", command=cv.yview)
    sb.pack(side="right", fill="y")
    cv.pack(fill="both", expand=True)
    cv.configure(yscrollcommand=sb.set)
    inner = tk.Frame(cv, bg="#0f1729")
    wid = cv.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: cv.configure(
        scrollregion=cv.bbox("all")))
    cv.bind("<Configure>", lambda e: cv.itemconfig(wid, width=e.width))
    cv.bind("<MouseWheel>", lambda e: cv.yview_scroll(-1*(e.delta//120), "units"))

    loading_lbl = tk.Label(inner, text="Loading changelog...",
                           bg="#0f1729", fg="#475569",
                           font=("Segoe UI", 11, "italic"))
    loading_lbl.pack(pady=40)

    def _load_changelog():
        """Try to fetch from GitHub, fallback to local."""
        entries = []
        try:
            import urllib.request, json as _json
            from ...core.updater import RAW_BASE, updates_enabled
            if not updates_enabled():
                from importlib.resources import files
                data = _json.loads(files("hanziflow").joinpath("changelog.json").read_text(encoding="utf-8"))
            else:
                url = f"{RAW_BASE}/hanziflow/changelog.json"
                with urllib.request.urlopen(url, timeout=5) as r:
                    data = _json.loads(r.read().decode())
            entries = data.get("entries", [])
        except Exception:
            # Fallback — show local version info
            entries = [{
                "version": CURRENT_VERSION,
                "date": "Latest",
                "sections": {
                    "✨ New Features": [
                        "Friends panel with drag panel memory",
                        "Sentence builder with drag & drop reorder",
                        "OpenRouter AI integration (Gemini 3 Flash)",
                        "Auto-updater system",
                        "Improved writing checker with synonym support",
                    ],
                    "🐛 Bug Fixes": [
                        "Fixed tooltip staying on screen after navigation",
                        "Fixed Friends button not appearing after login",
                        "Fixed audio time.sleep error",
                        "Fixed Mistakes view with empty scrambled sentences",
                    ],
                    "⚡ Improvements": [
                        "Dark scrollbar in Friends panel",
                        "Pinyin accepted without tone marks in Mistakes",
                        "Notification panel remembers position after drag",
                    ],
                }
            }]

        def _render():
            try: loading_lbl.destroy()
            except Exception: pass

            for entry in entries:
                ver_lbl = tk.Frame(inner, bg="#1e2236",
                                   highlightbackground="#2a3a5a",
                                   highlightthickness=1)
                ver_lbl.pack(fill="x", padx=14, pady=(10, 2))
                ver_row = tk.Frame(ver_lbl, bg="#1e2236")
                ver_row.pack(fill="x", padx=12, pady=8)
                tk.Label(ver_row,
                         text=f"v{entry.get('version', '?')}",
                         bg="#1e2236", fg="#3b82f6",
                         font=("Segoe UI", 13, "bold")).pack(side="left")
                tk.Label(ver_row,
                         text=entry.get("date", ""),
                         bg="#1e2236", fg="#475569",
                         font=("Segoe UI", 9)).pack(side="right")

                sections = entry.get("sections", {})
                for section_title, items in sections.items():
                    tk.Label(inner,
                             text=section_title,
                             bg="#0f1729", fg="#e2e8f0",
                             font=("Segoe UI", 10, "bold")).pack(
                             anchor="w", padx=20, pady=(8, 2))
                    for item in items:
                        row = tk.Frame(inner, bg="#0f1729")
                        row.pack(fill="x", padx=20, pady=1)
                        tk.Label(row, text="•", bg="#0f1729",
                                 fg="#3b82f6",
                                 font=("Segoe UI", 10)).pack(side="left", padx=(0, 6))
                        tk.Label(row, text=item, bg="#0f1729",
                                 fg="#94a3b8",
                                 font=("Segoe UI", 10),
                                 wraplength=420,
                                 justify="left").pack(side="left", anchor="w")

            tk.Frame(inner, bg="#0f1729", height=10).pack()

        try: win.after(0, _render)
        except Exception: pass

    _th.Thread(target=_load_changelog, daemon=True).start()

    # Close button
    tk.Button(win, text="✕  Close",
              bg="#1877f2", fg="#fff",
              font=("Segoe UI", 11, "bold"),
              relief="flat", cursor="hand2",
              padx=24, pady=8,
              command=win.destroy).pack(pady=(0, 14))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _try_lighten(btn: tk.Button, color: str):
    """Simple hover: slightly brighter by blending with white."""
    try:
        r = int(color[1:3], 16); g = int(color[3:5], 16); b = int(color[5:7], 16)
        r2 = min(255, r + 30); g2 = min(255, g + 30); b2 = min(255, b + 30)
        btn.config(bg=f"#{r2:02x}{g2:02x}{b2:02x}")
    except Exception:
        pass