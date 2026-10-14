from __future__ import annotations
import tkinter as tk
from tkinter import ttk

_LIGHT = dict(
    BG="#F0F4FF", BG_CARD="#FFFFFF", BG_SIDEBAR="#E4ECFF",
    BG_INPUT="#F8FAFF", BG_HOVER="#E8EFFF",
    TEXT="#1A1A2E", TEXT_MUTED="#6B7280", TEXT_LIGHT="#9CA3AF",
    BORDER="#C5D5F5", NOTIF_OK="#D5F5E3", NOTIF_ERR="#FADBD8", NOTIF_INFO="#D6EAF8",
)
_DARK = dict(
    BG="#0F1117", BG_CARD="#1A1D27", BG_SIDEBAR="#141720",
    BG_INPUT="#1E2130", BG_HOVER="#252838",
    TEXT="#E8E9F0", TEXT_MUTED="#8B92A8", TEXT_LIGHT="#5A6075",
    BORDER="#2D3145", NOTIF_OK="#1A3D2B", NOTIF_ERR="#3D1A1A", NOTIF_INFO="#1A2B3D",
)


def _detect_system_dark() -> bool:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return val == 0
    except Exception:
        pass
    try:
        import subprocess
        r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                           capture_output=True, text=True, timeout=2)
        return "dark" in r.stdout.lower()
    except Exception:
        pass
    return False


class C:
    PRIMARY = "#4F8EFF";  PRIMARY_DARK = "#2E6AE6";  PRIMARY_LIGHT = "#7AAEFF"
    SUCCESS = "#2ECC71";  SUCCESS_DARK = "#1E8449"
    WARNING = "#F39C12";  WARNING_DARK = "#D68910"
    DANGER  = "#E74C3C";  DANGER_DARK  = "#A93226"
    GOLD    = "#F1C40F";  GOLD_DARK    = "#D4AC0D"
    PURPLE  = "#9B59B6";  PURPLE_DARK  = "#7D3C98"
    TEAL    = "#1ABC9C";  TEAL_DARK    = "#148F77"
    ORANGE  = "#E67E22"
    TEXT_WHITE   = "#FFFFFF";  BORDER_FOCUS = "#4F8EFF"
    ARENA        = "#0D0D1E";  ARENA_CARD   = "#13132A"
    ARENA_GOLD   = "#FFD700";  ARENA_ACC    = "#FF6B35"

    BG = BG_CARD = BG_SIDEBAR = BG_INPUT = BG_HOVER = "#F0F4FF"
    TEXT = "#1A1A2E";  TEXT_MUTED = "#6B7280";  TEXT_LIGHT = "#9CA3AF"
    BORDER = "#C5D5F5";  NOTIF_OK = "#D5F5E3";  NOTIF_ERR = "#FADBD8";  NOTIF_INFO = "#D6EAF8"

    _current_mode: str = "system";  _is_dark: bool = False

    @classmethod
    def set_theme(cls, mode: str) -> None:
        cls._current_mode = mode
        dark = True if mode == "dark" else (False if mode == "light" else _detect_system_dark())
        cls._is_dark = dark
        for k, v in (_DARK if dark else _LIGHT).items():
            setattr(cls, k, v)

    @classmethod
    def is_dark(cls) -> bool:
        return cls._is_dark


C.set_theme("system")


class F:
    FAMILY = "Segoe UI"; MONO = "Consolas"
    TINY   = (FAMILY, 8);   SMALL  = (FAMILY, 10)
    BODY   = (FAMILY, 12);  BODY_B = (FAMILY, 12, "bold")
    LABEL  = (FAMILY, 13);  LABEL_B= (FAMILY, 13, "bold")
    TITLE  = (FAMILY, 15, "bold");  H2 = (FAMILY, 18, "bold")
    H1     = (FAMILY, 24, "bold");  DISPLAY = (FAMILY, 32, "bold")
    HANZI  = (FAMILY, 64, "bold");  HANZI_SM = (FAMILY, 42, "bold")
    MONO_F = (MONO, 12);   TIMER = (FAMILY, 22, "bold");  SCORE = (FAMILY, 36, "bold")
    COMBO  = (FAMILY, 52, "bold")


class S:
    XS=4; SM=8; MD=14; LG=20; XL=28; XXL=40; CARD_PAD=16


