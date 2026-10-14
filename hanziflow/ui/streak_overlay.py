"""
ui/streak_overlay.py — Fullscreen Streak Fire Animation + Daily Review

Pozivati:
    from .streak_overlay import StreakFireOverlay
    StreakFireOverlay.show(root, profile, lang="en")

Prikazuje:
  1. Fullscreen vatrena animacija (canvas + particles)
  2. Motivacioni tekst
  3. Auto-nestaje posle 3.5s ili na klik → fade out
  4. Zatim: Daily Review panel (yesterday's stats) sa slide-in
"""
from __future__ import annotations
import math, random, threading
import tkinter as tk
from datetime import date, timedelta
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
#  Lokalizacija
# ─────────────────────────────────────────────────────────────────────────────

_MESSAGES = {
    "en": [
        "🔥 Streak ON!",
        "🔥 Keep it up!",
        "🔥 You're on fire!",
        "🔥 Consistent learner!",
        "🔥 Daily grind pays off!",
    ],
    "sr": [
        "🔥 Streak upaljen!",
        "🔥 Samo nastavi!",
        "🔥 Goriš danas!",
        "🔥 Svaki dan se isplati!",
        "🔥 Odličan napredak!",
    ],
}

_SUB = {
    "en": "Complete a session every day to keep your streak alive.",
    "sr": "Završavaj sesije svaki dan da bi sačuvao streak.",
}

_REVIEW_TITLE = {"en": "Yesterday's Review", "sr": "Juče — pregled"}
_REVIEW_NONE  = {"en": "No data for yesterday.", "sr": "Nema podataka za juče."}
_XP_LBL       = {"en": "XP earned", "sr": "Zarađeni XP"}
_ACC_LBL      = {"en": "Accuracy", "sr": "Tačnost"}
_WORDS_LBL    = {"en": "Words practiced", "sr": "Reči uvežbano"}
_STR_LBL      = {"en": "Streak", "sr": "Streak"}
_CLOSE_LBL    = {"en": "Let's go! →", "sr": "Hajdemo! →"}
_STREAK_LBL   = {"en": "{} day streak 🔥", "sr": "{} dana streak 🔥"}


# ─────────────────────────────────────────────────────────────────────────────
#  Review data builder (lokalno — bez API poziva)
# ─────────────────────────────────────────────────────────────────────────────

