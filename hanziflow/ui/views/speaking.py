from __future__ import annotations
import random, threading, logging
import tkinter as tk
from typing import Callable

from ..theme import (C, F, S, PrimaryButton, GhostButton, ConfirmDialog,
                     bind_hover_translate, pulse_label)
from ..widgets import NotificationManager, AudioRecordButton, make_listen_btn
from ...core import Database, UserProfile, Word, check_achievements, play_audio, gemini, play_sound

logger = logging.getLogger("HanziFlow.Speaking")

_T = {
    "en": {
        "title": "🎤  Speaking Practice",
        "back": "⬅ Back",
        "progress": "{} / {}",
        "instr": "Pronounce this aloud:",
        "play_btn": "🔊  Play pronunciation",
        "score": "{}/100",
        "next": "Next ➡",
        "done": "Practice complete!",
        "empty": "No words yet. Add some first.",
        "feedback_great": "🎯 Excellent! +{} XP",
        "feedback_ok": "👍 Good try! +{} XP",
        "feedback_bad": "Keep practicing!",
        "heard": "🎤  Heard: \"{}\"",
        "no_mic": "⚠️  Install pyaudio for speaking practice.",
        "too_short": "⚠️  Hold longer while speaking.",
        "error": "❌ Could not analyze.",
        "sim_title": "Text Mode",
        "sim_instr": "Type the pinyin to simulate speaking:",
        "sim_check": "Submit",
        "confirm_back_title": "Leave Speaking?",
        "confirm_back_msg": "Your progress will not be saved.",
        "confirm_back_yes": "Leave",
        "confirm_back_no": "Keep going",
        "streak_gained": "🔥 Streak +1! Day {}",
    },
    "sr": {
        "title": "🎤  Vežba govora",
        "back": "⬅ Nazad",
        "progress": "{} / {}",
        "instr": "Izgovori naglas:",
        "play_btn": "🔊  Pusti izgovor",
        "score": "{}/100",
        "next": "Sledeća ➡",
        "done": "Vežba završena!",
        "empty": "Nema reči. Dodaj neke.",
        "feedback_great": "🎯 Odlično! +{} XP",
        "feedback_ok": "👍 Dobar pokušaj! +{} XP",
        "feedback_bad": "Vežbaj dalje!",
        "heard": "🎤  Čuo sam: \"{}\"",
        "no_mic": "⚠️  Instaliraj pyaudio za govornu vežbu.",
        "too_short": "⚠️  Drži duže dok govoriš.",
        "error": "❌ Greška pri analizi.",
        "sim_title": "Tekst mod",
        "sim_instr": "Ukucaj pinyin kao simulaciju govora:",
        "sim_check": "Potvrdi",
        "confirm_back_title": "Napusti Govornu?",
        "confirm_back_msg": "Napredak neće biti sačuvan.",
        "confirm_back_yes": "Napusti",
        "confirm_back_no": "Nastavi",
        "streak_gained": "🔥 Streak +1! Dan {}",
    },
}


def _meaning(w: Word, lang: str) -> str:
    return w.meaning_en if lang == "en" else w.meaning_sr


