"""
ui/views/arena.py — Word Arena.
FIX: GhostButton fg conflict resolved — arena uses plain tk.Button for custom colors.
"""
from __future__ import annotations
import random, time, threading, logging
import tkinter as tk
from typing import Callable

from ..theme import (C, F, S, PrimaryButton, SuccessButton, DangerButton,
                     flash_widget, pulse_label, ComboOverlay, ConfirmDialog)
from ..widgets import NotificationManager, LevelUpOverlay
from ...core import (Database, UserProfile, Word, check_achievements,
                     play_audio, preload_audio, Leaderboard, play_sound, gemini)
from ...core.adaptive import compute_arena_points, softmax_sample, compute_level

import unicodedata

logger = logging.getLogger("HanziFlow.Arena")


def _meaning(w: Word, lang: str) -> str:
    return w.meaning_en if lang == "en" else w.meaning_sr


def _norm_pinyin(p: str) -> str:
    s = unicodedata.normalize("NFD", p)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("v", "u").lower()


_T = {
    "en": {
        "title": "⚔️  Word Arena",
        "back": "⬅ Back",
        "score": "{}",
        "combo": "🔥 ×{}",
        "time_left": "{}",
        "type_hanzi": "Type Hanzi:",
        "check": "✔",
        "correct": "+{}",
        "wrong": "✗ {}",
        "game_over": "Game Over!",
        "final_score": "{}",
        "best_combo": "Best Combo: ×{}",
        "rank": "{} {}",
        "new_record": "🏆 New Record!",
        "play_again": "▶  Play Again",
        "back_menu": "⬅ Menu",
        "ready": "Get Ready!",
        "ready_sub": "Type Hanzi as fast as you can",
        "start": "⚔️  START",
        "words_left": "{}",
        "time_bonus": "⚡+{}",
        "combo_mult": "×{}",
        "accuracy": "Accuracy",
        "confirm_back_title": "Leave Arena?",
        "confirm_back_msg": "Game in progress. Score will be lost.",
        "confirm_back_yes": "Leave",
        "confirm_back_no": "Keep playing",
    },
    "sr": {
        "title": "⚔️  Word Arena",
        "back": "⬅ Nazad",
        "score": "{}",
        "combo": "🔥 ×{}",
        "time_left": "{}",
        "type_hanzi": "Ukucaj Hanzi:",
        "check": "✔",
        "correct": "+{}",
        "wrong": "✗ {}",
        "game_over": "Kraj igre!",
        "final_score": "{}",
        "best_combo": "Combo: ×{}",
        "rank": "{} {}",
        "new_record": "🏆 Novi rekord!",
        "play_again": "▶  Igraj ponovo",
        "back_menu": "⬅ Meni",
        "ready": "Spremi se!",
        "ready_sub": "Ukucaj Hanzi što brže možeš",
        "start": "⚔️  POČNI",
        "words_left": "{}",
        "time_bonus": "⚡+{}",
        "combo_mult": "×{}",
        "accuracy": "Tačnost",
        "confirm_back_title": "Napusti Arenu?",
        "confirm_back_msg": "Igra u toku. Skor će biti izgubljen.",
        "confirm_back_yes": "Napusti",
        "confirm_back_no": "Nastavi",
    },
}

ARENA_DURATION = 60
WORDS_PER_GAME = 25

_A = {
    "bg":       "#0D0D1E",
    "card":     "#13132A",
    "card2":    "#1A1A35",
    "gold":     "#FFD700",
    "orange":   "#FF6B35",
    "blue":     "#4F8EFF",
    "green":    "#2ECC71",
    "red":      "#E74C3C",
    "muted":    "#5A5A8A",
    "text":     "#E8E8FF",
    "text_dim": "#8888AA",
    "border":   "#2D2D4A",
    "entry_bg": "#1E1E3C",
}


def _arena_btn(parent, text, command, bg, fg="#FFFFFF", font=None):
    """Helper za custom arena dugme (ne koristi GhostButton zbog fg konflikta)."""
    f = font or (F.FAMILY, 12, "bold")
    b = tk.Button(parent, text=text, command=command,
                  bg=bg, fg=fg, font=f, relief="flat", bd=0,
                  cursor="hand2", activebackground=bg, activeforeground=fg,
                  padx=S.MD, pady=S.XS)
    b.bind("<Enter>", lambda e: _btn_lighten(b, bg))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b


