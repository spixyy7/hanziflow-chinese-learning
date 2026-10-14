"""
ui/views/login.py — Login sa Remember Me i auto-loginom.
"""
from __future__ import annotations
import os, tkinter as tk
from tkinter import ttk
from typing import Callable

from ..theme import C, F, S, PrimaryButton
from ...core import Database, UserProfile

_T = {
    "en": {
        "subtitle":     "Learn Chinese smarter 🐉",
        "lang_label":   "Language:",
        "welcome_back": "Welcome back",
        "new_account":  "Create account",
        "username":     "👤  Username",
        "email":        "✉️  Email",
        "password":     "🔑  Password",
        "remember_me":  "Remember me",
        "login_btn":    "Sign In →",
        "register_btn": "Create Account →",
        "no_account":   "Don't have an account? Sign up",
        "has_account":  "Already have an account? Sign in",
        "err_fields":   "Please fill in all fields.",
        "err_no_user":  "User not found.",
        "err_password": "Wrong password.",
        "err_email":    "Please enter your email.",
        "err_taken":    "Username already taken.",
        "auto_login":   "Signing in as {}...",
        "not_you":      "Not you? Sign in differently",
    },
    "sr": {
        "subtitle":     "Uči kineski pametnije 🐉",
        "lang_label":   "Jezik:",
        "welcome_back": "Dobrodošli nazad",
        "new_account":  "Novi nalog",
        "username":     "👤  Korisničko ime",
        "email":        "✉️  Email",
        "password":     "🔑  Lozinka",
        "remember_me":  "Zapamti me",
        "login_btn":    "Prijavi se →",
        "register_btn": "Registruj se →",
        "no_account":   "Nemaš nalog? Registruj se",
        "has_account":  "Već imaš nalog? Prijavi se",
        "err_fields":   "Popuni sva polja.",
        "err_no_user":  "Korisnik ne postoji.",
        "err_password": "Pogrešna lozinka.",
        "err_email":    "Unesi email.",
        "err_taken":    "Korisničko ime zauzeto.",
        "auto_login":   "Prijavljujem te kao {}...",
        "not_you":      "Nisi ti? Prijavi se drugačije",
    },
}


