"""
ui/widgets_calendar.py — Custom heatmap kalendar + streak panel.

Zamjena za tkcalendar — potpuno custom, theme-aware, animiran.
Stil: GitHub heatmap + Duolingo streak + game-like.
"""
from __future__ import annotations
import calendar
import tkinter as tk
from datetime import date, timedelta
from typing import Optional

from .theme import C, F, S


# ── Boje intenziteta aktivnosti ───────────────────────────────────────────────

def _activity_color(xp: int, daily_goal: int, is_dark: bool, is_completed: bool = False) -> str:
    if is_completed:
        return "#E87000" if is_dark else "#FF8C00"
    if xp <= 0:
        return C.BG_HOVER
    ratio = xp / max(daily_goal, 1)
    if ratio >= 1.0:
        return "#CC6600" if is_dark else "#FFA040"
    if ratio >= 0.5:
        return "#994400" if is_dark else "#FFB870"
    return "#663300" if is_dark else "#FFD0A0"
def _is_streak_day(day_iso: str, completed_days: list[str]) -> bool:
    return day_iso in completed_days


class HeatmapCalendar(tk.Frame):
    """
    Custom heatmap kalendar.

    Features:
    - GitHub-style aktivnost heatmap
    - Streak dani sa glow efektom
    - Hover tooltip sa XP info
    - Navigacija po mesecima
    - Propušteni dani crveno
    """

    DAY_SIZE = 32      # px po ćeliji
    GAP      = 3       # razmak između ćelija

    def __init__(self, parent, profile, **kw):
        super().__init__(parent, bg=C.BG_CARD, **kw)
        self._profile = profile
        self._today   = date.today()
        self._year    = self._today.year
        self._month   = self._today.month
        self._tooltip: Optional[tk.Toplevel] = None
        self._build()
        self.refresh()

    def _build(self):
        # Header: nav + month label
        hdr = tk.Frame(self, bg=C.BG_CARD); hdr.pack(fill="x", padx=S.SM, pady=(S.SM, 0))

        tk.Button(hdr, text="◀", bg=C.BG_CARD, fg=C.TEXT_MUTED,
                  font=F.BODY, relief="flat", bd=0, cursor="hand2",
                  activebackground=C.BG_HOVER,
                  command=self._prev_month).pack(side="left")

        self._month_lbl = tk.Label(hdr, text="", bg=C.BG_CARD,
                                   fg=C.TEXT, font=F.LABEL_B)
        self._month_lbl.pack(side="left", expand=True)

        tk.Button(hdr, text="▶", bg=C.BG_CARD, fg=C.TEXT_MUTED,
                  font=F.BODY, relief="flat", bd=0, cursor="hand2",
                  activebackground=C.BG_HOVER,
                  command=self._next_month).pack(side="right")

        # Day of week headers
        dow_frame = tk.Frame(self, bg=C.BG_CARD)
        dow_frame.pack(fill="x", padx=S.SM)
        days_short = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for d in days_short:
            tk.Label(dow_frame, text=d, bg=C.BG_CARD, fg=C.TEXT_MUTED,
                     font=F.TINY, width=3, anchor="center").pack(side="left", padx=self.GAP//2)

        # Grid canvas
        cols = 7
        rows = 6
        w = cols * (self.DAY_SIZE + self.GAP) + S.MD
        h = rows * (self.DAY_SIZE + self.GAP) + S.SM
        self._canvas = tk.Canvas(self, bg=C.BG_CARD, width=w, height=h,
                                 highlightthickness=0, bd=0)
        self._canvas.pack(padx=S.SM, pady=S.XS)
        self._canvas.bind("<Motion>",        self._on_hover)
        self._canvas.bind("<Leave>",         self._hide_tooltip)
        self._canvas.bind("<Button-1>",      self._on_click)

        # Cell registry: tag → date
        self._cells: dict[str, date] = {}

    def refresh(self):
        self._draw_month()

    def set_month(self, year: int, month: int):
        self._year  = year
        self._month = month
        self._draw_month()

    def _draw_month(self):
        self._canvas.delete("all")
        self._cells.clear()

        p     = self._profile
        xp_h  = p.daily_xp_history
        comp  = set(p.completed_days)
        goal  = p.daily_goal
        dark  = C.is_dark()
        today = date.today()

        # Month name
        month_name = date(self._year, self._month, 1).strftime("%B %Y")
        self._month_lbl.config(text=month_name)

        cal = calendar.monthcalendar(self._year, self._month)

        for row, week in enumerate(cal):
            for col, day_n in enumerate(week):
                if day_n == 0:
                    continue

                d    = date(self._year, self._month, day_n)
                d_s  = d.isoformat()
                x    = S.SM//2 + col * (self.DAY_SIZE + self.GAP)
                y    = row * (self.DAY_SIZE + self.GAP)

                is_today   = d == today
                is_future  = d > today
                xp_val     = xp_h.get(d_s, 0)
                is_done    = d_s in comp

                if is_future:
                    fill = C.BG
                elif is_done:
                    fill = _activity_color(xp_val, goal, dark, is_completed=True)
                elif d == today:
                    fill = C.BG_HOVER
                else:
                    fill = C.BG_HOVER

                # Draw cell
                tag = f"day_{d_s}"
                r   = 6  # border radius (simulated with oval)
                self._canvas.create_rectangle(x, y, x+self.DAY_SIZE, y+self.DAY_SIZE,
                                              fill=fill, outline="", tags=(tag,))

                if is_today:
                    ring_col = "#FF8C00" if is_done else C.PRIMARY
                    self._canvas.create_rectangle(x+1, y+1, x+self.DAY_SIZE-1, y+self.DAY_SIZE-1,
                                                  fill="", outline=ring_col, width=2, tags=(tag,))

                day_color = C.TEXT if not is_future else C.TEXT_LIGHT
                if is_done:
                    day_color = "#FFFFFF"

                self._canvas.create_text(x + self.DAY_SIZE//2, y + self.DAY_SIZE//2,
                                         text=str(day_n),
                                         font=(F.FAMILY, 9, "bold" if is_today else "normal"),
                                         fill=day_color, tags=(tag,))

                # Shield icon for streak days
                if is_done:
                    self._canvas.create_text(x + self.DAY_SIZE - 4, y + 5,
                                             text="✓", font=(F.FAMILY, 7),
                                             fill="white", tags=(tag,))

                self._cells[tag] = d

    def _prev_month(self):
        if self._month == 1: self._year -= 1; self._month = 12
        else: self._month -= 1
        self._draw_month()

    def _next_month(self):
        if self._month == 12: self._year += 1; self._month = 1
        else: self._month += 1
        self._draw_month()

    def _get_cell_at(self, x: int, y: int) -> Optional[date]:
        for tag, d in self._cells.items():
            col = list(self._cells.keys()).index(tag) % 7
            row = list(self._cells.keys()).index(tag) // 7
            items = self._canvas.find_withtag(tag)
            if items:
                bbox = self._canvas.bbox(items[0])
                if bbox and bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]:
                    return d
        # Use canvas find_closest as fallback
        items = self._canvas.find_closest(x, y)
        for item in items:
            tags = self._canvas.gettags(item)
            for t in tags:
                if t.startswith("day_"):
                    return self._cells.get(t)
        return None

    def _on_hover(self, e: tk.Event):
        d = self._get_cell_at(e.x, e.y)
        if d:
            self._show_tooltip(e, d)
        else:
            self._hide_tooltip()

    def _show_tooltip(self, e: tk.Event, d: date):
        self._hide_tooltip()

        p    = self._profile
        d_s  = d.isoformat()
        xp   = p.daily_xp_history.get(d_s, 0)
        done = d_s in p.completed_days
        today = date.today()

        if d > today:
            return  # no tooltip for future

        lines = [d.strftime("%A, %d %b %Y")]
        if xp > 0:
            lines.append(f"XP: {xp}")
            lines.append("✅ Goal met!" if done else f"🎯 Goal: {p.daily_goal}")
        else:
            lines.append("No activity" if p.lang == "en" else "Bez aktivnosti")

        tip = tk.Toplevel(self.winfo_toplevel())
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg=C.BG_CARD,
                      highlightbackground=C.BORDER,
                      highlightthickness=1)

        for line in lines:
            tk.Label(tip, text=line, bg=C.BG_CARD, fg=C.TEXT,
                     font=F.TINY, padx=8, pady=2).pack(anchor="w")

        # Position near cursor
        rx = self.winfo_rootx() + e.x + 12
        ry = self.winfo_rooty() + e.y + 12
        tip.geometry(f"+{rx}+{ry}")
        self._tooltip = tip

    def _hide_tooltip(self, _=None):
        if self._tooltip:
            try: self._tooltip.destroy()
            except Exception: pass
            self._tooltip = None

    def _on_click(self, e: tk.Event):
        self._hide_tooltip()