def setup_theme(root: tk.Tk, mode: str = "system") -> None:
    C.set_theme(mode); _apply_ttk(root)


def apply_theme_to_root(root: tk.Tk, on_rebuild=None) -> None:
    _apply_ttk(root)
    if on_rebuild: root.after(10, on_rebuild)
    else: _recolor_all(root)


def toggle_fullscreen(root: tk.Tk) -> bool:
    state = not root.attributes("-fullscreen")
    root.attributes("-fullscreen", state)
    return state


def _recolor_all(widget: tk.Widget) -> None:
    try:
        cls = widget.__class__.__name__
        if cls in ("Frame", "Tk", "Toplevel"):
            nb = _remap_bg(widget.cget("bg"))
            if nb: widget.configure(bg=nb)
        elif cls == "Label":
            kw = {}
            nb = _remap_bg(widget.cget("bg")); nf = _remap_fg(widget.cget("fg"))
            if nb: kw["bg"] = nb
            if nf: kw["fg"] = nf
            if kw: widget.configure(**kw)
        elif cls == "Button":
            nb = _remap_bg(widget.cget("bg"))
            if nb: widget.configure(bg=nb, activebackground=nb)
        elif cls == "Entry":
            widget.configure(bg=C.BG_INPUT, fg=C.TEXT, insertbackground=C.TEXT,
                             highlightbackground=C.BORDER)
        elif cls == "Canvas":
            nb = _remap_bg(widget.cget("bg"))
            if nb: widget.configure(bg=nb)
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        _recolor_all(child)


_BG_PAIRS = [
    ("#F0F4FF","#0F1117"),("#F2F5FF","#0F1117"),("#FFFFFF","#1A1D27"),
    ("#E4ECFF","#141720"),("#D6E4FF","#141720"),("#F8FAFF","#1E2130"),
    ("#FAFBFF","#1E2130"),("#E8EFFF","#252838"),("#EAF0FF","#252838"),("#C5D5F5","#2D3145"),
]
_FG_PAIRS = [("#1A1A2E","#E8E9F0"),("#6B7280","#8B92A8"),("#9CA3AF","#5A6075")]


def _remap_bg(color: str) -> str:
    if not color or not color.startswith("#"): return ""
    dark = C.is_dark()
    for lt, dk in _BG_PAIRS:
        if dark and color.lower() == lt.lower(): return dk
        if not dark and color.lower() == dk.lower(): return lt
    return ""


def _remap_fg(color: str) -> str:
    if not color or not color.startswith("#"): return ""
    dark = C.is_dark()
    for lt, dk in _FG_PAIRS:
        if dark and color.lower() == lt.lower(): return dk
        if not dark and color.lower() == dk.lower(): return lt
    return ""


def _apply_ttk(root: tk.Tk) -> None:
    root.configure(bg=C.BG)
    s = ttk.Style(root); s.theme_use("clam")
    s.configure("TFrame", background=C.BG)
    s.configure("TLabel", background=C.BG, foreground=C.TEXT, font=F.BODY)
    s.configure("TEntry", fieldbackground=C.BG_INPUT, foreground=C.TEXT,
                bordercolor=C.BORDER, relief="flat", padding=8, font=F.BODY)
    s.map("TEntry", bordercolor=[("focus", C.BORDER_FOCUS)])
    s.configure("TButton", background=C.PRIMARY, foreground=C.TEXT_WHITE,
                font=F.BODY_B, padding=(14, 8), relief="flat", borderwidth=0)
    s.map("TButton", background=[("active", C.PRIMARY_DARK), ("pressed", C.PRIMARY_DARK)])
    s.configure("TProgressbar", troughcolor=C.BORDER, background=C.PRIMARY, thickness=10)
    s.configure("XP.TProgressbar", troughcolor=C.BORDER, background=C.GOLD, thickness=14)
    s.configure("TCombobox", fieldbackground=C.BG_INPUT, background=C.BG_INPUT,
                foreground=C.TEXT, arrowcolor=C.TEXT, bordercolor=C.BORDER,
                darkcolor=C.BG_INPUT, lightcolor=C.BG_INPUT, font=F.BODY)
    s.map("TCombobox",
          fieldbackground=[("readonly", C.BG_INPUT)], foreground=[("readonly", C.TEXT)],
          background=[("readonly", C.BG_INPUT)],
          selectbackground=[("readonly", C.PRIMARY)], selectforeground=[("readonly", C.TEXT_WHITE)])
    try:
        root.option_add("*TCombobox*Listbox.background", C.BG_CARD)
        root.option_add("*TCombobox*Listbox.foreground", C.TEXT)
        root.option_add("*TCombobox*Listbox.selectBackground", C.PRIMARY)
        root.option_add("*TCombobox*Listbox.selectForeground", C.TEXT_WHITE)
        root.option_add("*TCombobox*Listbox.font", F.BODY)
    except Exception:
        pass