class LoginView(tk.Frame):
    def __init__(self, parent: tk.Widget, on_success: Callable[[UserProfile], None]):
        super().__init__(parent, bg=C.BG)
        self._db         = Database()
        self._on_success = on_success
        self._mode       = "login"
        self._lang       = "en"
        self._remember   = tk.BooleanVar(value=True)
        self._build()

        # Auto-login ako postoji sačuvana sesija
        saved = self._db.load_session()
        if saved:
            self._show_auto_login(saved)

    def _t(self, key: str, *args) -> str:
        txt = _T[self._lang].get(key, key)
        return txt.format(*args) if args else txt

    def _build(self):
        outer = tk.Frame(self, bg=C.BG)
        outer.place(relx=0.5, rely=0.5, anchor="center")

        self._card = tk.Frame(outer, bg=C.BG_CARD,
                              highlightbackground=C.BORDER, highlightthickness=1)
        self._card.pack(ipadx=S.XXL, ipady=S.XL)

        self._body = tk.Frame(self._card, bg=C.BG_CARD)
        self._body.pack(fill="both", expand=True, padx=S.XXL, pady=S.XL)

        # Logo
        tk.Label(self._body, text="HanziFlow", bg=C.BG_CARD, fg=C.PRIMARY,
                 font=(F.FAMILY, 26, "bold")).pack(pady=(0, S.XS))
        self._sub = tk.Label(self._body, text=self._t("subtitle"),
                             bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.SMALL)
        self._sub.pack(pady=(0, S.LG))

        # Language picker
        lang_row = tk.Frame(self._body, bg=C.BG_CARD); lang_row.pack()
        self._lang_lbl = tk.Label(lang_row, text=self._t("lang_label"),
                                  bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.SMALL)
        self._lang_lbl.pack(side="left")
        self._lang_var = tk.StringVar(value="English")
        ttk.Combobox(lang_row, textvariable=self._lang_var,
                     values=["English", "Srpski"],
                     state="readonly", width=10, font=F.SMALL).pack(side="left", padx=S.XS)
        self._lang_var.trace_add("write", self._on_lang_change)

        # Form
        self._form_frame = tk.Frame(self._body, bg=C.BG_CARD)
        self._form_frame.pack(fill="x", pady=S.MD)

        self._title_lbl = tk.Label(self._body, text="", bg=C.BG_CARD,
                                   fg=C.TEXT, font=F.H2)
        self._title_lbl.pack(pady=(S.SM, 0))

        self._err_lbl = tk.Label(self._body, text="", bg=C.BG_CARD,
                                 fg=C.DANGER, font=F.SMALL, wraplength=280)
        self._err_lbl.pack()

        # Remember me checkbox
        self._chk_frame = tk.Frame(self._body, bg=C.BG_CARD)
        self._chk_frame.pack(pady=(0, S.XS))
        self._chk = tk.Checkbutton(
            self._chk_frame, text=self._t("remember_me"),
            variable=self._remember,
            bg=C.BG_CARD, fg=C.TEXT_MUTED,
            activebackground=C.BG_CARD,
            selectcolor=C.BG_INPUT,
            font=F.SMALL, bd=0, cursor="hand2")
        self._chk.pack()

        self._btn_main = PrimaryButton(self._body, text="", command=self._submit, width=20)
        self._btn_main.pack(pady=S.SM)

        self._btn_switch = tk.Button(
            self._body, text="", bg=C.BG_CARD, fg=C.PRIMARY,
            font=F.BODY, relief="flat", bd=0,
            activebackground=C.BG_CARD, activeforeground=C.PRIMARY_DARK,
            cursor="hand2", padx=S.MD, pady=S.XS,
            command=self._toggle_mode)
        self._btn_switch.pack()

        self._render_form()

    def _show_auto_login(self, username: str):
        """Prikaži auto-login screen za zapamćenog korisnika."""
        for w in self._body.winfo_children():
            w.destroy()

        tk.Label(self._body, text="HanziFlow", bg=C.BG_CARD, fg=C.PRIMARY,
                 font=(F.FAMILY, 26, "bold")).pack(pady=(0, S.MD))

        # Avatar — prikazuje sliku profila ili inicijal
        av_size = 80
        av_cv = tk.Canvas(self._body, width=av_size, height=av_size,
                          bg=C.BG_CARD, highlightthickness=0)
        av_cv.pack(pady=(0, S.XS))

        # Pokušaj učitati profil i avatar
        profile = self._db.get_user(username)
        avatar_path = profile.avatar_path if profile else ""

        import logging as _logging
        _log = _logging.getLogger("HanziFlow.Login")
        _log.info(f"Auto-login avatar_path='{avatar_path}'")

        av_cv.create_oval(0, 0, av_size, av_size, fill=C.PRIMARY, outline="")
        if avatar_path and os.path.isfile(avatar_path):
            try:
                from PIL import Image, ImageTk, ImageDraw
                inner = av_size - 4
                img  = Image.open(avatar_path).resize((inner, inner), Image.LANCZOS)
                # Konvertuj u RGBA ako nije
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                mask = Image.new("L", (inner, inner), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, inner, inner), fill=255)
                result = Image.new("RGBA", (inner, inner))
                result.paste(img, mask=mask)
                self._auto_photo = ImageTk.PhotoImage(result)
                av_cv.create_image(2, 2, anchor="nw", image=self._auto_photo)
                _log.info("Auto-login avatar učitan uspješno")
            except Exception as e:
                _log.warning(f"Auto-login avatar greška: {e}")
                initial = username[0].upper()
                av_cv.create_text(av_size//2, av_size//2, text=initial,
                                  fill="white", font=(F.FAMILY, 28, "bold"))
        else:
            if avatar_path:
                _log.warning(f"Avatar fajl ne postoji: '{avatar_path}'")
            initial = username[0].upper()
            av_cv.create_text(av_size//2, av_size//2, text=initial,
                              fill="white", font=(F.FAMILY, 28, "bold"))

        tk.Label(self._body, text=username, bg=C.BG_CARD, fg=C.TEXT,
                 font=(F.FAMILY, 16, "bold")).pack(pady=(S.XS, S.MD))

        self._auto_lbl = tk.Label(self._body, text=self._t("auto_login", username),
                                  bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.SMALL)
        self._auto_lbl.pack(pady=(0, S.MD))

        PrimaryButton(self._body,
                      text=f"Continue as {username} →",
                      command=lambda: self._do_auto_login(username),
                      width=22).pack(pady=(0, S.SM))

        tk.Button(self._body, text=self._t("not_you"),
                  bg=C.BG_CARD, fg=C.TEXT_MUTED,
                  font=F.SMALL, relief="flat", bd=0,
                  cursor="hand2",
                  command=self._cancel_auto_login).pack()

    def _do_auto_login(self, username: str):
        profile = self._db.get_user(username)
        if profile:
            self._on_success(profile)
        else:
            self._db.clear_session()
            self._cancel_auto_login()

    def _cancel_auto_login(self):
        self._db.clear_session()
        for w in self._body.winfo_children():
            w.destroy()
        # Rebuild
        tk.Label(self._body, text="HanziFlow", bg=C.BG_CARD, fg=C.PRIMARY,
                 font=(F.FAMILY, 26, "bold")).pack(pady=(0, S.XS))
        self._sub = tk.Label(self._body, text=self._t("subtitle"),
                             bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.SMALL)
        self._sub.pack(pady=(0, S.LG))
        lang_row = tk.Frame(self._body, bg=C.BG_CARD); lang_row.pack()
        tk.Label(lang_row, text=self._t("lang_label"),
                 bg=C.BG_CARD, fg=C.TEXT_MUTED, font=F.SMALL).pack(side="left")
        ttk.Combobox(lang_row, textvariable=self._lang_var,
                     values=["English", "Srpski"],
                     state="readonly", width=10, font=F.SMALL).pack(side="left", padx=S.XS)
        self._form_frame = tk.Frame(self._body, bg=C.BG_CARD)
        self._form_frame.pack(fill="x", pady=S.MD)
        self._title_lbl = tk.Label(self._body, text="", bg=C.BG_CARD, fg=C.TEXT, font=F.H2)
        self._title_lbl.pack(pady=(S.SM, 0))
        self._err_lbl = tk.Label(self._body, text="", bg=C.BG_CARD,
                                 fg=C.DANGER, font=F.SMALL, wraplength=280)
        self._err_lbl.pack()
        self._chk_frame = tk.Frame(self._body, bg=C.BG_CARD); self._chk_frame.pack()
        self._chk = tk.Checkbutton(self._chk_frame, text=self._t("remember_me"),
                                   variable=self._remember, bg=C.BG_CARD, fg=C.TEXT_MUTED,
                                   activebackground=C.BG_CARD, selectcolor=C.BG_INPUT,
                                   font=F.SMALL, bd=0, cursor="hand2")
        self._chk.pack()
        self._btn_main = PrimaryButton(self._body, text="", command=self._submit, width=20)
        self._btn_main.pack(pady=S.SM)
        self._btn_switch = tk.Button(self._body, text="", bg=C.BG_CARD, fg=C.PRIMARY,
                                     font=F.BODY, relief="flat", bd=0,
                                     activebackground=C.BG_CARD, cursor="hand2",
                                     command=self._toggle_mode)
        self._btn_switch.pack()
        self._render_form()

    def _on_lang_change(self, *_):
        self._lang = "en" if self._lang_var.get() == "English" else "sr"
        self._sub.config(text=self._t("subtitle"))
        self._lang_lbl.config(text=self._t("lang_label")) if hasattr(self, "_lang_lbl") else None
        self._chk.config(text=self._t("remember_me"))
        self._render_form()

    def _render_form(self):
        for w in self._form_frame.winfo_children():
            w.destroy()
        self._entries: dict[str, tk.Entry] = {}

        fields = [("username", self._t("username"))]
        if self._mode == "register":
            fields.append(("email", self._t("email")))
        fields.append(("password", self._t("password")))

        for key, label in fields:
            tk.Label(self._form_frame, text=label, bg=C.BG_CARD,
                     fg=C.TEXT_MUTED, font=F.SMALL).pack(anchor="w")
            e = tk.Entry(self._form_frame,
                         bg=C.BG_INPUT, fg=C.TEXT, font=F.BODY,
                         relief="flat", bd=0,
                         highlightbackground=C.BORDER, highlightthickness=1,
                         highlightcolor=C.BORDER_FOCUS,
                         insertbackground=C.TEXT,
                         width=28,
                         show="*" if "password" in key else "")
            e.pack(fill="x", pady=(2, S.SM))
            e.bind("<Return>", lambda ev: self._submit())
            self._entries[key] = e

        if self._mode == "login":
            self._title_lbl.config(text=self._t("welcome_back"))
            self._btn_main.config(text=self._t("login_btn"))
            self._btn_switch.config(text=self._t("no_account"))
        else:
            self._title_lbl.config(text=self._t("new_account"))
            self._btn_main.config(text=self._t("register_btn"))
            self._btn_switch.config(text=self._t("has_account"))

        list(self._entries.values())[0].focus_set()

    def _toggle_mode(self):
        self._mode = "register" if self._mode == "login" else "login"
        self._err_lbl.config(text="")
        self._render_form()

    def _submit(self):
        self._err_lbl.config(text="")
        u = self._entries.get("username", tk.Entry()).get().strip()
        p = self._entries.get("password", tk.Entry()).get().strip()
        if not u or not p:
            self._err_lbl.config(text=self._t("err_fields")); return

        if self._mode == "login":
            if not self._db.user_exists(u):
                self._err_lbl.config(text=self._t("err_no_user")); return
            if not self._db.verify_password(u, p):
                self._err_lbl.config(text=self._t("err_password")); return
            profile = self._db.get_user(u)
        else:
            e = self._entries.get("email", tk.Entry()).get().strip()
            if not e:
                self._err_lbl.config(text=self._t("err_email")); return
            if self._db.user_exists(u):
                self._err_lbl.config(text=self._t("err_taken")); return
            try:
                profile = self._db.create_user(u, e, p)
            except ValueError as exc:
                self._err_lbl.config(text=str(exc)); return
            profile.lang = self._lang
            self._db.save_user(profile)

        # Remember me
        if self._remember.get():
            self._db.save_session(u)
        else:
            self._db.clear_session()

        self._on_success(profile)