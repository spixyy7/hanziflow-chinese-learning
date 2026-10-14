"""
ui/views/quiz.py — Quiz sa 4 moda, combo sistemom, try/except za svaki korak.
FIXES: quiz loading bug (try/except + fallback), custom back popup, combo overlay.
"""
from __future__ import annotations
import logging, random, threading, time
import tkinter as tk
from datetime import date, timedelta
from typing import Callable

from ..theme import (C, F, S, Card, PrimaryButton, SuccessButton, DangerButton,
                     GhostButton, TimerWidget, QuizProgressBar, ComboOverlay,
                     flash_widget, animate_score_pop, pulse_label,
                     ConfirmDialog, bind_hover_translate, hover_card)
from ..widgets import NotificationManager, DrawingCanvas
from ...core import (Database, UserProfile, Word, SessionStats,
                     sm2_update, softmax_sample, WeaknessDetector,
                     check_achievements, play_audio, preload_audio, gemini, play_sound)
from ...core.adaptive import compute_level

import unicodedata

logger = logging.getLogger("HanziFlow.Quiz")


def _meaning(w: Word, lang: str) -> str:
    return w.meaning_en if lang == "en" else w.meaning_sr


def _norm_pinyin(p: str) -> str:
    s = unicodedata.normalize("NFD", p)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("v", "u").lower()


def _get_mode_colors():
    if C.is_dark():
        return {
            "type":    ("#0D1A2E", "✍  Typing"),
            "draw":    ("#1A1500", "✏️  Drawing"),
            "listen":  ("#0D1A14", "🔊  Listening"),
            "meaning": ("#1A0D24", "❓  Meaning"),
            "pinyin":  ("#0D1A2E", "🔤  Pinyin"),
        }
    return {
        "type":    ("#EBF5FB", "✍  Typing"),
        "draw":    ("#FEF9E7", "✏️  Drawing"),
        "listen":  ("#EAFAF1", "🔊  Listening"),
        "meaning": ("#F4ECF7", "❓  Meaning"),
        "pinyin":  ("#EBF5FB", "🔤  Pinyin"),
    }


_T = {
    "en": {
        "quiz_title": "Quiz — {} left",
        "session_done": "Session Complete! 🎉",
        "empty": "No words due today!",
        "empty_sub": "Add new words or come back tomorrow.",
        "correct": "Correct! +{} XP",
        "wrong": "Wrong. Correct: {} ({})",
        "type_hanzi": "Type Hanzi:",
        "type_pinyin": "Type Pinyin:",
        "check": "✔  Check",
        "listen_btn": "🔊 Listen",
        "replay_btn": "🔄 Replay",
        "type_heard": "Type the Hanzi you heard:",
        "meaning_q": "What does this mean?",
        "draw_instr": "Draw this character:",
        "draw_submit": "✏️  Check my drawing",
        "draw_analyzing": "🔍  Analyzing...",
        "back": "⬅ Back",
        "confirm_back_title": "Leave Quiz?",
        "confirm_back_msg": "Your progress is saved. You can continue later.",
        "confirm_back_yes": "Leave",
        "confirm_back_no": "Keep going",
        "accuracy": "Accuracy",
        "xp_earned": "XP Earned",
        "avg_speed": "Avg Speed",
        "ai_feedback_title": "🤖 AI Coach says:",
        "loading_feedback": "Analyzing your performance...",
        "session_stats": "Session Stats",
        "back_to_menu": "⬅ Back to Menu",
        "choose_type": "What do you want to practice?",
        "choose_mode": "Choose your mode",
        "type_meaning_hanzi": "Meaning → Characters",
        "type_meaning_hanzi_sub": "Given the meaning — type Hanzi & Pinyin",
        "type_hanzi_meaning": "Characters → Meaning",
        "type_hanzi_meaning_sub": "Given the character — type the meaning",
        "type_pinyin_meaning": "Pinyin → Meaning & Characters",
        "type_pinyin_meaning_sub": "Given pinyin — type meaning and Hanzi",
        "mode_learning": "Learning Mode",
        "mode_learning_sub": "No timer · Mistakes shown instantly · AI helps",
        "mode_challenge": "Challenge Mode",
        "mode_challenge_sub": "Timer · Score + Streak · No hints",
        "step1": "Step 1 of 2",
        "step2": "Step 2 of 2",
        "streak_gained": "🔥 Streak +1! Day {}",
        "streak_shield": "🛡 Shield used! Streak saved at {}",
        "combo_label": "🔥 {} combo",
        "score_label": "Score: {}",
    },
    "sr": {
        "quiz_title": "Kviz — {} preostalo",
        "session_done": "Sesija završena! 🎉",
        "empty": "Nema reči za danas!",
        "empty_sub": "Dodaj nove reči ili se vrati sutra.",
        "correct": "Tačno! +{} XP",
        "wrong": "Netačno. Ispravno: {} ({})",
        "type_hanzi": "Ukucaj Hanzi:",
        "type_pinyin": "Ukucaj Pinyin:",
        "check": "✔  Proveri",
        "listen_btn": "🔊 Poslušaj",
        "replay_btn": "🔄 Ponovi",
        "type_heard": "Ukucaj Hanzi koji si čuo:",
        "meaning_q": "Šta ovo znači?",
        "draw_instr": "Nacrtaj ovaj karakter:",
        "draw_submit": "✏️  Proveri crtanje",
        "draw_analyzing": "🔍  Analiziram...",
        "back": "⬅ Nazad",
        "confirm_back_title": "Napusti Kviz?",
        "confirm_back_msg": "Progres je sačuvan. Možeš nastaviti kasnije.",
        "confirm_back_yes": "Napusti",
        "confirm_back_no": "Nastavi",
        "accuracy": "Tačnost",
        "xp_earned": "Zarađeni XP",
        "avg_speed": "Prosečna brzina",
        "ai_feedback_title": "🤖 AI Trener kaže:",
        "loading_feedback": "Analiziram tvoje performanse...",
        "session_stats": "Statistika sesije",
        "back_to_menu": "⬅ Nazad u meni",
        "choose_type": "Šta želiš da vežbaš?",
        "choose_mode": "Izaberi mod",
        "type_meaning_hanzi": "Značenje → Karakteri",
        "type_meaning_hanzi_sub": "Dato značenje — ukucaj Hanzi & Pinyin",
        "type_hanzi_meaning": "Karakteri → Značenje",
        "type_hanzi_meaning_sub": "Dat karakter — ukucaj značenje",
        "type_pinyin_meaning": "Pinyin → Značenje & Karakteri",
        "type_pinyin_meaning_sub": "Dat pinyin — ukucaj značenje i Hanzi",
        "mode_learning": "Mod učenja",
        "mode_learning_sub": "Bez tajmera · Greške odmah · AI pomaže",
        "mode_challenge": "Mod izazova",
        "mode_challenge_sub": "Tajmer · Score + Streak · Bez hint-ova",
        "step1": "Korak 1 od 2",
        "step2": "Korak 2 od 2",
        "streak_gained": "🔥 Streak +1! Dan {}",
        "streak_shield": "🛡 Štit iskorišten! Streak ostao na {}",
        "combo_label": "🔥 {} combo",
        "score_label": "Skor: {}",
    },
}