def flash_widget(widget, color_on, color_off, times=3, interval_ms=120):
    def step(n, on):
        try:
            widget.config(bg=color_on if on else color_off)
            if n > 0: widget.after(interval_ms, lambda: step(n-1, not on))
        except tk.TclError:
            pass
    step(times*2, True)


def animate_score_pop(root, text, x, y, color=None):
    color = color or C.GOLD
    lbl = tk.Label(root, text=text, bg=C.BG, fg=color, font=(F.FAMILY, 18, "bold"))
    lbl.place(x=x, y=y); lbl.lift()
    def move(n, cy):
        try:
            if n <= 0: lbl.destroy(); return
            lbl.place(y=cy-3)
            lbl.after(28, lambda: move(n-1, cy-3))
        except tk.TclError:
            pass
    move(22, y)


def pulse_label(label, scale_steps=4):
    try:
        orig = label.cget("font")
        fam = orig[0] if isinstance(orig, tuple) else F.FAMILY
        sz  = orig[1] if isinstance(orig, tuple) else 12
        rest= list(orig[2:]) if isinstance(orig, tuple) and len(orig)>2 else ["bold"]
        big = (fam, sz+6, *rest)
        def grow(n):
            try:
                label.config(font=big if n%2==0 else orig)
                if n>0: label.after(55, lambda: grow(n-1))
                else: label.config(font=orig)
            except tk.TclError:
                pass
        grow(scale_steps)
    except Exception:
        pass


def _hover(btn, normal, hover):
    btn.bind("<Enter>",          lambda e: _try_cfg(btn, bg=hover))
    btn.bind("<Leave>",          lambda e: _try_cfg(btn, bg=normal))
    btn.bind("<ButtonPress-1>",  lambda e: _try_cfg(btn, relief="sunken"))
    btn.bind("<ButtonRelease-1>",lambda e: _try_cfg(btn, relief="flat"))


def _try_cfg(w, **kw):
    try: w.config(**kw)
    except tk.TclError: pass


def hover_card(frame, normal_border, hover_border, normal_bg=None, hover_bg=None):
    def enter(e):
        _try_cfg(frame, highlightbackground=hover_border)
        if hover_bg: _set_bg_recursive(frame, hover_bg)
    def leave(e):
        _try_cfg(frame, highlightbackground=normal_border)
        if normal_bg: _set_bg_recursive(frame, normal_bg)
    frame.bind("<Enter>", enter, add=True)
    frame.bind("<Leave>", leave, add=True)
    frame.config(cursor="hand2")


def _set_bg_recursive(w, bg):
    try: w.config(bg=bg)
    except Exception: pass
    for c in w.winfo_children(): _set_bg_recursive(c, bg)


class Card(tk.Frame):
    def __init__(self, parent, pad=S.CARD_PAD, **kw):
        kw.setdefault("bg", C.BG_CARD)
        super().__init__(parent, highlightbackground=C.BORDER, highlightthickness=1, **kw)
        self._pad = pad

    def body(self):
        f = tk.Frame(self, bg=self["bg"])
        f.pack(fill="both", expand=True, padx=self._pad, pady=self._pad)
        return f


class PrimaryButton(tk.Button):
    def __init__(self, parent, text="", command=None, width=0, **kw):
        def _cmd():
            try:
                from ..core.sounds import play as _s; _s("click")
            except Exception: pass
            if command: command()
        super().__init__(parent, text=text, command=_cmd,
                         bg=C.PRIMARY, fg=C.TEXT_WHITE, font=F.BODY_B,
                         relief="flat", bd=0, activebackground=C.PRIMARY_DARK,
                         activeforeground=C.TEXT_WHITE, cursor="hand2",
                         padx=S.LG, pady=S.SM, width=width or 0, **kw)
        _hover(self, C.PRIMARY, C.PRIMARY_DARK)


