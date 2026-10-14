"""
ui/notif_bell.py — Notification Bell widget

A bell 🔔 button with badge count, placed in the dashboard header.
Click → dropdown panel showing all notifications.
"""
from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from typing import Callable, Optional
from ..config import validate_username

from .theme import C, F, S

# Colors
_BG  = "#1a1d2e"; _HDR = "#14172a"; _CRD = "#1e2236"
_BOR = "#2a2d40"; _WHT = "#ffffff"; _GRY = "#65676b"
_HOV = "#252840"; _RED = "#ff3b30"; _GRN = "#42b72a"
_ORG = "#FF9800"; _BLU = "#1877f2"; _ACC = "#1877f2"

# Notif type icons + colors
_TYPE_STYLE = {
    "friend_request":  ("🤝", _ORG),
    "friend_accepted": ("✅", _GRN),
    "message":         ("💬", _BLU),
    "achievement":     ("🏆", "#FFD700"),
    "system":          ("📢", _GRY),
}


class NotifBell:
    """
    Bell button + dropdown panel.

    Usage:
        bell = NotifBell(parent_frame, profile, lan_server, on_accept, on_open_chat)
        bell.widget.pack(side="left", padx=2)
        bell.refresh()  # call after login to load persisted notifs
    """

    PANEL_W = 300
    PANEL_H = 420

    def __init__(self, parent: tk.Frame, profile,
                 lan_server=None,
                 on_accept: Optional[Callable] = None,
                 on_open_chat: Optional[Callable] = None):
        self._parent    = parent
        self._profile   = profile
        self._lan       = lan_server
        self._on_accept = on_accept     # (username) → accept friend request
        self._on_chat   = on_open_chat  # (username) → open chat
        self._panel_win: Optional[tk.Toplevel] = None
        self._panel_target_h: int = self.PANEL_H
        self._panel_target_y: int = 0
        self._panel_target_x: int = -1   # -1 = not yet saved
        self._saved_pos_x:    int = -1
        self._saved_pos_y:    int = -1
        self._open      = False

        try:
            from ..core.notifications import NotifStore
            self._store = NotifStore(profile.username)
        except Exception:
            self._store = None

        # Load saved panel position from disk
        self._pos_file = None
        try:
            from pathlib import Path
            self._pos_file = Path("users") / f"{validate_username(profile.username)}_notif_pos.json"
            if self._pos_file.exists():
                import json
                d = json.loads(self._pos_file.read_text(encoding="utf-8"))
                self._saved_pos_x = int(d.get("x", -1))
                self._saved_pos_y = int(d.get("y", -1))
        except Exception:
            pass

        self._build()
        self._setup_lan_cbs()
        self._setup_minimize_cbs()

    # ── Minimize / restore ────────────────────────────────────────────────────

    def _setup_minimize_cbs(self):
        root = self._bell_btn.winfo_toplevel() if hasattr(self, '_bell_btn') else None
        try:
            parent = self._parent.winfo_toplevel()
            parent.bind("<Unmap>", self._on_main_minimize, add="+")
            parent.bind("<Map>",   self._on_main_restore,  add="+")
        except Exception:
            pass

    def _on_main_minimize(self, e=None):
        try:
            if e and str(e.widget) != str(self._parent.winfo_toplevel()):
                return
            if self._panel_win and self._panel_win.winfo_exists():
                self._panel_win.withdraw()
        except Exception:
            pass

    def _on_main_restore(self, e=None):
        try:
            if e and str(e.widget) != str(self._parent.winfo_toplevel()):
                return
            if self._panel_win and self._panel_win.winfo_exists():
                self._panel_win.deiconify()
                self._panel_win.lift()
        except Exception:
            pass

    # ── Build bell button ──────────────────────────────────────────────────────

    def _build(self):
        bg = C.BG_SIDEBAR
        container = tk.Frame(self._parent, bg=bg)
        self.widget = container

        self._bell_btn = tk.Button(
            container,
            text="🔔",
            bg=bg, fg=C.TEXT_MUTED,
            font=(F.FAMILY, 15),
            relief="flat", bd=0, cursor="hand2",
            activebackground=C.BG_HOVER,
            command=self._toggle
        )
        self._bell_btn.pack(side="left")
        self._bell_btn.bind("<Enter>", lambda e: self._bell_btn.config(fg="#DDDDDD") if not self._open else None)
        self._bell_btn.bind("<Leave>", lambda e: self._bell_btn.config(
            fg=C.TEXT if (self._store and self._store.unread_count() > 0) else C.TEXT_MUTED
        ) if not self._open else None)

        # Badge canvas (overlaid)
        self._badge_cv = tk.Canvas(container, width=16, height=16,
                                    bg=bg, highlightthickness=0)
        self._badge_cv.place(x=14, y=0)
        self._update_badge()

    def _update_badge(self):
        self._badge_cv.delete("all")
        count = self._store.unread_count() if self._store else 0
        if count > 0:
            self._badge_cv.create_oval(0, 0, 15, 15, fill=_RED, outline="")
            self._badge_cv.create_text(
                8, 8, text=str(min(count, 9)),
                fill=_WHT, font=(F.FAMILY, 8, "bold")
            )
            self._bell_btn.config(fg=C.TEXT)
        else:
            self._bell_btn.config(fg=C.TEXT_MUTED)

    # ── LAN callbacks ──────────────────────────────────────────────────────────

    def _setup_lan_cbs(self):
        if not self._lan: return
        old_req = self._lan.on_friend_request
        old_acc = self._lan.on_friend_accepted
        old_msg = self._lan.on_message

        def _req(u):
            self._bell_btn.after(0, lambda uu=u: self._on_friend_req_notif(uu))
            if old_req: old_req(u)

        def _acc(u):
            self._bell_btn.after(0, lambda uu=u: self._on_friend_acc_notif(uu))
            if old_acc: old_acc(u)

        def _msg(m):
            self._bell_btn.after(0, lambda mm=m: self._on_msg_notif(mm))
            if old_msg: old_msg(m)

        self._lan.on_friend_request  = _req
        self._lan.on_friend_accepted = _acc
        self._lan.on_message         = _msg

    def _on_friend_req_notif(self, from_user: str):
        if self._store:
            self._store.add_friend_request(from_user)
        self._update_badge()
        if self._open: self._refresh_panel()

    def _on_friend_acc_notif(self, from_user: str):
        if self._store:
            self._store.add_friend_accepted(from_user)
        self._update_badge()
        if self._open: self._refresh_panel()

    def _on_msg_notif(self, msg: dict):
        if self._store:
            self._store.add_message(msg.get("from", "?"), msg.get("text", ""))
        self._update_badge()
        if self._open: self._refresh_panel()

    # ── Public ────────────────────────────────────────────────────────────────

    def refresh(self):
        """Call after login to show any stored offline notifications."""
        self._update_badge()

    def add_notification(self, ntype: str, from_user: str, text: str):
        """Manually add a notification (e.g. from app layer)."""
        if self._store:
            self._store._add(ntype, from_user, text)
            self._update_badge()

    # ── Panel toggle ──────────────────────────────────────────────────────────

    def _toggle(self):
        if self._open:
            self._close()
        else:
            self._open_panel()

    def _set_bell_active(self, active: bool):
        try:
            bg = C.BG_SIDEBAR
            if active:
                self._bell_btn.config(fg="#FFFFFF", bg="#2a2d45",
                                      relief="flat", highlightthickness=0)
                self.widget.config(bg="#2a2d45")
                self._badge_cv.config(bg="#2a2d45")
            else:
                self._bell_btn.config(
                    fg=C.TEXT if (self._store and self._store.unread_count() > 0) else C.TEXT_MUTED,
                    bg=bg)
                self.widget.config(bg=bg)
                self._badge_cv.config(bg=bg)
        except Exception:
            pass

    def _open_panel(self):
        self._open = True
        self._set_bell_active(True)
        root = self._bell_btn.winfo_toplevel()
        root.update_idletasks()

        # 1. Uzimamo poziciju zvonceta
        bx = self._bell_btn.winfo_rootx()
        by = self._bell_btn.winfo_rooty()
        bw = self._bell_btn.winfo_width()
        bh = self._bell_btn.winfo_height()

        # 2. FIKSNA LOGIKA:
        # X: Desna ivica zvonceta (bx + bw) minus širina panela
        # Y: Ispod zvonceta (by + bh) + mali razmak od 4px
        px = (bx + bw) - self.PANEL_W
        py = by + bh + 4

        # 3. Kreiramo prozor
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=_BG, highlightbackground=_BOR, highlightthickness=1)

        # Postavljamo inicijalnu visinu na 0 zbog animacije slide_down
        win.geometry(f"{self.PANEL_W}x0+{px}+{py}")
        win.attributes("-alpha", 0.0)

        self._panel_win = win
        self._panel_target_h = self.PANEL_H
        self._panel_target_y = py

        # Drag support (ostavljamo ako zelis da mozes da ga pomeris naknadno)
        win.bind("<ButtonPress-1>",   self._drag_start)
        win.bind("<B1-Motion>",        self._drag_move)
        win.bind("<ButtonRelease-1>",  self._drag_end)

        self._build_panel_content()
        self._slide_down(0)

        root.bind("<Button-1>", self._outside_click, add="+")

    def _drag_start(self, e):
        self._drag_x = e.x_root - self._panel_win.winfo_rootx()
        self._drag_y = e.y_root - self._panel_win.winfo_rooty()

    def _drag_move(self, e):
        if not self._panel_win: return
        nx = e.x_root - self._drag_x
        ny = e.y_root - self._drag_y
        try:
            self._panel_win.geometry(f"+{nx}+{ny}")
            self._panel_target_y = ny
            self._panel_target_x = nx
            self._saved_pos_x = nx
            self._saved_pos_y = ny
        except Exception: pass

    def _drag_end(self, e):
        """Save position to disk when drag ends."""
        try:
            if self._pos_file and self._saved_pos_x >= 0:
                import json
                from pathlib import Path
                Path("users").mkdir(exist_ok=True)
                self._pos_file.write_text(
                    json.dumps({"x": self._saved_pos_x, "y": self._saved_pos_y}),
                    encoding="utf-8"
                )
        except Exception:
            pass

    def _close(self):
        self._open = False
        self._set_bell_active(False)
        if self._panel_win:
            self._slide_up()
        else:
            self._panel_win = None

    def _slide_down(self, step=0):
        steps = 12
        if step > steps:
            try:
                self._panel_win.geometry(
                    f"{self.PANEL_W}x{self._panel_target_h}+"
                    f"{self._panel_win.winfo_x()}+{self._panel_target_y}")
                self._panel_win.attributes("-alpha", 1.0)
            except tk.TclError: pass
            return
        frac = step / steps
        ease = frac * frac * (3 - 2 * frac)
        h    = max(4, int(self._panel_target_h * ease))
        a    = min(1.0, ease * 1.4)
        try:
            self._panel_win.geometry(
                f"{self.PANEL_W}x{h}+"
                f"{self._panel_win.winfo_x()}+{self._panel_target_y}")
            self._panel_win.attributes("-alpha", a)
            self._panel_win.after(14, lambda: self._slide_down(step + 1))
        except tk.TclError: pass

    def _slide_up(self, step=0):
        steps = 8
        if step > steps:
            try:
                if self._panel_win:
                    self._panel_win.destroy()
            except tk.TclError: pass
            self._panel_win = None
            return
        frac = 1.0 - step / steps
        ease = frac * frac
        h    = max(0, int(self._panel_target_h * ease))
        a    = max(0.0, ease * 0.9)
        try:
            self._panel_win.geometry(
                f"{self.PANEL_W}x{h}+"
                f"{self._panel_win.winfo_x()}+{self._panel_target_y}")
            self._panel_win.attributes("-alpha", a)
            self._panel_win.after(12, lambda: self._slide_up(step + 1))
        except tk.TclError:
            self._panel_win = None

    def _fade_in(self, s=0):
        a = min(1.0, s / 7)
        try: self._panel_win.attributes("-alpha", a)
        except tk.TclError: return
        if a < 1.0: self._panel_win.after(16, lambda: self._fade_in(s+1))

    def _outside_click(self, e):
        if not self._open or not self._panel_win: return
        try:
            pw = self._panel_win
            bb = self._bell_btn
            in_p = (pw.winfo_rootx() <= e.x_root <= pw.winfo_rootx() + pw.winfo_width() and
                    pw.winfo_rooty() <= e.y_root <= pw.winfo_rooty() + pw.winfo_height())
            in_b = (bb.winfo_rootx() <= e.x_root <= bb.winfo_rootx() + bb.winfo_width() + 20 and
                    bb.winfo_rooty() <= e.y_root <= bb.winfo_rooty() + bb.winfo_height())
            if not in_p and not in_b:
                self._close()
        except Exception: pass

    # ── Panel content ─────────────────────────────────────────────────────────

    def _build_panel_content(self):
        if not self._panel_win: return
        for w in self._panel_win.winfo_children(): w.destroy()
        win = self._panel_win

        # Header
        hdr = tk.Frame(win, bg=_HDR); hdr.pack(fill="x")
        tk.Label(hdr, text="🔔  Notifications", bg=_HDR, fg=_WHT,
                 font=("Segoe UI", 12, "bold")).pack(side="left", padx=12, pady=10)

        # Clear all button
        tk.Button(hdr, text="Clear all", bg=_HDR, fg=_GRY,
                  font=("Segoe UI", 9), relief="flat", bd=0, cursor="hand2",
                  activebackground=_HDR,
                  command=self._clear_all).pack(side="right", padx=10)

        tk.Button(hdr, text="✕", bg=_HDR, fg=_GRY,
                  font=("Segoe UI", 11), relief="flat", bd=0, cursor="hand2",
                  activebackground=_HDR,
                  command=self._close).pack(side="right", padx=4)

        # Notifications list
        cv = tk.Canvas(win, bg=_BG, highlightthickness=0)
        sb = tk.Scrollbar(win, orient="vertical", command=cv.yview)
        sb.pack(side="right", fill="y")
        cv.pack(fill="both", expand=True)
        cv.configure(yscrollcommand=sb.set)
        inner = tk.Frame(cv, bg=_BG)
        wid   = cv.create_window((0, 0), window=inner, anchor="nw")

        def _cfg(e=None):
            cv.configure(scrollregion=cv.bbox("all"))
            cv.itemconfig(wid, width=cv.winfo_width())
        inner.bind("<Configure>", _cfg)
        cv.bind("<Configure>", _cfg)
        cv.bind("<MouseWheel>", lambda e: cv.yview_scroll(-1*(e.delta//120), "units"))

        notifs = self._store.get_all()[::-1] if self._store else []  # newest first

        if not notifs:
            tk.Label(inner, text="No notifications",
                     bg=_BG, fg=_GRY,
                     font=("Segoe UI", 10)).pack(pady=50)
        else:
            for n in notifs:
                self._notif_card(inner, n)

        self._mark_all_read()

    def _refresh_panel(self):
        if self._panel_win:
            self._build_panel_content()

    def _make_avatar_canvas(self, parent, username, bg, size=32):
        cv = tk.Canvas(parent, width=size, height=size, bg=bg, highlightthickness=0)
        # Step 1: draw default circle with initial
        cv.create_oval(1, 1, size-1, size-1, fill=_ACC, outline="")
        cv.create_text(size//2, size//2,
                       text=username[0].upper() if username else "?",
                       fill=_WHT, font=("Segoe UI", size//3, "bold"))
        # Step 2: try to load real profile photo (same method as leaderboard)
        avatar_path = ""
        try:
            from ..core.database import Database as _DB
            user = _DB().get_user(username)
            if user:
                avatar_path = getattr(user, "avatar_path", "")
        except Exception:
            pass
        if avatar_path and os.path.exists(avatar_path):
            try:
                from PIL import Image, ImageTk, ImageDraw
                s    = size - 4
                img  = Image.open(avatar_path).resize((s, s), Image.LANCZOS)
                mask = Image.new("L", (s, s), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, s, s), fill=255)
                result = Image.new("RGBA", (s, s))
                result.paste(img, mask=mask)
                photo = ImageTk.PhotoImage(result)
                cv.delete("all")
                cv._photo = photo
                cv.create_image(2, 2, anchor="nw", image=photo)
            except Exception:
                pass
        return cv

    def _notif_card(self, parent: tk.Frame, n: dict):
        ntype       = n.get("type", "system")
        icon, color = _TYPE_STYLE.get(ntype, ("📢", _GRY))
        is_new      = not n.get("read", False)
        bg          = "#1a2040" if is_new else _CRD
        from_u      = n.get("from", "")
        ts          = n.get("timestamp", "")
        nid         = n.get("id", "")

        ts_str = ""
        try:
            dt   = datetime.fromisoformat(ts)
            diff = (datetime.now() - dt).total_seconds()
            if diff < 60:     ts_str = "now"
            elif diff < 3600: ts_str = f"{int(diff//60)}m"
            elif diff < 86400:ts_str = f"{int(diff//3600)}h"
            else:             ts_str = f"{int(diff//86400)}d"
        except Exception:
            pass

        card = tk.Frame(parent, bg=bg,
                        highlightbackground=color if is_new else _BOR,
                        highlightthickness=1 if is_new else 0,
                        cursor="hand2")
        card.pack(fill="x", padx=6, pady=2)
        card.bind("<Enter>", lambda e: card.config(bg="#22284a" if is_new else "#23263a"))
        card.bind("<Leave>", lambda e: card.config(bg=bg))

        ci = tk.Frame(card, bg=bg); ci.pack(fill="x", padx=10, pady=8)

        # ── Avatar left ──────────────────────────────────────────────────────
        av_frame = tk.Frame(ci, bg=bg); av_frame.pack(side="left", padx=(0, 8))
        if from_u and from_u != "system":
            av = self._make_avatar_canvas(av_frame, from_u, bg, 34)
            av.pack()
        else:
            tk.Label(av_frame, text=icon, bg=bg, fg=color,
                     font=("Segoe UI Emoji", 18)).pack()

        # ── Text middle ──────────────────────────────────────────────────────
        body = tk.Frame(ci, bg=bg); body.pack(side="left", expand=True, fill="x")
        tk.Label(body, text=n.get("text", ""),
                 bg=bg, fg=_WHT if is_new else "#BBBBBB",
                 font=("Segoe UI", 9, "bold" if is_new else "normal"),
                 wraplength=160, justify="left").pack(anchor="w")

        # ── Timestamp + unread dot right ─────────────────────────────────────
        right = tk.Frame(ci, bg=bg); right.pack(side="right", anchor="n", padx=(4, 0))
        if ts_str:
            tk.Label(right, text=ts_str, bg=bg, fg=_GRY,
                     font=("Segoe UI", 7)).pack(anchor="e")
        if is_new:
            dot = tk.Canvas(right, width=8, height=8, bg=bg, highlightthickness=0)
            dot.create_oval(1, 1, 7, 7, fill=color, outline="")
            dot.pack(pady=(2, 0))

        # ── Action buttons ───────────────────────────────────────────────────
        actions = tk.Frame(ci, bg=bg); actions.pack(side="right")

        if ntype == "friend_request" and from_u:
            already = False
            try:
                from ..core.lan_server import load_friends
                fd = load_friends(self._profile.username)
                already = from_u in fd.get("friends", [])
            except Exception:
                pass
            if not already:
                tk.Button(actions, text="Accept",
                          bg=_GRN, fg=_WHT, font=("Segoe UI", 8, "bold"),
                          relief="flat", cursor="hand2", padx=6, pady=2,
                          command=lambda u=from_u, i=nid: self._accept_req(u, i)
                          ).pack(pady=1)
                tk.Button(actions, text="Decline",
                          bg="#cc0000", fg=_WHT, font=("Segoe UI", 8),
                          relief="flat", cursor="hand2", padx=6, pady=2,
                          command=lambda u=from_u, i=nid: self._decline_req(u, i)
                          ).pack(pady=1)
            else:
                tk.Label(actions, text="✓ Friends", bg=bg, fg=_GRN,
                         font=("Segoe UI", 8)).pack()

        elif ntype == "message" and from_u:
            tk.Button(actions, text="Reply",
                      bg=_BLU, fg=_WHT, font=("Segoe UI", 8, "bold"),
                      relief="flat", cursor="hand2", padx=6, pady=2,
                      command=lambda u=from_u, i=nid: self._open_chat_from_notif(u, i)
                      ).pack()

        tk.Button(actions, text="×",
                  bg=bg, fg=_GRY, font=("Segoe UI", 11),
                  relief="flat", cursor="hand2", bd=0,
                  command=lambda i=nid: self._dismiss(i)
                  ).pack(anchor="e", pady=(4, 0))

        for w in [card, ci, body]:
            w.bind("<Enter>", lambda e, c=card: c.config(bg=_HOV))
            w.bind("<Leave>", lambda e, c=card, b=bg: c.config(bg=b))

    # ── Actions ────────────────────────────────────────────────────────────────

    def _accept_req(self, from_user: str, notif_id: str):
        """Accept friend request from notification."""
        try:
            if self._lan:
                self._lan.accept_friend_request(from_user)
            else:
                from ..core.lan_server import load_friends, save_friends
                d = load_friends(self._profile.username)
                if from_user in d.get("requests", []):
                    d["requests"].remove(from_user)
                if from_user not in d.get("friends", []):
                    d.setdefault("friends", []).append(from_user)
                save_friends(self._profile.username, d)
        except Exception: pass

        if self._store:
            self._store.mark_read(notif_id)
        if self._on_accept:
            self._on_accept(from_user)
        self._update_badge()
        self._refresh_panel()

    def _decline_req(self, from_user: str, notif_id: str):
        try:
            from ..core.lan_server import load_friends, save_friends
            d = load_friends(self._profile.username)
            if from_user in d.get("requests", []):
                d["requests"].remove(from_user)
            save_friends(self._profile.username, d)
        except Exception: pass
        if self._lan:
            self._lan.decline_friend_request(from_user)
        if self._store:
            self._store.delete(notif_id)
        self._update_badge()
        self._refresh_panel()

    def _open_chat_from_notif(self, from_user: str, notif_id: str):
        if self._store:
            self._store.mark_read(notif_id)
        self._update_badge()
        self._close()
        if self._on_chat:
            self._on_chat(from_user)

    def _dismiss(self, notif_id: str):
        if self._store:
            self._store.delete(notif_id)
        self._update_badge()
        self._refresh_panel()

    def _clear_all(self):
        if self._store:
            self._store.clear_all()
        self._update_badge()
        self._refresh_panel()

    def _mark_all_read(self):
        if self._store:
            self._store.mark_all_read()
        self._update_badge()