class QuizView(tk.Frame):

    def __init__(self, parent, profile: UserProfile,
                 notif: NotificationManager, on_back: Callable):
        super().__init__(parent, bg=C.BG)
        self._profile   = profile
        self._lang      = profile.lang
        self._db        = Database()
        self._notif     = notif
        self._on_back   = on_back
        self._wd        = WeaknessDetector(profile)
        self._stats     = SessionStats()
        self._due: list[Word] = []
        self._idx       = 0
        self._mode      = "type"
        self._direction = "meaning_to_hanzi"
        self._quiz_mode = "learning"
        self._q_start   = 0.0
        self._answered_idx = -1
        # Combo / score tracking
        self._combo     = 0
        self._best_combo= 0
        self._score     = 0
        self._consecutive = 0   # consecutive correct for milestone overlays
        self._blocking_overlay = False  # True while combo/level overlay is playing
        self._pending_next = False      # queued next_word call during overlay

        try:
            self._build()
            self._show_direction_pick()
        except Exception as e:
            logger.error(f"QuizView init error: {e}", exc_info=True)
            self._show_error(str(e))

    def _t(self, key: str, *args) -> str:
        txt = _T[self._lang].get(key, key)
        return txt.format(*args) if args else txt

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # Header bar
        hdr = tk.Frame(self, bg=C.BG_SIDEBAR); hdr.pack(fill="x")
        GhostButton(hdr, text=self._t("back"), command=self._confirm_back).pack(
            side="left", padx=S.MD, pady=S.SM)
        self._lbl_title = tk.Label(hdr, text="", bg=C.BG_SIDEBAR, fg=C.TEXT, font=F.TITLE)
        self._lbl_title.pack(side="left")

        # Score + combo (challenge mode)
        self._score_lbl = tk.Label(hdr, text="", bg=C.BG_SIDEBAR,
                                   fg=C.GOLD, font=F.LABEL_B)
        self._score_lbl.pack(side="right", padx=S.MD)
        self._combo_lbl = tk.Label(hdr, text="", bg=C.BG_SIDEBAR,
                                   fg=C.DANGER, font=F.LABEL_B)
        self._combo_lbl.pack(side="right", padx=S.SM)
        self._lbl_mode = tk.Label(hdr, text="", bg=C.BG_SIDEBAR,
                                  fg=C.TEXT_MUTED, font=F.SMALL)
        self._lbl_mode.pack(side="right", padx=S.MD)

        # Progress bar
        self._prog_bar = QuizProgressBar(self, total=20, bg=C.BG_SIDEBAR)
        self._prog_bar.pack(fill="x")

        self._content = tk.Frame(self, bg=C.BG)
        self._content.pack(fill="both", expand=True)

    # ── Step 1: Tip pitanja ───────────────────────────────────────────────────

    def _show_direction_pick(self):
        try:
            for c in self._content.winfo_children(): c.destroy()
        except Exception: pass
        self._lbl_title.config(text="🧠  Quiz")
        self._lbl_mode.config(text=""); self._score_lbl.config(text=""); self._combo_lbl.config(text="")

        outer = tk.Frame(self._content, bg=C.BG); outer.pack(expand=True)

        # Step indicator
        step_row = tk.Frame(outer, bg=C.BG); step_row.pack(pady=(S.MD, 0))
        tk.Label(step_row, text=self._t("step1"), bg=C.BG, fg=C.TEXT_MUTED, font=F.SMALL).pack(side="left")
        for i, active in enumerate([True, False]):
            tk.Label(step_row, text="●" if active else "○", bg=C.BG,
                     fg=C.PRIMARY if active else C.TEXT_LIGHT, font=(F.FAMILY, 10)).pack(side="left", padx=2)

        tk.Label(outer, text="🧠", bg=C.BG, font=(F.FAMILY, 36)).pack(pady=(S.SM, 0))
        tk.Label(outer, text=self._t("choose_type"), bg=C.BG, fg=C.TEXT, font=F.H2).pack(pady=(S.XS, S.LG))

        options = [
            ("meaning_to_hanzi", self._t("type_meaning_hanzi"), self._t("type_meaning_hanzi_sub"), C.PRIMARY, "✍"),
            ("hanzi_to_meaning", self._t("type_hanzi_meaning"), self._t("type_hanzi_meaning_sub"), C.PURPLE, "👁"),
            ("pinyin_to_meaning", self._t("type_pinyin_meaning"), self._t("type_pinyin_meaning_sub"), C.SUCCESS, "🔤"),
        ]

        for direction, title, sub, color, icon in options:
            def _make_card(d=direction, t=title, s=sub, col=color, ic=icon):
                card = tk.Frame(outer, bg=C.BG_CARD, highlightbackground=C.BORDER,
                                highlightthickness=1, cursor="hand2")
                card.pack(fill="x", padx=S.XXL, pady=S.SM)
                inner = tk.Frame(card, bg=C.BG_CARD)
                inner.pack(fill="x", padx=S.LG, pady=S.MD)
                tk.Label(inner, text=ic, bg=C.BG_CARD, font=(F.FAMILY, 22)).pack(side="left", padx=(0, S.MD))
                right = tk.Frame(inner, bg=C.BG_CARD)
                right.pack(side="left", fill="x", expand=True)
                tk.Label(right, text=t, bg=C.BG_CARD, fg=col, font=F.TITLE).pack(anchor="w")
                tk.Label(right, text=s, bg=C.BG_CARD, fg=C.TEXT_MUTED,
                         font=F.SMALL, wraplength=380, justify="left").pack(anchor="w")

                def _on_click(event=None, _d=d):
                    self._direction = _d
                    self._show_mode_pick()

                def _on_enter(e):
                    card.config(highlightbackground=col)
                    for child in card.winfo_children():
                        try: child.config(bg=C.BG_HOVER)
                        except Exception: pass
                        for gc in child.winfo_children():
                            try: gc.config(bg=C.BG_HOVER)
                            except Exception: pass
                            for ggc in gc.winfo_children():
                                try: ggc.config(bg=C.BG_HOVER)
                                except Exception: pass

                def _on_leave(e):
                    card.config(highlightbackground=C.BORDER)
                    for child in card.winfo_children():
                        try: child.config(bg=C.BG_CARD)
                        except Exception: pass
                        for gc in child.winfo_children():
                            try: gc.config(bg=C.BG_CARD)
                            except Exception: pass
                            for ggc in gc.winfo_children():
                                try: ggc.config(bg=C.BG_CARD)
                                except Exception: pass

                for widget in [card, inner, right] + list(inner.winfo_children()) + list(right.winfo_children()):
                    widget.bind("<Button-1>", _on_click)
                    widget.bind("<Enter>", _on_enter)
                    widget.bind("<Leave>", _on_leave)
                card.bind("<Enter>", _on_enter)
                card.bind("<Leave>", _on_leave)

            _make_card()

    # ── Step 2: Mod ───────────────────────────────────────────────────────────

    def _show_mode_pick(self):
        for c in self._content.winfo_children(): c.destroy()
        self._lbl_title.config(text="🧠  Quiz"); self._lbl_mode.config(text="")

        outer = tk.Frame(self._content, bg=C.BG); outer.pack(expand=True)

        step_row = tk.Frame(outer, bg=C.BG); step_row.pack(pady=(S.MD, 0))
        tk.Label(step_row, text=self._t("step2"), bg=C.BG, fg=C.TEXT_MUTED, font=F.SMALL).pack(side="left")
        for i, active in enumerate([False, True]):
            tk.Label(step_row, text="●" if active else "○", bg=C.BG,
                     fg=C.PRIMARY if active else C.TEXT_LIGHT, font=(F.FAMILY, 10)).pack(side="left", padx=2)

        dir_labels = {
            "meaning_to_hanzi":  ("✍", self._t("type_meaning_hanzi")),
            "hanzi_to_meaning":  ("👁", self._t("type_hanzi_meaning")),
            "pinyin_to_meaning": ("🔤", self._t("type_pinyin_meaning")),
        }
        icon, label = dir_labels.get(self._direction, ("🧠", "Quiz"))
        crumb = tk.Frame(outer, bg=C.BG_CARD, highlightthickness=1, highlightbackground=C.BORDER)
        crumb.pack(pady=(S.SM, S.LG), padx=S.XXL)
        tk.Label(crumb, text=f"{icon}  {label}", bg=C.BG_CARD, fg=C.TEXT_MUTED,
                 font=F.SMALL, padx=S.MD, pady=S.XS).pack()

        tk.Label(outer, text=self._t("choose_mode"), bg=C.BG, fg=C.TEXT, font=F.H2).pack(pady=(0, S.LG))

        modes = [
            ("learning", "📖", self._t("mode_learning"), self._t("mode_learning_sub"), C.PRIMARY),
            ("challenge", "⚔️", self._t("mode_challenge"), self._t("mode_challenge_sub"), C.WARNING),
        ]

        for mode_id, ic, title, sub, color in modes:
            def _make_mode_card(mid=mode_id, icon=ic, t=title, s=sub, col=color):
                card = tk.Frame(outer, bg=C.BG_CARD, highlightbackground=C.BORDER,
                                highlightthickness=1, cursor="hand2")
                card.pack(fill="x", padx=S.XXL, pady=S.SM)
                inner = tk.Frame(card, bg=C.BG_CARD)
                inner.pack(fill="x", padx=S.LG, pady=S.MD)
                tk.Label(inner, text=icon, bg=C.BG_CARD, font=(F.FAMILY, 24)).pack(side="left", padx=(0, S.MD))
                right = tk.Frame(inner, bg=C.BG_CARD)
                right.pack(side="left", fill="x", expand=True)
                tk.Label(right, text=t, bg=C.BG_CARD, fg=col, font=F.TITLE).pack(anchor="w")
                tk.Label(right, text=s, bg=C.BG_CARD, fg=C.TEXT_MUTED,
                         font=F.SMALL, wraplength=380, justify="left").pack(anchor="w")

                def _on_click(event=None, _m=mid):
                    self._quiz_mode = _m
                    self._load_session()

                def _on_enter(e):
                    card.config(highlightbackground=col)
                    for child in card.winfo_children():
                        try: child.config(bg=C.BG_HOVER)
                        except Exception: pass
                        for gc in child.winfo_children():
                            try: gc.config(bg=C.BG_HOVER)
                            except Exception: pass
                            for ggc in gc.winfo_children():
                                try: ggc.config(bg=C.BG_HOVER)
                                except Exception: pass

                def _on_leave(e):
                    card.config(highlightbackground=C.BORDER)
                    for child in card.winfo_children():
                        try: child.config(bg=C.BG_CARD)
                        except Exception: pass
                        for gc in child.winfo_children():
                            try: gc.config(bg=C.BG_CARD)
                            except Exception: pass
                            for ggc in gc.winfo_children():
                                try: ggc.config(bg=C.BG_CARD)
                                except Exception: pass

                for widget in [card, inner, right] + list(inner.winfo_children()) + list(right.winfo_children()):
                    widget.bind("<Button-1>", _on_click)
                    widget.bind("<Enter>", _on_enter)
                    widget.bind("<Leave>", _on_leave)

            _make_mode_card()

        tk.Button(outer, text="← " + ("Back" if self._lang == "en" else "Nazad"),
                  bg=C.BG, fg=C.TEXT_MUTED, font=F.SMALL, relief="flat", bd=0,
                  cursor="hand2", command=self._show_direction_pick).pack(pady=S.MD)

    # ── Session load (with try/except + fallback) ─────────────────────────────

    def _load_session(self):
        try:
            self._combo = 0; self._best_combo = 0; self._score = 0; self._consecutive = 0
            self._blocking_overlay = False; self._pending_next = False
            self._answered_idx = -1
            ComboOverlay._active = False

            due = self._db.get_due_words(self._profile.username)
            logger.info(f"Quiz load: {len(due)} due words, user={self._profile.username}")

            all_words = [Word.from_dict(w) for w in self._profile.vocab]
            if not all_words:
                self._show_empty(); return

            if not due:
                due = all_words
                logger.info("No due words — using all words as fallback")

            # Always sample at least 5, use full vocab to pad if needed
            sample_size = max(5, min(20, len(all_words)))
            # Merge: due words first, then pad from full vocab
            due_set  = {w.hanzi for w in due}
            extra    = [w for w in all_words if w.hanzi not in due_set]
            extended = due + extra
            self._due = softmax_sample(extended, min(sample_size, len(extended)))
            logger.info(f"Quiz sampled {len(self._due)} words")

            # Preload audio
            for w in self._due[:3]:
                try: preload_audio(w.hanzi)
                except Exception as e: logger.warning(f"Preload audio error: {e}")

            self._idx = 0
            self._stats = SessionStats()

            # Update progress bar
            self._prog_bar._total = len(self._due)

            mode_badge = ("⚔️ Challenge" if self._quiz_mode == "challenge"
                          else "📖 Learning") if self._lang == "en" else \
                         ("⚔️ Izazov" if self._quiz_mode == "challenge" else "📖 Učenje")
            self._lbl_mode.config(text=mode_badge,
                                  fg=C.WARNING if self._quiz_mode == "challenge" else C.PRIMARY)
            self._next_word()

        except Exception as e:
            logger.error(f"_load_session error: {e}", exc_info=True)
            self._show_error(str(e))

    def _next_word(self):
        if self._blocking_overlay:
            self._pending_next = True
            return
        try:
            self.unbind_all("<Return>")

            if self._idx >= len(self._due):
                logger.info(f"Quiz done: idx={self._idx} total={len(self._due)}")
                self._show_done(); return

            w = self._due[self._idx]

            if self._direction == "hanzi_to_meaning":
                self._mode = "meaning"
            elif self._direction == "pinyin_to_meaning":
                self._mode = "pinyin"
            elif self._direction == "meaning_to_hanzi":
                self._mode = "type"

            rem = len(self._due) - self._idx
            self._lbl_title.config(text=self._t("quiz_title", rem))
            self._prog_bar.set_progress(self._idx)

            for child in self._content.winfo_children(): child.destroy()

            MODE_COLORS = _get_mode_colors()
            bg = MODE_COLORS.get(self._mode, (C.BG, ""))[0]
            frame = tk.Frame(self._content, bg=bg); frame.pack(fill="both", expand=True)
            self._q_start = time.time()

            if self._mode == "type":    self._render_type(frame, w)
            elif self._mode == "draw":  self._render_draw(frame, w)
            elif self._mode == "listen":self._render_listen(frame, w)
            elif self._mode == "meaning":self._render_meaning(frame, w)
            elif self._mode == "pinyin": self._render_pinyin(frame, w)

            # --- DODATO: Automatsko puštanje zvuka za novu reč ---
            if self._mode != "listen":
                def auto_play(hanzi=w.hanzi):
                    try:
                        play_audio(hanzi)
                    except Exception as e:
                        logger.warning(f"Auto-play error: {e}")

                # Malo kašnjenje (300ms) da bi se UI prvo iscrtao
                self.after(300, auto_play)
            # -----------------------------------------------------

            if self._idx + 1 < len(self._due):
                try: preload_audio(self._due[self._idx + 1].hanzi)
                except Exception: pass

        except Exception as e:
            logger.error(f"_next_word error: {e}", exc_info=True)
            # Skip broken word
            self._idx += 1
            if self._idx < len(self._due):
                self.after(500, self._next_word)
            else:
                self._show_done()

    # ── Answer handler ────────────────────────────────────────────────────────

    def _answer(self, word: Word, quality: int):
        try:
            if self._answered_idx == self._idx:
                logger.warning(f"_answer called twice for idx={self._idx}, ignoring")
                return
            self._answered_idx = self._idx

            rt = time.time() - self._q_start
            correct = quality >= 3

            try: play_sound("correct" if correct else "wrong")
            except Exception: pass

            self._stats.total += 1
            self._stats.response_times.append(rt)
            if correct:
                self._stats.correct += 1
                self._profile.total_correct += 1
                self._combo += 1
                self._consecutive += 1
                self._best_combo = max(self._best_combo, self._combo)
                self._score += max(5, quality * 10)
            else:
                self._combo = 0
                self._consecutive = 0

            self._profile.total_answered += 1
            self._wd.record_answer(correct, rt)

            # Update HUD
            if self._quiz_mode == "challenge":
                self._score_lbl.config(text=self._t("score_label", self._score))
                if self._combo >= 2:
                    self._combo_lbl.config(text=self._t("combo_label", self._combo))
                else:
                    self._combo_lbl.config(text="")

            try:
                from ...xp_config import compute_quiz_xp as _cqx
                xp_gain = _cqx(word.xp, quality, rt)
            except ImportError:
                xp_gain = max(0, round(word.xp * quality / 5)) if correct else 0
            if xp_gain:
                self._stats.xp_gained += xp_gain
                self._gain_xp(xp_gain)

            updated = sm2_update(word, quality, rt)
            self._db.update_word(self._profile.username, updated)
            for i, w in enumerate(self._profile.vocab):
                if w.get("hanzi") == word.hanzi:
                    self._profile.vocab[i] = updated.to_dict(); break

            if not correct:
                self._add_mistake(word)

            try:
                new_ach = check_achievements(self._profile, event="answer", response_time=rt)
                for ach in new_ach: self._notif.show_achievement(ach)
            except Exception: pass

            self._db.save_user(self._profile)
            logger.info(f"Answer: idx {self._idx}→{self._idx+1} correct={correct} quality={quality}")
            self._idx += 1

            # Check for combo milestone overlay
            root = self.winfo_toplevel()
            if correct and self._consecutive > 0 and self._consecutive % 5 == 0:
                self._blocking_overlay = True
                ComboOverlay.show_streak(root, self._consecutive,
                    on_done=self._overlay_done)
            elif correct and self._combo in (5, 8, 10, 15, 20):
                self._blocking_overlay = True
                ComboOverlay.show_combo(root, self._combo,
                    on_done=self._overlay_done)
            else:
                self.after(1000, self._next_word)

        except Exception as e:
            logger.error(f"_answer error: {e}", exc_info=True)
            self._idx += 1
            self.after(500, self._next_word)

    def _overlay_done(self):
        self._blocking_overlay = False
        self.after(200, self._next_word)

    def _gain_xp(self, amount: int):
        try:
            play_sound("xp_gain")
        except Exception:
            pass
        self._profile.xp       += amount
        self._profile.daily_xp += amount
        today = date.today().isoformat()
        self._profile.daily_xp_history[today] = self._profile.daily_xp
        if self._profile.daily_xp >= self._profile.daily_goal:
            if today not in self._profile.completed_days:
                self._profile.completed_days.append(today)
        if today not in self._profile.completed_days:
            self._profile.completed_days.append(today)
        if today not in self._profile.completed_days:
            self._profile.completed_days.append(today)
        lvl, _, _ = compute_level(self._profile.xp)
        if lvl > self._profile.level:
            self._profile.level = lvl
            try: play_sound("level_up")
            except Exception: pass
            root = self.winfo_toplevel()
            self._blocking_overlay = True
            ComboOverlay.show_level_up(root, lvl, on_done=self._overlay_done)
            try:
                new_ach = check_achievements(self._profile)
                for ach in new_ach: self._notif.show_achievement(ach)
            except Exception:
                pass

    def _add_mistake(self, word: Word):
        try:
            existing = self._profile.mistakes.setdefault("words", [])
            for m in existing:
                if m.get("hanzi") == word.hanzi:
                    m["count"] = m.get("count", 1) + 1; return
            existing.append({
                "type": "word", "hanzi": word.hanzi, "pinyin": word.pinyin,
                "meaning_sr": word.meaning_sr, "meaning_en": word.meaning_en,
                "xp": word.xp, "correct": "", "scrambled": "", "count": 1,
                "last_seen": date.today().isoformat(),
            })
        except Exception as e:
            logger.warning(f"_add_mistake error: {e}")

    # ── MOD: Kucanje ──────────────────────────────────────────────────────────

    def _render_type(self, parent: tk.Frame, w: Word):
        try:
            from ..widgets import make_listen_btn
            root = self.winfo_toplevel()
            bg = parent["bg"]
            center = tk.Frame(parent, bg=bg); center.pack(fill="both", expand=True)

            if self._direction == "meaning_to_hanzi":
                card = tk.Frame(center, bg=C.BG_CARD,
                                highlightbackground=C.BORDER, highlightthickness=1)
                card.pack(anchor="center", padx=S.XXL, pady=(S.LG, S.MD), fill="x")
                card_inner = tk.Frame(card, bg=C.BG_CARD)
                card_inner.pack(padx=S.LG, pady=S.LG)
                tk.Label(card_inner, text=_meaning(w, self._lang), bg=C.BG_CARD,
                         fg=C.TEXT, font=(F.FAMILY, 26, "bold"),
                         wraplength=400, justify="center").pack()
                make_listen_btn(card_inner, w.meaning_en, bg=C.BG_CARD, size=15).pack(pady=(S.XS, 0))

            if self._direction != "meaning_to_hanzi":
                char_card = tk.Frame(center, bg=C.BG_CARD,
                                     highlightbackground=C.BORDER, highlightthickness=1)
                char_card.pack(padx=S.XXL, pady=(S.LG, S.XS), fill="x")
                char_inner = tk.Frame(char_card, bg=C.BG_CARD)
                char_inner.pack(pady=S.MD)

                hanzi_row = tk.Frame(char_inner, bg=C.BG_CARD)
                hanzi_row.pack()
                hanzi_lbl = tk.Label(hanzi_row, text=w.hanzi, bg=C.BG_CARD,
                                     fg=C.DANGER, font=F.HANZI)
                hanzi_lbl.pack(side="left")
                make_listen_btn(hanzi_row, w.hanzi, bg=C.BG_CARD, size=18).pack(
                    side="left", padx=(S.SM, 0))
                bind_hover_translate(hanzi_lbl, w.hanzi, _meaning(w, self._lang),
                                     root, competitive=(self._quiz_mode == "challenge"))
                tk.Label(char_inner, text=w.pinyin, bg=C.BG_CARD,
                         fg=C.TEXT_MUTED, font=F.H2).pack(pady=(S.XS, 0))

            timer = TimerWidget(center, seconds=30, countdown=True, bg=bg,
                                fg=C.WARNING, font=F.LABEL_B)
            if self._quiz_mode == "challenge":
                timer.pack(anchor="e", padx=S.LG)
                timer.start()

            row = tk.Frame(center, bg=bg); row.pack(pady=S.SM)
            if self._direction == "meaning_to_hanzi":
                tk.Label(row, text=self._t("type_hanzi"), bg=bg,
                         fg=C.TEXT_MUTED, font=F.SMALL).grid(row=0, column=0, sticky="e", padx=S.XS)
                e_hanzi = tk.Entry(row, font=(F.FAMILY, 22), justify="center", width=8,
                                   bg=C.BG_INPUT, fg=C.TEXT, relief="flat",
                                   highlightbackground=C.BORDER, highlightthickness=1,
                                   insertbackground=C.TEXT)
                e_hanzi.grid(row=0, column=1, padx=S.SM, ipady=S.SM)
                e_hanzi.bind("<FocusIn>", lambda e: e_hanzi.config(highlightbackground=C.BORDER_FOCUS, highlightthickness=2))
                e_hanzi.bind("<FocusOut>", lambda e: e_hanzi.config(highlightbackground=C.BORDER, highlightthickness=1))
                e_hanzi.focus_set()

                tk.Label(row, text=self._t("type_pinyin"), bg=bg,
                         fg=C.TEXT_MUTED, font=F.SMALL).grid(row=1, column=0, sticky="e", padx=S.XS, pady=(S.SM, 0))
                e_pinyin = tk.Entry(row, font=F.LABEL, justify="center", width=14,
                                    bg=C.BG_INPUT, fg=C.TEXT, relief="flat",
                                    highlightbackground=C.BORDER, highlightthickness=1,
                                    insertbackground=C.TEXT)
                e_pinyin.grid(row=1, column=1, padx=S.SM, pady=(S.SM, 0), ipady=S.SM)
            else:
                tk.Label(row, text=("Type the meaning:" if self._lang == "en" else "Ukucaj značenje:"),
                         bg=bg, fg=C.TEXT_MUTED, font=F.SMALL).pack(anchor="w")
                e_hanzi = tk.Entry(row, font=F.LABEL, justify="center", width=24,
                                   bg=C.BG_INPUT, fg=C.TEXT, relief="flat",
                                   highlightbackground=C.BORDER, highlightthickness=1,
                                   insertbackground=C.TEXT)
                e_hanzi.pack(pady=(S.XS, 0), ipady=S.SM)
                e_hanzi.focus_set()
                e_pinyin = None

            fb = tk.Label(center, text="", bg=bg, font=F.LABEL, wraplength=420)
            fb.pack(pady=S.XS)

            def check(ev=None):
                timer.stop()
                ans_h = e_hanzi.get().strip()
                ans_p = e_pinyin.get().strip() if e_pinyin else ""

                if self._direction == "meaning_to_hanzi":
                    h_ok = ans_h == w.hanzi
                    p_ok = _norm_pinyin(ans_p) == _norm_pinyin(w.pinyin) if ans_p else True
                    correct = h_ok
                    if not ans_h:
                        fb.config(text="⚠️ Type the Hanzi!", fg=C.WARNING); return
                    if correct:
                        bonus = " ✨ +pinyin" if (ans_p and _norm_pinyin(ans_p) == _norm_pinyin(w.pinyin)) else ""
                        fb.config(text=f"✅ {w.hanzi}  {w.pinyin}{bonus}", fg=C.SUCCESS)
                    else:
                        fb.config(text=f"❌ {w.hanzi}  ({w.pinyin})", fg=C.DANGER)
                        e_hanzi.config(bg="#3D1A1A" if C.is_dark() else "#FFE8E8")
                elif self._direction in ("hanzi_to_meaning", "pinyin_to_meaning"):
                    m_en = w.meaning_en.lower(); m_sr = w.meaning_sr.lower()
                    correct = ans_h.lower() in (m_en, m_sr)
                    if correct:
                        fb.config(text=f"✅ {w.meaning_en}", fg=C.SUCCESS)
                    else:
                        fb.config(text=f"❌ {w.meaning_en}", fg=C.DANGER)
                else:
                    correct = False

                btn.config(state="disabled")
                self.after(1000, lambda: self._answer(w, 4 if correct else 1))

            btn = PrimaryButton(center, text=self._t("check"), command=check)
            btn.pack(pady=S.MD)
            self.bind("<Return>", lambda e: check() if btn["state"] == "normal" else None)

            if self._quiz_mode == "challenge":
                timer._on_timeout = lambda: (
                    fb.config(text=f"⏰ {w.hanzi} ({w.pinyin})", fg=C.DANGER),
                    btn.config(state="disabled"),
                    self.after(1200, lambda: self._answer(w, 1))
                )

        except Exception as e:
            logger.error(f"_render_type error: {e}", exc_info=True)
            self._answer(w, 0)

    # ── MOD: Crtanje ──────────────────────────────────────────────────────────

    def _render_draw(self, parent: tk.Frame, w: Word):
        try:
            from ..widgets import make_listen_btn
            bg = parent["bg"]
            center = tk.Frame(parent, bg=bg); center.pack(fill="both", expand=True, pady=S.SM)
            tk.Label(center, text=self._t("draw_instr"), bg=bg, fg=C.TEXT_MUTED, font=F.SMALL).pack()

            hanzi_row = tk.Frame(center, bg=bg); hanzi_row.pack(pady=S.XS)
            tk.Label(hanzi_row, text=w.hanzi, bg=bg, fg=C.PRIMARY,
                     font=(F.FAMILY, 52, "bold")).pack(side="left")
            make_listen_btn(hanzi_row, w.hanzi, bg=bg, size=16).pack(side="left", padx=(S.SM, 0))

            tk.Label(center, text=f"{w.pinyin} — {_meaning(w, self._lang)}",
                     bg=bg, fg=C.TEXT_MUTED, font=F.SMALL).pack()

            canvas = DrawingCanvas(center); canvas.pack(pady=S.SM)
            fb = tk.Label(center, text="", bg=bg, font=F.LABEL, wraplength=380); fb.pack()

            timer = TimerWidget(center, seconds=45, countdown=True, bg=bg, fg=C.WARNING, font=F.LABEL_B)
            if self._quiz_mode == "challenge":
                timer.pack(anchor="e"); timer.start()

            def submit():
                btn_submit.config(state="disabled", text=self._t("draw_analyzing"))
                timer.stop()
                png = canvas.get_png_bytes()

                def do():
                    try:
                        result = gemini.evaluate_drawing(png, w.hanzi, w.pinyin, _meaning(w, self._lang))
                    except Exception as ex:
                        logger.warning(f"Drawing eval error: {ex}")
                        result = None
                    if self.winfo_exists():
                        self.after(0, lambda: handle(result))

                def handle(r):
                    btn_submit.config(state="normal", text=self._t("draw_submit"))
                    if r is None:
                        fb.config(text="❌ Error — counting as attempt.", fg=C.DANGER)
                        self._answer(w, 1); return
                    score = r.get("score", 0); msg = r.get("feedback", "")
                    if score >= 70:
                        fb.config(text=f"✅ {msg}  ({score}/100)", fg=C.SUCCESS)
                        self._notif.show(f"Great drawing! {score}/100", "success")
                        self._answer(w, 4 if score >= 85 else 3)
                    elif score >= 40:
                        fb.config(text=f"🟡 {msg}  ({score}/100)", fg=C.WARNING)
                        self._answer(w, 2)
                    else:
                        fb.config(text=f"❌ {msg}  ({score}/100)", fg=C.DANGER)
                        self._answer(w, 1)

                threading.Thread(target=do, daemon=True).start()

            btn_submit = PrimaryButton(center, text=self._t("draw_submit"), command=submit)
            btn_submit.pack(pady=S.SM)

        except Exception as e:
            logger.error(f"_render_draw error: {e}", exc_info=True)
            self._answer(w, 0)

    # ── MOD: Slušanje ─────────────────────────────────────────────────────────

    def _render_listen(self, parent: tk.Frame, w: Word):
        try:
            bg = parent["bg"]
            center = tk.Frame(parent, bg=bg); center.pack(expand=True)

            tk.Label(center, text=self._t("type_heard"), bg=bg,
                     fg=C.TEXT, font=F.LABEL).pack(pady=(S.LG, S.SM))

            played = [False]
            def play():
                played[0] = True
                try: play_audio(w.hanzi)
                except Exception: pass

            play_btn = tk.Button(center, text=self._t("listen_btn"),
                      bg=C.TEAL, fg=C.TEXT_WHITE, font=(F.FAMILY, 14, "bold"),
                      relief="flat", bd=0, cursor="hand2",
                      padx=S.XL, pady=S.MD, command=play)
            play_btn.pack(pady=S.SM)
            play_btn.bind("<Enter>", lambda e: play_btn.config(bg=C.TEAL_DARK))
            play_btn.bind("<Leave>", lambda e: play_btn.config(bg=C.TEAL))

            self.after(300, play)

            entry = tk.Entry(center, font=(F.FAMILY, 28), justify="center", width=8,
                             bg=C.BG_INPUT, fg=C.TEXT, relief="flat",
                             highlightbackground=C.BORDER, highlightthickness=1,
                             insertbackground=C.TEXT)
            entry.pack(pady=S.MD, ipady=S.SM)
            entry.bind("<FocusIn>", lambda e: entry.config(highlightbackground=C.BORDER_FOCUS, highlightthickness=2))
            entry.bind("<FocusOut>", lambda e: entry.config(highlightbackground=C.BORDER, highlightthickness=1))
            self.after(400, entry.focus_set)

            fb = tk.Label(center, text="", bg=bg, font=F.LABEL, wraplength=380)
            fb.pack(pady=S.XS)

            def check(ev=None):
                ans = entry.get().strip()
                if not ans: return
                correct = ans == w.hanzi
                if correct:
                    fb.config(text=f"✅ {w.hanzi}  ({w.pinyin})", fg=C.SUCCESS)
                else:
                    fb.config(text=f"❌ {w.hanzi}  ({w.pinyin})", fg=C.DANGER)
                btn.config(state="disabled")
                self.after(1000, lambda: self._answer(w, 4 if correct else 1))

            btn = PrimaryButton(center, text=self._t("check"), command=check)
            btn.pack(pady=S.SM)
            self.bind("<Return>", lambda e: check() if btn["state"] == "normal" else None)

        except Exception as e:
            logger.error(f"_render_listen error: {e}", exc_info=True)
            self._answer(w, 0)

    # ── MOD: Značenje (multiple choice) ──────────────────────────────────────

    def _render_meaning(self, parent: tk.Frame, w: Word):
        try:
            from ..widgets import make_listen_btn
            root = self.winfo_toplevel()
            bg = parent["bg"]
            center = tk.Frame(parent, bg=bg); center.pack(fill="both", expand=True)

            char_card = tk.Frame(center, bg=C.BG_CARD,
                                 highlightbackground=C.BORDER, highlightthickness=1)
            char_card.pack(padx=S.XXL, pady=(S.LG, S.MD), fill="x")
            char_inner = tk.Frame(char_card, bg=C.BG_CARD)
            char_inner.pack(pady=S.MD)

            hanzi_row = tk.Frame(char_inner, bg=C.BG_CARD)
            hanzi_row.pack()
            hanzi_lbl = tk.Label(hanzi_row, text=w.hanzi, bg=C.BG_CARD,
                                 fg=C.DANGER, font=F.HANZI)
            hanzi_lbl.pack(side="left")
            make_listen_btn(hanzi_row, w.hanzi, bg=C.BG_CARD, size=18).pack(
                side="left", padx=(S.SM, 0))
            bind_hover_translate(hanzi_lbl, w.hanzi, _meaning(w, self._lang),
                                 root, competitive=(self._quiz_mode == "challenge"))
            tk.Label(char_inner, text=w.pinyin, bg=C.BG_CARD,
                     fg=C.TEXT_MUTED, font=F.H2).pack(pady=(S.XS, 0))

            tk.Label(center, text=self._t("meaning_q"), bg=bg,
                     fg=C.TEXT_MUTED, font=F.SMALL).pack(pady=(0, S.XS))

            correct_meaning = _meaning(w, self._lang)
            all_words = [Word.from_dict(ww) for ww in self._profile.vocab if ww.get("hanzi") != w.hanzi]
            distractors = random.sample(all_words, min(3, len(all_words)))
            choices = [correct_meaning] + [_meaning(d, self._lang) for d in distractors]
            random.shuffle(choices)

            answered = [False]

            def pick(chosen):
                if answered[0]: return
                answered[0] = True
                correct = chosen == correct_meaning
                for btn_ref, ch in btns:
                    if ch == correct_meaning:
                        btn_ref.config(bg=C.SUCCESS, fg=C.TEXT_WHITE,
                                       activebackground=C.SUCCESS)
                    elif ch == chosen and not correct:
                        btn_ref.config(bg=C.DANGER, fg=C.TEXT_WHITE,
                                       activebackground=C.DANGER)
                    else:
                        btn_ref.config(state="disabled",
                                       bg=C.BG_HOVER, fg=C.TEXT_LIGHT)
                self.after(900, lambda: self._answer(w, 4 if correct else 1))

            btns = []
            for ch in choices:
                btn = tk.Button(center, text=ch, font=F.LABEL,
                                bg=C.BG_CARD, fg=C.TEXT, relief="flat", bd=0,
                                highlightbackground=C.BORDER, highlightthickness=1,
                                cursor="hand2", wraplength=400, justify="center",
                                padx=S.LG, pady=S.SM,
                                activebackground=C.BG_HOVER,
                                command=lambda c=ch: pick(c))
                btn.pack(fill="x", padx=S.XXL, pady=3)
                btns.append((btn, ch))
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg=C.BG_HOVER) if b["state"] == "normal" else None)
                btn.bind("<Leave>", lambda e, b=btn: b.config(bg=C.BG_CARD) if b["state"] == "normal" else None)

        except Exception as e:
            logger.error(f"_render_meaning error: {e}", exc_info=True)
            self._answer(w, 0)

    # ── MOD: Pinyin → Hanzi ───────────────────────────────────────────────────

    def _render_pinyin(self, parent: tk.Frame, w: Word):
        try:
            from ..widgets import make_listen_btn
            bg = parent["bg"]
            center = tk.Frame(parent, bg=bg); center.pack(fill="both", expand=True)

            pinyin_card = tk.Frame(center, bg=C.BG_CARD,
                                   highlightbackground=C.BORDER, highlightthickness=1)
            pinyin_card.pack(padx=S.XXL, pady=(S.LG, S.MD), fill="x")
            p_inner = tk.Frame(pinyin_card, bg=C.BG_CARD)
            p_inner.pack(pady=S.MD)

            p_row = tk.Frame(p_inner, bg=C.BG_CARD); p_row.pack()
            tk.Label(p_row, text=w.pinyin, bg=C.BG_CARD,
                     fg=C.PRIMARY, font=F.DISPLAY).pack(side="left")
            make_listen_btn(p_row, w.hanzi, bg=C.BG_CARD, size=18).pack(
                side="left", padx=(S.SM, 0))

            tk.Label(p_inner, text=_meaning(w, self._lang), bg=C.BG_CARD,
                     fg=C.TEXT_MUTED, font=F.LABEL).pack(pady=(S.XS, 0))

            tk.Label(center, text=("Type the Hanzi:" if self._lang == "en" else "Ukucaj Hanzi:"),
                     bg=bg, fg=C.TEXT_MUTED, font=F.SMALL).pack(pady=(0, S.XS))

            entry = tk.Entry(center, font=(F.FAMILY, 28), justify="center", width=8,
                             bg=C.BG_INPUT, fg=C.TEXT, relief="flat",
                             highlightbackground=C.BORDER, highlightthickness=1,
                             insertbackground=C.TEXT)
            entry.pack(pady=S.SM, ipady=S.SM)
            entry.bind("<FocusIn>", lambda e: entry.config(highlightbackground=C.BORDER_FOCUS, highlightthickness=2))
            entry.bind("<FocusOut>", lambda e: entry.config(highlightbackground=C.BORDER, highlightthickness=1))
            entry.focus_set()

            fb = tk.Label(center, text="", bg=bg, font=F.LABEL, wraplength=420)
            fb.pack()

            def check(ev=None):
                ans = entry.get().strip()
                correct = ans == w.hanzi
                fb.config(text=f"{'✅' if correct else '❌'} {w.hanzi}  ({w.pinyin})",
                          fg=C.SUCCESS if correct else C.DANGER)
                btn.config(state="disabled")
                self.after(900, lambda: self._answer(w, 4 if correct else 1))

            btn = PrimaryButton(center, text=self._t("check"), command=check)
            btn.pack(pady=S.MD)
            self.bind("<Return>", lambda e: check() if btn["state"] == "normal" else None)

        except Exception as e:
            logger.error(f"_render_pinyin error: {e}", exc_info=True)
            self._answer(w, 0)

    # ── Session done ──────────────────────────────────────────────────────────

    def _show_done(self):
        try:
            s = self._stats
            for c in self._content.winfo_children(): c.destroy()

            # Streak update
            try:
                _today = date.today().isoformat()
                if _today not in self._profile.completed_days:
                    self._profile.completed_days.append(_today)
                gained_streak = self._profile.award_session_streak()
                if gained_streak:
                    self._notif.show(self._t("streak_gained", self._profile.streak), "success")
            except Exception: pass

            try:
                new_ach = check_achievements(self._profile, event="session_done", stats=s)
                for ach in new_ach: self._notif.show_achievement(ach)
            except Exception: pass

            f = tk.Frame(self._content, bg=C.BG); f.pack(fill="both", expand=True, pady=S.LG)

            # Hero
            tk.Label(f, text="🎉", bg=C.BG, font=(F.FAMILY, 52)).pack(pady=(S.LG, S.XS))
            tk.Label(f, text=self._t("session_done"), bg=C.BG, fg=C.TEXT, font=F.H1).pack()

            # Stats cards
            stats_row = tk.Frame(f, bg=C.BG); stats_row.pack(pady=S.LG)

            def stat_card(parent, label, value, color):
                card = tk.Frame(parent, bg=C.BG_CARD, highlightbackground=C.BORDER, highlightthickness=1)
                card.pack(side="left", padx=S.SM, ipadx=S.LG, ipady=S.MD)
                tk.Label(card, text=value, bg=C.BG_CARD, fg=color, font=F.H2).pack()
                tk.Label(card, text=label, bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.TINY).pack()

            stat_card(stats_row, self._t("accuracy"),
                      f"{s.accuracy:.0f}%",
                      C.SUCCESS if s.accuracy >= 70 else C.WARNING)
            stat_card(stats_row, self._t("xp_earned"),
                      f"+{s.xp_gained}",
                      C.GOLD)
            stat_card(stats_row, self._t("avg_speed"),
                      f"{s.avg_response:.1f}s",
                      C.PRIMARY)

            if self._quiz_mode == "challenge":
                stat_card(stats_row, "Best Combo",
                          f"×{self._best_combo}",
                          C.ORANGE)
                stat_card(stats_row, "Score",
                          str(self._score),
                          C.PURPLE)

            # AI feedback
            ai_lbl = tk.Label(f, text=self._t("loading_feedback"), bg=C.BG,
                              fg=C.TEXT_MUTED, font=F.SMALL, wraplength=440, justify="center")
            ai_lbl.pack(pady=S.SM)

            def fetch_feedback():
                try:
                    wd = WeaknessDetector(self._profile)
                    weak = [ww.hanzi for ww in wd.weak_words()]
                    summary = (f"accuracy={s.accuracy:.0f}%, xp={s.xp_gained}, "
                               f"correct={s.correct}/{s.total}, avg_speed={s.avg_response:.1f}s")
                    fb = gemini.session_feedback(summary, weak, lang=self._lang)
                    if fb and self.winfo_exists():
                        self.after(0, lambda: ai_lbl.config(
                            text=f"{self._t('ai_feedback_title')}\n{fb}", fg=C.PRIMARY))
                except Exception as e:
                    logger.warning(f"session_feedback error: {e}")

            threading.Thread(target=fetch_feedback, daemon=True).start()

            btn_row = tk.Frame(f, bg=C.BG); btn_row.pack(pady=S.MD)
            PrimaryButton(btn_row, text=self._t("back_to_menu"),
                          command=self._on_back).pack(side="left", padx=S.SM)
            GhostButton(btn_row,
                        text="🔄 New Session" if self._lang == "en" else "🔄 Nova sesija",
                        command=self._show_direction_pick).pack(side="left")

        except Exception as e:
            logger.error(f"_show_done error: {e}", exc_info=True)
            self._on_back()

    def _show_empty(self):
        for c in self._content.winfo_children(): c.destroy()
        f = tk.Frame(self._content, bg=C.BG); f.pack(expand=True)
        tk.Label(f, text="📭", bg=C.BG, font=(F.FAMILY, 48)).pack(pady=S.LG)
        tk.Label(f, text=self._t("empty"), bg=C.BG, fg=C.TEXT, font=F.H2).pack()
        tk.Label(f, text=self._t("empty_sub"), bg=C.BG, fg=C.TEXT_MUTED,
                 font=F.BODY, wraplength=380, justify="center").pack(pady=S.SM)
        GhostButton(f, text=self._t("back"), command=self._on_back).pack(pady=S.MD)

    def _show_error(self, msg: str = ""):
        """Fallback error screen — quiz never silently fails."""
        for c in self._content.winfo_children(): c.destroy()
        f = tk.Frame(self._content, bg=C.BG); f.pack(expand=True)
        tk.Label(f, text="⚠️", bg=C.BG, font=(F.FAMILY, 48)).pack(pady=S.LG)
        tk.Label(f, text="Quiz error — please restart", bg=C.BG,
                 fg=C.DANGER, font=F.H2).pack()
        if msg:
            tk.Label(f, text=msg, bg=C.BG, fg=C.TEXT_MUTED,
                     font=F.SMALL, wraplength=400, justify="center").pack(pady=S.SM)
        PrimaryButton(f, text="← Back", command=self._on_back).pack(pady=S.MD)
        logger.error(f"Quiz error displayed: {msg}")

    def _confirm_back(self):
        ConfirmDialog(
            self,
            title=self._t("confirm_back_title"),
            message=self._t("confirm_back_msg"),
            yes_text=self._t("confirm_back_yes"),
            no_text=self._t("confirm_back_no"),
            on_yes=self._on_back,
            danger=True,
        )