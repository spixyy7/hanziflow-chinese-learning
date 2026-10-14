"""
ui/views/profile.py — Profil v2.
Novo: XP po danima grafikon, hidden achievements, Gemini achievements, moderan layout.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta
from typing import Callable

from ..theme import (C, F, S, Card, GhostButton, PrimaryButton, XPBar,
                     HoverTooltip, ConfirmDialog)
from ..widgets import NotificationManager
from ...core import UserProfile, Database, ACHIEVEMENTS, ACHIEVEMENT_MAP
from ...core.adaptive import compute_level

_T = {
    "en": {
        "title": "👤  Profile",
        "back": "⬅ Back",
        "stats_title": "Statistics",
        "total_answered": "Total answered",
        "total_correct": "Total correct",
        "accuracy": "Accuracy",
        "streak": "Current streak",
        "vocab_size": "Vocabulary",
        "grammar_done": "Sentences built",
        "arena_score": "Arena score",
        "rank_title": "Arena Rank",
        "level_rank_title": "Level Rank",
        "progress_to_next": "Progress to {}",
        "max_rank": "Maximum rank reached 🐉",
        "achievements_title": "Achievements",
        "unlocked": "unlocked",
        "locked": "???",
        "hidden": "🔒 Hidden",
        "settings_title": "Settings",
        "lang_label": "Language",
        "theme_label": "Theme",
        "save": "Save",
        "saved": "✅ Saved!",
        "xp_chart_title": "XP — Last 7 Days",
        "gemini_title": "🤖 Personal Achievements",
        "gemini_sub": "Unlocked by Gemini AI based on your progress",
        "no_gemini": "Play more to unlock AI-generated achievements!",
        "days_label": "days",
    },
    "sr": {
        "title": "👤  Profil",
        "back": "⬅ Nazad",
        "stats_title": "Statistike",
        "total_answered": "Ukupno odgovoreno",
        "total_correct": "Ukupno tačno",
        "accuracy": "Tačnost",
        "streak": "Trenutni streak",
        "vocab_size": "Rečnik",
        "grammar_done": "Rečenica složeno",
        "arena_score": "Arena skor",
        "rank_title": "Arena rang",
        "level_rank_title": "Rang po nivou",
        "progress_to_next": "Napredak ka {}",
        "max_rank": "Maksimalni rang! 🐉",
        "achievements_title": "Dostignuća",
        "unlocked": "otključano",
        "locked": "???",
        "hidden": "🔒 Skriveno",
        "settings_title": "Podešavanja",
        "lang_label": "Jezik",
        "theme_label": "Tema",
        "save": "Sačuvaj",
        "saved": "✅ Sačuvano!",
        "xp_chart_title": "XP — poslednjih 7 dana",
        "gemini_title": "🤖 Lična dostignuća",
        "gemini_sub": "Otključana od strane Gemini AI na osnovu tvog napretka",
        "no_gemini": "Igraj više da otključaš AI dostignuća!",
        "days_label": "dana",
    },
}


class ProfileView(tk.Frame):

    def __init__(self, parent, profile: UserProfile,
                 notif: NotificationManager, on_back: Callable):
        super().__init__(parent, bg=C.BG)
        self._profile = profile
        self._lang    = profile.lang
        self._db      = Database()
        self._notif   = notif
        self._on_back = on_back
        self._build()

    def _add_friend(self):
        """Send friend request via LAN (if available)."""
        try:
            from ...core.lan_server import load_friends
            fdata = load_friends(self._profile.username)
            target = getattr(self, "_view_username", None)
            if not target or target == self._profile.username:
                return
            if target in fdata.get("friends", []):
                self._notif.show("Already friends!", "info"); return
            # Try LAN
            sent = False
            try:
                from ...core.lan_server import LANServer
                # We don't have direct reference to lan server here,
                # just mark pending locally
                from ...core.lan_server import load_friends, save_friends
                data = load_friends(self._profile.username)
                if target not in data.get("pending", []):
                    data.setdefault("pending", []).append(target)
                save_friends(self._profile.username, data)
                sent = True
            except Exception:
                pass
            self._notif.show(f"Friend request sent to {target}!" if sent
                             else "Friend request saved (send when online)", "success")
            self._add_friend_btn.config(text="⏳ Pending", state="disabled")
        except Exception as e:
            self._notif.show(f"Error: {e}", "error")

    def _t(self, key: str, *args) -> str:
        txt = _T[self._lang].get(key, key)
        return txt.format(*args) if args else txt

    def _build(self):
        hdr = tk.Frame(self, bg=C.BG_SIDEBAR); hdr.pack(fill="x")
        GhostButton(hdr, text=self._t("back"), command=self._on_back).pack(
            side="left", padx=S.MD, pady=S.SM)
        tk.Label(hdr, text=self._t("title"), bg=C.BG_SIDEBAR,
                 fg=C.TEXT, font=F.H2).pack(side="left")
        # Add Friend button (shown for other users' profiles if applicable)
        self._add_friend_btn = tk.Button(
            hdr, text="+ Add Friend",
            bg="#1565C0", fg="white",
            font=F.SMALL, relief="flat", bd=0, cursor="hand2",
            padx=S.LG, pady=S.XS,
            command=self._add_friend)
        self._add_friend_btn.pack(side="right", padx=S.MD)
        # Hide by default (only show for other users)
        self._add_friend_btn.pack_forget()

        # Scrollable content
        canvas = tk.Canvas(self, bg=C.BG, highlightthickness=0)
        scroll = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        canvas.configure(yscrollcommand=scroll.set)

        content = tk.Frame(canvas, bg=C.BG)
        cw = canvas.create_window((0, 0), window=content, anchor="nw")

        def on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(cw, width=canvas.winfo_width())

        content.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", on_configure)
        def _scroll(e):
            canvas.yview_scroll(-1*(e.delta//120), "units")
        canvas.bind("<MouseWheel>", _scroll)
        content.bind("<MouseWheel>", _scroll)
        # Also bind children after they're created
        self._scroll_canvas = canvas
        self._scroll_fn = _scroll

        self._build_profile_header(content)
        self._build_xp_chart_widget(content)
        self._build_stats(content)
        self._build_rank_section(content)
        self._build_achievements(content)
        self._build_gemini_achievements(content)
        self._build_settings(content)

    # ── Profile header ─────────────────────────────────────────────────────────

    def _build_profile_header(self, parent):
        p = self._profile

        # Banner
        banner_h = 100
        banner_cv = tk.Canvas(parent, height=banner_h, bg=C.BG_SIDEBAR,
                              highlightthickness=0)
        banner_cv.pack(fill="x", padx=S.LG, pady=(S.SM, 0))

        def draw_banner():
            banner_cv.delete("all")
            banner_cv.update_idletasks()
            bw = banner_cv.winfo_width() or 500
            if p.banner_path:
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(p.banner_path).resize((bw, banner_h), Image.LANCZOS)
                    self._banner_photo = ImageTk.PhotoImage(img)
                    banner_cv.create_image(0, 0, anchor="nw", image=self._banner_photo)
                    return
                except Exception: pass
            # Gradient fallback
            for i in range(banner_h):
                ratio = i / banner_h
                r = int(61*(1-ratio) + 13*ratio)
                g = int(126*(1-ratio) + 13*ratio)
                bv = int(255*(1-ratio) + 30*ratio)
                banner_cv.create_line(0, i, bw, i, fill=f"#{r:02x}{g:02x}{bv:02x}")
            rank = p.get_rank()
            banner_cv.create_text(bw//2, banner_h//2,
                                  text=f"{rank['icon']}  {p.username}",
                                  fill="white", font=(F.FAMILY, 16, "bold"))

        banner_cv.bind("<Configure>", lambda e: draw_banner())
        self.after(100, draw_banner)  # slight delay to let canvas render

        # Avatar
        av_size = 80
        av_frame = tk.Frame(parent, bg=C.BG); av_frame.pack(pady=(S.SM, 0))
        av_cv = tk.Canvas(av_frame, width=av_size, height=av_size,
                          bg=C.BG, highlightthickness=0)
        av_cv.pack()

        def draw_avatar():
            av_cv.delete("all")
            av_cv.create_oval(0, 0, av_size, av_size, fill=C.PRIMARY, outline="")
            if p.avatar_path:
                try:
                    from PIL import Image, ImageTk, ImageDraw
                    inner = av_size - 4
                    img  = Image.open(p.avatar_path).resize((inner, inner), Image.LANCZOS)
                    mask = Image.new("L", (inner, inner), 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, inner, inner), fill=255)
                    result = Image.new("RGBA", (inner, inner))
                    result.paste(img, mask=mask)
                    self._av_photo_p = ImageTk.PhotoImage(result)
                    av_cv.create_image(2, 2, anchor="nw", image=self._av_photo_p)
                    return
                except Exception: pass
            init = p.username[0].upper() if p.username else "?"
            av_cv.create_oval(3, 3, av_size-3, av_size-3, fill=C.PRIMARY, outline="")
            av_cv.create_text(av_size//2, av_size//2, text=init,
                              fill="white", font=(F.FAMILY, 22, "bold"))

        draw_avatar()

        # Username + rank labels
        from ...core.models import get_rank
        from ..views.dashboard import get_level_rank
        rank     = get_rank(p.arena_score)
        lvl, _, _= compute_level(p.xp)
        lv_rank  = get_level_rank(lvl)

        tk.Label(parent, text=p.username, bg=C.BG,
                 fg=C.TEXT, font=(F.FAMILY, 16, "bold")).pack()
        tk.Label(parent, text=f"{lv_rank['icon']}  {lv_rank['name']}",
                 bg=C.BG, fg=lv_rank["color"], font=F.LABEL_B).pack()
        tk.Label(parent, text=f"Level {lvl}  •  {p.xp} XP  •  🔥 {p.streak} {self._t('days_label')}",
                 bg=C.BG, fg=C.TEXT_MUTED, font=F.SMALL).pack(pady=(0, S.SM))

    # ── XP Chart ───────────────────────────────────────────────────────────────

    def _build_xp_chart_widget(self, parent):
        from ..widgets import DailyXPChart
        card = Card(parent); card.pack(fill="x", padx=S.LG, pady=S.SM)
        b = card.body()
        DailyXPChart(b, self._profile, bg=C.BG_CARD).pack(fill="x")

    def _build_xp_chart(self, parent):
        card = Card(parent); card.pack(fill="x", padx=S.LG, pady=S.SM)
        b = card.body()
        tk.Label(b, text=self._t("xp_chart_title"), bg=C.BG_CARD,
                 fg=C.TEXT, font=F.TITLE).pack(anchor="w", pady=(0, S.XS))

        cv = tk.Canvas(b, height=110, bg=C.BG_CARD, highlightthickness=0, bd=0)
        cv.pack(fill="x")

        def draw(e=None):
            cv.delete("all")
            w = cv.winfo_width()
            h = cv.winfo_height()
            if not w or not h: return

            today  = date.today()
            days   = [(today - timedelta(days=6-i)) for i in range(7)]
            hist   = self._profile.daily_xp_history
            values = [hist.get(d.isoformat(), 0) for d in days]
            goal   = max(self._profile.daily_goal, 1)
            max_v  = max(max(values), goal, 1)

            bar_total = w - 24
            bar_slot  = bar_total // 7
            bar_w     = max(10, bar_slot - 6)

            for i, (d, v) in enumerate(zip(days, values)):
                x   = 12 + i * bar_slot + (bar_slot - bar_w) // 2
                pct = min(1.0, v / max_v)
                bh  = max(3, int((h - 28) * pct))
                y_top = h - 22 - bh

                is_today  = d == today
                met_goal  = v >= self._profile.daily_goal

                color = C.PRIMARY if is_today else (C.SUCCESS if met_goal else (C.WARNING if v > 0 else C.BORDER))

                # Bar shadow
                cv.create_rectangle(x+2, y_top+2, x+bar_w+2, h-22,
                                    fill=C.BORDER, outline="")
                cv.create_rectangle(x, y_top, x+bar_w, h-22, fill=color, outline="")

                # Highlight top strip
                if bh > 6:
                    cv.create_rectangle(x, y_top, x+bar_w, y_top+4,
                                        fill="white" if not C.is_dark() else "#FFFFFF33", outline="")

                # Day label
                day_lbl = d.strftime("%a")[0]
                cv.create_text(x + bar_w//2, h - 12, text=day_lbl,
                               fill=C.PRIMARY if is_today else C.TEXT_MUTED,
                               font=(F.FAMILY, 8, "bold" if is_today else "normal"))

                # Value
                if v > 0:
                    cv.create_text(x + bar_w//2, y_top - 7, text=str(v),
                                   fill=C.TEXT_MUTED, font=(F.FAMILY, 7))

            # Goal dashed line
            if max_v > 0:
                goal_y = h - 22 - int((h - 28) * min(1.0, goal / max_v))
                for xi in range(12, w-12, 8):
                    cv.create_line(xi, goal_y, xi+4, goal_y,
                                   fill=C.TEXT_LIGHT, width=1)
                cv.create_text(w - 8, goal_y - 6, text=f"Goal:{goal}",
                               fill=C.TEXT_LIGHT, font=(F.FAMILY, 7), anchor="e")

        cv.bind("<Configure>", draw)
        self.after(120, draw)  # wait for layout

    # ── Stats ──────────────────────────────────────────────────────────────────

    def _build_stats(self, parent):
        card = Card(parent); card.pack(fill="x", padx=S.LG, pady=S.SM)
        b = card.body()
        tk.Label(b, text=self._t("stats_title"), bg=C.BG_CARD,
                 fg=C.TEXT, font=F.TITLE).pack(anchor="w", pady=(0, S.SM))

        p   = self._profile
        lvl, cur, needed = compute_level(p.xp)
        total = p.total_answered
        corr  = p.total_correct
        acc   = f"{corr/total*100:.0f}%" if total else "—"

        stats_data = [
            (self._t("total_answered"), str(total),   C.PRIMARY),
            (self._t("total_correct"),  str(corr),    C.SUCCESS),
            (self._t("accuracy"),       acc,           C.TEAL),
            (self._t("streak"),         f"🔥 {p.streak}", C.WARNING),
            (self._t("vocab_size"),     str(len(p.vocab)), C.PURPLE),
            (self._t("grammar_done"),   str(p.grammar_completed), C.ORANGE),
            (self._t("arena_score"),    str(p.arena_score),       C.GOLD),
            (f"Level {lvl}",            f"{cur}/{needed} XP",     C.PRIMARY),
        ]

        # 2-column grid
        grid = tk.Frame(b, bg=C.BG_CARD); grid.pack(fill="x")
        for i, (lbl, val, color) in enumerate(stats_data):
            col = i % 2
            row = i // 2
            cell = tk.Frame(grid, bg=C.BG_CARD, highlightbackground=C.BORDER,
                            highlightthickness=1)
            cell.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
            grid.columnconfigure(col, weight=1)
            tk.Label(cell, text=val, bg=C.BG_CARD, fg=color,
                     font=F.H2).pack(pady=(S.SM, 0))
            tk.Label(cell, text=lbl, bg=C.BG_CARD, fg=C.TEXT_MUTED,
                     font=F.TINY).pack(pady=(0, S.SM))

    # ── Rank section ───────────────────────────────────────────────────────────

    def _build_rank_section(self, parent):
        from ...core.models import RANKS, get_rank, get_next_rank
        from ..views.dashboard import get_level_rank, get_next_level_rank, LEVEL_RANKS

        card = Card(parent); card.pack(fill="x", padx=S.LG, pady=S.SM)
        b = card.body()

        lvl, _, _ = compute_level(self._profile.xp)

        # Level rank
        lv_rank  = get_level_rank(lvl)
        nxt_lv   = get_next_level_rank(lvl)
        tk.Label(b, text=self._t("level_rank_title"), bg=C.BG_CARD,
                 fg=C.TEXT_MUTED, font=F.SMALL).pack(anchor="w")
        tk.Label(b, text=f"{lv_rank['icon']}  {lv_rank['name']}",
                 bg=C.BG_CARD, fg=lv_rank["color"], font=F.H1).pack()
        if nxt_lv:
            rank_prog = lvl - lv_rank["min_level"]
            rank_span = nxt_lv["min_level"] - lv_rank["min_level"]
            pct       = min(1.0, rank_prog / max(rank_span, 1))
            tk.Label(b, text=self._t("progress_to_next", nxt_lv["name"]),
                     bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.SMALL).pack(anchor="w", pady=(S.SM, 2))
            bar_bg = tk.Frame(b, bg=C.BORDER, height=10); bar_bg.pack(fill="x")
            def _draw_bar(e, pct=pct, color=lv_rank["color"]):
                bar_bg.update_idletasks()
                bw = int(bar_bg.winfo_width() * pct)
                tk.Frame(bar_bg, bg=color, height=10, width=bw).place(x=0, y=0)
            bar_bg.bind("<Configure>", _draw_bar)
            tk.Label(b, text=f"Level {lvl} → Level {nxt_lv['min_level']}",
                     bg=C.BG_CARD, fg=C.TEXT_LIGHT, font=F.TINY).pack(anchor="e")
        else:
            tk.Label(b, text=self._t("max_rank"), bg=C.BG_CARD,
                     fg=C.GOLD, font=F.LABEL_B).pack(pady=S.SM)

        tk.Frame(b, bg=C.BORDER, height=1).pack(fill="x", pady=S.SM)

        # Arena rank
        arena_rank = get_rank(self._profile.arena_score)
        nxt_arena  = get_next_rank(self._profile.arena_score)
        tk.Label(b, text=self._t("rank_title"), bg=C.BG_CARD,
                 fg=C.TEXT_MUTED, font=F.SMALL).pack(anchor="w")
        tk.Label(b, text=f"{arena_rank['icon']}  {arena_rank['name']}",
                 bg=C.BG_CARD, fg=arena_rank["color"], font=F.H2).pack()
        if nxt_arena:
            progress = self._profile.arena_score - arena_rank["min_score"]
            span     = nxt_arena["min_score"] - arena_rank["min_score"]
            pct      = min(1.0, progress / max(span, 1))
            tk.Label(b, text=self._t("progress_to_next", nxt_arena["name"]),
                     bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.SMALL).pack(anchor="w", pady=(S.SM, 2))
            bar2 = tk.Frame(b, bg=C.BORDER, height=8); bar2.pack(fill="x")
            def _draw_bar2(e, pct=pct, color=arena_rank["color"]):
                bar2.update_idletasks()
                bw = int(bar2.winfo_width() * pct)
                tk.Frame(bar2, bg=color, height=8, width=bw).place(x=0, y=0)
            bar2.bind("<Configure>", _draw_bar2)
            tk.Label(b, text=f"{self._profile.arena_score} / {nxt_arena['min_score']} Arena pts",
                     bg=C.BG_CARD, fg=C.TEXT_LIGHT, font=F.TINY).pack(anchor="e")

    # ── Achievements ───────────────────────────────────────────────────────────

    def _build_achievements(self, parent):
        card = Card(parent); card.pack(fill="x", padx=S.LG, pady=S.SM)
        b = card.body()

        p         = self._profile
        unlocked  = len(p.achievements)
        # Only count non-hidden in total display
        visible   = [a for a in ACHIEVEMENTS if not a.get("hidden", False)]
        hidden_ach= [a for a in ACHIEVEMENTS if a.get("hidden", False)]

        tk.Label(b, text=self._t("achievements_title"), bg=C.BG_CARD,
                 fg=C.TEXT, font=F.TITLE).pack(anchor="w")
        tk.Label(b, text=f"{unlocked} {self._t('unlocked')}",
                 bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.SMALL).pack(anchor="w", pady=(0, S.SM))

        # Regular achievements grid (3 columns)
        grid = tk.Frame(b, bg=C.BG_CARD); grid.pack(fill="x")
        for i, ach in enumerate(visible):
            self._ach_cell(grid, ach, i, 3)

        # Hidden achievements section
        tk.Label(b, text="— " + self._t("hidden") + " —",
                 bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.SMALL).pack(pady=(S.MD, S.XS))

        hgrid = tk.Frame(b, bg=C.BG_CARD); hgrid.pack(fill="x")
        for i, ach in enumerate(hidden_ach):
            self._ach_cell(hgrid, ach, i, 3, is_hidden_section=True)

    def _ach_cell(self, grid, ach, idx, cols, is_hidden_section=False):
        p    = self._profile
        done = ach["id"] in p.achievements
        r, c = divmod(idx, cols)

        if done:
            bg = C.NOTIF_OK if not C.is_dark() else "#1A3D2B"
            fg = C.SUCCESS
        elif is_hidden_section and not done:
            bg = C.BG_INPUT
            fg = C.TEXT_LIGHT
        else:
            bg = C.BG
            fg = C.TEXT_LIGHT

        frame = tk.Frame(grid, bg=bg, highlightbackground=C.BORDER,
                         highlightthickness=1)
        frame.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
        grid.columnconfigure(c, weight=1)

        if done:
            icon_text = ach["icon"]
            name_text = ach["name"]
            desc_text = f"+{ach['xp']} XP"
            desc_color= C.SUCCESS
        elif is_hidden_section:
            icon_text = "🔒"
            name_text = "???"
            desc_text = ach["desc"] if not ach.get("hidden") else "???"
            desc_color= C.TEXT_LIGHT
        else:
            icon_text = "🔒"
            name_text = ach["name"]
            desc_text = ach["desc"]
            desc_color= C.TEXT_LIGHT

        tk.Label(frame, text=icon_text, bg=bg,
                 font=(F.FAMILY, 18)).pack(pady=(S.SM, 0))
        tk.Label(frame, text=name_text, bg=bg, fg=fg,
                 font=F.TINY, wraplength=100, justify="center").pack()
        tk.Label(frame, text=desc_text, bg=bg, fg=desc_color,
                 font=F.TINY, wraplength=100, justify="center").pack(pady=(0, S.XS))

        # Hover tooltip for locked ones
        if not done:
            from ..widgets import bind_achievement_tooltip
            bind_achievement_tooltip(frame, ach, self._profile, self.winfo_toplevel())

    # ── Gemini personal achievements ───────────────────────────────────────────

    def _build_gemini_achievements(self, parent):
        """Sekcija za AI-generisana lična dostignuća."""
        card = Card(parent); card.pack(fill="x", padx=S.LG, pady=S.SM)
        b = card.body()

        tk.Label(b, text=self._t("gemini_title"), bg=C.BG_CARD,
                 fg=C.PRIMARY, font=F.TITLE).pack(anchor="w")
        tk.Label(b, text=self._t("gemini_sub"), bg=C.BG_CARD,
                 fg=C.TEXT_MUTED, font=F.TINY).pack(anchor="w", pady=(0, S.SM))

        p = self._profile
        # Collect gemini achievements (those with gemini_ prefix that are unlocked)
        gemini_unlocked = [
            ACHIEVEMENT_MAP.get(aid)
            for aid in p.achievements
            if aid.startswith("gemini_") and aid in ACHIEVEMENT_MAP
        ]

        if not gemini_unlocked:
            tk.Label(b, text=self._t("no_gemini"), bg=C.BG_CARD,
                     fg=C.TEXT_LIGHT, font=F.SMALL).pack(pady=S.MD)
            return

        grid = tk.Frame(b, bg=C.BG_CARD); grid.pack(fill="x")
        for i, ach in enumerate(gemini_unlocked):
            if not ach: continue
            r, c = divmod(i, 3)
            cell = tk.Frame(grid, bg=C.NOTIF_OK if not C.is_dark() else "#1A2B3D",
                            highlightbackground=C.PRIMARY, highlightthickness=1)
            cell.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
            grid.columnconfigure(c, weight=1)
            tk.Label(cell, text=ach.get("icon", "🤖"),
                     bg=cell["bg"], font=(F.FAMILY, 18)).pack(pady=(S.SM, 0))
            tk.Label(cell, text=ach.get("name", ""),
                     bg=cell["bg"], fg=C.PRIMARY, font=F.TINY,
                     wraplength=100, justify="center").pack()
            tk.Label(cell, text=ach.get("desc", ""),
                     bg=cell["bg"], fg=C.TEXT_MUTED, font=F.TINY,
                     wraplength=100, justify="center").pack(pady=(0, S.XS))

    # ── Settings ───────────────────────────────────────────────────────────────

    def _build_settings(self, parent):
        card = Card(parent); card.pack(fill="x", padx=S.LG, pady=S.SM)
        b = card.body()
        tk.Label(b, text=self._t("settings_title"), bg=C.BG_CARD,
                 fg=C.TEXT, font=F.TITLE).pack(anchor="w", pady=(0, S.SM))

        # Language
        row1 = tk.Frame(b, bg=C.BG_CARD); row1.pack(fill="x", pady=2)
        tk.Label(row1, text=self._t("lang_label"), bg=C.BG_CARD,
                 fg=C.TEXT_MUTED, font=F.BODY).pack(side="left")
        lang_var = tk.StringVar(value="English" if self._profile.lang == "en" else "Srpski")
        ttk.Combobox(row1, textvariable=lang_var,
                     values=["English", "Srpski"],
                     state="readonly", width=10, font=F.BODY).pack(side="right", padx=S.SM)

        # Theme
        row2 = tk.Frame(b, bg=C.BG_CARD); row2.pack(fill="x", pady=2)
        tk.Label(row2, text=self._t("theme_label"), bg=C.BG_CARD,
                 fg=C.TEXT_MUTED, font=F.BODY).pack(side="left")
        theme_map = {
            "en": {"light": "☀️ Light", "dark": "🌙 Dark", "system": "🖥 System"},
            "sr": {"light": "☀️ Svetla", "dark": "🌙 Tamna", "system": "🖥 Sistemska"},
        }[self._profile.lang]
        theme_rev = {v: k for k, v in theme_map.items()}
        current_theme_label = theme_map.get(self._profile.theme, theme_map["system"])
        theme_var = tk.StringVar(value=current_theme_label)
        ttk.Combobox(row2, textvariable=theme_var,
                     values=list(theme_map.values()),
                     state="readonly", width=12, font=F.BODY).pack(side="right", padx=S.SM)

        save_lbl = tk.Label(b, text="", bg=C.BG_CARD, fg=C.SUCCESS, font=F.SMALL)
        save_lbl.pack()

        def save():
            self._profile.lang  = "en" if lang_var.get() == "English" else "sr"
            new_theme = theme_rev.get(theme_var.get(), "system")
            self._profile.theme = new_theme
            self._db.save_user(self._profile)
            C.set_theme(new_theme)
            from ..theme import _apply_ttk
            _apply_ttk(self.winfo_toplevel())
            save_lbl.config(text=self._t("saved"))
            self._notif.show(self._t("saved"), "success")

        PrimaryButton(b, text=self._t("save"), command=save).pack(pady=S.SM)

        # Bottom spacer
        tk.Frame(b, bg=C.BG_CARD, height=S.LG).pack()