class SpeakingView(tk.Frame):

    def __init__(self, parent, profile: UserProfile,
                 notif: NotificationManager, on_back: Callable):
        super().__init__(parent, bg=C.BG)
        self._profile = profile
        self._lang    = profile.lang
        self._db      = Database()
        self._notif   = notif
        self._on_back = on_back
        self._pool: list[Word] = []
        self._idx     = 0
        self._total_xp= 0
        self._correct = 0
        self._streak_awarded = False
        self._build()
        self._load()

    def _t(self, key, *args):
        txt = _T[self._lang].get(key, key)
        return txt.format(*args) if args else txt

    def _build(self):
        hdr = tk.Frame(self, bg=C.BG_SIDEBAR); hdr.pack(fill="x")
        GhostButton(hdr, text=self._t("back"), command=self._confirm_back).pack(
            side="left", padx=S.MD, pady=S.SM)
        tk.Label(hdr, text=self._t("title"), bg=C.BG_SIDEBAR,
                 fg=C.TEXT, font=F.H2).pack(side="left")
        self._progress_lbl = tk.Label(hdr, text="", bg=C.BG_SIDEBAR,
                                      fg=C.TEXT_MUTED, font=F.SMALL)
        self._progress_lbl.pack(side="right", padx=S.MD)
        self._xp_lbl = tk.Label(hdr, text="", bg=C.BG_SIDEBAR,
                                fg=C.GOLD, font=F.LABEL_B)
        self._xp_lbl.pack(side="right", padx=S.SM)

        self._content = tk.Frame(self, bg=C.BG)
        self._content.pack(fill="both", expand=True)

    def _load(self):
        words = [Word.from_dict(w) for w in self._profile.vocab]
        if not words:
            self._show_empty(); return
        self._pool = words[:]
        random.shuffle(self._pool)
        self._idx = 0
        self._total_xp = 0
        self._correct  = 0
        self._streak_awarded = False
        self._show_word()

    def _show_word(self):
        if self._idx >= len(self._pool):
            self._show_done(); return

        for c in self._content.winfo_children(): c.destroy()
        w = self._pool[self._idx]
        self._progress_lbl.config(text=self._t("progress", self._idx + 1, len(self._pool)))
        if self._total_xp: self._xp_lbl.config(text=f"⭐ {self._total_xp} XP")

        root = self.winfo_toplevel()
        center = tk.Frame(self._content, bg=C.BG); center.pack(expand=True)

        char_frame = tk.Frame(center, bg=C.BG_CARD,
                              highlightbackground=C.BORDER, highlightthickness=1)
        char_frame.pack(pady=S.LG, padx=S.XXL, fill="x")

        char_inner = tk.Frame(char_frame, bg=C.BG_CARD)
        char_inner.pack(pady=S.MD)

        hanzi_lbl = tk.Label(char_inner, text=w.hanzi, bg=C.BG_CARD,
                             fg=C.DANGER, font=(F.FAMILY, 72, "bold"))
        hanzi_lbl.pack()
        bind_hover_translate(hanzi_lbl, w.hanzi, _meaning(w, self._lang), root)

        pinyin_row = tk.Frame(char_inner, bg=C.BG_CARD)
        pinyin_row.pack()
        tk.Label(pinyin_row, text=w.pinyin, bg=C.BG_CARD,
                 fg=C.TEXT_MUTED, font=F.H2).pack(side="left", padx=(0, S.XS))
        listen_pinyin = make_listen_btn(pinyin_row, w.hanzi, bg=C.BG_CARD, size=16)
        listen_pinyin.pack(side="left")

        tk.Label(char_frame, text=_meaning(w, self._lang), bg=C.BG_CARD,
                 fg=C.PRIMARY, font=F.LABEL_B).pack(pady=(0, S.MD))

        tk.Label(center, text=self._t("instr"), bg=C.BG,
                 fg=C.TEXT, font=F.LABEL).pack(pady=(S.SM, S.XS))

        score_lbl = tk.Label(center, text="", bg=C.BG, fg=C.TEXT, font=(F.FAMILY, 28, "bold"))
        score_lbl.pack(pady=S.XS)
        fb_lbl = tk.Label(center, text="", bg=C.BG, fg=C.TEXT_MUTED,
                          font=F.LABEL, wraplength=420, justify="center")
        fb_lbl.pack(pady=S.XS)
        heard_lbl = tk.Label(center, text="", bg=C.BG,
                             fg=C.TEXT_MUTED, font=F.SMALL)
        heard_lbl.pack()

        next_btn = PrimaryButton(center, text=self._t("next"), command=self._next_word)

        def _show_result(score, fb_text, heard, xp=0):
            if score >= 75:
                color = C.SUCCESS
                score_lbl.config(text=f"✅ {score}/100", fg=color)
                fb_lbl.config(text=self._t("feedback_great", xp) if xp else fb_text, fg=color)
            elif score >= 45:
                color = C.WARNING
                score_lbl.config(text=f"🟡 {score}/100", fg=color)
                fb_lbl.config(text=self._t("feedback_ok", xp) if xp else fb_text, fg=color)
            else:
                color = C.DANGER
                score_lbl.config(text=f"❌ {score}/100", fg=color)
                fb_lbl.config(text=self._t("feedback_bad"), fg=color)

            if heard: heard_lbl.config(text=self._t("heard", heard))
            try: pulse_label(score_lbl)
            except Exception: pass
            next_btn.pack(pady=S.MD)

            if score >= 45 and not self._streak_awarded:
                try:
                    from datetime import date as _d
                    _td = _d.today().isoformat()
                    if _td not in self._profile.completed_days:
                        self._profile.completed_days.append(_td)
                    gained = self._profile.award_session_streak()
                    if gained:
                        self._streak_awarded = True
                        self._notif.show(self._t("streak_gained", self._profile.streak), "success")
                        self._db.save_user(self._profile)
                except Exception:
                    pass

        has_mic = True
        try:
            import pyaudio; pyaudio.PyAudio()
        except Exception:
            has_mic = False

        if has_mic:
            def on_recorded(wav_bytes: bytes):
                if not wav_bytes or len(wav_bytes) < 1000:
                    fb_lbl.config(text=self._t("too_short"), fg=C.WARNING); return

                fb_lbl.config(text="🤖 Analyzing...", fg=C.PRIMARY)
                score_lbl.config(text=""); heard_lbl.config(text="")

                def do():
                    try:
                        result = gemini.evaluate_speaking(wav_bytes, w.hanzi, w.pinyin)
                    except Exception as ex:
                        logger.warning(f"evaluate_speaking error: {ex}")
                        result = None
                    if self.winfo_exists():
                        self.after(0, lambda: handle(result))

                def handle(r):
                    if r is None:
                        cooldown = 18; rec.set_enabled(False)
                        def _countdown(secs):
                            try:
                                if not self.winfo_exists(): return
                                if secs > 0:
                                    fb_lbl.config(text=f"⏳ API busy — {secs}s", fg=C.WARNING)
                                    self.after(1000, lambda: _countdown(secs - 1))
                                else:
                                    fb_lbl.config(text="🎙 Ready!", fg=C.TEXT_MUTED)
                                    rec.set_enabled(True)
                            except tk.TclError: pass
                        _countdown(cooldown)
                        next_btn.pack(pady=S.MD)
                        return

                    score   = r.get("score", 0)
                    fb_text = r.get("feedback", "")
                    heard   = r.get("heard", "").strip()
                    xp = 0
                    try:
                        from ...xp_config import compute_speaking_xp as _csx
                        xp = _csx(w.xp, score)
                    except ImportError:
                        if score >= 75:   xp = w.xp
                        elif score >= 45: xp = max(3, w.xp // 2)
                    if xp > 0:
                        self._gain_xp(xp)
                        if score >= 75: self._correct += 1
                    _show_result(score, fb_text, heard, xp)

                threading.Thread(target=do, daemon=True).start()

            rec = AudioRecordButton(center, on_recorded=on_recorded)
            rec.pack(pady=S.LG)

        else:
            tk.Label(center, text=self._t("sim_title"), bg=C.BG,
                     fg=C.WARNING, font=F.LABEL_B).pack(pady=(S.MD, 0))
            tk.Label(center, text=self._t("sim_instr"), bg=C.BG,
                     fg=C.TEXT_MUTED, font=F.SMALL).pack(pady=(S.XS, S.SM))

            sim_entry = tk.Entry(center, font=F.LABEL, justify="center", width=18,
                                 bg=C.BG_INPUT, fg=C.TEXT, relief="flat",
                                 highlightbackground=C.BORDER, highlightthickness=1,
                                 insertbackground=C.TEXT)
            sim_entry.pack(ipady=S.XS)
            sim_entry.bind("<FocusIn>", lambda e: sim_entry.config(highlightbackground=C.BORDER_FOCUS, highlightthickness=2))
            sim_entry.bind("<FocusOut>", lambda e: sim_entry.config(highlightbackground=C.BORDER, highlightthickness=1))
            sim_entry.focus_set()

            def _simulate():
                import unicodedata
                typed = sim_entry.get().strip()
                if not typed: return
                sim_btn.config(state="disabled")
                def _norm(p):
                    s = unicodedata.normalize("NFD", p.lower().replace(" ", ""))
                    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("v", "u")
                target = _norm(w.pinyin)
                answer = _norm(typed)
                if answer == target:
                    score = 95
                elif answer == w.hanzi:
                    score = 90
                else:
                    common = sum(1 for a, b in zip(answer, target) if a == b)
                    score = int(common / max(len(target), 1) * 80)
                xp = 0
                try:
                    from ...xp_config import compute_speaking_xp as _csx
                    xp = _csx(w.xp, score)
                except ImportError:
                    if score >= 75:   xp = w.xp
                    elif score >= 45: xp = max(3, w.xp // 2)
                if xp > 0:
                    self._gain_xp(xp)
                    if score >= 75:
                        self._correct += 1
                        try: play_sound("correct")
                        except Exception: pass
                _show_result(score, "", typed, xp)

            sim_btn = PrimaryButton(center, text=self._t("sim_check"), command=_simulate)
            sim_btn.pack(pady=S.SM)
            sim_entry.bind("<Return>", lambda e: _simulate())
            tk.Label(center, text="💡 " + self._t("no_mic"),
                     bg=C.BG, fg=C.TEXT_LIGHT, font=F.TINY).pack(pady=S.XS)

    def _next_word(self):
        self._idx += 1
        self._show_word()

    def _gain_xp(self, amount: int):
        self._total_xp        += amount
        self._profile.xp      += amount
        self._profile.daily_xp += amount
        self._db.save_user(self._profile)
        try: self._xp_lbl.config(text=f"⭐ {self._total_xp} XP")
        except tk.TclError: pass

    def _show_empty(self):
        for c in self._content.winfo_children(): c.destroy()
        f = tk.Frame(self._content, bg=C.BG); f.pack(expand=True)
        tk.Label(f, text="📭", bg=C.BG, font=(F.FAMILY, 48)).pack(pady=S.LG)
        tk.Label(f, text=self._t("empty"), bg=C.BG, fg=C.TEXT, font=F.H2).pack()
        GhostButton(f, text=self._t("back"), command=self._on_back).pack(pady=S.MD)

    def _show_done(self):
        for c in self._content.winfo_children(): c.destroy()
        f = tk.Frame(self._content, bg=C.BG); f.pack(expand=True)
        tk.Label(f, text="🎤", bg=C.BG, font=(F.FAMILY, 56)).pack(pady=(S.LG, S.SM))
        tk.Label(f, text=self._t("done"), bg=C.BG, fg=C.TEXT, font=F.H1).pack()
        stats_row = tk.Frame(f, bg=C.BG); stats_row.pack(pady=S.LG)
        def stat(parent, label, value, color):
            b = tk.Frame(parent, bg=C.BG_CARD, highlightbackground=C.BORDER, highlightthickness=1)
            b.pack(side="left", padx=S.SM, ipadx=S.LG, ipady=S.MD)
            tk.Label(b, text=value, bg=C.BG_CARD, fg=color, font=F.H2).pack()
            tk.Label(b, text=label, bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.TINY).pack()
        stat(stats_row, "XP Earned", f"+{self._total_xp}", C.GOLD)
        stat(stats_row, "Correct", str(self._correct), C.SUCCESS)
        stat(stats_row, "Words", str(len(self._pool)), C.PRIMARY)
        PrimaryButton(f, text=self._t("back"), command=self._on_back).pack(pady=S.MD)

    def _confirm_back(self):
        ConfirmDialog(self,
                      title=self._t("confirm_back_title"),
                      message=self._t("confirm_back_msg"),
                      yes_text=self._t("confirm_back_yes"),
                      no_text=self._t("confirm_back_no"),
                      on_yes=self._on_back)