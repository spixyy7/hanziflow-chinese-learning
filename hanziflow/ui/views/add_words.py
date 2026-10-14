"""
ui/views/add_words.py — Dodavanje reči sa language-aware UI.
"""
from __future__ import annotations
import base64, io, os, threading
import tkinter as tk
from typing import Callable

from ..theme import C, F, S, Card, PrimaryButton, GhostButton, StyledEntry
from ..widgets import DropZone, NotificationManager
from ...core import Database, UserProfile, Word, gemini

try:
    import PyPDF2; PDF_OK = True
except ImportError:
    PDF_OK = False
try:
    import docx as _docx; DOCX_OK = True
except ImportError:
    DOCX_OK = False

_T = {
    "en": {
        "title": "📖  Add Words",
        "back": "⬅ Back",
        "manual_title": "✍  Manual Entry",
        "hanzi_lbl": "Hanzi (characters):",
        "pinyin_lbl": "Pinyin:",
        "meaning_lbl": "Meaning:",
        "save_btn": "💾  Save",
        "translating": "⏳ Translating...",
        "saved_ok": "✅ '{}' added!",
        "fill_all": "Fill in all fields.",
        "file_title": "📂  Upload File / Image",
        "drop_hint": "Drag a file here or click\nPNG · JPG · TXT · PDF · DOCX",
        "paste_hint": "💡 Ctrl+V to paste image or text",
        "reading_clip": "📋 Reading clipboard...",
        "clip_empty": "❌ Clipboard has no image, file or text.",
    },
    "sr": {
        "title": "📖  Dodaj reči",
        "back": "⬅ Nazad",
        "manual_title": "✍  Ručni unos",
        "hanzi_lbl": "Hanzi (karakteri):",
        "pinyin_lbl": "Pinyin:",
        "meaning_lbl": "Značenje:",
        "save_btn": "💾  Sačuvaj",
        "translating": "⏳ Prevodi...",
        "saved_ok": "✅ '{}' dodato!",
        "fill_all": "Popuni sva polja.",
        "file_title": "📂  Učitaj fajl / sliku",
        "drop_hint": "Prevuci fajl ovde ili klikni\nPNG · JPG · TXT · PDF · DOCX",
        "paste_hint": "💡 Ctrl+V za paste slike ili teksta",
        "reading_clip": "📋 Čitam clipboard...",
        "clip_empty": "❌ Clipboard nema sliku, fajl ni tekst.",
    },
}


