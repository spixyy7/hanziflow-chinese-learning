from __future__ import annotations
import random, threading, time, logging
import tkinter as tk
from typing import Callable

from ..theme import (C, F, S, Card, PrimaryButton, SuccessButton, GhostButton,
                     DangerButton, flash_widget, pulse_label, ComboOverlay, ConfirmDialog)
from ..widgets import NotificationManager, SentenceBuilder, make_listen_btn
from ...core import Database, UserProfile, check_achievements, play_audio, gemini, play_sound
from ...core.adaptive import WeaknessDetector, compute_level

logger = logging.getLogger("HanziFlow.Grammar")
TIME_LIMIT = 60

_T = {
    "en": {
        "title": "📝  Sentence Builder",
        "back": "⬅ Back",
        "setup_q": "How many sentences?",
        "start": "Start",
        "progress": "{} / {}",
        "build_q": "Arrange the sentence:",
        "meaning": "Meaning: {}",
        "reward": "⭐ {} XP",
        "check": "✔  Check",
        "correct": "✅ Perfect! +{} XP",
        "wrong_attempts": "❌ Wrong! {} left",
        "out_of_attempts": "❌ Answer: {}",
        "time_up": "⏰ Time's up! {}",
        "done": "🎉 {} sentences done!",
        "not_enough": "Need at least 3 words.",
        "loading": "Generating sentence...",
        "back_menu": "⬅ Back to Menu",
        "confirm_back_title": "Leave Grammar?",
        "confirm_back_msg": "Current sentence progress will be lost.",
        "confirm_back_yes": "Leave",
        "confirm_back_no": "Stay",
        "streak_gained": "🔥 Streak +1! Day {}",
    },
    "sr": {
        "title": "📝  Sentence Builder",
        "back": "⬅ Nazad",
        "setup_q": "Koliko rečenica?",
        "start": "Počni",
        "progress": "{} / {}",
        "build_q": "Složi rečenicu:",
        "meaning": "Značenje: {}",
        "reward": "⭐ {} XP",
        "check": "✔  Proveri",
        "correct": "✅ Savršeno! +{} XP",
        "wrong_attempts": "❌ Netačno! Preostalo: {}",
        "out_of_attempts": "❌ Ispravno: {}",
        "time_up": "⏰ Vreme! {}",
        "done": "🎉 {} rečenica završeno!",
        "not_enough": "Treba ti barem 3 reči.",
        "loading": "Generišem rečenicu...",
        "back_menu": "⬅ Nazad u meni",
        "confirm_back_title": "Napusti Gramatiku?",
        "confirm_back_msg": "Napredak tekuće rečenice biće izgubljen.",
        "confirm_back_yes": "Napusti",
        "confirm_back_no": "Ostani",
        "streak_gained": "🔥 Streak +1! Dan {}",
    },
}


