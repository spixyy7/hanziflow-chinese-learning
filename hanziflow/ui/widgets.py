from __future__ import annotations
import io, os, threading, wave
import tkinter as tk
from typing import Callable, Optional

from .theme import C, F, S, PrimaryButton, GhostButton, DangerButton, flash_widget

try:
    from tkinterdnd2 import DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

try:
    import pyaudio
    PYAUDIO_OK = True
except ImportError:
    PYAUDIO_OK = False

import logging
logger = logging.getLogger("HanziFlow.UI")


def fade_in_frame(frame: tk.Frame, steps: int = 8, interval: int = 18) -> None:
    try:
        frame.pack_configure(pady=40)
        def _step(n):
            if not frame.winfo_exists(): return
            pad = max(0, 40 - n * (40 // steps))
            try: frame.pack_configure(pady=pad)
            except Exception: return
            if n < steps:
                frame.after(interval, lambda: _step(n + 1))
        frame.after(interval, lambda: _step(1))
    except Exception:
        pass


def make_listen_btn(parent, text: str, bg: str = None, size: int = 14) -> tk.Button:
    from ..core import play_audio as _play
    _bg = bg or C.BG_CARD
    btn = tk.Button(
        parent,
        text="🔊",
        bg=_bg, fg=C.TEAL,
        font=(F.FAMILY, size),
        relief="flat", bd=0,
        cursor="hand2",
        activebackground=_bg,
        activeforeground=C.TEAL_DARK,
        padx=4, pady=2,
        command=lambda: _play(text)
    )
    btn.bind("<Enter>", lambda e: btn.config(fg=C.TEAL_DARK))
    btn.bind("<Leave>", lambda e: btn.config(fg=C.TEAL))
    return btn


class AchievementTooltip:
    _instance = None

    @classmethod
    def show(cls, root: tk.Tk, ach: dict, profile, x: int, y: int):
        cls.hide()
        unlocked_count = len(profile.achievements)
        pct = min(99, max(1, int(unlocked_count / max(1, len(profile.achievements) + 5) * 80)))

        lines = []
        if ach.get("hidden") and ach["id"] not in profile.achievements:
            lines = [
                ("🔒  Hidden Achievement", C.TEXT, F.BODY_B),
                ("Keep playing to discover...", C.TEXT_MUTED, F.SMALL),
            ]
        else:
            lines = [
                (f"{ach.get('icon', '🏆')}  {ach.get('name', '')}", C.TEXT, F.BODY_B),
                (ach.get("desc", ""), C.TEXT_MUTED, F.SMALL),
                (f"+{ach.get('xp', 0)} XP reward", C.GOLD, F.SMALL),
                (f"≈{pct}% of players have this", C.PRIMARY, F.TINY),
            ]

        tip = tk.Toplevel(root)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.attributes("-alpha", 0.0)
        tip.configure(bg=C.BG_CARD)

        inner = tk.Frame(tip, bg=C.BG_CARD,
                         highlightbackground=C.BORDER, highlightthickness=1)
        inner.pack(padx=1, pady=1)

        for line_text, fg_col, font in lines:
            tk.Label(inner, text=line_text, bg=C.BG_CARD, fg=fg_col,
                     font=font, padx=12, pady=2, justify="left",
                     wraplength=220).pack(anchor="w")

        tip.update_idletasks()
        tw, th = tip.winfo_reqwidth(), tip.winfo_reqheight()
        sx, sy = root.winfo_screenwidth(), root.winfo_screenheight()
        px = min(x + 12, sx - tw - 4)
        py = max(y - th - 6, 4)
        tip.geometry(f"+{px}+{py}")

        cls._instance = tip
        cls._fade(tip, 0.0, 1.0)

    @classmethod
    def hide(cls):
        if cls._instance:
            tip = cls._instance
            cls._instance = None
            cls._fade(tip, None, 0.0, on_done=lambda: _safe_destroy(tip))

    @classmethod
    def _fade(cls, tip, start, end, steps=7, on_done=None):
        def step(n):
            try:
                if start is not None and n == 0:
                    tip.attributes("-alpha", start)
                cur = tip.attributes("-alpha")
                nxt = cur + (end - cur) * 0.45
                tip.attributes("-alpha", max(0.0, min(1.0, nxt)))
                if n < steps and abs(tip.attributes("-alpha") - end) > 0.02:
                    tip.after(16, lambda: step(n + 1))
                elif on_done: on_done()
            except tk.TclError:
                if on_done: on_done()
        step(0)


def _safe_destroy(w):
    try: w.destroy()
    except tk.TclError: pass


def bind_achievement_tooltip(widget: tk.Widget, ach: dict, profile, root: tk.Tk):
    widget.bind("<Enter>",
                lambda e, a=ach, p=profile: AchievementTooltip.show(root, a, p, e.x_root, e.y_root),
                add=True)
    widget.bind("<Leave>",
                lambda e: AchievementTooltip.hide(),
                add=True)
    for child in widget.winfo_children():
        bind_achievement_tooltip(child, ach, profile, root)


class DailyXPChart(tk.Frame):
    def __init__(self, parent, profile, **kw):
        bg = kw.pop("bg", C.BG_CARD)
        super().__init__(parent, bg=bg, **kw)
        self._profile = profile
        self._bg      = bg

        from datetime import date, timedelta
        today  = date.today()
        self._days   = [(today - timedelta(days=6-i)) for i in range(7)]
        self._values = [profile.daily_xp_history.get(d.isoformat(), 0) for d in self._days]
        self._goal   = max(profile.daily_goal, 1)

        top_row = tk.Frame(self, bg=bg); top_row.pack(fill="x", pady=(0, S.XS))
        tk.Label(top_row, text="XP — Last 7 Days", bg=bg,
                 fg=C.TEXT, font=F.LABEL_B).pack(side="left")

        total_xp = profile.xp
        streak   = profile.streak
        streak_bonus = streak * 5
        tk.Label(top_row,
                 text=f"Total: {total_xp} XP  •  🔥×{streak_bonus} streak bonus",
                 bg=bg, fg=C.TEXT_MUTED, font=F.TINY).pack(side="right")

        self._cv = tk.Canvas(self, height=100, bg=bg,
                             highlightthickness=0, bd=0)
        self._cv.pack(fill="x")
        self._cv.bind("<Configure>", lambda e: self._draw())
        self._cv.bind("<Motion>",    self._on_hover)
        self._cv.bind("<Leave>",     self._on_leave)
        self._cv.bind("<Destroy>",   self._on_leave)

        self._bar_rects: list[tuple[int,int,int,int,int]] = []

    def _draw(self):
        cv = self._cv
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if not w or not h: return

        from datetime import date
        today = date.today()
        max_v = max(max(self._values), self._goal, 1)
        slot  = (w - 16) // 7
        bar_w = max(10, slot - 8)
        self._bar_rects = []

        for i, (d, v) in enumerate(zip(self._days, self._values)):
            x1 = 8 + i * slot + (slot - bar_w) // 2
            x2 = x1 + bar_w
            bar_h = max(3, int((h - 22) * v / max_v))
            y2 = h - 18
            y1 = y2 - bar_h

            is_today  = d == today
            met_goal  = v >= self._goal
            color = C.PRIMARY if is_today else (C.SUCCESS if met_goal else (C.WARNING if v > 0 else C.BORDER))

            cv.create_rectangle(x1+2, y1+2, x2+2, y2+2, fill=C.BORDER, outline="")
            cv.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
            if bar_h > 6:
                cv.create_rectangle(x1, y1, x2, y1+3, fill="white", outline="")

            day_lbl = d.strftime("%a")[0]
            cv.create_text(x1 + bar_w//2, h - 9, text=day_lbl,
                           fill=C.PRIMARY if is_today else C.TEXT_MUTED,
                           font=(F.FAMILY, 8, "bold" if is_today else "normal"))
            if v > 0:
                cv.create_text(x1 + bar_w//2, y1 - 7, text=str(v),
                               fill=C.TEXT_MUTED, font=(F.FAMILY, 7))

            self._bar_rects.append((x1, y1, x2, y2+2, i))

        goal_y = h - 18 - int((h - 22) * min(1.0, self._goal / max_v))
        for xi in range(8, w-8, 7):
            cv.create_line(xi, goal_y, xi+3, goal_y, fill=C.TEXT_LIGHT)
        cv.create_text(w - 6, goal_y - 6, text=f"goal:{self._goal}",
                       fill=C.TEXT_LIGHT, font=(F.FAMILY, 7), anchor="e")

    def _on_leave(self, e=None):
        from .theme import HoverTooltip
        HoverTooltip.hide()
        AchievementTooltip.hide()

    def _on_hover(self, event):
        for (x1, y1, x2, y2, idx) in self._bar_rects:
            if x1 <= event.x <= x2:
                d = self._days[idx]
                v = self._values[idx]
                from datetime import date
                label = "Today" if d == date.today() else d.strftime("%A, %b %d")
                streak_day = "✅ Goal met!" if v >= self._goal else f"Goal: {self._goal}"
                AchievementTooltip._instance = None
                root = self.winfo_toplevel()
                from .theme import HoverTooltip
                bar_screen_x = self.winfo_rootx() + (x1 + x2) // 2
                bar_screen_y = self.winfo_rooty() + y1 - 8
                HoverTooltip.show(root, f"{label}: {v} XP",
                                  bar_screen_x, bar_screen_y,
                                  extra_lines=[streak_day])
                return
        from .theme import HoverTooltip
        HoverTooltip.hide()


class NotificationManager:
    H = 64; W = 310; PAD = 8

    def __init__(self, root: tk.Tk):
        self._root  = root
        self._stack: list[tk.Toplevel] = []

    def show(self, msg: str, kind: str = "info", delay_ms: int = 3500) -> None:
        bg   = {"success": C.NOTIF_OK, "error": C.NOTIF_ERR,
                "warning": "#FEF9E7", "info": C.NOTIF_INFO}.get(kind, C.NOTIF_INFO)
        icon = {"success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(kind, "ℹ️")

        win = tk.Toplevel(self._root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=bg)
        win.attributes("-alpha", 0.0)

        tk.Label(win, text=f"{icon}  {msg}", bg=bg, fg=C.TEXT,
                 font=F.BODY, wraplength=self.W - 24, justify="left",
                 padx=12, pady=10).pack(fill="both", expand=True)

        self._stack.append(win)
        self._reposition()
        self._fade(win, 0.0, 0.95, steps=8)

        def close():
            self._fade(win, 0.95, 0.0, steps=6, on_done=lambda: self._destroy(win))
        win.after(delay_ms, close)
        win.bind("<Button-1>", lambda e: close())

    def show_achievement(self, ach: dict) -> None:
        try:
            from ..core.sounds import play as _play_snd
            _play_snd("achievement")
        except Exception: pass

        root = self._root
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        W, H = 340, 110
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)

        bg_card, fg_title, fg_sub = "#1A1500", "#FFD700", "#FFC107"
        win.configure(bg=bg_card)
        win.geometry(f"{W}x{H}+{sw - W - 20}+{sh - H - 60}")

        inner = tk.Frame(win, bg=bg_card, padx=16, pady=12)
        inner.pack(fill="both", expand=True)
        top_row = tk.Frame(inner, bg=bg_card)
        top_row.pack(fill="x")
        tk.Label(top_row, text=ach.get("icon", "🏆"), bg=bg_card,
                 font=(F.FAMILY, 24)).pack(side="left", padx=(0, 10))
        txt_col = tk.Frame(top_row, bg=bg_card)
        txt_col.pack(side="left", fill="x", expand=True)
        tk.Label(txt_col, text="Achievement unlocked!", bg=bg_card, fg=fg_sub,
                 font=(F.FAMILY, 8, "bold")).pack(anchor="w")
        tk.Label(txt_col, text=ach.get("name", ""), bg=bg_card, fg=fg_title,
                 font=(F.FAMILY, 13, "bold")).pack(anchor="w")

        tk.Frame(inner, bg=fg_title, height=1).pack(fill="x", pady=(8, 4))
        bot = tk.Frame(inner, bg=bg_card)
        bot.pack(fill="x")
        tk.Label(bot, text=ach.get("desc", ""), bg=bg_card, fg=fg_sub,
                 font=(F.FAMILY, 9)).pack(side="left")
        tk.Label(bot, text=f"+{ach.get('xp', 0)} XP", bg=bg_card, fg=fg_title,
                 font=(F.FAMILY, 10, "bold")).pack(side="right")

        self._stack.append(win)
        self._reposition()
        self._fade(win, 0.0, 0.95, steps=8)
        def close():
            self._fade(win, 0.95, 0.0, steps=6, on_done=lambda: self._destroy(win))
        win.after(3500, close)

    def _reposition(self):
        root = self._root
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        y = sh - self.PAD
        for win in reversed(self._stack):
            if not win.winfo_exists(): continue
            win.update_idletasks()
            h = win.winfo_height() or self.H
            y -= h + self.PAD
            win.geometry(f"{self.W}x{h}+{sw - self.W - self.PAD}+{y}")

    def _destroy(self, win: tk.Toplevel):
        try:
            if win in self._stack: self._stack.remove(win)
            win.destroy()
        except tk.TclError: pass
        self._reposition()

    def _fade(self, win: tk.Toplevel, start: float, end: float,
              steps: int = 8, on_done=None):
        delta = (end - start) / max(steps, 1)
        def step(n, a):
            try:
                win.attributes("-alpha", max(0.0, min(1.0, a)))
                if n < steps:
                    win.after(16, lambda: step(n + 1, a + delta))
                elif on_done: on_done()
            except tk.TclError:
                if on_done: on_done()
        step(0, start)


def _get_level_info(level: int, lang: str):
    thresholds = [
        (50, "Dragon Scholar",  "🐉", "#FF4F4F", "#FFD700"),
        (35, "Fluency King",    "👑", "#B44FE8", "#FFD700"),
        (21, "Master",          "💎", "#50C8FF", "#00FFFF"),
        (11, "Scholar",         "🎓", "#FFD700", "#FFD700"),
        (6,  "Student",         "📖", "#4F8EFF", "#AADDFF"),
        (1,  "Beginner",        "🌱", "#2ECC71", "#AAFFCC"),
    ]
    for min_lv, name, icon, bg, accent in thresholds:
        if level >= min_lv:
            name_sr = {"Dragon Scholar":"Zmajev Učenjak","Fluency King":"Kralj Tečnosti",
                       "Master":"Majstor","Scholar":"Naučnik","Student":"Student",
                       "Beginner":"Početnik"}.get(name, name)
            return (name if lang == "en" else name_sr), icon, bg, accent
    return "Beginner", "🌱", "#2ECC71", "#AAFFCC"


class LevelUpOverlay:
    @staticmethod
    def show(root: tk.Tk, level: int, lang: str = "en", on_done: callable = None) -> None:
        import random as _rnd
        level_name, level_icon, bg_color, accent = _get_level_info(level, lang)
        overlay = tk.Toplevel(root)
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        overlay.attributes("-alpha", 0.0)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        overlay.geometry(f"{sw}x{sh}+0+0")
        overlay.configure(bg=bg_color)

        cv = tk.Canvas(overlay, bg=bg_color, highlightthickness=0, width=sw, height=sh)
        cv.place(x=0, y=0, relwidth=1, relheight=1)

        particles = [[_rnd.randint(0, sw), _rnd.randint(0, sh), _rnd.randint(2, 6), _rnd.uniform(0.5, 2.5), _rnd.choice(["✦", "★", "✸", "·", "◆"])] for _ in range(35)]

        center = tk.Frame(overlay, bg=bg_color)
        center.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(center, text=level_icon, bg=bg_color, font=("Segoe UI Emoji", 72)).pack(pady=(0, 10))
        tk.Label(center, text="LEVEL UP!" if lang == "en" else "LEVEL GORE!", bg=bg_color, fg=accent, font=("Segoe UI", 42, "bold")).pack()
        tk.Label(center, text=f"Level  {level}", bg=bg_color, fg="#FFFFFF", font=("Segoe UI", 28, "bold")).pack(pady=(4, 2))
        tk.Label(center, text=level_name, bg=bg_color, fg=accent, font=("Segoe UI", 20, "italic")).pack(pady=(0, 12))
        tk.Frame(center, bg=accent, height=2, width=320).pack()

        def animate_particles():
            cv.delete("particle")
            for p in particles:
                x, y, r, speed, char = p
                cv.create_text(x, y, text=char, fill=accent, font=("Segoe UI", r * 3), tags="particle")
                p[1] = y - speed
                if p[1] < -20: p[1], p[0] = sh + 20, _rnd.randint(0, sw)
            try: overlay.after(40, animate_particles)
            except tk.TclError: pass

        def fade_in(alpha):
            try:
                overlay.attributes("-alpha", min(alpha, 0.95))
                if alpha < 0.95: overlay.after(20, lambda: fade_in(alpha + 0.08))
                else: animate_particles(); overlay.after(2200, fade_out)
            except tk.TclError: pass

        def fade_out(alpha=0.95):
            try:
                overlay.attributes("-alpha", max(alpha, 0.0))
                if alpha > 0.0: overlay.after(20, lambda: fade_out(alpha - 0.08))
                else: overlay.destroy(); (on_done() if on_done else None)
            except tk.TclError: (on_done() if on_done else None)

        overlay.after(50, lambda: fade_in(0.0))


class DropZone(tk.Frame):
    SUPPORTED = {".txt", ".pdf", ".docx", ".png", ".jpg", ".jpeg"}

    def __init__(self, parent, on_file: Callable[[str], None],
                 hint: str = "Drag file or click", **kw):
        super().__init__(parent, bg=C.BG_CARD, highlightbackground=C.BORDER, highlightthickness=2, **kw)
        self._on_file = on_file
        self._status_var = tk.StringVar(value="")

        inner = tk.Frame(self, bg=C.BG_CARD)
        inner.pack(expand=True, fill="both", padx=S.LG, pady=S.LG)
        tk.Label(inner, text="📂", bg=C.BG_CARD, fg=C.PRIMARY, font=(F.FAMILY, 28)).pack()
        tk.Label(inner, text=hint, bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.BODY, wraplength=280, justify="center").pack(pady=(4, 0))
        self._status = tk.Label(inner, textvariable=self._status_var, bg=C.BG_CARD, fg=C.PRIMARY, font=F.SMALL)
        self._status.pack(pady=(4, 0))

        for w in [self, inner] + list(inner.winfo_children()):
            try:
                w.bind("<Enter>", lambda e: self.config(highlightbackground=C.PRIMARY))
                w.bind("<Leave>", lambda e: self.config(highlightbackground=C.BORDER))
                w.bind("<Button-1>", self._open_dialog)
            except Exception: pass

        if DND_AVAILABLE:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
            self.dnd_bind("<<DragEnter>>", lambda e: self._set_drag(True))
            self.dnd_bind("<<DragLeave>>", lambda e: self._set_drag(False))

    def set_status(self, msg: str, color: str = None):
        self._status_var.set(msg); self._status.config(fg=color or C.PRIMARY)

    def _set_drag(self, active: bool):
        self.config(bg=C.BG_HOVER if active else C.BG_CARD,
                    highlightbackground=C.PRIMARY if active else C.BORDER)

    def _on_drop(self, event):
        self._set_drag(False)
        try: files = self.tk.splitlist(event.data)
        except Exception: files = [event.data.strip("{}")]
        if files: self._dispatch(files[0])

    def _open_dialog(self, _=None):
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("Supported", "*.txt *.pdf *.docx *.png *.jpg *.jpeg"), ("All", "*.*")])
        if path: self._dispatch(path)

    def _dispatch(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext not in self.SUPPORTED:
            self.set_status(f"❌ Unsupported: {ext}", C.DANGER); return
        self.set_status(f"⏳ Loading: {os.path.basename(path)}", C.PRIMARY)
        self._on_file(path)


class SentenceBuilder(tk.Frame):
    _SRC  = "#2563eb"; _SRC_H = "#1d4ed8"
    _ANS  = "#1e3a5f"; _OK = "#166534"; _ERR = "#7f1d1d"
    _LIFT = "#f59e0b"

    def __init__(self, parent, audio_enabled: bool = True, **kw):
        kw.setdefault("bg", C.BG)
        super().__init__(parent, **kw)
        self._audio   = audio_enabled
        self._source: list[str] = []
        self._answer: list[str] = []

        self._ghost: Optional[tk.Label] = None
        self._drag_idx = -1
        self._press_idx = -1
        self._from_src = False  # Prati da li vučemo iz donjeg reda
        self._press_x = self._press_y = 0
        self._drop_idx = -1
        self._dragging = False

        tk.Label(self, text="Your answer:", bg=C.BG, fg=C.TEXT_MUTED, font=(F.FAMILY, 9)).pack(anchor="w", padx=4)
        self._ans_bg = tk.Frame(self, bg="#0d1526", highlightbackground="#2a3a5a", highlightthickness=1)
        self._ans_bg.pack(fill="x", padx=2, pady=(2, 8), ipady=4)
        self._ans_row = tk.Frame(self._ans_bg, bg="#0d1526")
        self._ans_row.pack(fill="x", padx=4, pady=4)

        self._src_row = tk.Frame(self, bg=C.BG)
        self._src_row.pack(fill="x", pady=(0, 4))

    def load(self, words: list[str]) -> None:
        import random
        self._kill_ghost()
        self._source = list(words); random.shuffle(self._source)
        self._answer = []
        self._dragging = False; self._rebuild()

    def get_answer(self) -> str: return "".join(self._answer)

    def _rebuild(self) -> None:
        self._build_ans(); self._build_src()

    def _build_ans(self) -> None:
        for c in list(self._ans_row.winfo_children()): c.destroy()
        if not self._answer:
            tk.Label(self._ans_row, text="Click or drag words here",
                     bg="#0d1526", fg="#334155", font=(F.FAMILY, 10, "italic")).pack(pady=6)
            return
        for i, word in enumerate(self._answer):
            chip = tk.Label(self._ans_row, text=word, bg=self._ANS, fg="#93c5fd",
                            font=(F.FAMILY, 13, "bold"), padx=11, pady=5, cursor="fleur", relief="flat")
            chip.pack(side="left", padx=2, pady=2)
            chip.bind("<ButtonPress-1>",   lambda e, idx=i, b=chip: self._on_press(e, idx, b, from_src=False))
            chip.bind("<B1-Motion>",       self._on_motion)
            chip.bind("<ButtonRelease-1>", self._on_release)

    def _build_src(self) -> None:
        for c in list(self._src_row.winfo_children()): c.destroy()
        for i, word in enumerate(self._source):
            chip = tk.Label(self._src_row, text=word, bg=self._SRC, fg="#ffffff",
                            font=(F.FAMILY, 13, "bold"), padx=11, pady=5, cursor="hand2", relief="flat")
            chip.pack(side="left", padx=3, pady=2)
            # DODATO: Sada i donji čipovi imaju press i motion bind za drag
            chip.bind("<ButtonPress-1>",   lambda e, idx=i, b=chip: self._on_press(e, idx, b, from_src=True))
            chip.bind("<B1-Motion>",       self._on_motion)
            chip.bind("<ButtonRelease-1>", self._on_release)

    def _on_press(self, e, idx: int, chip: tk.Label, from_src: bool) -> None:
        self._press_x, self._press_y = e.x_root, e.y_root
        self._press_idx = idx
        self._from_src = from_src
        self._dragging = False
        chip.grab_set()

    def _on_motion(self, e) -> None:
        if not self._dragging:
            if abs(e.x_root - self._press_x) < 6 and abs(e.y_root - self._press_y) < 6: return
            self._dragging = True
            self._drag_idx = self._press_idx

            # Uzmi reč iz odgovarajuće liste
            lst = self._source if self._from_src else self._answer
            word = lst[self._drag_idx] if 0 <= self._drag_idx < len(lst) else "?"

            root = self.winfo_toplevel()
            self._kill_ghost()
            self._ghost = tk.Label(root, text=word, bg=self._LIFT, fg="#000000",
                                   font=(F.FAMILY, 13, "bold"), padx=11, pady=5, relief="flat")
            self._ghost.lift()

            if not self._from_src:
                self._update_gap(self._drag_idx)

        if self._ghost and self._ghost.winfo_exists():
            root = self.winfo_toplevel()
            self._ghost.place(x=e.x_root - root.winfo_rootx() - 25, y=e.y_root - root.winfo_rooty() - 18)

        # Provera pozicije za drop zonu
        ans_y_top = self._ans_bg.winfo_rooty()
        ans_y_bot = ans_y_top + self._ans_bg.winfo_height()

        if ans_y_top - 20 <= e.y_root <= ans_y_bot + 20:
            # UNUTAR GORNJE ZONE
            self._ghost.config(bg=self._LIFT)
            self._drop_idx = self._find_drop(e.x_root)
            self._update_gap(self._drop_idx if self._from_src else self._drop_idx)
        else:
            # VAN ZONE
            if not self._from_src:
                self._ghost.config(bg=C.DANGER) # Crveno ako izbacujemo
            self._drop_idx = -1
            self._update_gap(-1)

    def _on_release(self, e) -> None:
        try: e.widget.grab_release()
        except: pass
        self._kill_ghost()

        ans_y_top = self._ans_bg.winfo_rooty()
        ans_y_bot = ans_y_top + self._ans_bg.winfo_height()
        in_zone = (ans_y_top - 20 <= e.y_root <= ans_y_bot + 20)

        # 1. KLIK (bez draga)
        if not self._dragging:
            if self._from_src:
                if 0 <= self._press_idx < len(self._source):
                    self._answer.append(self._source.pop(self._press_idx))
            else:
                if 0 <= self._press_idx < len(self._answer):
                    self._source.append(self._answer.pop(self._press_idx))

        # 2. DRAG AND DROP
        else:
            if self._from_src:
                if in_zone and 0 <= self._drag_idx < len(self._source):
                    word = self._source.pop(self._drag_idx)
                    dest = self._find_drop(e.x_root)
                    self._answer.insert(dest, word)
            else:
                if in_zone:
                    if 0 <= self._drag_idx < len(self._answer):
                        word = self._answer.pop(self._drag_idx)
                        dest = self._find_drop(e.x_root)
                        ins = dest if dest <= self._drag_idx else dest - 1
                        self._answer.insert(max(0, ins), word)
                else:
                    # Izbačeno napolje
                    if 0 <= self._drag_idx < len(self._answer):
                        self._source.append(self._answer.pop(self._drag_idx))

        self._dragging = False
        self._rebuild()

    def _find_drop(self, x_root: int) -> int:
        chips = [c for c in self._ans_row.winfo_children() if isinstance(c, tk.Label) and c.winfo_viewable()]
        for i, c in enumerate(chips):
            if x_root < c.winfo_rootx() + c.winfo_width() // 2: return i
        return len(self._answer)

    def _update_gap(self, gap_idx: int) -> None:
        chips = [c for c in self._ans_row.winfo_children() if isinstance(c, tk.Label)]
        for i, c in enumerate(chips):
            if i == gap_idx:
                c.config(bg="#1a2a4a", fg="#1a2a4a") # "Rupa"
            else:
                c.config(bg=self._ANS, fg="#93c5fd")

    def _kill_ghost(self) -> None:
        if self._ghost:
            try: self._ghost.destroy()
            except: pass
            self._ghost = None

    def mark_correct(self) -> None:
        for c in self._ans_row.winfo_children():
            try: c.config(bg=self._OK, fg="#ffffff")
            except: pass

    def mark_wrong(self) -> None:
        for c in self._ans_row.winfo_children():
            try: c.config(bg=self._ERR, fg="#ffffff")
            except: pass
        self.after(600, self._rebuild)


class AudioRecordButton(tk.Frame):
    CHUNK, RATE = 1024, 16000
    def __init__(self, parent, on_recorded: Callable[[bytes], None], lang: str = "en", **kw):
        kw.setdefault("bg", C.BG); super().__init__(parent, **kw)
        self._on_recorded, self._lang = on_recorded, lang
        self._recording, self._frames = False, []
        self._btn = tk.Button(self, text="🎙  Hold to speak" if lang == "en" else "🎙  Drži da govoriš",
                              bg=C.DANGER, fg=C.TEXT_WHITE, font=F.BODY_B, relief="flat", bd=0, cursor="hand2", padx=S.XL, pady=S.MD)
        self._btn.pack()
        if PYAUDIO_OK:
            self._btn.bind("<ButtonPress-1>", self._start_rec)
            self._btn.bind("<ButtonRelease-1>", self._stop_rec)
        else:
            self._btn.config(text="⚠️ pyaudio missing", state="disabled", bg=C.BG_HOVER, fg=C.TEXT_MUTED)

    def _start_rec(self, e=None):
        if self._recording: return
        self._recording, self._frames = True, []
        self._btn.config(bg="#AA0000", text="🔴  Recording..." if self._lang == "en" else "🔴  Snimam...")
        threading.Thread(target=self._record_loop, daemon=True).start()

    def _stop_rec(self, e=None):
        self._recording = False
        self._btn.config(bg=C.DANGER, text="🎙  Hold to speak" if self._lang == "en" else "🎙  Drži da govoriš")
        if self._frames:
            wav = self._frames_to_wav(self._frames)
            if wav: self.after(0, lambda: self._on_recorded(wav))

    def _record_loop(self):
        import pyaudio as _pa
        pa = _pa.PyAudio()
        stream = pa.open(format=_pa.paInt16, channels=1, rate=self.RATE, input=True, frames_per_buffer=self.CHUNK)
        while self._recording:
            try: self._frames.append(stream.read(self.CHUNK, exception_on_overflow=False))
            except: break
        stream.stop_stream(); stream.close(); pa.terminate()

    def _frames_to_wav(self, frames):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(self.RATE)
            wf.writeframes(b"".join(frames))
        return buf.getvalue()


class DrawingCanvas(tk.Canvas):
    def __init__(self, parent, size: int = 220, **kw):
        kw.setdefault("bg", "#FFFFFF" if not C.is_dark() else "#1E1E1E")
        kw.setdefault("highlightthickness", 2); kw.setdefault("highlightbackground", C.BORDER)
        super().__init__(parent, width=size, height=size, **kw)
        self._last_x = self._last_y = None; self._size = size
        self.bind("<ButtonPress-1>", self._on_press); self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release); self._draw_grid()
        tk.Button(parent, text="✕ Clear", bg=C.BG, fg=C.TEXT_MUTED, font=F.SMALL, relief="flat", bd=0, command=self._clear).pack(pady=(2, 0))

    def _draw_grid(self):
        mid = self._size // 2
        self.create_line(mid, 0, mid, self._size, fill=C.BORDER, dash=(4, 4))
        self.create_line(0, mid, self._size, mid, fill=C.BORDER, dash=(4, 4))

    def _clear(self): self.delete("all"); self._draw_grid()
    def _on_press(self, e): self._last_x, self._last_y = e.x, e.y
    def _on_drag(self, e):
        if self._last_x is not None:
            color = "#1A1A2E" if not C.is_dark() else "#E8E9F0"
            self.create_line(self._last_x, self._last_y, e.x, e.y, fill=color, width=3, capstyle="round", smooth=True)
        self._last_x, self._last_y = e.x, e.y
    def _on_release(self, e): self._last_x = self._last_y = None