class AddWordsView(tk.Frame):

    def __init__(self, parent, profile: UserProfile,
                 notif: NotificationManager, on_back: Callable):
        super().__init__(parent, bg=C.BG)
        self._profile = profile
        self._lang    = profile.lang
        self._db      = Database()
        self._notif   = notif
        self._on_back = on_back
        self._build()

    def _t(self, key: str, *args) -> str:
        txt = _T[self._lang].get(key, key)
        return txt.format(*args) if args else txt

    def _build(self):
        hdr = tk.Frame(self, bg=C.BG_SIDEBAR); hdr.pack(fill="x")
        GhostButton(hdr, text=self._t("back"), command=self._on_back).pack(
            side="left", padx=S.MD, pady=S.SM)
        tk.Label(hdr, text=self._t("title"), bg=C.BG_SIDEBAR,
                 fg=C.TEXT, font=F.H2).pack(side="left")

        body = tk.Frame(self, bg=C.BG)
        body.pack(fill="both", expand=True, padx=S.XL, pady=S.LG)

        # Left — manual
        left = Card(body); left.pack(side="left", fill="both", expand=True, padx=(0, S.MD))
        lb   = left.body()
        tk.Label(lb, text=self._t("manual_title"), bg=C.BG_CARD, fg=C.TEXT,
                 font=F.TITLE).pack(anchor="w", pady=(0, S.MD))

        for lbl_key, attr in [("hanzi_lbl", "_e_hanzi"),
                               ("pinyin_lbl", "_e_pinyin"),
                               ("meaning_lbl", "_e_meaning")]:
            tk.Label(lb, text=self._t(lbl_key), bg=C.BG_CARD,
                     fg=C.TEXT_MUTED, font=F.SMALL).pack(anchor="w")
            e = StyledEntry(lb, width=28)
            e.pack(fill="x", pady=(2, S.SM))
            e.bind("<Return>", lambda ev: self._save_manual())
            setattr(self, attr, e)

        self._btn_save = PrimaryButton(lb, text=self._t("save_btn"),
                                       command=self._save_manual)
        self._btn_save.pack(pady=S.SM)
        self._manual_status = tk.Label(lb, text="", bg=C.BG_CARD,
                                       fg=C.TEXT_MUTED, font=F.SMALL, wraplength=240)
        self._manual_status.pack()

        # Right — upload
        right = Card(body); right.pack(side="right", fill="both", expand=True)
        rb    = right.body()
        tk.Label(rb, text=self._t("file_title"), bg=C.BG_CARD, fg=C.TEXT,
                 font=F.TITLE).pack(anchor="w", pady=(0, S.MD))

        self._drop = DropZone(rb, on_file=self._on_file, hint=self._t("drop_hint"))
        self._drop.pack(fill="both", expand=True)

        tk.Label(rb, text=self._t("paste_hint"), bg=C.BG_CARD,
                 fg=C.TEXT_MUTED, font=F.TINY).pack(pady=(S.XS, 0))

        self.bind_all("<Control-v>", self._handle_paste)

    # ── Manual save ───────────────────────────────────────────────────────────

    def _save_manual(self):
        h = self._e_hanzi.get().strip()
        p = self._e_pinyin.get().strip()
        m = self._e_meaning.get().strip()
        if not (h and p and m):
            self._manual_status.config(text=self._t("fill_all"), fg=C.DANGER); return

        self._btn_save.config(state="disabled", text=self._t("translating"))
        self._manual_status.config(text=self._t("translating"), fg=C.PRIMARY)

        def do():
            sr, en = gemini.translate_meaning(m)
            word = Word(hanzi=h, pinyin=p, meaning_sr=sr, meaning_en=en)
            added = self._db.add_word(self._profile.username, word)
            if added:
                self._profile.vocab.append(word.to_dict())
                self._db.save_user(self._profile)
            self.after(0, lambda: done(added))

        def done(added: bool):
            self._btn_save.config(state="normal", text=self._t("save_btn"))
            if added:
                self._manual_status.config(text=self._t("saved_ok", h), fg=C.SUCCESS)
                self._notif.show(self._t("saved_ok", h), "success")
                self._e_hanzi.delete(0, "end"); self._e_pinyin.delete(0, "end")
                self._e_meaning.delete(0, "end")
                # Auto-download audio za novu reč
                from ...core.audio import preload as _preload
                _preload(h)
            else:
                self._manual_status.config(
                    text=f"'{h}' already in vocab.", fg=C.WARNING)

        threading.Thread(target=do, daemon=True).start()

    # ── File upload ───────────────────────────────────────────────────────────

    def _on_file(self, filepath: str):
        self._drop.set_status("⏳ Loading...", C.PRIMARY)
        threading.Thread(target=lambda: self._process_file(filepath), daemon=True).start()

    def _process_file(self, filepath: str):
        ext = os.path.splitext(filepath)[1].lower()
        text = ""; image_bytes = None; mime = "image/png"
        try:
            if ext in (".png", ".jpg", ".jpeg"):
                with open(filepath, "rb") as f: image_bytes = f.read()
                mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
            elif ext == ".txt":
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            elif ext == ".pdf" and PDF_OK:
                import PyPDF2
                with open(filepath, "rb") as f:
                    r = PyPDF2.PdfReader(f)
                    text = " ".join(p.extract_text() or "" for p in r.pages)
            elif ext == ".docx" and DOCX_OK:
                import docx as _d
                doc = _d.Document(filepath)
                text = " ".join(p.text for p in doc.paragraphs)
        except Exception as e:
            self.after(0, lambda: self._drop.set_status(f"❌ Error: {e}", C.DANGER))
            return
        self._extract_and_add(text=text, image_bytes=image_bytes, mime=mime)

    def _extract_and_add(self, text="", image_bytes=None, mime="image/png"):
        # ISPRAVKA: Ako je ubačena slika, ali nema teksta, dajemo instrukciju AI-u
        if not text.strip() and image_bytes:
            text = "Extract all Chinese words from the attached image. Return ONLY a JSON array containing objects with 'hanzi', 'pinyin', and 'meaning_en'/'meaning_sr' keys."
        elif not text.strip() and not image_bytes:
            self.after(0, lambda: self._drop.set_status("❌ No content provided.", C.DANGER))
            return

        words = gemini.extract_words(text=text, image_bytes=image_bytes, mime=mime)
        if not words:
            self.after(0, lambda: self._drop.set_status("❌ No words found.", C.DANGER))
            return

        added = 0
        for w in words:
            if "hanzi" in w and "pinyin" in w:
                word = Word(hanzi=w["hanzi"], pinyin=w["pinyin"],
                            meaning_sr=w.get("meaning_sr", ""),
                            meaning_en=w.get("meaning_en", ""),
                            xp=int(w.get("xp", 15)))
                existing = [x.get("hanzi") for x in self._profile.vocab]
                if word.hanzi not in existing:
                    self._profile.vocab.append(word.to_dict()); added += 1

        self._db.save_user(self._profile)
        msg = f"✅ Added {added} words!"
        self.after(0, lambda: self._drop.set_status(msg, C.SUCCESS))
        self.after(0, lambda: self._notif.show(msg, "success"))

        # Auto-download audio za sve nove reči
        if added > 0:
            from ...core.audio import preload as _preload
            for w in self._profile.vocab[-added:]:
                h = w.get("hanzi", "")
                if h:
                    _preload(h)

    # ── Ctrl+V ────────────────────────────────────────────────────────────────

    def _handle_paste(self, _=None):
        self._drop.set_status(self._t("reading_clip"), C.PRIMARY)

        def do():
            from PIL import ImageGrab, Image
            clip = None
            try: clip = ImageGrab.grabclipboard()
            except Exception: pass

            if isinstance(clip, Image.Image):
                buf = io.BytesIO(); clip.save(buf, format="PNG")
                self._extract_and_add(image_bytes=buf.getvalue()); return

            if isinstance(clip, list):
                paths = [x for x in clip if isinstance(x, str) and os.path.isfile(x)]
                if paths: self._process_file(paths[0]); return

            try:
                txt = self.clipboard_get()
                if txt and txt.strip():
                    stripped = txt.strip().strip('"').strip("'")
                    if os.path.isfile(stripped):
                        self._process_file(stripped); return
                    self._extract_and_add(text=txt); return
            except Exception: pass

            self.after(0, lambda: self._drop.set_status(self._t("clip_empty"), C.DANGER))

        threading.Thread(target=do, daemon=True).start()