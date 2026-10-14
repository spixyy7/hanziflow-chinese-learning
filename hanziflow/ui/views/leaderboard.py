"""
ui/views/leaderboard.py — Leaderboard v3
• Add Friend button per player
• Pending / Accept request notifications
• Encrypted chat window per friend
• LAN peer discovery
"""
from __future__ import annotations

import os, threading
import tkinter as tk
from datetime import datetime
from typing import Callable

from ..theme import C, F, S, GhostButton, PrimaryButton, SuccessButton, DangerButton
from ..widgets import NotificationManager
from ...core import UserProfile, Leaderboard, Database
from ...core.adaptive import compute_level

_T = {
    "en": {
        "title":        "🏆  Leaderboard",
        "back":         "⬅ Back",
        "refresh":      "🔄 Refresh",
        "syncing":      "⏳ Syncing...",
        "you":          " (You)",
        "empty":        "No players yet.\nPlay Word Arena to appear!",
        "hint":         "Set HANZIFLOW_ONEDRIVE_TOKEN for cloud sync.",
        "add_friend":   "+ Friend",
        "friends_tab":  "Friends",
        "lb_tab":       "Leaderboard",
        "online":       "🟢 online",
        "offline":      "⚫ offline",
        "chat":         "💬 Chat",
        "pending":      "⏳ Pending",
        "accept":       "✔ Accept",
        "decline":      "✖ Decline",
        "requests_lbl": "Friend Requests",
        "no_friends":   "No friends yet.\nFind players on the Leaderboard!",
        "chat_title":   "Chat with {}",
        "send":         "Send",
        "type_msg":     "Type a message...",
        "not_online":   "⚠ {} is not on LAN right now.",
        "msg_sent":     "✓ Message sent",
        "msg_failed":   "✗ Could not reach {}",
    },
    "sr": {
        "title":        "🏆  Tabela rezultata",
        "back":         "⬅ Nazad",
        "refresh":      "🔄 Osveži",
        "syncing":      "⏳ Sinhronizujem...",
        "you":          " (Ti)",
        "empty":        "Nema igrača.\nIgraj Word Arenu da se pojaviš!",
        "hint":         "Postavi HANZIFLOW_ONEDRIVE_TOKEN za cloud sync.",
        "add_friend":   "+ Prijatelj",
        "friends_tab":  "Prijatelji",
        "lb_tab":       "Tabela",
        "online":       "🟢 online",
        "offline":      "⚫ offline",
        "chat":         "💬 Chat",
        "pending":      "⏳ Čekanje",
        "accept":       "✔ Prihvati",
        "decline":      "✖ Odbij",
        "requests_lbl": "Zahtevi za prijateljstvo",
        "no_friends":   "Nema prijatelja.\nNađi igrače na tabeli!",
        "chat_title":   "Razgovor sa {}",
        "send":         "Pošalji",
        "type_msg":     "Upiši poruku...",
        "not_online":   "⚠ {} nije na mreži.",
        "msg_sent":     "✓ Poruka poslata",
        "msg_failed":   "✗ Nije moguće doći do {}",
    },
}

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
_TOP_BG = {
    1: {"bg": "#2A1F00", "border": "#FFD700"},
    2: {"bg": "#1A1A1E", "border": "#C0C0C0"},
    3: {"bg": "#1A1200", "border": "#CD7F32"},
}
_DEF    = {"bg": "#16161F", "border": "#2A2A3A"}