def _btn_lighten(btn, color):
    try:
        r = min(255, int(color[1:3], 16) + 25)
        g = min(255, int(color[3:5], 16) + 25)
        b = min(255, int(color[5:7], 16) + 25)
        btn.config(bg=f"#{r:02x}{g:02x}{b:02x}")
    except Exception:
        pass



def _load_global_word_pool(profile, db) -> list:
    """Loads words from ALL users for global arena pool."""
    from ...core.models import Word as _Word
    pool = {}  # hanzi → Word (deduplicated)
    try:
        for username in db.all_usernames():
            user = db.get_user(username)
            if user:
                for w_dict in user.vocab:
                    hanzi = w_dict.get("hanzi", "")
                    if hanzi and hanzi not in pool:
                        pool[hanzi] = _Word.from_dict(w_dict)
    except Exception as e:
        import logging
        logging.getLogger("HanziFlow.Arena").warning(f"Global pool error: {e}")
    # Always include current user's words
    for w_dict in profile.vocab:
        hanzi = w_dict.get("hanzi", "")
        if hanzi and hanzi not in pool:
            pool[hanzi] = _Word.from_dict(w_dict)
    return list(pool.values())

class ArenaView(tk.Frame):

    def __init__(self, parent, profile: UserProfile,
                 notif: NotificationManager, on_back: Callable):
        super().__init__(parent, bg=_A["bg"])
        self._profile = profile
        self._db      = Database()
        self._lang    = profile.lang
        self._db      = Database()
        self._notif   = notif
        self._on_back = on_back

        self._running        = False
        self._score          = 0
        self._combo          = 0
        self._best_combo     = 0
        self._correct_streak = 0
        self._total_attempts = 0
        self._total_correct  = 0
        self._time_left      = ARENA_DURATION
        self._idx            = 0
        self._words: list[Word] = []
        self._q_start        = 0.0
        self._blocking       = False

        try:
            self._build()
        except Exception as e:
            logger.error(f"ArenaView init error: {e}", exc_info=True)

    def _t(self, key, *args):
        txt = _T[self._lang].get(key, key)
        return txt.format(*args) if args else txt

    def _build(self):
        # Header — plain tk.Button, brez GhostButton-a (izbjegava fg konflikt)
        hdr = tk.Frame(self, bg=_A["card"]); hdr.pack(fill="x")

        back_btn = tk.Button(hdr, text=self._t("back"),
                             command=self._confirm_back,
                             bg=_A["card"], fg=_A["muted"],
                             font=F.BODY, relief="flat", bd=0,
                             cursor="hand2",
                             activebackground=_A["card2"],
                             activeforeground=_A["text"])
        back_btn.pack(side="left", padx=S.MD, pady=S.SM)
        back_btn.bind("<Enter>", lambda e: back_btn.config(fg=_A["text"]))
        back_btn.bind("<Leave>", lambda e: back_btn.config(fg=_A["muted"]))

        tk.Label(hdr, text=self._t("title"), bg=_A["card"],
                 fg=_A["gold"], font=F.TITLE).pack(side="left")

        self._content = tk.Frame(self, bg=_A["bg"])
        self._content.pack(fill="both", expand=True)
        self._show_ready()

    def _show_ready(self):
        for c in self._content.winfo_children(): c.destroy()
        f = tk.Frame(self._content, bg=_A["bg"]); f.pack(expand=True)

        tk.Label(f, text="⚔️", bg=_A["bg"], font=(F.FAMILY, 56)).pack(pady=(S.LG, S.SM))
        tk.Label(f, text=self._t("ready"), bg=_A["bg"],
                 fg=_A["gold"], font=(F.FAMILY, 28, "bold")).pack()
        tk.Label(f, text=self._t("ready_sub"), bg=_A["bg"],
                 fg=_A["muted"], font=F.LABEL).pack(pady=(S.XS, S.XL))

        words = _load_global_word_pool(self._profile, self._db)

        info_row = tk.Frame(f, bg=_A["bg"]); info_row.pack()

        def info_box(parent, label, value, color):
            box = tk.Frame(parent, bg=_A["card"], highlightbackground=_A["border"],
                           highlightthickness=1)
            box.pack(side="left", padx=S.SM, ipadx=S.LG, ipady=S.SM)
            tk.Label(box, text=value, bg=_A["card"], fg=color, font=F.H2).pack()
            tk.Label(box, text=label, bg=_A["card"], fg=_A["muted"], font=F.TINY).pack()

        info_box(info_row, "Words", str(len(words)), _A["blue"])
        info_box(info_row, "Time", f"{ARENA_DURATION}s", _A["orange"])
        info_box(info_row, "Best", str(self._profile.arena_score), _A["gold"])

        start_btn = _arena_btn(f, self._t("start"), self._start_game,
                               _A["orange"], "#FFFFFF", (F.FAMILY, 16, "bold"))
        start_btn.config(padx=S.XL, pady=S.MD)
        start_btn.pack(pady=S.XL)

    def _start_game(self):
        try:
            words = _load_global_word_pool(self._profile, self._db)
            if not words:
                self._notif.show("Add some words first!", "error"); return

            sample = softmax_sample(words, min(WORDS_PER_GAME, len(words)))
            random.shuffle(sample)
            self._words = sample

            self._running = True
            self._score = 0; self._combo = 0; self._best_combo = 0
            self._correct_streak = 0; self._total_attempts = 0; self._total_correct = 0
            self._idx = 0; self._time_left = ARENA_DURATION
            self._blocking = False

            for c in self._content.winfo_children(): c.destroy()
            game = tk.Frame(self._content, bg=_A["bg"]); game.pack(fill="both", expand=True)
            self._game_frame = game

            # HUD
            hud = tk.Frame(game, bg=_A["card"]); hud.pack(fill="x")

            timer_outer = tk.Frame(hud, bg=_A["card"]); timer_outer.pack(side="left", padx=S.MD, pady=S.SM)
            self._timer_lbl = tk.Label(timer_outer, text="60", bg=_A["card"],
                                       fg=_A["red"], font=(F.FAMILY, 30, "bold"), width=3)
            self._timer_lbl.pack()
            tk.Label(timer_outer, text="sec", bg=_A["card"], fg=_A["muted"], font=F.TINY).pack()

            self._timer_bar = tk.Canvas(hud, height=6, bg=_A["card"], highlightthickness=0, bd=0)
            self._timer_bar.pack(side="left", fill="x", expand=True, padx=(0, S.MD), pady=S.SM)

            score_outer = tk.Frame(hud, bg=_A["card"]); score_outer.pack(side="right", padx=S.MD, pady=S.SM)
            self._score_lbl = tk.Label(score_outer, text="0", bg=_A["card"],
                                       fg=_A["gold"], font=(F.FAMILY, 30, "bold"), width=6)
            self._score_lbl.pack()
            tk.Label(score_outer, text="pts", bg=_A["card"], fg=_A["muted"], font=F.TINY).pack()

            self._combo_lbl = tk.Label(hud, text="", bg=_A["card"],
                                       fg=_A["orange"], font=(F.FAMILY, 16, "bold"))
            self._combo_lbl.pack(side="right", padx=S.LG)

            self._lives_lbl = tk.Label(hud, text="❤️❤️❤️", bg=_A["card"],
                                       fg=_A["red"], font=(F.FAMILY, 13))
            self._lives_lbl.pack(side="right", padx=S.MD)

            self._q_frame = tk.Frame(game, bg=_A["bg"])
            self._q_frame.pack(expand=True, fill="both")

            self._tick_timer()
            self._show_arena_word()

            for w in self._words[:3]:
                try: preload_audio(w.hanzi)
                except Exception: pass

        except Exception as e:
            logger.error(f"Arena start error: {e}", exc_info=True)
            self._show_ready()

    def _tick_timer(self):
        if not self._running: return
        self._time_left -= 1
        remaining = self._time_left
        color = _A["red"] if remaining <= 10 else _A["orange"] if remaining <= 20 else _A["text"]
        try:
            self._timer_lbl.config(text=str(remaining), fg=color)
            w = self._timer_bar.winfo_width()
            self._timer_bar.delete("all")
            if w:
                pct = remaining / ARENA_DURATION
                bw  = max(2, int(w * pct))
                self._timer_bar.create_rectangle(0, 0, w, 6, fill=_A["border"], outline="")
                self._timer_bar.create_rectangle(0, 0, bw, 6, fill=color, outline="")
        except tk.TclError:
            return
        if remaining <= 0:
            self._end_game(); return
        self.after(1000, self._tick_timer)

    def _show_arena_word(self):
        if self._blocking: return
        for c in self._q_frame.winfo_children(): c.destroy()
        if self._idx >= len(self._words) or not self._running:
            self._end_game(); return

        w = self._words[self._idx]
        self._q_start = time.time()
        try: preload_audio(w.hanzi)
        except Exception: pass

        center = tk.Frame(self._q_frame, bg=_A["bg"]); center.pack(expand=True)

        tk.Label(center, text=f"{self._idx+1} / {len(self._words)}",
                 bg=_A["bg"], fg=_A["muted"], font=F.TINY).pack(pady=(S.SM, 0))

        tk.Label(center, text=_meaning(w, self._lang), bg=_A["bg"],
                 fg=_A["text"], font=(F.FAMILY, 22, "bold"), wraplength=440).pack(pady=S.MD)

        tk.Button(center, text="🔊", bg=_A["bg"], fg=_A["muted"],
                  font=(F.FAMILY, 16), relief="flat", bd=0, cursor="hand2",
                  command=lambda: play_audio(w.hanzi)).pack()

        entry = tk.Entry(center, font=(F.FAMILY, 26), justify="center", width=9,
                         bg=_A["entry_bg"], fg=_A["gold"],
                         insertbackground=_A["gold"],
                         relief="flat",
                         highlightbackground=_A["gold"], highlightthickness=2)
        entry.pack(pady=S.MD, ipady=S.SM)
        self.after(100, entry.focus_set)

        fb = tk.Label(center, text="", bg=_A["bg"], font=(F.FAMILY, 16, "bold"), width=20)
        fb.pack(pady=S.XS)

        attempts = [0]

        def update_lives():
            hearts = "❤️" * (3 - attempts[0]) + "🖤" * attempts[0]
            try: self._lives_lbl.config(text=hearts)
            except tk.TclError: pass

        def check(ev=None):
            ans = entry.get().strip()
            entry.delete(0, "end")
            rt  = time.time() - self._q_start
            self._total_attempts += 1

            if ans == w.hanzi:
                try: play_sound("correct")
                except Exception: pass
                self._combo += 1
                self._best_combo = max(self._best_combo, self._combo)
                self._correct_streak += 1
                self._total_correct  += 1
                pts = compute_arena_points(True, rt, self._combo, w.xp)
                self._score += pts
                attempts[0] = 0; update_lives()
                try:
                    self._score_lbl.config(text=str(self._score))
                    pulse_label(self._score_lbl)
                except tk.TclError: pass
                if self._combo >= 2:
                    try: self._combo_lbl.config(text=self._t("combo_mult", self._combo))
                    except tk.TclError: pass
                fb.config(text=self._t("correct", pts), fg=_A["gold"])

                if self._combo in (5, 8, 10, 15, 20):
                    self._blocking = True
                    ComboOverlay.show_combo(self.winfo_toplevel(), self._combo,
                        on_done=self._unblock_and_next)
                else:
                    self._idx += 1
                    self.after(400, self._show_arena_word)

                try:
                    new_ach = check_achievements(self._profile, event="arena_combo", combo=self._combo)
                    for ach in new_ach: self._notif.show_achievement(ach)
                except Exception: pass

            else:
                try: play_sound("wrong")
                except Exception: pass
                attempts[0] += 1; update_lives()
                self._combo = 0; self._correct_streak = 0
                try: self._combo_lbl.config(text="")
                except tk.TclError: pass

                if attempts[0] >= 3:
                    flash_widget(entry, _A["red"], _A["entry_bg"], times=2)
                    fb.config(text=f"✅ {w.hanzi}  ({w.pinyin})", fg="#FF8888")
                    entry.config(state="disabled")
                    self._idx += 1
                    self.after(1200, self._show_arena_word)
                else:
                    fb.config(text=self._t("wrong", w.hanzi), fg=_A["red"])
                    flash_widget(entry, _A["red"], _A["entry_bg"], times=1)

        entry.bind("<Return>", check)
        _arena_btn(center, self._t("check"), check, _A["orange"]).pack()

    def _unblock_and_next(self):
        self._blocking = False
        self._idx += 1
        self._show_arena_word()

    def _end_game(self):
        self._running = False
        is_new_record = False
        try:
            is_new_record = self._score > self._profile.arena_score
            if is_new_record:
                self._profile.arena_score = self._score
            self._profile.total_correct  += self._total_correct
            self._profile.total_answered += self._total_attempts
            try:
                from ...xp_config import arena_score_to_xp as _a2x
                xp_reward = _a2x(self._score)
            except ImportError:
                xp_reward = max(10, self._score // 10)
            self._profile.xp       += xp_reward
            self._profile.daily_xp += xp_reward
            self._db.save_user(self._profile)
            try: Leaderboard().update(self._profile)
            except Exception: pass
            try:
                new_ach = check_achievements(self._profile, event="arena_done",
                                             score=self._score, combo=self._best_combo)
                for ach in new_ach: self._notif.show_achievement(ach)
            except Exception: pass
        except Exception as e:
            logger.error(f"Arena end_game save error: {e}", exc_info=True)

        try:
            today = __import__("datetime").date.today().isoformat()
            if today not in self._profile.completed_days:
                self._profile.completed_days.append(today)
            gained = self._profile.award_session_streak()
            if gained:
                self._notif.show(
                    f"🔥 Streak +1! Day {self._profile.streak}" if self._profile.lang == "en"
                    else f"🔥 Streak +1! Dan {self._profile.streak}", "success")
            self._db.save_user(self._profile)
        except Exception as e:
            logger.warning(f"Arena streak error: {e}")

        for c in self._content.winfo_children(): c.destroy()
        f = tk.Frame(self._content, bg=_A["bg"]); f.pack(fill="both", expand=True)

        tk.Label(f, text=self._t("game_over"), bg=_A["bg"],
                 fg=_A["gold"], font=(F.FAMILY, 28, "bold")).pack(pady=(S.XL, S.SM))
        tk.Label(f, text=str(self._score), bg=_A["bg"],
                 fg=_A["gold"], font=(F.FAMILY, 64, "bold")).pack()
        tk.Label(f, text="points", bg=_A["bg"], fg=_A["muted"], font=F.LABEL).pack()

        if is_new_record:
            tk.Label(f, text=self._t("new_record"), bg=_A["bg"],
                     fg=_A["orange"], font=F.TITLE).pack(pady=S.SM)

        stats = tk.Frame(f, bg=_A["bg"]); stats.pack(pady=S.LG)
        acc = int(self._total_correct / max(1, self._total_attempts) * 100)

        def stat(parent, label, value, color):
            b = tk.Frame(parent, bg=_A["card"], highlightbackground=_A["border"], highlightthickness=1)
            b.pack(side="left", padx=S.SM, ipadx=S.LG, ipady=S.SM)
            tk.Label(b, text=value, bg=_A["card"], fg=color, font=F.H2).pack()
            tk.Label(b, text=label, bg=_A["card"], fg=_A["muted"], font=F.TINY).pack()

        stat(stats, "Best Combo", f"×{self._best_combo}", _A["orange"])
        stat(stats, self._t("accuracy"), f"{acc}%",
             _A["green"] if acc >= 70 else _A["orange"])
        stat(stats, "XP Earned", f"+{max(10, self._score//10)}", _A["gold"])
        rank = self._profile.get_rank()
        stat(stats, "Rank", f"{rank['icon']} {rank['name']}", C.PRIMARY)

        btn_row = tk.Frame(f, bg=_A["bg"]); btn_row.pack(pady=S.LG)
        play_btn = _arena_btn(btn_row, self._t("play_again"), self._show_ready,
                              _A["orange"], "#FFFFFF", (F.FAMILY, 13, "bold"))
        play_btn.config(padx=S.XL, pady=S.SM)
        play_btn.pack(side="left", padx=S.SM)

        back_btn = tk.Button(btn_row, text=self._t("back_menu"),
                             command=self._on_back,
                             bg=_A["bg"], fg=_A["muted"],
                             font=F.BODY, relief="flat", bd=0, cursor="hand2",
                             activebackground=_A["card"])
        back_btn.pack(side="left", padx=S.SM)

    def _confirm_back(self):
        if not self._running:
            self._on_back(); return
        ConfirmDialog(self,
                      title=self._t("confirm_back_title"),
                      message=self._t("confirm_back_msg"),
                      yes_text=self._t("confirm_back_yes"),
                      no_text=self._t("confirm_back_no"),
                      on_yes=self._do_back, danger=True)

    def _do_back(self):
        self._running = False
        self._on_back()