class StreakPanel(tk.Frame):
    """
    Streak panel sa shield-ovima i statistikama.
    Pokazuje: current streak, longest streak, shields.
    """

    def __init__(self, parent, profile, on_quiz=None, **kw):
        super().__init__(parent, bg=C.BG_CARD, **kw)
        self._profile  = profile
        self._on_quiz  = on_quiz
        self._build()
        self.refresh()

    def _build(self):
        # Streak fire display
        fire_row = tk.Frame(self, bg=C.BG_CARD); fire_row.pack(pady=(S.SM, 0))

        # Animated fire canvas (36x36)
        self._fire_cv = tk.Canvas(fire_row, width=36, height=36,
                                   bg=C.BG_CARD, highlightthickness=0)
        self._fire_cv.pack(side="left")
        self._fire_phase = 0
        self._fire_job   = None
        self._animate_fire()

        streak_col = tk.Frame(fire_row, bg=C.BG_CARD); streak_col.pack(side="left", padx=S.XS)
        self._streak_lbl = tk.Label(streak_col, text="", bg=C.BG_CARD,
                                    fg=C.WARNING, font=(F.FAMILY, 20, "bold"))
        self._streak_lbl.pack(anchor="w")
        self._streak_sub = tk.Label(streak_col, text="", bg=C.BG_CARD,
                                    fg=C.TEXT_MUTED, font=F.TINY)
        self._streak_sub.pack(anchor="w")

        # Stats row: longest + shields
        stats = tk.Frame(self, bg=C.BG_CARD); stats.pack(fill="x", padx=S.SM, pady=(S.XS, S.SM))

        # Longest streak
        long_col = tk.Frame(stats, bg=C.BG_CARD); long_col.pack(side="left", expand=True)
        tk.Label(long_col, text="BEST", bg=C.BG_CARD,
                 fg=C.TEXT_LIGHT, font=(F.FAMILY, 7)).pack()
        self._longest_lbl = tk.Label(long_col, text="", bg=C.BG_CARD,
                                     fg=C.GOLD, font=(F.FAMILY, 14, "bold"))
        self._longest_lbl.pack()

        # Separator
        tk.Frame(stats, bg=C.BORDER, width=1).pack(side="left", fill="y", padx=S.XS)

        # Shields
        shield_col = tk.Frame(stats, bg=C.BG_CARD); shield_col.pack(side="left", expand=True)
        tk.Label(shield_col, text="SHIELDS", bg=C.BG_CARD,
                 fg=C.TEXT_LIGHT, font=(F.FAMILY, 7)).pack()
        self._shields_row = tk.Frame(shield_col, bg=C.BG_CARD)
        self._shields_row.pack()

    def _animate_fire(self):
        """Draws a small animated flame using overlapping ovals."""
        cv = self._fire_cv
        cv.delete("all")
        p = self._fire_phase
        import math
        # Base colors cycling through orange/yellow/red
        layers = [
            ("#CC2200", 18, 32, 0),   # dark red core
            ("#FF4400", 14, 26, 0),   # orange
            ("#FF8800", 10, 18, math.sin(p * 0.3) * 2),  # amber sway
            ("#FFCC00", 6,  10, math.sin(p * 0.5) * 1),  # tip yellow
        ]
        for color, w, h, sway in layers:
            cx = 18 + sway
            cv.create_oval(cx - w//2, 36 - h, cx + w//2, 36 + 2,
                           fill=color, outline="")
        self._fire_phase = (p + 1) % 30
        # Only animate if streak > 0
        streak = getattr(self._profile, "streak", 0)
        interval = 80 if streak > 0 else 1000
        self._fire_job = self.after(interval, self._animate_fire)

    def _stop_fire(self):
        if self._fire_job:
            try: self.after_cancel(self._fire_job)
            except Exception: pass

    def refresh(self):
        p = self._profile

        streak = p.streak
        lang   = p.lang

        self._streak_lbl.config(text=f"{streak} {'day' if lang=='en' else 'dan'}")

        if streak == 0:
            sub = "Start a streak today!" if lang == "en" else "Počni streak danas!"
            self._streak_lbl.config(fg="#888888")
        elif streak < 3:
            sub = "Keep it up! 💪" if lang == "en" else "Samo tako! 💪"
            self._streak_lbl.config(fg="#FF6600")   # orange
        elif streak < 7:
            sub = "You're on fire! 🔥" if lang == "en" else "Goriš! 🔥"
            self._streak_lbl.config(fg="#FF4400")   # deep orange
        else:
            sub = f"Legendary! {streak} days 🏆" if lang == "en" else f"Legendarno! {streak} dana 🏆"
            self._streak_lbl.config(fg="#FFD700")   # gold

        self._streak_sub.config(text=sub)

        longest = max(p.longest_streak, streak)
        self._longest_lbl.config(text=f"{longest}🔥")

        # Shields display
        for w in self._shields_row.winfo_children():
            w.destroy()
        shields = getattr(p, 'streak_shields', 0)
        for i in range(3):
            color = C.PRIMARY if i < shields else C.BORDER
            tk.Label(self._shields_row, text="🛡️", bg=C.BG_CARD,
                     fg=color, font=(F.FAMILY, 12 if i < shields else 10),
                     ).pack(side="left", padx=1)
        if shields < 3:
            tk.Label(self._shields_row, text=f" {shields}/3",
                     bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.TINY).pack(side="left")