class GrammarView(tk.Frame):

    def __init__(self, parent, profile: UserProfile,
                 notif: NotificationManager, on_back: Callable):
        super().__init__(parent, bg=C.BG)
        self._profile = profile
        self._lang    = profile.lang
        self._db      = Database()
        self._notif   = notif
        self._on_back = on_back
        self._wd      = WeaknessDetector(profile)

        self._target      = 3
        self._done        = 0
        self._queue: list[dict] = []
        self._is_fetching = False
        self._attempts    = 0
        self._error_count = 0
        self._score       = 0
        self._combo       = 0
        self._blocking    = False

        self._build()
        if len(self._profile.vocab) < 3:
            self._show_not_enough()
        else:
            self._show_setup()

    def _t(self, key, *args):
        txt = _T[self._lang].get(key, key)
        return txt.format(*args) if args else txt

    def _build(self):
        hdr = tk.Frame(self, bg=C.BG_SIDEBAR); hdr.pack(fill="x")
        GhostButton(hdr, text=self._t("back"), command=self._confirm_back).pack(
            side="left", padx=S.MD, pady=S.SM)
        tk.Label(hdr, text=self._t("title"), bg=C.BG_SIDEBAR,
                 fg=C.TEXT, font=F.H2).pack(side="left")

        self._score_lbl = tk.Label(hdr, text="", bg=C.BG_SIDEBAR,
                                   fg=C.GOLD, font=F.LABEL_B)
        self._score_lbl.pack(side="right", padx=S.SM)
        self._progress_lbl = tk.Label(hdr, text="", bg=C.BG_SIDEBAR,
                                      fg=C.TEXT_MUTED, font=F.SMALL)
        self._progress_lbl.pack(side="right", padx=S.MD)

        self._content = tk.Frame(self, bg=C.BG)
        self._content.pack(fill="both", expand=True)

    def _show_setup(self):
        for c in self._content.winfo_children(): c.destroy()
        self._score = 0; self._combo = 0
        f = tk.Frame(self._content, bg=C.BG); f.pack(expand=True)

        tk.Label(f, text="📝", bg=C.BG, font=(F.FAMILY, 48)).pack(pady=(S.LG, S.SM))
        tk.Label(f, text=self._t("setup_q"), bg=C.BG, fg=C.TEXT, font=F.H2).pack(pady=(0, S.LG))

        counts_row = tk.Frame(f, bg=C.BG); counts_row.pack()
        for n, color in [(1, C.TEAL), (3, C.PRIMARY), (5, C.WARNING), (10, C.DANGER)]:
            btn = tk.Button(counts_row, text=str(n), font=(F.FAMILY, 18, "bold"),
                            bg=color, fg=C.TEXT_WHITE, relief="flat", bd=0,
                            cursor="hand2", width=4, pady=S.SM,
                            command=lambda v=n: self._start(v))
            btn.pack(side="left", padx=S.SM)
            btn.bind("<Enter>", lambda e, b=btn, c=color: b.config(bg=C.PRIMARY_DARK if c == C.PRIMARY else c))
            btn.bind("<Leave>", lambda e, b=btn, c=color: b.config(bg=c))

        cust = tk.Frame(f, bg=C.BG); cust.pack(pady=S.MD)
        tk.Label(cust, text="Custom:", bg=C.BG, fg=C.TEXT_MUTED, font=F.SMALL).pack(side="left")
        e = tk.Entry(cust, width=5, font=F.BODY, justify="center",
                     bg=C.BG_INPUT, fg=C.TEXT, relief="flat",
                     highlightbackground=C.BORDER, highlightthickness=1,
                     insertbackground=C.TEXT)
        e.pack(side="left", padx=S.XS, ipady=S.XS)
        GhostButton(cust, text=self._t("start"),
                    command=lambda: self._start(int(e.get() or 3))).pack(side="left")

    def _start(self, count: int):
        self._target = max(1, count)
        self._done   = 0; self._queue = []
        self._score  = 0; self._combo = 0
        for c in self._content.winfo_children(): c.destroy()
        self._show_loading()
        self._fetch_next()

    def _fetch_next(self):
        if self._is_fetching or len(self._queue) >= 2: return
        self._is_fetching = True

        def do():
            try:
                known  = [w.get("hanzi", "") for w in self._profile.vocab]
                sample = random.sample(known, min(len(known), 25))
                perf   = self._wd.ai_difficulty_prompt()
                result = gemini.generate_sentence(sample, perf, lang=self._lang)
            except Exception as ex:
                logger.warning(f"fetch_next error: {ex}")
                result = None
            if self.winfo_exists():
                self.after(0, lambda: self._on_fetched(result))

        threading.Thread(target=do, daemon=True).start()

    def _on_fetched(self, result):
        self._is_fetching = False
        if result:
            self._error_count = 0
            self._queue.append(result)
            if self._showing_loading():
                self._show_sentence()
            else:
                self._fetch_next()
        else:
            self._error_count += 1
            if self._error_count >= 3:
                self._notif.show("API not responding — going back.", "error")
                self._on_back(); return
            self.after(2500, self._fetch_next)

    def _showing_loading(self) -> bool:
        for c in self._content.winfo_children():
            if getattr(c, "_is_loading", False): return True
        return False

    def _show_loading(self):
        for c in self._content.winfo_children(): c.destroy()
        f = tk.Frame(self._content, bg=C.BG); f.pack(expand=True)
        f._is_loading = True
        tk.Label(f, text="📝", bg=C.BG, font=(F.FAMILY, 40)).pack(pady=S.LG)
        lbl = tk.Label(f, text=self._t("loading"), bg=C.BG,
                       fg=C.TEXT_MUTED, font=F.LABEL)
        lbl.pack()
        dots = ["", ".", "..", "..."]
        def _animate(i=0):
            if not self._showing_loading(): return
            try: lbl.config(text=self._t("loading") + dots[i % len(dots)])
            except tk.TclError: return
            self.after(400, lambda: _animate(i+1))
        _animate()

    def _show_sentence(self):
        if not self._queue:
            self._show_loading(); return
        item = self._queue.pop(0)
        self._fetch_next()

        for c in self._content.winfo_children(): c.destroy()
        self._progress_lbl.config(text=self._t("progress", self._done + 1, self._target))
        self._score_lbl.config(text=f"⭐ {self._score}")
        self._attempts = 0

        xp_val  = item.get("xp", 30)
        meaning = item.get(f"meaning_{self._lang}", item.get("meaning_en", ""))
        correct = item.get("correct", "").strip()
        words   = [w.strip() for w in item.get("scrambled", "").split(",") if w.strip()]

        outer = tk.Frame(self._content, bg=C.BG)
        outer.pack(fill="both", expand=True, padx=S.LG, pady=S.MD)

        top = tk.Frame(outer, bg=C.BG); top.pack(fill="x", pady=(0, S.XS))
        xp_lbl = tk.Label(top, text=self._t("reward", xp_val),
                          bg=C.BG, fg=C.GOLD, font=F.LABEL_B)
        xp_lbl.pack(side="left")
        timer_lbl = tk.Label(top, text=f"⏱ {TIME_LIMIT}s",
                             bg=C.BG, fg=C.TEXT_MUTED, font=F.LABEL_B)
        timer_lbl.pack(side="right")

        meaning_row = tk.Frame(outer, bg=C.BG_CARD,
                               highlightbackground=C.BORDER, highlightthickness=1)
        meaning_row.pack(fill="x", pady=(0, S.MD))
        meaning_inner = tk.Frame(meaning_row, bg=C.BG_CARD)
        meaning_inner.pack(fill="x", padx=S.LG, pady=S.SM)
        tk.Label(meaning_inner, text=f"💡 {meaning}", bg=C.BG_CARD,
                 fg=C.PRIMARY, font=F.LABEL, wraplength=460,
                 justify="left").pack(side="left", anchor="w", expand=True)

        listen_row = tk.Frame(outer, bg=C.BG); listen_row.pack(fill="x", pady=(0, S.XS))
        tk.Label(listen_row, text=self._t("build_q"),
                 bg=C.BG, fg=C.TEXT_MUTED, font=F.SMALL).pack(side="left", anchor="w")

        builder = SentenceBuilder(outer, audio_enabled=self._profile.audio_enabled)
        builder.pack(fill="x", pady=S.SM)
        builder.load(words)

        fb = tk.Label(outer, text="", bg=C.BG, font=F.LABEL, wraplength=480)
        fb.pack(pady=S.XS)
        answer_lbl = tk.Label(outer, text="", bg=C.BG, fg=C.TEXT_MUTED,
                              font=F.SMALL, wraplength=480, justify="left")

        _time_left = [TIME_LIMIT]
        _timer_running = [True]

        def _tick():
            if not _timer_running[0]: return
            _time_left[0] -= 1
            remaining = _time_left[0]
            color = C.DANGER if remaining <= 10 else C.WARNING if remaining <= 20 else C.TEXT_MUTED
            try: timer_lbl.config(text=f"⏱ {remaining}s", fg=color)
            except tk.TclError: return
            if remaining <= 0: _time_expired()
            else: outer.after(1000, _tick)

        def _time_expired():
            _timer_running[0] = False
            self.unbind("<Return>")
            self._combo = 0
            builder.mark_wrong()
            fb.config(text=self._t("time_up", correct), fg=C.DANGER)
            answer_lbl.config(text=f"✅ {correct}")
            answer_lbl.pack(anchor="w", pady=(S.SM, 0))
            btn_check.config(state="disabled")

            listen_ans = make_listen_btn(outer, correct, bg=C.BG, size=13)
            listen_ans.pack(anchor="w")

            self._add_sentence_mistake(item)
            self._done += 1
            self.after(4000, self._next_sentence)

        outer.after(1000, _tick)

        def strip_punct(s):
            for ch in "。？！.?!": s = s.replace(ch, "")
            return s

        def check():
            _timer_running[0] = False
            self.unbind("<Return>")
            ans = builder.get_answer()

            if strip_punct(ans) == strip_punct(correct):
                builder.mark_correct()
                try:
                    from ...xp_config import compute_grammar_xp as _cgx
                    base_xp, time_bonus = _cgx(xp_val, _time_left[0])
                except ImportError:
                    base_xp   = xp_val
                    time_bonus = max(0, (_time_left[0] // 10))
                total_xp = base_xp + time_bonus
                self._combo += 1
                self._score += total_xp
                self._profile.xp       += total_xp
                self._profile.daily_xp += total_xp
                self._profile.grammar_completed += 1
                self._db.save_user(self._profile)
                self._score_lbl.config(text=f"⭐ {self._score}")

                bonus_txt = f" +{time_bonus} speed!" if time_bonus > 0 else ""
                fb.config(text=self._t("correct", total_xp) + bonus_txt, fg=C.SUCCESS)
                xp_lbl.config(text=f"⭐ +{total_xp}", fg=C.SUCCESS)
                btn_check.config(state="disabled")

                builder.play_sentence(correct)

                listen_correct = make_listen_btn(outer, correct, bg=C.BG, size=13)
                listen_correct.pack(anchor="w")

                try:
                    play_sound("correct")
                except Exception:
                    pass

                try:
                    new_ach = check_achievements(self._profile)
                    for ach in new_ach: self._notif.show_achievement(ach)
                except Exception:
                    pass

                self._done += 1

                try:
                    from datetime import date as _d
                    _td = _d.today().isoformat()
                    if _td not in self._profile.completed_days:
                        self._profile.completed_days.append(_td)
                    gained = self._profile.award_session_streak()
                    if gained:
                        self._notif.show(self._t("streak_gained", self._profile.streak), "success")
                        self._db.save_user(self._profile)
                except Exception:
                    pass

                if self._combo in (3, 5, 8, 10):
                    self._blocking = True
                    ComboOverlay.show_combo(self.winfo_toplevel(), self._combo,
                        on_done=self._unblock_next)
                else:
                    self.after(2200, self._next_sentence)
            else:
                _timer_running[0] = True
                self._combo = 0
                self._attempts += 1
                builder.mark_wrong()
                try: play_sound("wrong")
                except Exception: pass

                if self._attempts >= 3:
                    _timer_running[0] = False
                    fb.config(text=self._t("out_of_attempts", correct), fg=C.DANGER)
                    answer_lbl.config(text=f"✅ {correct}")
                    answer_lbl.pack(anchor="w", pady=(S.SM, 0))

                    listen_ans = make_listen_btn(outer, correct, bg=C.BG, size=13)
                    listen_ans.pack(anchor="w")

                    self._add_sentence_mistake(item)
                    btn_check.config(state="disabled")
                    self._done += 1
                    self.after(4000, self._next_sentence)
                else:
                    fb.config(text=self._t("wrong_attempts", 3 - self._attempts), fg=C.WARNING)
                    self.after(500, lambda: builder.load(words))

        btn_check = SuccessButton(outer, text=self._t("check"), command=check)
        btn_check.pack(pady=S.MD)
        self.bind("<Return>", lambda e: check())

    def _unblock_next(self):
        self._blocking = False
        self.after(200, self._next_sentence)

    def _next_sentence(self):
        if self._done >= self._target:
            self._show_done(); return
        if self._queue: self._show_sentence()
        else: self._show_loading(); self._fetch_next()

    def _add_sentence_mistake(self, item: dict):
        try:
            existing = self._profile.mistakes.setdefault("sentences", [])
            for m in existing:
                if m.get("correct") == item.get("correct"):
                    m["count"] = m.get("count", 1) + 1; return
            existing.append({
                "type": "sentence",
                "correct": item.get("correct", ""),
                "scrambled": item.get("scrambled", ""),
                "meaning_sr": item.get("meaning_sr", ""),
                "meaning_en": item.get("meaning_en", ""),
                "xp": item.get("xp", 30), "count": 1,
                "hanzi": item.get("correct", ""), "pinyin": "",
            })
            self._db.save_user(self._profile)
        except Exception as ex:
            logger.warning(f"_add_sentence_mistake error: {ex}")

    def _show_done(self):
        for c in self._content.winfo_children(): c.destroy()
        f = tk.Frame(self._content, bg=C.BG); f.pack(expand=True)
        tk.Label(f, text="🎉", bg=C.BG, font=(F.FAMILY, 56)).pack(pady=(S.LG, S.SM))
        tk.Label(f, text=f"{self._target} sentences done!", bg=C.BG,
                 fg=C.TEXT, font=F.H1).pack()
        tk.Label(f, text=f"Score: {self._score} XP", bg=C.BG,
                 fg=C.GOLD, font=F.H2).pack(pady=S.SM)
        PrimaryButton(f, text=self._t("back_menu"), command=self._on_back).pack(pady=S.LG)

    def _show_not_enough(self):
        for c in self._content.winfo_children(): c.destroy()
        f = tk.Frame(self._content, bg=C.BG); f.pack(expand=True)
        tk.Label(f, text="📭", bg=C.BG, font=(F.FAMILY, 48)).pack(pady=S.LG)
        tk.Label(f, text=self._t("not_enough"), bg=C.BG, fg=C.TEXT, font=F.H2).pack()
        GhostButton(f, text=self._t("back"), command=self._on_back).pack(pady=S.MD)

    def _confirm_back(self):
        ConfirmDialog(self,
                      title=self._t("confirm_back_title"),
                      message=self._t("confirm_back_msg"),
                      yes_text=self._t("confirm_back_yes"),
                      no_text=self._t("confirm_back_no"),
                      on_yes=self._on_back, danger=True)