class SuccessButton(tk.Button):
    def __init__(self, parent, text="", command=None, **kw):
        def _cmd():
            try:
                from ..core.sounds import play as _s; _s("click")
            except Exception: pass
            if command: command()
        super().__init__(parent, text=text, command=_cmd,
                         bg=C.SUCCESS, fg=C.TEXT_WHITE, font=F.BODY_B,
                         relief="flat", bd=0, activebackground=C.SUCCESS_DARK,
                         activeforeground=C.TEXT_WHITE, cursor="hand2",
                         padx=S.LG, pady=S.SM, **kw)
        _hover(self, C.SUCCESS, C.SUCCESS_DARK)


class DangerButton(tk.Button):
    def __init__(self, parent, text="", command=None, **kw):
        super().__init__(parent, text=text, command=command,
                         bg=C.DANGER, fg=C.TEXT_WHITE, font=F.BODY_B,
                         relief="flat", bd=0, activebackground=C.DANGER_DARK,
                         activeforeground=C.TEXT_WHITE, cursor="hand2",
                         padx=S.LG, pady=S.SM, **kw)
        _hover(self, C.DANGER, C.DANGER_DARK)


class GhostButton(tk.Button):
    def __init__(self, parent, text="", command=None, **kw):
        bg = kw.pop("bg", C.BG)
        fg = kw.pop("fg", C.PRIMARY)
        active_fg = kw.pop("activeforeground", C.PRIMARY_DARK)
        super().__init__(parent, text=text, command=command,
                         bg=bg, fg=fg, font=F.BODY, relief="flat", bd=0,
                         activebackground=C.BG_HOVER, activeforeground=active_fg,
                         cursor="hand2", padx=S.MD, pady=S.XS, **kw)
        _hover(self, bg, C.BG_HOVER)


class IconButton(tk.Button):
    def __init__(self, parent, text="", command=None, bg=None, fg=None, **kw):
        _bg = bg or C.BG_CARD; _fg = fg or C.TEXT
        super().__init__(parent, text=text, command=command,
                         bg=_bg, fg=_fg, font=(F.FAMILY, 14), relief="flat", bd=0,
                         activebackground=C.BG_HOVER, activeforeground=_fg,
                         cursor="hand2", width=2, **kw)
        _hover(self, _bg, C.BG_HOVER)


class StyledEntry(tk.Entry):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=C.BG_INPUT, fg=C.TEXT, font=F.BODY,
                         relief="flat", bd=0, highlightbackground=C.BORDER,
                         highlightthickness=1, highlightcolor=C.BORDER_FOCUS,
                         insertbackground=C.TEXT, **kw)
        self.bind("<FocusIn>",  lambda e: self.config(highlightbackground=C.BORDER_FOCUS, highlightthickness=2))
        self.bind("<FocusOut>", lambda e: self.config(highlightbackground=C.BORDER, highlightthickness=1))


class XPBar(tk.Frame):
    def __init__(self, parent, **kw):
        bg = kw.pop("bg", C.BG)
        super().__init__(parent, bg=bg, **kw)
        self._bg = bg
        self._lbl = tk.Label(self, text="", bg=bg, fg=C.TEXT_MUTED, font=F.TINY)
        self._lbl.pack(anchor="w")
        self._canvas = tk.Canvas(self, height=14, bg=C.BORDER, highlightthickness=0, bd=0)
        self._canvas.pack(fill="x", pady=(2,0))
        self._anim_val = 0.0
        self._canvas.bind("<Configure>", lambda e: self._redraw())

    def set(self, current, total, label=""):
        self._lbl.config(text=label)
        self._animate_to(current / max(1, total))

    def _animate_to(self, target):
        curr = self._anim_val
        if abs(target - curr) < 0.005:
            self._anim_val = target; self._redraw(); return
        self._anim_val += (target - curr) * 0.18
        self._redraw()
        self._canvas.after(14, lambda: self._animate_to(target))

    def _redraw(self):
        w = self._canvas.winfo_width()
        if not w: return
        self._canvas.delete("all")
        bw = max(2, int(w * min(1.0, self._anim_val)))
        self._canvas.create_rectangle(0, 0, w, 14, fill=C.BORDER, outline="")
        self._canvas.create_rectangle(0, 0, bw, 14, fill=C.GOLD, outline="")
        if bw > 6:
            self._canvas.create_rectangle(0, 0, bw, 5, fill="#F5D040", outline="")