def _build_review(profile) -> dict | None:
    """Vraća rečnik sa podacima od juče iz profila."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    xp = profile.daily_xp_history.get(yesterday, 0)
    if xp == 0:
        return None

    total    = getattr(profile, "total_answered", 0)
    correct  = getattr(profile, "total_correct",  0)
    accuracy = round(correct / max(total, 1) * 100)
    vocab    = len(getattr(profile, "vocab", []))

    return {
        "date":     yesterday,
        "xp":       xp,
        "accuracy": accuracy,
        "vocab":    vocab,
        "streak":   getattr(profile, "streak", 0),
        "goal":     getattr(profile, "daily_goal", 100),
        "goal_met": xp >= getattr(profile, "daily_goal", 100),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Fire Particle
# ─────────────────────────────────────────────────────────────────────────────

class _Particle:
    __slots__ = ("x", "y", "vx", "vy", "r", "life", "max_life", "color_idx")

    COLORS = ["#FF1A00", "#FF4500", "#FF6600", "#FF8C00", "#FFA500",
              "#FFB833", "#FFD700", "#FFEC8B"]

    def __init__(self, sw: int, sh: int):
        self.x       = random.randint(sw // 5, sw * 4 // 5)
        self.y       = sh + random.randint(0, 80)
        self.vx      = random.uniform(-1.5, 1.5)
        self.vy      = random.uniform(-4.5, -2.5)
        self.r       = random.randint(8, 28)
        self.life    = 0
        self.max_life = random.randint(40, 80)
        self.color_idx = random.randint(0, 3)

    def step(self):
        self.x     += self.vx + random.uniform(-0.5, 0.5)
        self.y     += self.vy
        self.vy    *= 0.98
        self.r     = max(2, self.r - 0.25)
        self.life  += 1
        if self.life % 6 == 0 and self.color_idx < len(self.COLORS) - 1:
            self.color_idx += 1

    @property
    def color(self) -> str:
        return self.COLORS[self.color_idx]

    @property
    def alive(self) -> bool:
        return self.life < self.max_life and self.r > 2


# ─────────────────────────────────────────────────────────────────────────────
#  Main Overlay Class
# ─────────────────────────────────────────────────────────────────────────────

class StreakFireOverlay:

    @staticmethod
    def show(root: tk.Tk, profile, lang: str = "en") -> None:
        """Prikazuje fullscreen fire overlay. Non-blocking."""
        try:
            _StreakOverlayImpl(root, profile, lang)
        except Exception as e:
            print(f"[StreakFireOverlay] error: {e}")


class _StreakOverlayImpl:

    FIRE_DURATION_MS = 3500   # koliko dugo gori vatrica
    FRAME_MS         = 40     # ~25 fps
    FADE_STEPS       = 12

    def __init__(self, root: tk.Tk, profile, lang: str):
        self._root    = root
        self._profile = profile
        self._lang    = lang
        self._closed  = False

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        self._sw, self._sh = sw, sh

        # ── Fullscreen overlay ──────────────────────────────────────────────
        self._win = tk.Toplevel(root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.attributes("-alpha",    0.0)
        self._win.geometry(f"{sw}x{sh}+0+0")
        self._win.configure(bg="#0D0000")

        self._cv = tk.Canvas(self._win, bg="#0D0000",
                             highlightthickness=0, width=sw, height=sh)
        self._cv.pack(fill="both", expand=True)

        # ── Text overlay ────────────────────────────────────────────────────
        msg = random.choice(_MESSAGES.get(lang, _MESSAGES["en"]))
        streak_n = getattr(profile, "streak", 1)
        streak_txt = _STREAK_LBL[lang].format(streak_n)

        self._cv.create_text(sw // 2, sh // 2 - 60,
                             text=streak_txt,
                             font=("Segoe UI Emoji", 28, "bold"),
                             fill="#FFD700", tags="txt")
        self._cv.create_text(sw // 2, sh // 2,
                             text=msg,
                             font=("Segoe UI Emoji", 36, "bold"),
                             fill="#FFFFFF", tags="txt")
        self._cv.create_text(sw // 2, sh // 2 + 56,
                             text=_SUB.get(lang, ""),
                             font=("Segoe UI Emoji", 13),
                             fill="#FFCC88", tags="txt")
        self._cv.create_text(sw // 2, sh - 60,
                             text="[ tap to continue ]",
                             font=("Segoe UI Emoji", 11),
                             fill="#FF8844", tags="txt")

        # ── Particles ───────────────────────────────────────────────────────
        self._particles: list[_Particle] = [
            _Particle(sw, sh) for _ in range(55)
        ]
        self._particle_ids: list = []

        # ── Events ──────────────────────────────────────────────────────────
        self._win.bind("<Button-1>", lambda e: self._close_fire())
        self._win.bind("<Key>",      lambda e: self._close_fire())

        # ── Sound ───────────────────────────────────────────────────────────
        try:
            from .views import __file__ as _vf  # noqa
            from ..core.sounds import play as _snd
            _snd("streak")
        except Exception:
            pass

        # ── Fade in ─────────────────────────────────────────────────────────
        self._fade_in()

    # ── Fade in ───────────────────────────────────────────────────────────────

    def _fade_in(self, step: int = 0) -> None:
        alpha = min(1.0, step / self.FADE_STEPS)
        try:
            self._win.attributes("-alpha", alpha)
        except tk.TclError:
            return
        if alpha < 1.0:
            self._win.after(20, lambda: self._fade_in(step + 1))
        else:
            self._animate_frame()
            self._win.after(self.FIRE_DURATION_MS, self._close_fire)

    # ── Particle animation ────────────────────────────────────────────────────

    def _animate_frame(self) -> None:
        if self._closed:
            return
        try:
            cv = self._cv
            sw, sh = self._sw, self._sh

            # Delete old particle drawings
            for pid in self._particle_ids:
                cv.delete(pid)
            self._particle_ids.clear()

            # Spawn new particles
            if len(self._particles) < 70:
                for _ in range(3):
                    self._particles.append(_Particle(sw, sh))

            # Draw & step
            dead = []
            for p in self._particles:
                if not p.alive:
                    dead.append(p)
                    continue
                x1, y1 = p.x - p.r, p.y - p.r
                x2, y2 = p.x + p.r, p.y + p.r
                pid = cv.create_oval(x1, y1, x2, y2,
                                     fill=p.color, outline="",
                                     tags="particle")
                # Keep text on top
                cv.tag_raise("txt")
                self._particle_ids.append(pid)
                p.step()

            for p in dead:
                self._particles.remove(p)

            self._win.after(self.FRAME_MS, self._animate_frame)
        except tk.TclError:
            pass

    # ── Close & show review ───────────────────────────────────────────────────

    def _close_fire(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._fade_out(step=0)

    def _fade_out(self, step: int) -> None:
        alpha = max(0.0, 1.0 - step / self.FADE_STEPS)
        try:
            self._win.attributes("-alpha", alpha)
        except tk.TclError:
            self._show_review()
            return
        if alpha > 0:
            self._win.after(18, lambda: self._fade_out(step + 1))
        else:
            try:
                self._win.destroy()
            except tk.TclError:
                pass
            self._win.after(100, self._show_review)

    # ── Daily Review ─────────────────────────────────────────────────────────

    def _show_review(self) -> None:
        try:
            review = _build_review(self._profile)
            _DailyReviewPanel(self._root, self._profile, review, self._lang)
        except Exception as e:
            print(f"[StreakFireOverlay] review error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Daily Review Panel
# ─────────────────────────────────────────────────────────────────────────────

class _DailyReviewPanel:

    W, H = 480, 380

    def __init__(self, root: tk.Tk, profile, review: dict | None, lang: str):
        self._root = root
        self._lang = lang

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x  = (sw - self.W) // 2
        y  = (sh - self.H) // 2

        self._win = tk.Toplevel(root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.attributes("-alpha", 0.0)
        self._win.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self._win.configure(bg="#12121E")
        self._win.bind("<Button-1>", lambda e: self._close())

        self._build(review)
        self._slide_in()

    def _build(self, review: dict | None) -> None:
        win = self._win
        W   = self.W
        lang = self._lang

        # ── Background card ──────────────────────────────────────────────────
        cv = tk.Canvas(win, bg="#12121E", highlightthickness=0, width=W, height=self.H)
        cv.pack(fill="both", expand=True)

        # Glow border
        cv.create_rectangle(4, 4, W - 4, self.H - 4,
                             outline="#FF6600", width=2)
        cv.create_rectangle(8, 8, W - 8, self.H - 8,
                             outline="#FF440055", width=1)

        y = 28
        # Title
        cv.create_text(W // 2, y, text=_REVIEW_TITLE.get(lang, "Review"),
                       font=("Segoe UI Emoji", 16, "bold"),
                       fill="#FFD700")
        y += 32

        if review is None:
            cv.create_text(W // 2, self.H // 2,
                           text=_REVIEW_NONE.get(lang, "No data."),
                           font=("Segoe UI Emoji", 13),
                           fill="#888888")
        else:
            # Date line
            cv.create_text(W // 2, y,
                           text=review["date"],
                           font=("Segoe UI Emoji", 11),
                           fill="#888888")
            y += 30

            # Stat cards (4 boxes)
            stats = [
                (_XP_LBL[lang],   str(review["xp"]),      "#FFD700"),
                (_ACC_LBL[lang],  f"{review['accuracy']}%","#00CC66"),
                (_WORDS_LBL[lang],str(review["vocab"]),    "#50C8FF"),
                (_STR_LBL[lang],  f"{review['streak']} 🔥","#FF6600"),
            ]

            box_w = (W - 60) // 4
            bx    = 30
            for label, val, color in stats:
                # Box bg
                cv.create_rectangle(bx, y, bx + box_w - 6, y + 72,
                                    fill="#1E1E30", outline=color + "44", width=1)
                cv.create_text(bx + (box_w - 6) // 2, y + 22,
                               text=val, font=("Segoe UI Emoji", 20, "bold"),
                               fill=color)
                cv.create_text(bx + (box_w - 6) // 2, y + 50,
                               text=label, font=("Segoe UI Emoji", 9),
                               fill="#AAAAAA")
                bx += box_w

            y += 90

            # Goal bar
            goal_met = review["goal_met"]
            bar_label = ("✅ Daily goal reached!" if goal_met
                         else f"XP: {review['xp']} / {review['goal']} goal")
            bar_color = "#00CC66" if goal_met else "#FF8800"
            cv.create_text(W // 2, y,
                           text=bar_label,
                           font=("Segoe UI Emoji", 12, "bold"),
                           fill=bar_color)
            y += 30

            # Progress bar
            bar_w   = W - 80
            bar_pct = min(1.0, review["xp"] / max(review["goal"], 1))
            cv.create_rectangle(40, y, 40 + bar_w, y + 12,
                                 fill="#1E1E1E", outline="#333333")
            if bar_pct > 0:
                cv.create_rectangle(40, y, 40 + int(bar_w * bar_pct), y + 12,
                                     fill=bar_color, outline="")
            y += 26

            # AI-style motivational text
            msgs_ok  = {
                "en": "Yesterday was great! You're building momentum.",
                "sr": "Juče je bilo odlično! Gradite zamah.",
            }
            msgs_bad = {
                "en": "Today is a new chance to shine! Go get it.",
                "sr": "Danas je nova šansa! Hajde, možeš!",
            }
            mot = msgs_ok.get(self._lang, "") if goal_met else msgs_bad.get(self._lang, "")
            cv.create_text(W // 2, y + 4,
                           text=mot,
                           font=("Segoe UI Emoji", 11, "italic"),
                           fill="#CCCCCC", width=W - 60)
            y += 30

        # Close hint
        cv.create_text(W // 2, self.H - 20,
                       text=_CLOSE_LBL.get(lang, "Let's go! →"),
                       font=("Segoe UI Emoji", 11, "bold"),
                       fill="#FF9922")

    # ── Slide in ──────────────────────────────────────────────────────────────

    def _slide_in(self, step: int = 0) -> None:
        steps = 14
        alpha = min(1.0, step / steps)
        try:
            self._win.attributes("-alpha", alpha)
        except tk.TclError:
            return
        if alpha < 1.0:
            self._win.after(18, lambda: self._slide_in(step + 1))
        else:
            # Play reward sound
            try:
                from ..core.sounds import play as _snd
                _snd("achievement")
            except Exception:
                pass
            # Auto close after 6s
            self._win.after(6000, self._close)

    def _close(self) -> None:
        try:
            self._win.destroy()
        except tk.TclError:
            pass