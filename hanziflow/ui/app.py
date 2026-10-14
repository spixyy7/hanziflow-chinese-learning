"""
ui/app.py — Glavni aplikacioni kontroler.
NOVO: fullscreen (F11 + dugme), moderan MistakesView sa karticama.
"""
from __future__ import annotations
import os, threading, unicodedata, random, logging
import tkinter as tk
from datetime import date, timedelta

try:
    from tkinterdnd2 import TkinterDnD; DND_ROOT = True
except ImportError:
    DND_ROOT = False

import pygame

from .theme import setup_theme, C, F, S, GhostButton, PrimaryButton, SuccessButton, DangerButton
from .theme import ConfirmDialog, toggle_fullscreen, Card, hover_card
from .widgets import NotificationManager, SentenceBuilder, LevelUpOverlay
from .friends_panel import FriendsPanel
from .views import (LoginView, DashboardView, QuizView, GrammarView,
                    SpeakingView, AddWordsView, ArenaView, LeaderboardView, ProfileView)
from ..core import (Database, UserProfile, WeaknessDetector, Leaderboard,
                    gemini, check_achievements, set_audio_enabled, is_audio_enabled)
from ..core.adaptive import compute_level

logger = logging.getLogger("HanziFlow.App")


class App:
    W = 580; H = 800

    def __init__(self):
        self._db      = Database()
        self._profile: UserProfile | None = None
        self._fullscreen = False

        if DND_ROOT:
            self._root = TkinterDnD.Tk()
        else:
            self._root = tk.Tk()

        self._root.title("HanziFlow")
        self._root.geometry(f"{self.W}x{self.H}")
        self._root.minsize(460, 600)
        self._root.configure(bg=C.BG)
        self._root.protocol("WM_DELETE_WINDOW", self._on_quit)

        # Fullscreen hotkey
        self._root.bind("<F11>", lambda e: self._toggle_fullscreen())
        self._root.bind("<Escape>", lambda e: self._exit_fullscreen())

        setup_theme(self._root, mode="system")
        try:
            pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=512)
        except Exception:
            pass

        from ..core.sounds import preload_all as _preload_sounds
        threading.Thread(target=_preload_sounds, daemon=True).start()

        self._notif   = NotificationManager(self._root)
        self._current: tk.Frame | None = None
        self._lan     = None
        self._chat_fl = None

        self._show_login()
        self._root.mainloop()

    def _toggle_fullscreen(self):
        self._fullscreen = toggle_fullscreen(self._root)

    def _exit_fullscreen(self):
        if self._fullscreen:
            self._fullscreen = False
            self._root.attributes("-fullscreen", False)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _swap(self, new_frame: tk.Frame):
        if self._current:
            self._current.destroy()
        self._current = new_frame
        new_frame.pack(fill="both", expand=True)
        if self._chat_fl:
            try: self._chat_fl._bwin.lift()
            except Exception: pass

    def _show_login(self):
        from .theme import C as _C, _apply_ttk
        _C.set_theme(_C._current_mode)
        _apply_ttk(self._root)
        self._swap(LoginView(self._root, on_success=self._on_login))

    def _on_login(self, profile: UserProfile):
        self._profile = profile
        from .theme import C as _C, apply_theme_to_root, _apply_ttk
        _C.set_theme(profile.theme)
        _apply_ttk(self._root)
        from ..core.audio import set_user as _set_audio_user
        _set_audio_user(profile.username)
        set_audio_enabled(profile.audio_enabled)
        self._check_streak()
        # LAN server
        try:
            from ..core.lan_server import LANServer
            from ..core.notifications import NotifStore
            self._lan = LANServer(self._profile, self._db)
            _ns = NotifStore(self._profile.username)
            self._lan.on_friend_request  = lambda u: _ns.add_friend_request(u)
            self._lan.on_friend_accepted = lambda u: _ns.add_friend_accepted(u)
            self._lan.on_message         = lambda m: _ns.add_message(m.get("from","?"), m.get("text",""))
            self._lan.start()
        except Exception as _e:
            import logging; logging.getLogger("HanziFlow").debug(f"LAN: {_e}")
        # Friends panel
        try:
            # Always create fresh FriendsPanel on login
            # (previous instance was hidden on logout and set to None)
            self._chat_fl = FriendsPanel(self._root, self._profile, self._lan)
            self._root.after(800, self._chat_fl.show)
        except Exception: pass
        self._show_dashboard()
        # Check for updates in background (non-blocking)
        self._root.after(3000, self._check_update)
        threading.Thread(target=self._bg_coach_check, daemon=True).start()
        threading.Thread(target=lambda: Leaderboard().fetch_from_onedrive(), daemon=True).start()
        self._root.after(800, lambda: self._preload_audio_popup(profile))

    def _show_dashboard(self):
        dash = DashboardView(
            self._root,
            profile       = self._profile,
            on_quiz       = self._show_quiz,
            on_grammar    = self._show_grammar,
            on_speaking   = self._show_speaking,
            on_add_word   = self._show_add_words,
            on_mistakes   = self._show_mistakes,
            on_goal       = self._show_goal,
            on_logout     = self._on_logout,
            on_arena      = self._show_arena,
            on_leaderboard= self._show_leaderboard,
            on_profile    = self._show_profile,
            on_writing    = self._show_writing,
        )
        dash.bind("<<ThemeChanged>>", lambda e: self._show_dashboard())
        self._swap(dash)
        self._wire_notif_bell(dash)

    def _wire_notif_bell(self, dash):
        try:
            from .notif_bell import NotifBell
            from ..core.notifications import NotifStore

            store = NotifStore(self._profile.username)

            def _open_chat(username):
                try:
                    if self._chat_fl:
                        self._chat_fl.open_chat(username)
                except Exception:
                    pass

            bell = NotifBell(
                dash,
                self._profile,
                lan_server    = self._lan,
                on_accept     = None,
                on_open_chat  = _open_chat,
            )

            def _toggle_bell():
                bell._toggle()

            dash.set_notif_callback(_toggle_bell, store.unread_count())

            self._bell = bell

            def _poll_badge():
                try:
                    if not dash.winfo_exists():
                        return
                    count = store.unread_count()
                    dash.update_notif_count(count)
                    dash.after(3000, _poll_badge)
                except Exception:
                    pass

            dash.after(1000, _poll_badge)

        except Exception as e:
            logger.warning(f"NotifBell wire error: {e}")

    def _show_quiz(self):
        self._swap(QuizView(self._root, self._profile, self._notif,
                            on_back=self._show_dashboard))

    def _show_grammar(self):
        self._swap(GrammarView(self._root, self._profile, self._notif,
                               on_back=self._show_dashboard))

    def _show_speaking(self):
        self._swap(SpeakingView(self._root, self._profile, self._notif,
                                on_back=self._show_dashboard))

    def _show_add_words(self):
        self._swap(AddWordsView(self._root, self._profile, self._notif,
                                on_back=self._show_dashboard))

    def _show_arena(self):
        self._swap(ArenaView(self._root, self._profile, self._notif,
                             on_back=self._show_dashboard))

    def _show_leaderboard(self):
        self._swap(LeaderboardView(self._root, self._profile, self._notif,
                                   on_back=self._show_dashboard, lan_server=self._lan))

    def _show_profile(self):
        self._swap(ProfileView(self._root, self._profile, self._notif,
                               on_back=self._show_dashboard))

    def _show_goal(self):
        self._swap(_GoalView(self._root, self._profile, self._notif,
                             on_back=self._show_dashboard))

    def _show_mistakes(self):
        m = self._profile.get_mistakes()
        if len(m["words"]) + len(m["sentences"]) == 0:
            self._notif.show("No mistakes! 🎉" if self._profile.lang == "en"
                             else "Nema grešaka! 🎉", "success"); return
        self._swap(_MistakesView(self._root, self._profile, self._notif,
                                 on_back=self._show_dashboard))

    def _show_writing(self):
        try:
            from .views.writing import WritingView
            self._swap(WritingView(self._root, self._profile, self._notif,
                                   on_back=self._show_dashboard))
        except Exception as e:
            logger.warning(f"_show_writing error: {e}")
            self._show_dashboard()

    def _check_update(self):
        """Check GitHub for new version — runs in background."""
        import threading
        def _do():
            try:
                from ..core.updater import check_for_update, download_and_apply
                info = check_for_update()
                if info:
                    self._root.after(0, lambda: self._show_update_dialog(info))
            except Exception:
                pass
        threading.Thread(target=_do, daemon=True).start()

    def _show_update_dialog(self, info: dict):
        try:
            from .update_dialog import show_update_dialog
            from ..core.updater import download_and_apply
            def do_update(on_progress, on_done, on_error):
                download_and_apply(
                    info["download_url"],
                    on_progress=on_progress,
                    on_done=on_done,
                    on_error=on_error,
                )
            show_update_dialog(self._root, info,
                               on_update=do_update,
                               on_skip=lambda: None)
        except Exception:
            pass

    def _on_logout(self):
        if self._lan:
            try: self._lan.stop()
            except Exception: pass
            self._lan = None
        if self._chat_fl:
            try:
                self._chat_fl.hide()          # withdraw button + panel
                self._chat_fl._open = False   # reset state
            except Exception: pass
            self._chat_fl = None              # will be recreated on next login
        if self._profile:
            self._db.save_user(self._profile)
        Database().clear_session()
        self._profile = None
        self._show_login()

    # ── Streak ────────────────────────────────────────────────────────────────

    def _check_streak(self):
        p     = self._profile
        today = date.today().isoformat()
        today_dt = date.today()

        if not p.last_date or p.last_date == today:
            if p.last_date != today: p.daily_xp = 0
            p.last_date = today
            self._db.save_user(p); return

        try:
            last_dt   = date.fromisoformat(p.last_date)
            days_away = (today_dt - last_dt).days
        except ValueError:
            days_away = 0

        p.daily_xp = 0; p.last_date = today

        if days_away <= 0:
            self._db.save_user(p); return

        yesterday = (today_dt - timedelta(days=1)).isoformat()
        goal_met_yesterday = yesterday in p.completed_days

        if not goal_met_yesterday and p.streak > 0:
            if p.streak_shields > 0:
                p.streak_shields -= 1
                self._notif.show(
                    f"🛡️ Streak Shield used! {p.streak_shields} left." if p.lang == "en"
                    else f"🛡️ Streak Shield! Preostalo: {p.streak_shields}", "info", delay_ms=5000)
            else:
                p.streak = 0
                self._notif.show("💔 Streak lost! Start again today." if p.lang == "en"
                                 else "💔 Streak izgubljen!", "warning")

        # No XP penalty for inactivity

        if p.streak > p.longest_streak: p.longest_streak = p.streak
        self._db.save_user(p)

        if p.streak > 0 and p.streak % 7 == 0 and p.streak_shields < 3:
            if p.last_shield_earn != today:
                p.streak_shields = min(3, p.streak_shields + 1)
                p.last_shield_earn = today
                self._db.save_user(p)
                self._notif.show(f"🛡️ Streak Shield earned! ({p.streak_shields}/3)", "success")

        if days_away >= 2 and p.vocab:
            self._root.after(2000, self._show_return_popup)

    def _show_return_popup(self):
        p = self._profile
        msg = "Welcome back! 🎉\nWant to review what you learned?" if p.lang == "en" \
              else "Dobrodošli nazad! 🎉\nŽeliš li da ponoviš?"
        win = tk.Toplevel(self._root)
        win.title(""); win.configure(bg=C.BG_CARD)
        win.resizable(False, False); win.attributes("-topmost", True)
        root = self._root
        rx, ry = root.winfo_rootx(), root.winfo_rooty()
        rw, rh = root.winfo_width(), root.winfo_height()
        w, h = 360, 220
        win.geometry(f"{w}x{h}+{rx+(rw-w)//2}+{ry+(rh-h)//2}")
        win.transient(root); win.grab_set()
        tk.Label(win, text="📖", bg=C.BG_CARD, font=(F.FAMILY, 36)).pack(pady=(S.LG, S.XS))
        tk.Label(win, text=msg, bg=C.BG_CARD, fg=C.TEXT, font=F.LABEL_B,
                 justify="center", wraplength=300).pack(pady=(0, S.LG))
        row = tk.Frame(win, bg=C.BG_CARD); row.pack()
        PrimaryButton(row, text="Yes, let's go! →" if p.lang == "en" else "Da, hajde! →",
                      command=lambda: (win.destroy(), self._show_quiz())).pack(side="left", padx=S.SM)
        GhostButton(row, text="Later" if p.lang == "en" else "Kasnije",
                    command=win.destroy).pack(side="left")

    # ── Audio preload ─────────────────────────────────────────────────────────

    def _preload_audio_popup(self, profile: UserProfile) -> None:
        from ..core.audio import has_cached, preload_all as preload_all_audio
        vocab = profile.vocab
        if not vocab: return
        hanzi_list = [w.get("hanzi", "") for w in vocab if w.get("hanzi")]
        missing = [h for h in hanzi_list if not has_cached(h)]
        if not missing: return
        total = len(missing)

        overlay = tk.Frame(self._root, bg=C.BG)
        overlay.place(x=0, y=0, relwidth=1, relheight=1); overlay.lift()
        center = tk.Frame(overlay, bg=C.BG)
        center.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(center, text="🔊", bg=C.BG, fg=C.PRIMARY, font=(F.FAMILY, 48)).pack(pady=(0, S.MD))
        tk.Label(center, text="Downloading pronunciation audio...",
                 bg=C.BG, fg=C.TEXT, font=(F.FAMILY, 14, "bold")).pack()
        tk.Label(center, text="Please wait...", bg=C.BG,
                 fg=C.TEXT_MUTED, font=F.SMALL).pack(pady=(S.XS, S.LG))
        prog_var = tk.StringVar(value=f"0 / {total} words")
        prog_lbl = tk.Label(center, textvariable=prog_var, bg=C.BG,
                            fg=C.TEXT_MUTED, font=F.BODY); prog_lbl.pack(pady=(0, S.SM))
        bar_frame = tk.Frame(center, bg=C.BORDER, height=8, width=400)
        bar_frame.pack(pady=(0, S.LG)); bar_frame.pack_propagate(False)
        bar_fill = tk.Frame(bar_frame, bg=C.PRIMARY, height=8, width=0)
        bar_fill.place(x=0, y=0, height=8)
        tk.Button(center, text="✕  Exit", bg=C.DANGER, fg=C.TEXT_WHITE,
                  font=F.BODY, relief="flat", bd=0, cursor="hand2",
                  padx=S.XL, pady=S.SM, command=self._on_quit).pack()
        done_flag = [False]

        def _update(done, total_cnt):
            if done_flag[0]: return
            try:
                prog_var.set(f"{done} / {total_cnt} words")
                bar_fill.place(x=0, y=0, height=8, width=int(400 * done / max(total_cnt, 1)))
            except tk.TclError: pass

        def _finish():
            if done_flag[0]: return
            done_flag[0] = True
            try:
                prog_var.set(f"✅ {total} ready!"); prog_lbl.config(fg=C.SUCCESS)
                bar_fill.config(bg=C.SUCCESS); bar_fill.place(x=0, y=0, height=8, width=400)
                overlay.after(1500, overlay.destroy)
            except tk.TclError: pass

        preload_all_audio(missing,
                          on_progress=lambda d, t: self._root.after(0, lambda: _update(d, t)),
                          on_done=lambda: self._root.after(0, _finish))

    # ── Background coach ──────────────────────────────────────────────────────

    def _bg_coach_check(self):
        p = self._profile; today = date.today().isoformat()
        if p.last_goal_check == today: return
        try:
            wd = WeaknessDetector(p); perf = wd.ai_difficulty_prompt()
            result = gemini.ai_coach(p.daily_goal, p.daily_xp_history, perf)
            if result and result.get("action") in ("increase", "decrease"):
                p.last_goal_check = today; self._db.save_user(p)
                msg = result.get("message", "")
                self._root.after(4000, lambda: self._notif.show(f"🤖 {msg}", "info", delay_ms=7000))
        except Exception as e:
            logger.warning(f"bg_coach_check error: {e}")

    def _on_quit(self):
        if self._profile:
            self._db.save_user(self._profile)
        try: pygame.mixer.quit()
        except Exception: pass
        self._root.destroy()
        os._exit(0)