class TimerWidget(tk.Label):
    def __init__(self, parent, seconds=0, countdown=False, on_timeout=None, **kw):
        bg = kw.pop("bg", C.BG); fg = kw.pop("fg", C.TEXT_MUTED); font = kw.pop("font", F.TINY)
        super().__init__(parent, text="", bg=bg, fg=fg, font=font, **kw)
        self._seconds = seconds; self._countdown = countdown
        self._on_timeout = on_timeout; self._running = False
        self._elapsed = 0.0; self._after_id = None

    def start(self):
        self._running = True; self._elapsed = 0.0; self._tick()

    def stop(self):
        self._running = False
        if self._after_id:
            try: self.after_cancel(self._after_id)
            except Exception: pass
        return self._elapsed

    def _tick(self):
        if not self._running: return
        self._elapsed += 0.1
        if self._countdown:
            remaining = max(0, self._seconds - self._elapsed)
            self.config(text=f"{remaining:.0f}s",
                        fg=C.DANGER if remaining < 5 else C.WARNING if remaining < 15 else C.TEXT_MUTED)
            if remaining <= 0:
                self._running = False
                if self._on_timeout: self._on_timeout()
                return
        else:
            self.config(text=f"⏱ {self._elapsed:.1f}s")
        self._after_id = self.after(100, self._tick)


class QuizProgressBar(tk.Canvas):
    H = 8
    def __init__(self, parent, total, **kw):
        bg = kw.pop("bg", C.BG_SIDEBAR)
        super().__init__(parent, height=self.H, bg=bg, highlightthickness=0, bd=0, **kw)
        self._total = max(1, total); self._anim = 1.0
        self.bind("<Configure>", lambda e: self._draw(self._anim))

    def set_progress(self, done):
        self._animate_to(max(0.0, 1.0 - done / self._total))

    def _animate_to(self, target):
        curr = self._anim
        if abs(target - curr) < 0.005:
            self._anim = target; self._draw(target); return
        self._anim += (target - curr) * 0.2
        self._draw(self._anim)
        self.after(14, lambda: self._animate_to(target))

    def _draw(self, pct):
        self.delete("all")
        w = self.winfo_width()
        if not w: return
        self.create_rectangle(0, 0, w, self.H, fill=C.BORDER, outline="")
        bw = max(2, int(w * min(1.0, pct)))
        color = C.PRIMARY if pct > 0.5 else C.WARNING if pct > 0.25 else C.DANGER
        self.create_rectangle(0, 0, bw, self.H, fill=color, outline="")


class ComboOverlay:
    _active = False

    @classmethod
    def show_combo(cls, root, combo, on_done=None):
        if cls._active: return
        colors = {5: C.GOLD, 8: C.ORANGE, 10: C.DANGER, 15: "#FF00FF", 20: "#00FFFF"}
        color  = next((v for k, v in sorted(colors.items(), reverse=True) if combo >= k), C.SUCCESS)
        emoji  = "🔥" if combo < 10 else "⚡" if combo < 15 else "💥"
        cls._show(root, f"{emoji} COMBO ×{combo}!", color, duration=1300, on_done=on_done)

    @classmethod
    def show_level_up(cls, root, level, on_done=None):
        if cls._active: return
        cls._show(root, f"⭐ LEVEL {level}!", C.GOLD, subtitle="Keep it up!", duration=1800, on_done=on_done)

    @classmethod
    def show_streak(cls, root, streak, on_done=None):
        if cls._active: return
        cls._show(root, f"🔥 {streak} in a row!", C.SUCCESS, duration=900, on_done=on_done)

    @classmethod
    def _show(cls, root, text, color, subtitle="", duration=1200, on_done=None):
        cls._active = True
        overlay = tk.Frame(root, bg="#000000")
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()
        cv = tk.Canvas(overlay, bg="#000000", highlightthickness=0)
        cv.place(relx=0, rely=0, relwidth=1, relheight=1)
        cv.create_rectangle(0, 0, 9999, 9999, fill="#000000", stipple="gray50")
        lbl = tk.Label(overlay, text=text, bg="#000000", fg=color, font=(F.FAMILY, 46, "bold"))
        lbl.place(relx=0.5, rely=0.43, anchor="center")
        if subtitle:
            tk.Label(overlay, text=subtitle, bg="#000000",
                     fg=C.TEXT_WHITE, font=F.H2).place(relx=0.5, rely=0.57, anchor="center")
        sizes = [46, 54, 46, 52, 46, 50, 46]
        def _pulse(i=0):
            if i >= len(sizes): return
            try:
                lbl.config(font=(F.FAMILY, sizes[i], "bold"))
                overlay.after(95, lambda: _pulse(i+1))
            except tk.TclError: pass
        _pulse()
        def _finish():
            cls._active = False
            try: overlay.destroy()
            except tk.TclError: pass
            if on_done: on_done()
        overlay.after(duration, _finish)