class LeaderboardView(tk.Frame):

    def __init__(self, parent, profile: UserProfile,
                 notif: NotificationManager, on_back: Callable,
                 lan_server=None):
        super().__init__(parent, bg=C.BG)
        self._profile    = profile
        self._lang       = profile.lang
        self._lb         = Leaderboard()
        self._db         = Database()
        self._notif      = notif
        self._on_back    = on_back
        self._lan        = lan_server   # LANServer instance (optional)

        self._active_tab = "lb"   # "lb" or "friends"
        self._setup_lan_callbacks()

        self._build()
        self._load_lb()

    def _t(self, key: str, *args) -> str:
        txt = _T[self._lang].get(key, key)
        return txt.format(*args) if args else txt

    # ── LAN callbacks ─────────────────────────────────────────────────────────

    def _setup_lan_callbacks(self):
        if not self._lan:
            return
        self._lan.on_friend_request  = lambda u: self.after(0, lambda: self._on_friend_request(u))
        self._lan.on_friend_accepted = lambda u: self.after(0, lambda: self._on_friend_accepted(u))
        self._lan.on_message         = lambda m: self.after(0, lambda: self._on_message(m))
        self._lan.on_peer_discovered = lambda u, ip: self.after(0, lambda: self._refresh_friends())

    def _on_friend_request(self, from_user: str):
        self._notif.show(f"🤝 Friend request from {from_user}!", "info")
        if self._active_tab == "friends":
            self._load_friends()

    def _on_friend_accepted(self, from_user: str):
        self._notif.show(f"✅ {from_user} accepted your friend request!", "success")
        if self._active_tab == "friends":
            self._load_friends()

    def _on_message(self, msg: dict):
        self._notif.show(f"💬 {msg['from']}: {msg['text'][:40]}", "info")

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=C.BG_SIDEBAR)
        hdr.pack(fill="x")

        GhostButton(hdr, text=self._t("back"),
                    command=self._on_back).pack(side="left", padx=S.MD, pady=S.SM)
        tk.Label(hdr, text=self._t("title"),
                 bg=C.BG_SIDEBAR, fg=C.TEXT, font=F.H2).pack(side="left")

        self._refresh_btn = tk.Button(
            hdr, text=self._t("refresh"),
            bg=C.BG_SIDEBAR, fg=C.PRIMARY, font=F.SMALL,
            relief="flat", cursor="hand2",
            activebackground=C.BG_HOVER,
            command=self._sync_and_refresh)
        self._refresh_btn.pack(side="right", padx=S.MD)

        # Tabs
        tab_frame = tk.Frame(self, bg=C.BG_SIDEBAR)
        tab_frame.pack(fill="x")

        for tab_key, label_key in [("lb", "lb_tab"), ("friends", "friends_tab")]:
            btn = tk.Button(
                tab_frame, text=self._t(label_key),
                bg=C.PRIMARY if tab_key == self._active_tab else C.BG_SIDEBAR,
                fg=C.TEXT_WHITE if tab_key == self._active_tab else C.TEXT_MUTED,
                font=F.BODY_B, relief="flat", bd=0, cursor="hand2",
                padx=S.LG, pady=S.XS,
                activebackground=C.BG_HOVER,
                command=lambda t=tab_key: self._switch_tab(t))
            btn.pack(side="left")
            setattr(self, f"_tab_btn_{tab_key}", btn)

        self._status = tk.Label(self, text="", bg=C.BG,
                                fg=C.TEXT_MUTED, font=F.SMALL)
        self._status.pack()

        # Content area
        self._body = tk.Frame(self, bg=C.BG)
        self._body.pack(fill="both", expand=True)

        tk.Label(self, text=self._t("hint"),
                 bg=C.BG, fg=C.TEXT_LIGHT, font=F.TINY).pack(side="bottom", pady=S.XS)

    def _switch_tab(self, tab: str):
        self._active_tab = tab
        for t in ("lb", "friends"):
            btn = getattr(self, f"_tab_btn_{t}", None)
            if btn:
                btn.config(bg=C.PRIMARY if t == tab else C.BG_SIDEBAR,
                           fg=C.TEXT_WHITE if t == tab else C.TEXT_MUTED)
        for w in self._body.winfo_children():
            w.destroy()
        if tab == "lb":
            self._load_lb()
        else:
            self._load_friends()

    # ── Scrollable helper ──────────────────────────────────────────────────────

    def _make_scroll(self) -> tk.Frame:
        """Creates a scrollable frame inside self._body, returns inner frame."""
        for w in self._body.winfo_children():
            w.destroy()
        cv = tk.Canvas(self._body, bg=C.BG, highlightthickness=0)
        sb = tk.Scrollbar(self._body, orient="vertical", command=cv.yview)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        cv.configure(yscrollcommand=sb.set)
        inner = tk.Frame(cv, bg=C.BG)
        wid   = cv.create_window((0, 0), window=inner, anchor="nw")
        def _cfg(e=None):
            cv.configure(scrollregion=cv.bbox("all"))
            cv.itemconfig(wid, width=cv.winfo_width())
        inner.bind("<Configure>", _cfg)
        cv.bind("<Configure>", _cfg)
        cv.bind_all("<MouseWheel>",
            lambda e: cv.yview_scroll(-1*(e.delta//120), "units"))
        return inner

    # ── Leaderboard tab ────────────────────────────────────────────────────────

    def _load_lb(self):
        inner = self._make_scroll()
        entries = self._lb.get_top(30)
        if not entries:
            tk.Label(inner, text=self._t("empty"), bg=C.BG,
                     fg=C.TEXT_MUTED, font=F.LABEL, justify="center").pack(pady=60)
            return

        # Load friends data for "add/pending" buttons
        try:
            from ...core.lan_server import load_friends
            fdata = load_friends(self._profile.username)
        except Exception:
            fdata = {"friends": [], "pending": [], "requests": []}

        for i, entry in enumerate(entries):
            self._build_lb_card(inner, entry, fdata, delay_ms=i * 35)

    def _build_lb_card(self, parent: tk.Frame, entry: dict,
                       fdata: dict, delay_ms: int = 0):
        rank_n  = entry.get("rank_num", 0)
        is_me   = entry.get("username") == self._profile.username
        colors  = _TOP_BG.get(rank_n, _DEF)
        if is_me:
            colors = {"bg": "#0D1E30", "border": C.PRIMARY}

        wrapper = tk.Frame(parent, bg=colors["border"], pady=1, padx=1)
        card    = tk.Frame(wrapper, bg=colors["bg"])
        card.pack(fill="x")
        inner   = tk.Frame(card, bg=colors["bg"])
        inner.pack(fill="x", padx=S.MD, pady=8)

        # Avatar
        AVATAR_D = 38
        av_cv = tk.Canvas(inner, width=AVATAR_D, height=AVATAR_D,
                          bg=colors["bg"], highlightthickness=0)
        av_cv.pack(side="left", padx=(0, S.SM))
        self._draw_avatar(av_cv, entry, AVATAR_D, colors["border"])

        # Info
        info = tk.Frame(inner, bg=colors["bg"])
        info.pack(side="left", fill="x", expand=True)

        medal    = _MEDALS.get(rank_n, "")
        username = entry.get("username", "?") + (self._t("you") if is_me else "")
        rank_nm  = f"{entry.get('rank_icon','')} {entry.get('rank_name','')}"

        row1 = tk.Frame(info, bg=colors["bg"])
        row1.pack(anchor="w")
        if medal:
            tk.Label(row1, text=medal, bg=colors["bg"],
                     font=(F.FAMILY, 14)).pack(side="left", padx=(0, 4))
        fg_name = C.PRIMARY if is_me else (colors.get("border", C.TEXT) if rank_n <= 3 else C.TEXT)
        tk.Label(row1, text=f"#{rank_n}  {username}",
                 bg=colors["bg"], fg=fg_name,
                 font=F.BODY_B if (rank_n <= 3 or is_me) else F.BODY).pack(side="left")

        row2 = tk.Frame(info, bg=colors["bg"])
        row2.pack(anchor="w", pady=(2, 0))
        tk.Label(row2, text=rank_nm, bg=colors["bg"],
                 fg=entry.get("color", C.TEXT_MUTED), font=F.SMALL).pack(side="left")
        tk.Label(row2, text=f"  Lv {entry.get('level', 1)}",
                 bg=colors["bg"], fg=C.TEXT_MUTED, font=F.TINY).pack(side="left")

        # Score + buttons
        right = tk.Frame(inner, bg=colors["bg"])
        right.pack(side="right")

        score_c = colors.get("border", C.SUCCESS) if rank_n <= 3 else C.SUCCESS
        tk.Label(right, text=f"Arena: {entry.get('arena_score', 0)}",
                 bg=colors["bg"], fg=score_c,
                 font=(F.FAMILY, 12, "bold")).pack(anchor="e")

        if not is_me:
            uname = entry.get("username", "")
            # Friend button state
            if uname in fdata.get("friends", []):
                # Already friends → show chat button
                tk.Button(right, text=self._t("chat"),
                          bg="#1565C0", fg="white",
                          font=F.TINY, relief="flat", cursor="hand2",
                          padx=6, pady=2,
                          command=lambda u=uname: self._open_chat(u)
                          ).pack(anchor="e", pady=(4, 0))
            elif uname in fdata.get("pending", []):
                tk.Label(right, text=self._t("pending"),
                         bg=colors["bg"], fg=C.TEXT_MUTED, font=F.TINY).pack(anchor="e", pady=(4, 0))
            elif uname in fdata.get("requests", []):
                # They sent us a request
                btn_row = tk.Frame(right, bg=colors["bg"])
                btn_row.pack(anchor="e", pady=(4, 0))
                tk.Button(btn_row, text=self._t("accept"),
                          bg=C.SUCCESS, fg="white",
                          font=F.TINY, relief="flat", cursor="hand2",
                          padx=4, pady=1,
                          command=lambda u=uname: self._accept_friend(u)
                          ).pack(side="left", padx=1)
                tk.Button(btn_row, text=self._t("decline"),
                          bg=C.DANGER, fg="white",
                          font=F.TINY, relief="flat", cursor="hand2",
                          padx=4, pady=1,
                          command=lambda u=uname: self._decline_friend(u)
                          ).pack(side="left", padx=1)
            else:
                tk.Button(right, text=self._t("add_friend"),
                          bg="#263238", fg=C.PRIMARY,
                          font=F.TINY, relief="flat", cursor="hand2",
                          padx=6, pady=2,
                          highlightbackground=C.PRIMARY,
                          highlightthickness=1,
                          command=lambda u=uname: self._send_friend_request(u)
                          ).pack(anchor="e", pady=(4, 0))

        # Hover + click to profile
        all_widgets = [wrapper, card, inner, info, row1, row2, right, av_cv]
        hover_bg  = C.BG_HOVER
        normal_bg = colors["bg"]

        def _enter(e):
            for w in all_widgets:
                try: w.config(bg=hover_bg)
                except Exception: pass
        def _leave(e):
            for w in all_widgets:
                try: w.config(bg=normal_bg)
                except Exception: pass

        for w in [card, inner, info, row1, row2, av_cv]:
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)
            w.bind("<Button-1>", lambda e, en=entry: self._open_profile_popup(en))

        if delay_ms:
            wrapper.pack_forget()
            parent.after(delay_ms, lambda ww=wrapper: ww.pack(fill="x", padx=S.SM, pady=2))
        else:
            wrapper.pack(fill="x", padx=S.SM, pady=2)

    # ── Friends tab ────────────────────────────────────────────────────────────

    def _load_friends(self):
        inner = self._make_scroll()
        try:
            from ...core.lan_server import load_friends
            fdata = load_friends(self._profile.username)
        except Exception:
            fdata = {"friends": [], "pending": [], "requests": []}

        online_set = set()
        if self._lan:
            online_set = set(self._lan.get_online_friends())

        # Pending requests received
        requests = fdata.get("requests", [])
        if requests:
            tk.Label(inner, text=self._t("requests_lbl"),
                     bg=C.BG, fg=C.WARNING, font=F.LABEL_B).pack(anchor="w", padx=S.LG, pady=(S.MD, S.XS))
            for uname in requests:
                r = tk.Frame(inner, bg=C.BG_CARD,
                             highlightbackground=C.WARNING, highlightthickness=1)
                r.pack(fill="x", padx=S.LG, pady=2)
                ri = tk.Frame(r, bg=C.BG_CARD)
                ri.pack(fill="x", padx=S.MD, pady=S.SM)
                tk.Label(ri, text=f"🤝  {uname}", bg=C.BG_CARD,
                         fg=C.TEXT, font=F.BODY_B).pack(side="left", expand=True, anchor="w")
                tk.Button(ri, text=self._t("decline"),
                          bg=C.DANGER, fg="white", font=F.SMALL,
                          relief="flat", cursor="hand2", padx=6,
                          command=lambda u=uname: self._decline_friend(u)
                          ).pack(side="right", padx=2)
                tk.Button(ri, text=self._t("accept"),
                          bg=C.SUCCESS, fg="white", font=F.SMALL,
                          relief="flat", cursor="hand2", padx=6,
                          command=lambda u=uname: self._accept_friend(u)
                          ).pack(side="right", padx=2)

        # Friends list
        friends = fdata.get("friends", [])
        if not friends and not requests:
            tk.Label(inner, text=self._t("no_friends"),
                     bg=C.BG, fg=C.TEXT_MUTED,
                     font=F.LABEL, justify="center").pack(pady=60)
            return

        if friends:
            tk.Label(inner, text=self._t("friends_tab"),
                     bg=C.BG, fg=C.TEXT, font=F.LABEL_B).pack(anchor="w", padx=S.LG, pady=(S.MD, S.XS))

        for uname in friends:
            is_online = uname in online_set
            status_txt = self._t("online") if is_online else self._t("offline")
            status_col = "#4CAF50" if is_online else "#555555"

            wrapper = tk.Frame(inner, bg="#1565C0" if is_online else "#1A1A2E",
                               pady=1, padx=1)
            card = tk.Frame(wrapper, bg="#0D1E30" if is_online else "#16161F")
            card.pack(fill="x")
            ci = tk.Frame(card, bg=card["bg"])
            ci.pack(fill="x", padx=S.MD, pady=S.SM)

            # Avatar
            av = tk.Canvas(ci, width=32, height=32, bg=card["bg"], highlightthickness=0)
            av.pack(side="left", padx=(0, S.SM))
            av.create_oval(2, 2, 30, 30, fill=C.PRIMARY, outline="")
            av.create_text(16, 16, text=uname[0].upper(), fill="white",
                           font=(F.FAMILY, 12, "bold"))

            name_col = tk.Frame(ci, bg=card["bg"])
            name_col.pack(side="left", expand=True, fill="x")
            tk.Label(name_col, text=uname, bg=card["bg"],
                     fg=C.TEXT, font=F.BODY_B).pack(anchor="w")
            tk.Label(name_col, text=status_txt, bg=card["bg"],
                     fg=status_col, font=F.TINY).pack(anchor="w")

            btn_row = tk.Frame(ci, bg=card["bg"])
            btn_row.pack(side="right")

            if is_online:
                tk.Button(btn_row, text=self._t("chat"),
                          bg="#1565C0", fg="white",
                          font=F.SMALL, relief="flat", cursor="hand2",
                          padx=8, pady=3,
                          command=lambda u=uname: self._open_chat(u)
                          ).pack(side="left", padx=2)

            tk.Button(btn_row, text="✖",
                      bg=C.BG_CARD, fg=C.DANGER,
                      font=F.TINY, relief="flat", cursor="hand2",
                      command=lambda u=uname: self._remove_friend(u)
                      ).pack(side="left")

            wrapper.pack(fill="x", padx=S.LG, pady=2)

    def _refresh_friends(self):
        if self._active_tab == "friends":
            self._load_friends()

    # ── Friend actions ────────────────────────────────────────────────────────

    def _send_friend_request(self, to_username: str):
        if not self._lan:
            self._notif.show("LAN server not running.", "warning")
            return
        self._lan.broadcast_presence()
        ok = self._lan.send_friend_request(to_username)
        if ok:
            self._notif.show(f"🤝 Friend request sent to {to_username}!", "success")
        else:
            self._notif.show(self._t("not_online", to_username), "warning")
        self._load_lb()

    def _accept_friend(self, from_username: str):
        if not self._lan:
            # Accept locally even without LAN
            try:
                from ...core.lan_server import load_friends, save_friends
                data = load_friends(self._profile.username)
                if from_username in data.get("requests", []):
                    data["requests"].remove(from_username)
                if from_username not in data["friends"]:
                    data["friends"].append(from_username)
                save_friends(self._profile.username, data)
            except Exception:
                pass
        else:
            self._lan.accept_friend_request(from_username)
        self._notif.show(f"✅ Now friends with {from_username}!", "success")
        self._switch_tab(self._active_tab)

    def _decline_friend(self, from_username: str):
        try:
            from ...core.lan_server import load_friends, save_friends
            data = load_friends(self._profile.username)
            if from_username in data.get("requests", []):
                data["requests"].remove(from_username)
            save_friends(self._profile.username, data)
        except Exception:
            pass
        if self._lan:
            self._lan.decline_friend_request(from_username)
        self._switch_tab(self._active_tab)

    def _remove_friend(self, username: str):
        try:
            from ...core.lan_server import load_friends, save_friends
            data = load_friends(self._profile.username)
            if username in data.get("friends", []):
                data["friends"].remove(username)
            save_friends(self._profile.username, data)
        except Exception:
            pass
        if self._lan:
            self._lan.remove_friend(username)
        self._load_friends()

    # ── Chat window ────────────────────────────────────────────────────────────

    def _open_chat(self, friend_username: str):
        root = self.winfo_toplevel()
        _ChatWindow(root, self._profile.username, friend_username,
                    self._lan, self._lang)

    # ── Profile popup ─────────────────────────────────────────────────────────

    def _open_profile_popup(self, entry: dict):
        username = entry.get("username", "")
        lang     = self._lang

        try:
            user = self._db.get_user(username)
        except Exception:
            user = None

        root = self.winfo_toplevel()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        W, H   = 380, 340
        popup  = tk.Toplevel(root)
        popup.title(f"Player Profile")
        popup.configure(bg=C.BG_CARD)
        popup.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        popup.transient(root)
        popup.grab_set()

        hdr = tk.Frame(popup, bg=C.BG_SIDEBAR)
        hdr.pack(fill="x")

        av_size = 52
        av_cv   = tk.Canvas(hdr, width=av_size, height=av_size,
                             bg=C.BG_SIDEBAR, highlightthickness=0)
        av_cv.pack(side="left", padx=S.MD, pady=S.SM)
        self._draw_avatar(av_cv, entry, av_size, entry.get("color", C.PRIMARY))

        name_c = tk.Frame(hdr, bg=C.BG_SIDEBAR)
        name_c.pack(side="left")
        tk.Label(name_c, text=username, bg=C.BG_SIDEBAR,
                 fg=C.TEXT, font=F.H2).pack(anchor="w")
        tk.Label(name_c,
                 text=f"{entry.get('rank_icon','')} {entry.get('rank_name','')}",
                 bg=C.BG_SIDEBAR,
                 fg=entry.get("color", C.TEXT_MUTED), font=F.SMALL).pack(anchor="w")

        body = tk.Frame(popup, bg=C.BG_CARD)
        body.pack(fill="both", expand=True, padx=S.LG, pady=S.SM)

        def row(lbl, val, fg=C.TEXT):
            r = tk.Frame(body, bg=C.BG_CARD)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=lbl, bg=C.BG_CARD, fg=C.TEXT_MUTED,
                     font=F.SMALL, width=16, anchor="w").pack(side="left")
            tk.Label(r, text=val, bg=C.BG_CARD, fg=fg,
                     font=F.BODY_B).pack(side="left")

        row("Arena score:", str(entry.get("arena_score", 0)), "#4CAF50")
        row("Level:",       str(entry.get("level", 1)), C.PRIMARY)
        row("XP:",          str(entry.get("xp", 0)), "#FFD700")

        if user:
            total    = getattr(user, "total_answered", 0)
            correct  = getattr(user, "total_correct", 0)
            acc      = round(correct / max(total, 1) * 100)
            row("Accuracy:", f"{acc}%", "#00CC66")
            row("Vocabulary:", str(len(getattr(user, "vocab", []))), "#50C8FF")
            row("Streak:", f"{getattr(user, 'streak', 0)} 🔥", "#FF6600")
            row("Sentences:", str(getattr(user, "grammar_completed", 0)), C.TEXT_MUTED)

        btn_row = tk.Frame(popup, bg=C.BG_CARD)
        btn_row.pack(pady=S.SM)
        tk.Button(btn_row, text="Close", bg=C.PRIMARY, fg="white",
                  font=F.BODY_B, relief="flat", padx=S.LG, pady=S.XS,
                  cursor="hand2", command=popup.destroy).pack(side="left", padx=4)

        if username != self._profile.username:
            tk.Button(btn_row, text=self._t("chat"),
                      bg="#1565C0", fg="white",
                      font=F.BODY_B, relief="flat", padx=S.LG, pady=S.XS,
                      cursor="hand2",
                      command=lambda: (popup.destroy(), self._open_chat(username))
                      ).pack(side="left", padx=4)

    # ── Avatar ─────────────────────────────────────────────────────────────────

    def _draw_avatar(self, cv: tk.Canvas, entry: dict, size: int, ring_color: str):
        username = entry.get("username", "")
        avatar_path = ""
        try:
            user = self._db.get_user(username)
            if user:
                avatar_path = getattr(user, "avatar_path", "")
        except Exception:
            pass

        cv.create_oval(1, 1, size - 1, size - 1, outline=ring_color, width=2, fill="")

        if avatar_path and os.path.exists(avatar_path):
            try:
                from PIL import Image, ImageTk, ImageDraw
                img  = Image.open(avatar_path).resize((size - 6, size - 6), Image.LANCZOS)
                mask = Image.new("L", (size - 6, size - 6), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size - 6, size - 6), fill=255)
                result = Image.new("RGBA", (size - 6, size - 6))
                result.paste(img, mask=mask)
                photo = ImageTk.PhotoImage(result)
                cv._photo = photo
                cv.create_image(3, 3, anchor="nw", image=photo)
                return
            except Exception:
                pass

        rank_colors = {1: "#FFD700", 2: "#C0C0C0", 3: "#CD7F32"}
        fc = rank_colors.get(entry.get("rank_num", 0), C.PRIMARY)
        cv.create_oval(3, 3, size - 3, size - 3, fill=fc, outline="")
        cv.create_text(size // 2, size // 2,
                       text=(username[0].upper() if username else "?"),
                       font=(F.FAMILY, size // 3, "bold"), fill="white")

    # ── Sync ──────────────────────────────────────────────────────────────────

    def _sync_and_refresh(self):
        self._refresh_btn.config(state="disabled", text=self._t("syncing"))
        self._status.config(text=self._t("syncing"), fg=C.PRIMARY)
        if self._lan:
            self._lan.broadcast_presence()

        def do():
            self._lb.fetch_from_onedrive()
            self.after(0, done)

        def done():
            self._refresh_btn.config(state="normal", text=self._t("refresh"))
            self._status.config(text="", fg=C.TEXT_MUTED)
            if self._active_tab == "lb":
                self._load_lb()

        threading.Thread(target=do, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
#  Chat Window
# ─────────────────────────────────────────────────────────────────────────────

class _ChatWindow:
    """Encrypted chat window between two LAN users."""

    W, H = 440, 520

    def __init__(self, root: tk.Tk, my_username: str, friend_username: str,
                 lan_server, lang: str = "en"):
        self._root    = root
        self._me      = my_username
        self._friend  = friend_username
        self._lan     = lan_server
        self._lang    = lang

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        self._win = tk.Toplevel(root)
        self._win.title(f"💬 {friend_username}")
        self._win.configure(bg=C.BG_CARD)
        self._win.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}")
        self._win.resizable(True, True)

        self._build()
        self._load_history()

        # Register live message callback
        if self._lan:
            old_cb = self._lan.on_message
            def _new_cb(msg):
                if msg.get("from") == friend_username:
                    self._win.after(0, lambda m=msg: self._add_bubble(m["text"], mine=False))
                if old_cb:
                    old_cb(msg)
            self._lan.on_message = _new_cb

    def _t(self, key: str, *args) -> str:
        txt = _T[self._lang].get(key, key)
        return txt.format(*args) if args else txt

    def _build(self):
        win = self._win

        # Header
        hdr = tk.Frame(win, bg=C.BG_SIDEBAR)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"💬  {self._friend}",
                 bg=C.BG_SIDEBAR, fg=C.TEXT, font=F.H2).pack(side="left", padx=S.MD, pady=S.SM)
        tk.Label(hdr, text="🔒 encrypted",
                 bg=C.BG_SIDEBAR, fg="#4CAF50", font=F.TINY).pack(side="right", padx=S.MD)

        # Messages area
        msg_frame = tk.Frame(win, bg=C.BG)
        msg_frame.pack(fill="both", expand=True)

        self._msg_cv = tk.Canvas(msg_frame, bg=C.BG, highlightthickness=0)
        sb = tk.Scrollbar(msg_frame, orient="vertical", command=self._msg_cv.yview)
        sb.pack(side="right", fill="y")
        self._msg_cv.pack(side="left", fill="both", expand=True)
        self._msg_cv.configure(yscrollcommand=sb.set)

        self._msg_inner = tk.Frame(self._msg_cv, bg=C.BG)
        self._msg_win   = self._msg_cv.create_window((0, 0), window=self._msg_inner, anchor="nw")

        def _cfg(e=None):
            self._msg_cv.configure(scrollregion=self._msg_cv.bbox("all"))
            self._msg_cv.itemconfig(self._msg_win, width=self._msg_cv.winfo_width())
        self._msg_inner.bind("<Configure>", _cfg)
        self._msg_cv.bind("<Configure>", _cfg)
        self._msg_cv.bind_all("<MouseWheel>",
            lambda e: self._msg_cv.yview_scroll(-1*(e.delta//120), "units"))

        # Input area
        inp_frame = tk.Frame(win, bg=C.BG_SIDEBAR)
        inp_frame.pack(fill="x", padx=S.SM, pady=S.SM)

        self._entry = tk.Entry(inp_frame, font=F.BODY,
                               bg=C.BG_INPUT, fg=C.TEXT,
                               insertbackground=C.TEXT,
                               relief="flat",
                               highlightbackground=C.BORDER,
                               highlightthickness=1)
        self._entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, S.SM))
        self._entry.bind("<Return>", lambda e: self._send())

        # Placeholder
        hint = self._t("type_msg")
        self._entry.insert(0, hint)
        self._entry.config(fg=C.TEXT_MUTED)
        self._entry.bind("<FocusIn>",
            lambda e: (self._entry.delete(0, "end"), self._entry.config(fg=C.TEXT))
            if self._entry.get() == hint else None)

        tk.Button(inp_frame, text=self._t("send"),
                  bg=C.PRIMARY, fg="white",
                  font=F.BODY_B, relief="flat", cursor="hand2",
                  padx=S.LG, pady=4,
                  command=self._send).pack(side="right")

    def _load_history(self):
        try:
            from ...core.lan_server import get_chat_history
            msgs = get_chat_history(self._me, self._friend)
            for m in msgs:
                self._add_bubble(m["text"], mine=m["mine"],
                                 timestamp=m.get("timestamp", ""))
        except Exception:
            pass

    def _add_bubble(self, text: str, mine: bool = True, timestamp: str = ""):
        bg     = "#1565C0" if mine else "#263238"
        anchor = "e" if mine else "w"
        pad_l  = S.XXL if mine else S.SM
        pad_r  = S.SM if mine else S.XXL

        outer = tk.Frame(self._msg_inner, bg=C.BG)
        outer.pack(fill="x", padx=S.SM, pady=2)

        bubble = tk.Frame(outer, bg=bg)
        bubble.pack(anchor=anchor, padx=(pad_l, pad_r))

        tk.Label(bubble, text=text, bg=bg, fg="white",
                 font=F.BODY, wraplength=280,
                 justify="left" if not mine else "right",
                 padx=10, pady=6).pack()

        if timestamp:
            try:
                ts_str = datetime.fromisoformat(timestamp).strftime("%H:%M")
            except Exception:
                ts_str = ""
            tk.Label(outer, text=ts_str, bg=C.BG, fg=C.TEXT_MUTED,
                     font=(F.FAMILY, 7)).pack(anchor=anchor, padx=(pad_l, pad_r))

        # Auto-scroll to bottom
        self._msg_cv.after(50, lambda: self._msg_cv.yview_moveto(1.0))

    def _send(self):
        hint = self._t("type_msg")
        text = self._entry.get().strip()
        if not text or text == hint:
            return

        self._entry.delete(0, "end")

        # Show locally first
        self._add_bubble(text, mine=True, timestamp=datetime.now().isoformat())

        # Send via LAN
        if self._lan:
            ok = self._lan.send_message(self._friend, text)
            if not ok:
                self._add_bubble(self._t("msg_failed", self._friend), mine=False)
        else:
            # Save locally even without LAN
            try:
                from ...core.lan_server import _make_key, _xor_encrypt, save_message
                key = _make_key(self._me, self._friend)
                save_message(self._me, {
                    "type": "chat", "from": self._me, "to": self._friend,
                    "data": _xor_encrypt(text, key),
                    "timestamp": datetime.now().isoformat(),
                })
            except Exception:
                pass