# ─── Goal View ────────────────────────────────────────────────────────────────

class _GoalView(tk.Frame):
    _T = {
        "en": {
            "title": "🎯  Daily Goal", "back": "⬅ Back",
            "current": "Current goal: {} XP",
            "easy": "😴  Casual", "easy_xp": "50 XP / day",
            "regular": "📚  Regular", "regular_xp": "200 XP / day",
            "hard": "🔥  Intense", "hard_xp": "1000 XP / day",
            "custom": "Custom XP:", "set": "Set",
            "updated": "Goal set to {} XP!",
            "coach_title": "🤖  AI Coach Analysis",
            "coach_loading": "Analyzing your learning history...",
            "coach_accept": "✅  Accept: {} XP",
            "coach_keep": "Your current pace is great!",
            "coach_error": "AI coach unavailable.",
        },
        "sr": {
            "title": "🎯  Dnevni cilj", "back": "⬅ Nazad",
            "current": "Trenutni cilj: {} XP",
            "easy": "😴  Opušteno", "easy_xp": "50 XP / dan",
            "regular": "📚  Redovno", "regular_xp": "200 XP / dan",
            "hard": "🔥  Intenzivno", "hard_xp": "1000 XP / dan",
            "custom": "Custom XP:", "set": "Postavi",
            "updated": "Cilj: {} XP!",
            "coach_title": "🤖  AI Trener",
            "coach_loading": "Analiziram istoriju...",
            "coach_accept": "✅  Prihvati: {} XP",
            "coach_keep": "Tempo je odličan!",
            "coach_error": "AI trener nedostupan.",
        },
    }

    def __init__(self, parent, profile, notif, on_back):
        super().__init__(parent, bg=C.BG)
        self._profile = profile; self._lang = profile.lang
        self._db = Database(); self._notif = notif; self._on_back = on_back
        self._build()
        threading.Thread(target=self._fetch_coach, daemon=True).start()

    def _t(self, k, *a):
        txt = self._T[self._lang].get(k, k)
        return txt.format(*a) if a else txt

    def _build(self):
        hdr = tk.Frame(self, bg=C.BG_SIDEBAR); hdr.pack(fill="x")
        GhostButton(hdr, text=self._t("back"), command=self._on_back).pack(side="left", padx=S.MD, pady=S.SM)
        tk.Label(hdr, text=self._t("title"), bg=C.BG_SIDEBAR, fg=C.TEXT, font=F.H2).pack(side="left")

        body = tk.Frame(self, bg=C.BG); body.pack(fill="both", expand=True, padx=S.XL, pady=S.LG)
        tk.Label(body, text=self._t("current", self._profile.daily_goal),
                 bg=C.BG, fg=C.TEXT, font=F.H1).pack(pady=(0, S.LG))

        presets = tk.Frame(body, bg=C.BG); presets.pack(fill="x", pady=(0, S.MD))
        for col, (key, val, color) in enumerate([("easy", 50, C.SUCCESS), ("regular", 200, C.PRIMARY), ("hard", 1000, C.DANGER)]):
            card = tk.Frame(presets, bg=color, cursor="hand2")
            card.grid(row=0, column=col, padx=S.XS, sticky="ew")
            presets.columnconfigure(col, weight=1)
            tk.Label(card, text=self._t(key), bg=color, fg="white", font=F.BODY_B).pack(pady=(S.MD, 2))
            tk.Label(card, text=self._t(key+"_xp"), bg=color, fg="white", font=F.SMALL).pack(pady=(0, S.MD))
            for w in [card] + list(card.winfo_children()):
                w.bind("<Button-1>", lambda e, v=val: self._set(v))

        row = tk.Frame(body, bg=C.BG); row.pack(pady=S.SM)
        tk.Label(row, text=self._t("custom"), bg=C.BG, fg=C.TEXT_MUTED, font=F.SMALL).pack(side="left")
        self._e = tk.Entry(row, width=7, font=F.BODY, justify="center",
                           bg=C.BG_INPUT, fg=C.TEXT, relief="flat",
                           highlightbackground=C.BORDER, highlightthickness=1)
        self._e.pack(side="left", padx=S.XS)
        GhostButton(row, text=self._t("set"), command=lambda: self._set(self._e.get())).pack(side="left")

        coach_card = tk.Frame(body, bg=C.BG_CARD, highlightbackground=C.BORDER, highlightthickness=1)
        coach_card.pack(fill="x", pady=(S.LG, 0))
        inner = tk.Frame(coach_card, bg=C.BG_CARD); inner.pack(fill="both", padx=S.LG, pady=S.MD)
        tk.Label(inner, text=self._t("coach_title"), bg=C.BG_CARD, fg=C.PRIMARY, font=F.TITLE).pack(anchor="w")
        self._coach_msg = tk.Label(inner, text=self._t("coach_loading"),
                                   bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.BODY, wraplength=460, justify="left")
        self._coach_msg.pack(anchor="w", pady=(S.XS, S.SM))
        self._coach_btn_frame = tk.Frame(inner, bg=C.BG_CARD)
        self._coach_btn_frame.pack(anchor="w")

    def _fetch_coach(self):
        try:
            wd = WeaknessDetector(self._profile); perf = wd.ai_difficulty_prompt()
            result = gemini.ai_coach(self._profile.daily_goal, self._profile.daily_xp_history, perf)
        except Exception:
            result = None
        if self.winfo_exists():
            self.after(0, lambda: self._show_coach(result))

    def _show_coach(self, result):
        try:
            if not self._coach_btn_frame.winfo_exists(): return
            for w in self._coach_btn_frame.winfo_children(): w.destroy()
        except Exception: return
        if not result:
            try: self._coach_msg.config(text=self._t("coach_error"), fg=C.DANGER)
            except Exception: pass
            return
        action = result.get("action", "keep"); message = result.get("message", self._t("coach_keep"))
        suggested = result.get("suggested_goal", self._profile.daily_goal)
        try: self._coach_msg.config(text=message, fg=C.TEXT)
        except Exception: return
        if action in ("increase", "decrease"):
            tk.Button(self._coach_btn_frame,
                      text=self._t("coach_accept", suggested),
                      bg=C.SUCCESS if action == "increase" else C.WARNING,
                      fg=C.TEXT_WHITE, font=F.BODY_B, relief="flat", bd=0,
                      cursor="hand2", padx=S.LG, pady=S.XS,
                      command=lambda: self._set(suggested)).pack(side="left")

    def _set(self, val):
        try: g = int(val); assert g > 0
        except (ValueError, AssertionError): return
        self._profile.daily_goal = g; self._profile.goal_setup_done = True
        self._db.save_user(self._profile)
        self._notif.show(self._t("updated", g), "success")
        self._on_back()