class ConfirmDialog:
    """
    Modal sa poluprovidnim overlay-em.
    Koristi Toplevel sa -alpha atributom za pravi dim efekat.
    Pozadina je vidljiva ali zatamnjena — NE potpuno crna.
    """
    def __init__(self, parent, title, message, yes_text="Yes", no_text="No",
                 on_yes=None, on_no=None, danger=False):
        self._on_yes = on_yes
        self._on_no  = on_no
        root = parent.winfo_toplevel()

        root.update_idletasks()
        rw = root.winfo_width()  or 580
        rh = root.winfo_height() or 800
        rx = root.winfo_rootx()
        ry = root.winfo_rooty()

        self._dim = tk.Toplevel(root)
        self._dim.overrideredirect(True)
        self._dim.geometry(f"{rw}x{rh}+{rx}+{ry}")
        self._dim.configure(bg="#000000")
        self._dim.attributes("-alpha", 0.0)
        self._dim.attributes("-topmost", True)
        self._dim.lift()

        self._dlg = tk.Toplevel(root)
        self._dlg.overrideredirect(True)
        w, h = 400, 195
        x = rx + (rw - w) // 2
        y = ry + (rh - h) // 2
        self._dlg.geometry(f"{w}x{h}+{x}+{y}")
        self._dlg.configure(bg=C.BG_CARD)
        self._dlg.attributes("-alpha", 0.0)
        self._dlg.attributes("-topmost", True)

        cv = tk.Canvas(self._dlg, bg=C.BG_CARD, highlightthickness=0,
                       width=w, height=h)
        cv.place(x=0, y=0)
        r = 12
        cv.create_polygon(
            r, 0, w-r, 0, w, r, w, h-r, w-r, h, r, h, 0, h-r, 0, r,
            smooth=True, fill=C.BG_CARD, outline=C.BORDER, width=1
        )

        tk.Label(self._dlg, text=title, bg=C.BG_CARD, fg=C.TEXT,
                 font=F.TITLE).place(relx=0.5, y=30, anchor="center")
        tk.Label(self._dlg, text=message, bg=C.BG_CARD, fg=C.TEXT_MUTED,
                 font=F.BODY, wraplength=360, justify="center").place(relx=0.5, y=75, anchor="center")

        btn_y = 138
        no_btn = tk.Button(self._dlg, text=no_text, command=self._no,
                           bg=C.BG_CARD, fg=C.PRIMARY, font=F.BODY,
                           relief="flat", bd=0, cursor="hand2",
                           padx=S.LG, pady=S.XS,
                           activebackground=C.BG_HOVER)
        no_btn.place(x=w//2 - 130, y=btn_y)
        no_btn.bind("<Enter>", lambda e: no_btn.config(bg=C.BG_HOVER))
        no_btn.bind("<Leave>", lambda e: no_btn.config(bg=C.BG_CARD))

        yes_bg = C.DANGER if danger else C.PRIMARY
        yes_dark = C.DANGER_DARK if danger else C.PRIMARY_DARK
        yes_btn = tk.Button(self._dlg, text=yes_text, command=self._yes,
                            bg=yes_bg, fg=C.TEXT_WHITE, font=F.BODY_B,
                            relief="flat", bd=0, cursor="hand2",
                            padx=S.LG, pady=S.XS,
                            activebackground=yes_dark, activeforeground=C.TEXT_WHITE)
        yes_btn.place(x=w//2 + 20, y=btn_y)
        yes_btn.bind("<Enter>", lambda e: yes_btn.config(bg=yes_dark))
        yes_btn.bind("<Leave>", lambda e: yes_btn.config(bg=yes_bg))

        self._dim.bind("<Button-1>", lambda e: self._no())
        self._dlg.focus_set()
        self._dlg.bind("<Escape>", lambda e: self._no())
        self._dlg.bind("<Return>",  lambda e: self._yes())

        self._fade_in()

    def _fade_in(self, step=0):
        target_dim = 0.45
        target_dlg = 1.0
        steps = 10
        if step > steps: return
        alpha_dim = min(target_dim, target_dim * step / steps)
        alpha_dlg = min(target_dlg, target_dlg * step / steps)
        try:
            self._dim.attributes("-alpha", alpha_dim)
            self._dlg.attributes("-alpha", alpha_dlg)
            if step < steps:
                self._dlg.after(18, lambda: self._fade_in(step + 1))
        except tk.TclError:
            pass

    def _yes(self):
        self._close()
        if self._on_yes: self._on_yes()

    def _no(self):
        self._close()
        if self._on_no: self._on_no()

    def _close(self):
        for w in (self._dim, self._dlg):
            try: w.destroy()
            except tk.TclError: pass


class HoverTooltip:
    """
    Tooltip sa fade-in/fade-out animacijom koristeći Toplevel -alpha.
    Zaobljeni uglovi simulirani Canvas polygon-om.
    """
    _instance = None

    @classmethod
    def show(cls, root, text, x, y, extra_lines: list[str] = None):
        cls.hide()
        if not text: return

        tip = tk.Toplevel(root)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.attributes("-alpha", 0.0)
        tip.configure(bg=C.BG_CARD)

        lines = [text] + (extra_lines or [])
        inner = tk.Frame(tip, bg=C.BG_CARD, padx=12, pady=8)
        inner.pack()
        for i, line in enumerate(lines):
            fg = C.TEXT if i == 0 else C.TEXT_MUTED
            font = F.BODY_B if i == 0 else F.SMALL
            tk.Label(inner, text=line, bg=C.BG_CARD, fg=fg, font=font).pack(anchor="w")

        tip.update_idletasks()
        tw = tip.winfo_reqwidth()
        th = tip.winfo_reqheight()

        sx = root.winfo_screenwidth()
        sy = root.winfo_screenheight()
        px = min(x + 14, sx - tw - 4)
        py = max(y - th - 8, 4)
        tip.geometry(f"+{px}+{py}")

        cls._instance = tip
        cls._fade(tip, 0.0, 1.0, steps=8)

        # Auto-hide when root minimizes or loses focus
        try:
            root.bind("<Unmap>",    lambda e: cls.hide() if e.widget is root else None, add="+")
            root.bind("<FocusOut>", lambda e: cls.hide() if e.widget is root else None, add="+")
        except Exception:
            pass

    @classmethod
    def hide(cls):
        if cls._instance:
            tip = cls._instance
            cls._instance = None
            try:
                tip.attributes("-alpha", 0.0)
                tip.withdraw()
                tip.after(50, lambda: _safe_destroy(tip))
            except Exception:
                pass

    @classmethod
    def _fade(cls, tip, start, end, steps=8, on_done=None):
        def step(n):
            try:
                current = tip.attributes("-alpha")
                if start is not None and n == 0:
                    tip.attributes("-alpha", start)
                new_val = current + (end - current) * 0.4
                tip.attributes("-alpha", max(0.0, min(1.0, new_val)))
                if n < steps and abs(tip.attributes("-alpha") - end) > 0.02:
                    tip.after(16, lambda: step(n + 1))
                elif on_done:
                    on_done()
            except tk.TclError:
                if on_done: on_done()
        step(0)


def _safe_destroy(w):
    try: w.destroy()
    except tk.TclError: pass


def bind_hover_translate(widget, hanzi, meaning, root, competitive=False):
    if competitive: return
    def on_enter(e):
        try: text = widget.cget("text")
        except Exception: text = ""
        is_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in text)
        HoverTooltip.show(root, meaning if is_chinese else hanzi, e.x_root, e.y_root)
    widget.bind("<Enter>", on_enter, add=True)
    widget.bind("<Leave>", lambda e: HoverTooltip.hide(), add=True)