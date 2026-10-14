"""
ui/friends_panel.py — Friends & Chat (Facebook Messenger style)
• Pill-shaped floating button (bottom-right), always on top
• Slide-up panel: Online / Offline sections + search bar
• Inline chat with encrypted messages
• Add friend from search results
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Optional

# Colors — modernized palette
_BG   = "#1e2130"; _HDR = "#151825"; _CRD = "#242840"
_BOR  = "#2a2e48"; _ACC = "#3b82f6"; _GRN = "#22c55e"
_GRY  = "#64748b"; _WHT = "#f1f5f9"; _HOV = "#222640"
_ME   = "#1d4ed8"; _FD  = "#1e2642"
_ICON = "#4a5080"  # subtle icon color
_DOT_ON  = "#22c55e"   # online dot
_DOT_OFF = "#475569"   # offline dot
_CARD_HOV = "#232745"



from datetime import datetime as _DT

def _last_seen_str(ts: float) -> str:
    """Human-readable 'last seen' from unix timestamp."""
    if ts <= 0:
        return "never"
    diff = _DT.now().timestamp() - ts
    if diff < 35:    return "Active now"
    if diff < 60:    return f"{int(diff)}s ago"
    if diff < 3600:  return f"{int(diff//60)}m ago"
    if diff < 86400: return f"{int(diff//3600)}h ago"
    days = int(diff // 86400)
    return f"{days}d ago"

def _is_online(ts: float) -> bool:
    return ts > 0 and (_DT.now().timestamp() - ts) < 35


def _show_toast(root: "tk.Tk", message: str, color: str = "#1877f2",
                duration_ms: int = 3500) -> None:
    """
    Show a small notification toast in bottom-right corner.
    Fades in, stays, fades out. Non-blocking.
    """
    try:
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        W, H = 280, 56
        x = root.winfo_rootx() + root.winfo_width()  - W - 20
        y = root.winfo_rooty() + root.winfo_height() - H - 70  # above friends btn

        toast = tk.Toplevel(root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.attributes("-alpha", 0.0)
        toast.configure(bg="#111827")
        toast.geometry(f"{W}x{H}+{x}+{y}")

        # Card
        frame = tk.Frame(toast, bg="#111827", highlightbackground=color,
                         highlightthickness=2)
        frame.pack(fill="both", expand=True)

        # Color stripe on left
        stripe = tk.Frame(frame, bg=color, width=4)
        stripe.pack(side="left", fill="y")

        # Message
        tk.Label(frame, text=message, bg="#111827", fg="#FFFFFF",
                 font=("Segoe UI", 10), wraplength=240,
                 justify="left", padx=10, pady=8).pack(side="left", expand=True, anchor="w")

        def _fade_in(s=0):
            a = min(0.95, s / 8)
            try: toast.attributes("-alpha", a)
            except tk.TclError: return
            if a < 0.95: toast.after(16, lambda: _fade_in(s+1))

        def _fade_out(s=0):
            a = max(0.0, 0.95 - s / 8)
            try: toast.attributes("-alpha", a)
            except tk.TclError: return
            if a > 0: toast.after(16, lambda: _fade_out(s+1))
            else:
                try: toast.destroy()
                except Exception: pass

        _fade_in()
        toast.after(duration_ms, lambda: _fade_out())
        toast.bind("<Button-1>", lambda e: _fade_out())
    except Exception:
        pass


class FriendsPanel:
    """Persistent floating chat panel. Call show() after login, hide() on logout."""

    BTN_W = 140; BTN_H = 46; PW = 340; PH = 500; MAR = 16; RAD = 22

    def __init__(self, root: tk.Tk, profile, lan=None):
        self._root = root; self._p = profile; self._lan = lan
        self._open = False; self._chat = None; self._badge = 0
        self._bwin = None; self._pwin = None; self._bcv = None
        self._mi = None; self._mcv = None
        self._saved_panel_x: int = -1
        self._saved_panel_y: int = -1
        self._build_btn()
        self._build_persistent_panel()   # create once, never destroy
        self._setup_cbs()

    # ── Button ─────────────────────────────────────────────────────────────────
    def _build_btn(self):
        WIN_BG = "#11141f"
        bw = tk.Toplevel(self._root); bw.overrideredirect(True)
        bw.attributes("-topmost", True)
        bw.configure(bg=WIN_BG)
        bw.withdraw(); self._bwin = bw
        cv = tk.Canvas(bw, width=self.BTN_W, height=self.BTN_H,
                       bg=WIN_BG, highlightthickness=0)
        cv.pack(); self._bcv = cv
        self._draw_btn(False)
        cv.bind("<Button-1>", self._toggle)
        cv.bind("<Enter>",    lambda e: self._draw_btn(True))
        cv.bind("<Leave>",    lambda e: self._draw_btn(False))
        # Repositioning done on open only, not on every configure event

    def _draw_btn(self, hover):
        cv = self._bcv; cv.delete("all")
        W, H   = self.BTN_W, self.BTN_H
        WIN_BG = "#11141f"
        BTN    = "#4f8ff7" if hover else "#3b82f6"
        R      = 14   # rounded rectangle, not pill

        # Fill entire canvas with window bg (removes any box artefact)
        cv.create_rectangle(0, 0, W, H, fill=WIN_BG, outline=WIN_BG)

        # Rounded rectangle using polygon with R=14
        pts = [
            R, 0,   W-R, 0,
            W, R,   W, H-R,
            W-R, H, R, H,
            0, H-R, 0, R
        ]
        cv.create_polygon(pts, fill=BTN, outline=BTN, smooth=True)

        # Icon + label
        cv.create_text(22, H//2, text="💬",
                       font=("Segoe UI Emoji", 12), fill=_WHT)
        cv.create_text(W//2 + 10, H//2, text="Friends",
                       fill=_WHT, font=("Segoe UI", 10, "bold"))

        # Badge
        if self._badge > 0:
            bx = W - 18
            cv.create_oval(bx, 3, bx+13, 16, fill="#ef4444",
                           outline=WIN_BG, width=1)
            cv.create_text(bx+7, 9, text=str(min(self._badge, 9)),
                           fill=_WHT, font=("Segoe UI", 7, "bold"))
        # topmost already set at creation — no lift() needed on every draw

    def _build_persistent_panel(self):
        """Create panel Toplevel ONCE. Never destroy it — only withdraw/deiconify."""
        pw = tk.Toplevel(self._root)
        pw.overrideredirect(True)
        pw.attributes("-topmost", True)
        pw.configure(bg=_BG, highlightbackground="#2e3358", highlightthickness=1)
        pw.geometry(f"{self.PW}x{self.PH}+9999+9999")  # offscreen until shown
        pw.withdraw()                                     # hidden at start
        pw.attributes("-alpha", 0.0)
        self._pwin = pw
        # Drag bindings — permanent
        self._drag_x = 0; self._drag_y = 0
        pw.bind("<ButtonPress-1>", self._drag_start)
        pw.bind("<B1-Motion>",      self._drag_move)
        pw.bind("<ButtonRelease-1>", self._drag_end)

    def _setup_cbs(self):
        if not self._lan: return
        old = {k: getattr(self._lan, f"on_{k}") for k in ["friend_request","message","friend_accepted","peer_discovered"]}
        def _req(u):
            self._root.after(0, lambda uu=u: (
                self._bump(),
                self._refresh(),
                _show_toast(self._root,
                            f"🤝 {uu} sent you a friend request!",
                            color="#FF9800")
            ))
            if old["friend_request"]: old["friend_request"](u)
        def _msg(m):
            def _handle(mm=m):
                self._bump()
                self._live(mm)
                # Only show toast if chat isn't open with this person
                sender = mm.get("from", "")
                if not (self._open and self._chat == sender):
                    preview = mm.get("text","")[:40]
                    _show_toast(self._root,
                                f"💬 {sender}: {preview}",
                                color="#1877f2")
            self._root.after(0, _handle)
            if old["message"]: old["message"](m)
        def _acc(u):
            def _handle(uu=u):
                self._refresh()
                _show_toast(self._root,
                            f"✅ {uu} accepted your friend request!",
                            color="#42b72a")
            self._root.after(0, _handle)
            if old["friend_accepted"]: old["friend_accepted"](u)
        def _disc(u, ip):
            self._root.after(0, self._refresh)
            if old["peer_discovered"]: old["peer_discovered"](u, ip)
        self._lan.on_friend_request  = _req
        self._lan.on_message         = _msg
        self._lan.on_friend_accepted = _acc
        self._lan.on_peer_discovered = _disc

    def _bump(self):
        self._badge += 1; self._draw_btn(False)

    def _clr_badge(self):
        self._badge = 0; self._draw_btn(False)

    def _setup_minimize_cbs(self):
        try:
            self._root.bind("<Unmap>", self._on_minimize, add="+")
            self._root.bind("<Map>",   self._on_restore_map, add="+")
        except Exception:
            pass

    def _on_minimize(self, e=None):
        try:
            if e and e.widget != self._root: return
            if self._bwin: self._bwin.withdraw()
            if self._open and self._pwin: self._pwin.withdraw()
        except Exception: pass

    def _on_restore_map(self, e=None):
        try:
            if e and e.widget != self._root: return
            if self._bwin: self._bwin.deiconify(); self._bwin.lift()
            if self._open and self._pwin:
                self._pwin.deiconify(); self._pwin.lift()
        except Exception: pass

    def show(self):
        import logging
        _log = logging.getLogger("HanziFlow.FriendsPanel")
        try:
            if not self._bwin:
                _log.error("show() called but _bwin is None")
                return
            self._bwin.deiconify()
            self._bwin.lift()
            # Position button
            rw = self._root.winfo_width()
            rh = self._root.winfo_height()
            rx = self._root.winfo_rootx()
            ry = self._root.winfo_rooty()
            _log.info(f"show(): root at {rx},{ry} size {rw}x{rh}")
            if rw > 100 and rh > 100:
                x = rx + rw - self.BTN_W - self.MAR
                y = ry + rh - self.BTN_H - self.MAR
                self._bwin.geometry(f"{self.BTN_W}x{self.BTN_H}+{x}+{y}")
                self._bwin.lift()
                _log.info(f"show(): button placed at {x},{y}")
            else:
                _log.warning(f"show(): root not ready, scheduling repos")
            # One retry after window is fully drawn
            self._root.after(500, self._repos_btn)
            self._root.bind("<Configure>", self._on_root_configure, add="+")
            self._setup_minimize_cbs()
        except Exception as e:
            import logging
            logging.getLogger("HanziFlow.FriendsPanel").error(f"show() error: {e}", exc_info=True)

    def _on_root_configure(self, e=None):
        try:
            if e and e.widget != self._root: return
            # Debounce: cancel pending reposition, schedule new one
            if hasattr(self, "_repos_after"):
                try: self._root.after_cancel(self._repos_after)
                except Exception: pass
            self._repos_after = self._root.after(150, self._repos_btn)
        except Exception: pass

    def _repos_btn(self, retry=0):
        """Position button — called once on show + on <Configure>. No loop."""
        try:
            if not self._bwin or not self._bwin.winfo_exists():
                return
            rw = self._root.winfo_width()
            rh = self._root.winfo_height()
            rx = self._root.winfo_rootx()
            ry = self._root.winfo_rooty()
            if rw < 100 or rh < 100:
                if retry < 10:
                    self._bwin.after(300, lambda: self._repos_btn(retry+1))
                return
            if rx == 0 and ry == 0:
                sw = self._root.winfo_screenwidth()
                sh = self._root.winfo_screenheight()
                x = sw - self.BTN_W - self.MAR - 10
                y = sh - self.BTN_H - self.MAR - 50
            else:
                x = rx + rw - self.BTN_W - self.MAR
                y = ry + rh - self.BTN_H - self.MAR
            self._bwin.geometry(f"{self.BTN_W}x{self.BTN_H}+{x}+{y}")
            self._bwin.lift()
            # No after() loop — <Configure> handles repositioning on resize
        except Exception:
            pass

    def hide(self):
        try: self._bwin.withdraw()
        except Exception: pass
        self._open = False; self._chat = None
        try: self._pwin.withdraw()
        except Exception: pass

    def _repos(self, e=None):
        """Reposition button + panel when panel is open."""
        try:
            rw = self._root.winfo_width();  rh = self._root.winfo_height()
            rx = self._root.winfo_rootx(); ry = self._root.winfo_rooty()
            if rw <= 1 or rh <= 1: return
            x = rx + rw - self.BTN_W - self.MAR
            y = ry + rh - self.BTN_H - self.MAR
            self._bwin.geometry(f"{self.BTN_W}x{self.BTN_H}+{x}+{y}")
            self._bwin.lift()
            if self._open and self._pwin:
                px = rx + rw - self.PW - self.MAR
                py = ry + rh - self.PH - self.BTN_H - self.MAR * 2
                self._pwin.geometry(f"{self.PW}x{self.PH}+{px}+{py}")
                self._pwin.lift()
        except Exception: pass

    def _toggle(self, e=None):
        if getattr(self, "_toggling", False):
            return          # guard against double-fire (tkinter can fire twice)
        self._toggling = True
        try:
            if self._open:
                self._close()
            else:
                self._open_panel()
        finally:
            self._bcv.after(200, lambda: setattr(self, "_toggling", False))

    def _open_panel(self):
        self._open = True; self._chat = None; self._clr_badge()

        # Calculate position (saved or default)
        rw = self._root.winfo_width();  rh = self._root.winfo_height()
        rx = self._root.winfo_rootx(); ry = self._root.winfo_rooty()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()

        if self._saved_panel_x >= 0 and self._saved_panel_y >= 0:
            px = max(0, min(self._saved_panel_x, sw - self.PW - 4))
            py = max(0, min(self._saved_panel_y, sh - self.PH - 4))
        else:
            px = rx + rw - self.PW - self.MAR
            py = ry + rh - self.PH - self.BTN_H - self.MAR * 2

        # Show panel — already created, just reposition and reveal
        self._pwin.geometry(f"{self.PW}x{self.PH}+{px}+{py}")
        self._pwin.attributes("-alpha", 0.0)
        self._pwin.deiconify()
        self._pwin.lift()

        self._build_panel()    # rebuild content in-place
        self._fade(0)          # fade in
        self._schedule_refresh()
        self._root.bind("<Button-1>", self._outside, add="+")

    def _drag_start(self, e):
        self._drag_x = e.x_root - self._pwin.winfo_rootx()
        self._drag_y = e.y_root - self._pwin.winfo_rooty()

    def _drag_move(self, e):
        if not self._pwin: return
        nx = e.x_root - self._drag_x
        ny = e.y_root - self._drag_y
        try: self._pwin.geometry(f"+{nx}+{ny}")
        except Exception: pass

    def _drag_end(self, e):
        if self._pwin:
            self._saved_panel_x = self._pwin.winfo_rootx()
            self._saved_panel_y = self._pwin.winfo_rooty()

    def _schedule_refresh(self):
        if not self._open or not self._pwin: return
        try:
            if self._chat is None:
                self._build_panel()
            self._pwin.after(15000, self._schedule_refresh)
        except Exception: pass

    def _close(self):
        self._open = False; self._chat = None
        if self._pwin:
            self._fade_out(0)   # fade out then withdraw (never destroy)

    def _fade_out(self, s=0):
        steps = 8
        a = max(0.0, 1.0 - s / steps)
        try:
            self._pwin.attributes("-alpha", a)
        except Exception:
            return
        if a > 0:
            self._pwin.after(14, lambda: self._fade_out(s + 1))
        else:
            try:
                self._pwin.withdraw()          # hide, keep alive
                self._pwin.attributes("-alpha", 0.0)
            except Exception:
                pass

    def _fade(self, s=0):
        if not self._open: return      # stop if closed mid-animation
        a = min(1.0, s / 8)
        try:
            self._pwin.attributes("-alpha", a)
        except tk.TclError:
            return
        if a < 1.0:
            self._pwin.after(14, lambda: self._fade(s + 1))

    def _outside(self, e):
        if not self._open or not self._pwin: return
        try:
            pw=self._pwin; bw=self._bwin
            ip=(pw.winfo_rootx()<=e.x_root<=pw.winfo_rootx()+pw.winfo_width() and
                pw.winfo_rooty()<=e.y_root<=pw.winfo_rooty()+pw.winfo_height())
            ib=(bw.winfo_rootx()<=e.x_root<=bw.winfo_rootx()+bw.winfo_width() and
                bw.winfo_rooty()<=e.y_root<=bw.winfo_rooty()+bw.winfo_height())
            if not ip and not ib: self._close()
        except Exception: pass

    def _refresh(self):
        if self._open and self._pwin and not self._chat:
            self._build_panel()

    # ── Panel ──────────────────────────────────────────────────────────────────
    def _build_panel(self):
        if not self._pwin: return
        for w in list(self._pwin.winfo_children()):
            try: w.destroy()
            except Exception: pass
        win = self._pwin

        # Header
        hdr = tk.Frame(win, bg=_HDR); hdr.pack(fill="x")
        tk.Label(hdr, text="💬  Friends", bg=_HDR, fg=_WHT,
                 font=("Segoe UI",13,"bold")).pack(side="left",padx=12,pady=10)
        tk.Button(hdr, text="✕", bg=_HDR, fg=_GRY, font=("Segoe UI",12),
                  relief="flat",bd=0,cursor="hand2",activebackground=_HDR,
                  command=self._close).pack(side="right",padx=10)

        # Integrated search bar
        sf = tk.Frame(win, bg="#1c1f35",
                      highlightbackground=_BOR, highlightthickness=1)
        sf.pack(fill="x", padx=14, pady=(10, 6))
        ph = "Search users..."
        self._se = tk.Entry(sf, font=("Segoe UI", 10), bg="#1c1f35",
                             fg=_GRY, insertbackground=_WHT,
                             relief="flat", bd=0)
        self._se.pack(side="left", fill="x", expand=True, ipady=8, padx=(12, 4))
        self._se.insert(0, ph)
        # 🔍 icon inside field (right side)
        lupe = tk.Label(sf, text="🔍", bg="#1c1f35", fg=_GRY,
                        font=("Segoe UI", 10), cursor="hand2")
        lupe.pack(side="right", padx=(0, 10))
        lupe.bind("<Button-1>", self._do_search)
        def _sf_focus_in(e):
            if self._se.get() == ph:
                self._se.delete(0, "end"); self._se.config(fg=_WHT)
            sf.config(highlightbackground=_ACC)
        def _sf_focus_out(e):
            if not self._se.get().strip():
                self._se.insert(0, ph); self._se.config(fg=_GRY)
            sf.config(highlightbackground=_BOR)
        self._se.bind("<FocusIn>",  _sf_focus_in)
        self._se.bind("<FocusOut>", _sf_focus_out)
        self._se.bind("<Return>",   self._do_search)

        # Search results area (hidden initially)
        self._sr_frame = tk.Frame(win,bg=_BG); self._sr_frame.pack(fill="x",padx=6)

        # Friends list
        cv = tk.Canvas(win,bg=_BG,highlightthickness=0)
        # Dark styled scrollbar
        style_id = "FP.Vertical.TScrollbar"
        _st = ttk.Style()
        _st.theme_use("default")
        _st.configure(style_id,
                      background="#252840",
                      troughcolor="#16192b",
                      bordercolor="#16192b",
                      arrowcolor="#3b5080",
                      relief="flat", borderwidth=0)
        _st.map(style_id, background=[("active", "#3b4270")])
        sb = ttk.Scrollbar(win, orient="vertical",
                           command=cv.yview, style=style_id)
        sb.pack(side="right", fill="y")
        cv.pack(fill="both", expand=True)
        # Auto-hide scrollbar when not needed (no layout jump)
        def _smart_scroll(*args):
            lo, hi = float(args[0]), float(args[1])
            if lo <= 0.0 and hi >= 1.0:
                sb.pack_forget()   # hide when all content fits
            else:
                sb.pack(side="right", fill="y", before=cv)
            cv.yview_moveto(lo)
        cv.configure(yscrollcommand=_smart_scroll)
        inn = tk.Frame(cv,bg=_BG); wid=cv.create_window((0,0),window=inn,anchor="nw")
        def _cfg(e=None):
            cv.configure(scrollregion=cv.bbox("all")); cv.itemconfig(wid,width=cv.winfo_width())
        inn.bind("<Configure>",_cfg); cv.bind("<Configure>",_cfg)
        cv.bind("<MouseWheel>",lambda e:cv.yview_scroll(-1*(e.delta//120),"units"))
        self._pop(inn)

    def _do_search(self, e=None):
        query = self._se.get().strip()
        ph = "Search users..."
        if not query or query == ph: return
        for w in self._sr_frame.winfo_children(): w.destroy()
        # Search local users + LAN peers
        results = set()
        try:
            from ..core.database import Database as _DB
            db = _DB()
            for uname in db.all_usernames():
                if query.lower() in uname.lower() and uname != self._p.username:
                    results.add(uname)
        except Exception: pass
        if self._lan:
            for uname in self._lan.get_all_peers():
                if query.lower() in uname.lower(): results.add(uname)
        if not results:
            tk.Label(self._sr_frame, text="No users found.",
                     bg=_BG, fg=_GRY, font=("Segoe UI",9)).pack(pady=4)
            return
        tk.Label(self._sr_frame, text="Search results:",
                 bg=_BG, fg=_GRY, font=("Segoe UI",8,"bold")).pack(anchor="w",padx=8,pady=(4,2))
        try:
            from ..core.lan_server import load_friends
            fdata = load_friends(self._p.username)
            friends = set(fdata.get("friends",[]))
            pending = set(fdata.get("pending",[]))
        except Exception:
            friends, pending = set(), set()
        for uname in sorted(results)[:6]:
            self._search_card(self._sr_frame, uname, uname in friends, uname in pending)
        tk.Frame(self._sr_frame, bg=_BOR, height=1).pack(fill="x",padx=6,pady=(6,2))

    def _search_card(self, parent, uname, is_friend, is_pending):
        c = tk.Frame(parent, bg=_CRD); c.pack(fill="x",padx=6,pady=2)
        ci= tk.Frame(c, bg=_CRD); ci.pack(fill="x",padx=8,pady=5)
        av= self._avatar(ci, uname, _CRD, _ACC, 26); av.pack(side="left",padx=(0,6))
        av.bind("<Button-1>", lambda e, uu=uname: self._show_profile_popup(uu))
        nl3 = tk.Label(ci,text=uname,bg=_CRD,fg=_WHT,font=("Segoe UI",10,"bold"),cursor="hand2")
        nl3.pack(side="left",expand=True,anchor="w")
        nl3.bind("<Button-1>", lambda e, uu=uname: self._show_profile_popup(uu))
        if is_friend:
            tk.Button(ci,text="💬",bg=_ACC,fg=_WHT,font=("Segoe UI",10),
                      relief="flat",cursor="hand2",padx=6,pady=2,
                      command=lambda u=uname:self._open_chat(u)).pack(side="right")
        elif is_pending:
            pf = tk.Frame(ci, bg=_CRD); pf.pack(side="right")
            tk.Label(pf,text="⏳ Sent",bg=_CRD,fg=_GRY,font=("Segoe UI",9)).pack()
            tk.Button(pf,text="Cancel",bg="#2a2d3a",fg="#cc4444",font=("Segoe UI",8),
                      relief="flat",cursor="hand2",padx=4,pady=1,
                      command=lambda uu=uname:self._remove_pending(uu)).pack(pady=(2,0))
        else:
            tk.Button(ci,text="+ Add",bg="#2a3547",fg=_ACC,font=("Segoe UI",8,"bold"),
                      relief="flat",cursor="hand2",padx=8,pady=2,
                      command=lambda u=uname:self._add(u)).pack(side="right")

    def _pop(self, inn):
        try:
            from ..core.lan_server import load_friends
            fdata = load_friends(self._p.username)
        except Exception:
            fdata = {"friends":[],"pending":[],"requests":[]}
        # Get last_seen timestamps for all known users
        def _ts(u):
            if self._lan and hasattr(self._lan, 'get_peer_last_seen'):
                return self._lan.get_peer_last_seen(u)
            return 0.0
        online  = set(self._lan.get_online_friends() if self._lan else [])
        peers   = dict(self._lan.get_all_peers()      if self._lan else {})
        friends = fdata.get("friends",[])
        reqs    = fdata.get("requests",[])

        if reqs:
            self._sec(inn,"Friend Requests","#FF9800")
            for u in reqs: self._req_card(inn,u)
            tk.Frame(inn,bg=_BOR,height=1).pack(fill="x",padx=6,pady=4)

        online_f  = [f for f in friends if f in online]
        # Sort offline by last_seen (most recent first)
        offline_f = sorted([f for f in friends if f not in online],
                           key=lambda u: _ts(u), reverse=True)

        if online_f:  self._sec(inn,f"Online ({len(online_f)})",_GRN)
        for u in online_f:  self._friend_card(inn, u, True, _ts(u))
        if offline_f: self._sec(inn,f"Offline ({len(offline_f)})",_GRY)
        for u in offline_f: self._friend_card(inn, u, False, _ts(u))

        nearby = [u for u in peers if u not in friends and u!=self._p.username]
        if nearby:
            tk.Frame(inn,bg=_BOR,height=1).pack(fill="x",padx=6,pady=4)
            self._sec(inn,"Nearby",_GRY)
            for u in nearby[:5]: self._near_card(inn,u)

        if not friends and not reqs and not nearby:
            tk.Label(inn,text="No friends yet.\nSearch or play on LAN to find people!",
                     bg=_BG,fg=_GRY,font=("Segoe UI",10),justify="center").pack(pady=40)

    def _sec(self, p, t, col):
        f = tk.Frame(p, bg=_BG); f.pack(fill="x", padx=12, pady=(10, 3))
        tk.Label(f, text=t.upper(), bg=_BG, fg=col,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Frame(f, bg=_BOR, height=1).pack(side="left", fill="x",
                                             expand=True, padx=(8, 0))

    def _friend_card(self, parent, u, online, last_ts=0.0):
        bg = _CRD
        c  = tk.Frame(parent, bg=bg); c.pack(fill="x", padx=8, pady=2)
        ci = tk.Frame(c, bg=bg);      ci.pack(fill="x", padx=12, pady=9)

        # ── Avatar + status dot ───────────────────────────────────────────────
        AV = 36
        av_wrap = tk.Frame(ci, bg=bg); av_wrap.pack(side="left", padx=(0, 10))
        av_cv = self._avatar(av_wrap, u, bg, _ACC if online else "#3a3d55", AV)
        av_cv.pack()
        # Status dot pinned bottom-right of avatar
        dot_cv = tk.Canvas(av_wrap, width=10, height=10, bg=bg, highlightthickness=0)
        dot_cv.place(x=AV-9, y=AV-9)
        dot_col = _DOT_ON if online else _DOT_OFF
        dot_cv.create_oval(1, 1, 9, 9, fill=dot_col, outline=bg, width=1)
        av_cv.bind("<Button-1>", lambda e, uu=u: self._show_profile_popup(uu))

        # ── Name + status ─────────────────────────────────────────────────────
        inf = tk.Frame(ci, bg=bg); inf.pack(side="left", expand=True, fill="x")
        name_col = _WHT if online else "#9ca3af"
        nl = tk.Label(inf, text=u, bg=bg, fg=name_col,
                      font=("Segoe UI", 10, "bold"), cursor="hand2")
        nl.pack(anchor="w")
        nl.bind("<Button-1>", lambda e, uu=u: self._show_profile_popup(uu))
        status_txt = _last_seen_str(last_ts) if last_ts > 0 else ("Active now" if online else "Offline")
        tk.Label(inf, text=status_txt, bg=bg,
                 fg=_DOT_ON if online else _GRY,
                 font=("Segoe UI", 8)).pack(anchor="w")

        # ── Icon actions (fade on hover) ──────────────────────────────────────
        act = tk.Frame(ci, bg=bg); act.pack(side="right")
        chat_btn = tk.Label(act, text="💬", bg=bg, fg=_ICON,
                            font=("Segoe UI Emoji", 14), cursor="hand2")
        chat_btn.pack(side="left", padx=(0, 4))
        trash_btn = tk.Label(act, text="🗑", bg=bg, fg=_ICON,
                             font=("Segoe UI Emoji", 13), cursor="hand2")
        trash_btn.pack(side="left")
        chat_btn.bind("<Button-1>",  lambda e, uu=u: self._open_chat(uu))
        trash_btn.bind("<Button-1>", lambda e, uu=u: self._remove_friend(uu))
        # hover: icons brighten
        chat_btn.bind("<Enter>",  lambda e: chat_btn.config(fg="#93c5fd"))
        chat_btn.bind("<Leave>",  lambda e: chat_btn.config(fg=_ICON))
        trash_btn.bind("<Enter>", lambda e: trash_btn.config(fg="#f87171"))
        trash_btn.bind("<Leave>", lambda e: trash_btn.config(fg=_ICON))

        def _enter(e):
            c.config(bg=_CARD_HOV); ci.config(bg=_CARD_HOV)
            inf.config(bg=_CARD_HOV); nl.config(bg=_CARD_HOV)
            act.config(bg=_CARD_HOV); chat_btn.config(bg=_CARD_HOV)
            trash_btn.config(bg=_CARD_HOV)
        def _leave(e):
            c.config(bg=bg); ci.config(bg=bg); inf.config(bg=bg)
            nl.config(bg=bg); act.config(bg=bg); chat_btn.config(bg=bg)
            trash_btn.config(bg=bg)
        for w in [c, ci, inf, nl]:
            w.bind("<Enter>", _enter); w.bind("<Leave>", _leave)

    def _req_card(self, parent, u):
        c   = tk.Frame(parent, bg=_CRD,
                       highlightbackground="#f59e0b",
                       highlightthickness=1)
        c.pack(fill="x", padx=8, pady=3)
        row = tk.Frame(c, bg=_CRD); row.pack(fill="x", padx=12, pady=(10, 4))
        av  = self._avatar(row, u, _CRD, "#f59e0b", 34)
        av.pack(side="left", padx=(0, 10))
        av.bind("<Button-1>", lambda e, uu=u: self._show_profile_popup(uu))
        inf = tk.Frame(row, bg=_CRD); inf.pack(side="left", expand=True, fill="x")
        nl  = tk.Label(inf, text=u, bg=_CRD, fg=_WHT,
                       font=("Segoe UI", 10, "bold"), cursor="hand2")
        nl.pack(anchor="w")
        nl.bind("<Button-1>", lambda e, uu=u: self._show_profile_popup(uu))
        tk.Label(inf, text="wants to be your friend", bg=_CRD,
                 fg="#f59e0b", font=("Segoe UI", 8)).pack(anchor="w")
        btns = tk.Frame(c, bg=_CRD); btns.pack(fill="x", padx=12, pady=(0, 10))
        tk.Button(btns, text="Accept",
                  bg="#22c55e", fg=_WHT, font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2", padx=16, pady=4,
                  activebackground="#16a34a",
                  command=lambda uu=u: self._accept(uu)).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="Decline",
                  bg=_CRD, fg=_GRY, font=("Segoe UI", 9),
                  relief="flat", cursor="hand2", padx=12, pady=4,
                  highlightbackground=_BOR, highlightthickness=1,
                  activebackground=_HOV,
                  command=lambda uu=u: self._decline(uu)).pack(side="left")

    def _near_card(self,parent,u):
        c=tk.Frame(parent,bg=_CRD); c.pack(fill="x",padx=6,pady=2)
        ci=tk.Frame(c,bg=_CRD); ci.pack(fill="x",padx=10,pady=6)
        av=self._avatar(ci,u,_CRD,_GRY,26); av.pack(side="left",padx=(0,8))
        av.bind("<Button-1>", lambda e, uu=u: self._show_profile_popup(uu))
        nl4 = tk.Label(ci,text=u,bg=_CRD,fg="#AAAAAA",font=("Segoe UI",9),cursor="hand2")
        nl4.pack(side="left",expand=True,anchor="w")
        nl4.bind("<Button-1>", lambda e, uu=u: self._show_profile_popup(uu))
        tk.Button(ci,text="+ Add",bg="#2a3547",fg=_ACC,font=("Segoe UI",8,"bold"),
                  relief="flat",cursor="hand2",padx=8,pady=2,
                  command=lambda uu=u:self._add(uu)).pack(side="right")

    def _avatar(self, parent, u, bg, col, sz):
        av = tk.Canvas(parent, width=sz, height=sz, bg=bg, highlightthickness=0)
        av.create_oval(1, 1, sz-1, sz-1, fill=col, outline="")
        av.create_text(sz//2, sz//2, text=u[0].upper(),
                       fill=_WHT, font=("Segoe UI", sz//3, "bold"))
        try:
            from ..core.database import Database as _DB
            prof = _DB().get_user(u)
            path = getattr(prof, "avatar_path", "") if prof else ""
            if path:
                from PIL import Image, ImageTk, ImageDraw
                img = Image.open(path).resize((sz-2, sz-2), Image.LANCZOS)
                mask = Image.new("L", (sz-2, sz-2), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, sz-2, sz-2), fill=255)
                result = Image.new("RGBA", (sz-2, sz-2))
                result.paste(img, mask=mask)
                photo = ImageTk.PhotoImage(result)
                av.create_image(1, 1, anchor="nw", image=photo)
                av._photo_ref = photo
        except Exception:
            pass
        return av

    # ── Profile popup ─────────────────────────────────────────────────────────
    def _show_profile_popup(self, username: str):
        try:
            from ..core.database import Database as _DB
            from ..core.adaptive import compute_level
            from ..core.lan_server import load_friends
            db = _DB()
            profile = db.get_user(username)
        except Exception:
            profile = None

        root = self._root
        popup = tk.Toplevel(root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=_BG, highlightbackground=_BOR, highlightthickness=1)
        W, H = 240, 200
        sx = root.winfo_screenwidth(); sy = root.winfo_screenheight()
        px = (root.winfo_rootx() + root.winfo_width()  - W) // 1
        py = (root.winfo_rooty() + root.winfo_height() - H) // 2
        px = min(px, sx - W - 8); py = min(py, sy - H - 8)
        popup.geometry(f"{W}x{H}+{px}+{py}")
        popup.attributes("-alpha", 0.0)

        tk.Button(popup, text="✕", bg=_BG, fg=_GRY, font=("Segoe UI",10),
                  relief="flat", bd=0, cursor="hand2",
                  command=popup.destroy).place(relx=1.0, x=-4, y=4, anchor="ne")

        av_cv = tk.Canvas(popup, width=52, height=52, bg=_BG, highlightthickness=0)
        av_cv.place(relx=0.5, y=24, anchor="n")
        col = _ACC if profile else _GRY
        av_cv.create_oval(2, 2, 50, 50, fill=col, outline="")
        av_cv.create_text(26, 26, text=username[0].upper(),
                          fill=_WHT, font=("Segoe UI", 18, "bold"))

        tk.Label(popup, text=username, bg=_BG, fg=_WHT,
                 font=("Segoe UI", 12, "bold")).place(relx=0.5, y=82, anchor="n")

        if profile:
            try:
                lvl, cur, needed = compute_level(profile.xp)
                tk.Label(popup, text=f"Level {lvl}  •  {profile.xp} XP",
                         bg=_BG, fg=_GRY, font=("Segoe UI", 9)).place(relx=0.5, y=104, anchor="n")
                from ..core.models import get_rank
                rank = get_rank(profile.arena_score)
                tk.Label(popup, text=f"{rank['icon']} {rank['name']}",
                         bg=_BG, fg=rank["color"],
                         font=("Segoe UI", 9, "bold")).place(relx=0.5, y=122, anchor="n")
            except Exception:
                pass
        else:
            tk.Label(popup, text="User info unavailable",
                     bg=_BG, fg=_GRY, font=("Segoe UI", 9)).place(relx=0.5, y=104, anchor="n")

        try:
            fdata = load_friends(self._p.username)
            is_friend = username in fdata.get("friends", [])
            is_pending = username in fdata.get("pending", [])
            is_req = username in fdata.get("requests", [])
        except Exception:
            is_friend = is_pending = is_req = False

        if username != self._p.username:
            if is_friend:
                tk.Button(popup, text="💬 Message", bg=_ACC, fg=_WHT,
                          font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
                          padx=12, pady=4,
                          command=lambda: (popup.destroy(), self._open_panel() if not self._open else None, self._open_chat(username))
                          ).place(relx=0.5, y=152, anchor="n")
            elif is_pending:
                tk.Label(popup, text="⏳ Request sent", bg=_BG, fg="#FF9800",
                         font=("Segoe UI", 9)).place(relx=0.5, y=152, anchor="n")
            elif is_req:
                bf = tk.Frame(popup, bg=_BG); bf.place(relx=0.5, y=148, anchor="n")
                tk.Button(bf, text="✔ Accept", bg=_GRN, fg=_WHT,
                          font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
                          padx=8, pady=3,
                          command=lambda: (popup.destroy(), self._accept(username))
                          ).pack(side="left", padx=(0,4))
                tk.Button(bf, text="✖", bg="#cc0000", fg=_WHT,
                          font=("Segoe UI", 9), relief="flat", cursor="hand2",
                          padx=6, pady=3,
                          command=lambda: (popup.destroy(), self._decline(username))
                          ).pack(side="left")
            else:
                tk.Button(popup, text="+ Add Friend", bg="#2a3547", fg=_ACC,
                          font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
                          padx=12, pady=4,
                          command=lambda: (popup.destroy(), self._add(username))
                          ).place(relx=0.5, y=152, anchor="n")

        def _fade_popup(s=0):
            a = min(1.0, s/6)
            try: popup.attributes("-alpha", a)
            except tk.TclError: return
            if a < 1.0: popup.after(16, lambda: _fade_popup(s+1))
        _fade_popup()
        popup.bind("<FocusOut>", lambda e: popup.destroy())
        popup.focus_set()

    # ── Actions ────────────────────────────────────────────────────────────────
    def _accept(self,u):
        try:
            if self._lan: self._lan.accept_friend_request(u)
            else:
                from ..core.lan_server import load_friends,save_friends
                d=load_friends(self._p.username)
                if u in d.get("requests",[]): d["requests"].remove(u)
                if u not in d["friends"]: d["friends"].append(u)
                save_friends(self._p.username,d)
        except Exception: pass
        self._build_panel()

    def _decline(self,u):
        try:
            from ..core.lan_server import load_friends,save_friends
            d=load_friends(self._p.username)
            if u in d.get("requests",[]): d["requests"].remove(u)
            save_friends(self._p.username,d)
        except Exception: pass
        if self._lan: self._lan.decline_friend_request(u)
        self._build_panel()

    def _remove_friend(self, u):
        try:
            if self._lan:
                self._lan.remove_friend(u)
            else:
                from ..core.lan_server import load_friends, save_friends
                d = load_friends(self._p.username)
                if u in d.get("friends", []): d["friends"].remove(u)
                save_friends(self._p.username, d)
        except Exception: pass
        _show_toast(self._root, f"Removed {u} from friends", color="#cc4444")
        self._build_panel()

    def _remove_pending(self, u):
        try:
            from ..core.lan_server import load_friends, save_friends
            d = load_friends(self._p.username)
            if u in d.get("pending", []): d["pending"].remove(u)
            save_friends(self._p.username, d)
        except Exception: pass
        _show_toast(self._root, f"Cancelled request to {u}", color="#888")
        self._build_panel()

    def _add(self, u):
        sent = False
        try:
            if self._lan:
                sent = self._lan.send_friend_request(u)
            else:
                from ..core.lan_server import load_friends, save_friends
                d = load_friends(self._p.username)
                d.setdefault("pending", []).append(u)
                save_friends(self._p.username, d)
                sent = True
        except Exception:
            pass
        _show_toast(self._root, f"🤝 Friend request sent to {u}!", color="#FF9800")
        self._build_panel()

    # ── Chat ───────────────────────────────────────────────────────────────────
    def _open_chat(self,friend):
        self._chat=friend; self._clr_badge()
        if not self._pwin: return
        for w in self._pwin.winfo_children(): w.destroy()
        self._build_chat(friend)

    def _build_chat(self,friend):
        win=self._pwin
        hdr=tk.Frame(win,bg=_HDR); hdr.pack(fill="x")
        tk.Button(hdr,text="←",bg=_HDR,fg=_GRY,font=("Segoe UI",13),relief="flat",cursor="hand2",bd=0,
                  command=lambda:(setattr(self,"_chat",None),self._build_panel())).pack(side="left",padx=8,pady=8)
        tk.Label(hdr,text=friend,bg=_HDR,fg=_WHT,font=("Segoe UI",12,"bold")).pack(side="left")
        # Show online status in chat header
        _ts_val = self._lan.get_peer_last_seen(friend) if (self._lan and hasattr(self._lan,"get_peer_last_seen")) else 0
        _status = _last_seen_str(_ts_val) if _ts_val > 0 else "Offline"
        _scol   = _GRN if _is_online(_ts_val) else _GRY
        tk.Label(hdr,text=_status,bg=_HDR,fg=_scol,font=("Segoe UI",8)).pack(side="left",padx=(4,0))
        tk.Label(hdr,text="🔒",bg=_HDR,fg=_GRN,font=("Segoe UI",9)).pack(side="right",padx=10)
        mcv=tk.Canvas(win,bg=_BG,highlightthickness=0)
        _st2 = ttk.Style()
        _st2.configure("FPChat.Vertical.TScrollbar",
                       background="#252840", troughcolor="#16192b",
                       bordercolor="#16192b", arrowcolor="#3b5080",
                       relief="flat", borderwidth=0)
        _st2.map("FPChat.Vertical.TScrollbar",
                 background=[("active", "#3b4270")])
        msb = ttk.Scrollbar(win, orient="vertical",
                            command=mcv.yview,
                            style="FPChat.Vertical.TScrollbar")
        msb.pack(side="right", fill="y")
        mcv.pack(fill="both", expand=True)
        mcv.configure(yscrollcommand=msb.set)
        self._mi=tk.Frame(mcv,bg=_BG); wid=mcv.create_window((0,0),window=self._mi,anchor="nw")
        def _cfg(e=None):
            mcv.configure(scrollregion=mcv.bbox("all")); mcv.itemconfig(wid,width=mcv.winfo_width())
        self._mi.bind("<Configure>",_cfg); mcv.bind("<Configure>",_cfg)
        mcv.bind("<MouseWheel>",lambda e:mcv.yview_scroll(-1*(e.delta//120),"units"))
        self._mcv=mcv
        try:
            from ..core.lan_server import get_chat_history
            for m in get_chat_history(self._p.username,friend):
                self._bubble(m["text"],m["mine"],m.get("timestamp",""))
        except Exception: pass
        inp=tk.Frame(win,bg=_HDR); inp.pack(fill="x")
        self._ce=tk.Entry(inp,font=("Segoe UI",10),bg="#22253a",fg=_WHT,
                           insertbackground=_WHT,relief="flat",
                           highlightbackground=_BOR,highlightthickness=1)
        self._ce.pack(side="left",fill="x",expand=True,ipady=7,padx=(8,4),pady=8)
        self._ce.bind("<Return>",lambda e:self._send(friend))
        tk.Button(inp,text="➤",bg=_ACC,fg=_WHT,font=("Segoe UI",12),
                  relief="flat",cursor="hand2",padx=8,pady=5,
                  command=lambda:self._send(friend)).pack(side="right",padx=(0,8))
        # Live CB
        if self._lan:
            old=self._lan.on_message
            def _live(m):
                if m.get("from")==friend and self._mi:
                    win.after(0,lambda mm=m:self._bubble(mm["text"],False,mm.get("timestamp","")))
                if old: old(m)
            self._lan.on_message=_live

    def _make_chat_avatar(self, parent, username, bg_frame, size=26):
        av = tk.Canvas(parent, width=size, height=size, bg=bg_frame, highlightthickness=0)
        try:
            from ..core.database import Database as _DB
            prof = _DB().get_user(username)
            path = getattr(prof, "avatar_path", "") if prof else ""
            if path:
                from PIL import Image, ImageTk, ImageDraw
                img = Image.open(path).resize((size-2, size-2), Image.LANCZOS)
                mask = Image.new("L", (size-2, size-2), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size-2, size-2), fill=255)
                result = Image.new("RGBA", (size-2, size-2))
                result.paste(img, mask=mask)
                photo = ImageTk.PhotoImage(result)
                av.create_image(1, 1, anchor="nw", image=photo)
                av._photo = photo
                return av
        except Exception:
            pass
        col = _ACC if username == self._p.username else "#4a5060"
        av.create_oval(0, 0, size, size, fill=col, outline="")
        av.create_text(size//2, size//2, text=username[0].upper() if username else "?",
                       fill=_WHT, font=("Segoe UI", size//3, "bold"))
        return av

    def _bubble(self, text, mine, ts=""):
        if not self._mi: return
        BG_B = _ME if mine else _FD
        outer = tk.Frame(self._mi, bg=_BG)
        outer.pack(fill="x", padx=6, pady=2)

        if mine:
            msg_row = tk.Frame(outer, bg=_BG)
            msg_row.pack(anchor="e")
            time_row = tk.Frame(outer, bg=_BG)
            time_row.pack(anchor="e", padx=4)

            bubble = tk.Frame(msg_row, bg=BG_B)
            bubble.pack(side="right", padx=(8, 0))
            tk.Label(bubble, text=text, bg=BG_B, fg=_WHT,
                     font=("Segoe UI", 9), wraplength=185,
                     justify="left", padx=10, pady=7).pack()

            av = self._make_chat_avatar(msg_row, self._p.username, _BG, 26)
            av.pack(side="right")
        else:
            friend = self._chat or ""
            msg_row = tk.Frame(outer, bg=_BG)
            msg_row.pack(anchor="w")
            time_row = tk.Frame(outer, bg=_BG)
            time_row.pack(anchor="w", padx=4)

            av = self._make_chat_avatar(msg_row, friend, _BG, 26)
            av.pack(side="left")
            bubble = tk.Frame(msg_row, bg=BG_B)
            bubble.pack(side="left", padx=(8, 0))
            tk.Label(bubble, text=text, bg=BG_B, fg=_WHT,
                     font=("Segoe UI", 9), wraplength=185,
                     justify="left", padx=10, pady=7).pack()

        if ts:
            try: ts2 = datetime.fromisoformat(ts).strftime("%H:%M")
            except Exception: ts2 = ""
            if ts2:
                tk.Label(time_row, text=ts2, bg=_BG, fg="#555",
                         font=("Segoe UI", 7)).pack()

        if self._mcv: self._mcv.after(50, lambda: self._mcv.yview_moveto(1.0))

    def _send(self,friend):
        t=self._ce.get().strip()
        if not t: return
        self._ce.delete(0,"end")
        self._bubble(t,mine=True,ts=datetime.now().isoformat())
        if self._lan: self._lan.send_message(friend,t)
        else:
            try:
                from ..core.lan_server import _make_key,_xor_encrypt,save_message
                k=_make_key(self._p.username,friend)
                save_message(self._p.username,{"type":"chat","from":self._p.username,
                             "to":friend,"data":_xor_encrypt(t,k),"timestamp":datetime.now().isoformat()})
            except Exception: pass