# ─── Mistakes View (modernized with cards) ────────────────────────────────────

class _MistakesView(tk.Frame):
    _T = {
        "en": {
            "title": "📋  Mistakes",
            "back": "⬅ Back",
            "progress": "{} remaining",
            "word_prompt": "Meaning: {}",
            "type_hanzi": "Type Hanzi:",
            "type_pinyin": "Type Pinyin:",
            "check": "✔  Check",
            "correct_word": "✅  Correct!",
            "wrong_word": "❌  Answer: {} ({})",
            "build_q": "Arrange:",
            "correct_sent": "✅  Correct!",
            "wrong_sent": "❌  Answer: {}",
            "cleared": "All mistakes cleared! 🎉",
            "retry_btn": "🔄  Try Again",
        },
        "sr": {
            "title": "📋  Greške",
            "back": "⬅ Nazad",
            "progress": "{} preostalo",
            "word_prompt": "Značenje: {}",
            "type_hanzi": "Ukucaj Hanzi:",
            "type_pinyin": "Ukucaj Pinyin:",
            "check": "✔  Proveri",
            "correct_word": "✅  Tačno!",
            "wrong_word": "❌  Odgovor: {} ({})",
            "build_q": "Složi:",
            "correct_sent": "✅  Tačno!",
            "wrong_sent": "❌  Odgovor: {}",
            "cleared": "Sve greške ispravljene! 🎉",
            "retry_btn": "🔄  Pokušaj ponovo",
        },
    }

    def __init__(self, parent, profile, notif, on_back):
        super().__init__(parent, bg=C.BG)
        self._profile = profile; self._lang = profile.lang
        self._db = Database(); self._notif = notif; self._on_back = on_back
        self._build()

    def _t(self, k, *a):
        txt = self._T[self._lang].get(k, k)
        return txt.format(*a) if a else txt

    def _build(self):
        hdr = tk.Frame(self, bg=C.BG_SIDEBAR); hdr.pack(fill="x")
        GhostButton(hdr, text=self._t("back"), command=self._on_back).pack(side="left", padx=S.MD, pady=S.SM)
        self._title_lbl = tk.Label(hdr, text=self._t("title"),
                                   bg=C.BG_SIDEBAR, fg=C.TEXT, font=F.H2)
        self._title_lbl.pack(side="left")
        self._progress_lbl = tk.Label(hdr, text="", bg=C.BG_SIDEBAR,
                                      fg=C.TEXT_MUTED, font=F.SMALL)
        self._progress_lbl.pack(side="right", padx=S.MD)

        self._content = tk.Frame(self, bg=C.BG)
        self._content.pack(fill="both", expand=True)

        m = self._profile.get_mistakes()

        # Filter sentences: skip those with no correct text at all
        valid_sentences = [s for s in m["sentences"]
                           if s.__dict__.get("correct", "").strip()]

        queue = ([{"type": "word", "data": w.__dict__} for w in m["words"]] +
                 [{"type": "sentence", "data": s.__dict__} for s in valid_sentences])
        random.shuffle(queue)
        self._queue = queue
        self._show_next()

    def _show_next(self):
        for c in self._content.winfo_children(): c.destroy()

        if not self._queue:
            try:
                new_ach = check_achievements(self._profile, event="mistakes_cleared")
                for ach in new_ach: self._notif.show_achievement(ach)
            except Exception: pass
            self._notif.show(self._t("cleared"), "success")
            self._on_back(); return

        self._progress_lbl.config(text=self._t("progress", len(self._queue)))
        item = self._queue[0]

        outer = tk.Frame(self._content, bg=C.BG)
        outer.pack(fill="both", expand=True, padx=S.LG, pady=S.LG)

        def np(p):
            s = unicodedata.normalize("NFD", p or "")
            return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()

        if item["type"] == "word":
            d    = item["data"]
            lang = self._lang
            mean = d.get(f"meaning_{lang}", d.get("meaning_sr", ""))

            # Word card
            card = tk.Frame(outer, bg=C.BG_CARD, highlightbackground=C.BORDER, highlightthickness=1)
            card.pack(fill="x", pady=(0, S.LG))
            tk.Label(card, text=self._t("word_prompt", mean),
                     bg=C.BG_CARD, fg=C.PRIMARY, font=F.H2,
                     wraplength=480, justify="left",
                     padx=S.LG, pady=S.MD).pack(anchor="w")

            # Input fields in a styled card
            fields = tk.Frame(outer, bg=C.BG_CARD, highlightbackground=C.BORDER, highlightthickness=1)
            fields.pack(fill="x", pady=(0, S.SM))
            fi = tk.Frame(fields, bg=C.BG_CARD); fi.pack(fill="x", padx=S.LG, pady=S.MD)

            tk.Label(fi, text=self._t("type_hanzi"), bg=C.BG_CARD,
                     fg=C.TEXT_MUTED, font=F.SMALL).pack(anchor="w")
            e_h = tk.Entry(fi, font=(F.FAMILY, 20), justify="center", width=12,
                           bg=C.BG_INPUT, fg=C.TEXT, insertbackground=C.TEXT,
                           relief="flat", highlightbackground=C.BORDER, highlightthickness=1)
            e_h.pack(fill="x", pady=(S.XS, S.SM), ipady=S.XS)
            e_h.bind("<FocusIn>", lambda e: e_h.config(highlightbackground=C.BORDER_FOCUS, highlightthickness=2))
            e_h.bind("<FocusOut>", lambda e: e_h.config(highlightbackground=C.BORDER, highlightthickness=1))

            tk.Label(fi, text=self._t("type_pinyin"), bg=C.BG_CARD,
                     fg=C.TEXT_MUTED, font=F.SMALL).pack(anchor="w")
            e_p = tk.Entry(fi, font=F.LABEL, justify="center", width=18,
                           bg=C.BG_INPUT, fg=C.TEXT, insertbackground=C.TEXT,
                           relief="flat", highlightbackground=C.BORDER, highlightthickness=1)
            e_p.pack(fill="x", pady=(S.XS, 0), ipady=S.XS)
            e_p.bind("<FocusIn>", lambda e: e_p.config(highlightbackground=C.BORDER_FOCUS, highlightthickness=2))
            e_p.bind("<FocusOut>", lambda e: e_p.config(highlightbackground=C.BORDER, highlightthickness=1))
            e_h.focus_set()

            fb = tk.Label(outer, text="", bg=C.BG, font=F.LABEL, wraplength=480); fb.pack(pady=S.SM)

            def check_word(ev=None):
                self.unbind("<Return>")
                h_ok = e_h.get().strip() == d["hanzi"]
                # Pinyin required but tones optional (ni hao = nǐ hǎo)
                p_ok = np(e_p.get().strip()) == np(d.get("pinyin", ""))
                if h_ok and p_ok:
                    fb.config(text=self._t("correct_word"), fg=C.SUCCESS)
                    e_h.config(bg="#E8FFE8" if not C.is_dark() else "#1A3D1A")
                    self._profile.mistakes["words"] = [
                        m for m in self._profile.mistakes["words"] if m.get("hanzi") != d["hanzi"]]
                    self._db.save_user(self._profile)
                    self._queue.pop(0)
                    try: __import__("hanziflow.core.sounds", fromlist=["play"]).play("correct")
                    except Exception: pass
                else:
                    fb.config(text=self._t("wrong_word", d["hanzi"], d.get("pinyin", "")), fg=C.DANGER)
                    if not h_ok: e_h.config(bg="#FFE8E8" if not C.is_dark() else "#3D1A1A")
                    if not p_ok: e_p.config(bg="#FFE8E8" if not C.is_dark() else "#3D1A1A")
                    self._queue.append(self._queue.pop(0))
                btn_check.config(state="disabled")
                self.after(1200, self._show_next)

            btn_row = tk.Frame(outer, bg=C.BG); btn_row.pack(pady=S.SM)
            btn_check = SuccessButton(btn_row, text=self._t("check"), command=check_word)
            btn_check.pack(side="left", padx=S.SM)
            self.bind("<Return>", check_word)

        else:
            d         = item["data"]
            lang      = self._lang
            correct_s = d.get("correct", "").strip()
            mean      = d.get(f"meaning_{lang}") or d.get("meaning_en") or d.get("meaning_sr") or ""

            # If no correct sentence at all — skip this item
            if not correct_s:
                self._queue.pop(0)
                self.after(100, self._show_next)
                return

            # Build words_list from scrambled or from correct sentence
            words_list = [w.strip() for w in d.get("scrambled", "").split(",") if w.strip()]
            if not words_list:
                import re as _re, random as _r2
                raw = _re.sub(r'[。？！.?!，,]', '', correct_s).strip()
                # Group into 2-char words (typical Chinese word length)
                chunks = []
                i = 0
                while i < len(raw):
                    # Take 2 chars if possible, else 1
                    size = 2 if i + 2 <= len(raw) else 1
                    chunks.append(raw[i:i+size])
                    i += size
                words_list = chunks
                _r2.shuffle(words_list)

            # Hint card — show meaning only, hide correct sentence
            card = tk.Frame(outer, bg=C.BG_CARD,
                            highlightbackground=C.BORDER, highlightthickness=1)
            card.pack(fill="x", pady=(0, S.MD))
            card_inner = tk.Frame(card, bg=C.BG_CARD)
            card_inner.pack(fill="x", padx=S.LG, pady=S.MD)
            if mean:
                tk.Label(card_inner, text=f"💡 {mean}", bg=C.BG_CARD,
                         fg=C.PRIMARY, font=F.LABEL_B,
                         wraplength=480, justify="left").pack(anchor="w")
            # Answer reveal label — hidden until wrong answer
            reveal_lbl = tk.Label(card_inner, text="", bg=C.BG_CARD,
                                  fg="#FFD700", font=(F.FAMILY, 16, "bold"),
                                  wraplength=480, justify="center")
            reveal_lbl.pack(pady=(S.XS, 0))

            tk.Label(outer, text=self._t("build_q"), bg=C.BG,
                     fg=C.TEXT_MUTED, font=F.SMALL).pack(anchor="w", pady=(0, S.XS))

            builder = SentenceBuilder(outer, audio_enabled=self._profile.audio_enabled)
            builder.pack(fill="x")
            builder.load(words_list)

            fb = tk.Label(outer, text="", bg=C.BG, font=F.LABEL, wraplength=460)
            fb.pack(pady=S.XS)

            def strip_p(s):
                for ch in "。？！.?!": s = s.replace(ch, "")
                return s.strip()

            def check_sentence(ev=None):
                self.unbind("<Return>")
                ans     = strip_p(builder.get_answer())
                correct = strip_p(d.get("correct", ""))
                if ans == correct:
                    builder.mark_correct()
                    reveal_lbl.config(text="")
                    fb.config(text=self._t("correct_sent"), fg=C.SUCCESS)
                    self._profile.mistakes["sentences"] = [
                        m for m in self._profile.mistakes["sentences"]
                        if m.get("correct") != d.get("correct")]
                    self._db.save_user(self._profile)
                    self._queue.pop(0)
                else:
                    builder.mark_wrong()
                    # Reveal correct sentence only on wrong answer
                    reveal_lbl.config(text=f"✓ {d.get('correct','')}")
                    fb.config(text=self._t("wrong_sent", d.get("correct","")), fg=C.DANGER)
                    self._queue.append(self._queue.pop(0))
                btn_check2.config(state="disabled")
                self.after(1800, self._show_next)

            btn_row2 = tk.Frame(outer, bg=C.BG); btn_row2.pack(pady=S.SM)
            btn_check2 = SuccessButton(btn_row2, text=self._t("check"),
                                       command=check_sentence)
            btn_check2.pack(side="left", padx=S.SM)
            self.bind("<Return>", check_sentence)