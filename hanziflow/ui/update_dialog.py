"""
update_dialog.py — UI za update notifikaciju
Stavi u: hanziflow_app/hanziflow/ui/update_dialog.py
"""
from __future__ import annotations
import tkinter as tk
from typing import Callable


def show_update_dialog(root: tk.Tk, update_info: dict, on_update: Callable, on_skip: Callable):
    """
    Prikazuje dialog za update.
    update_info = {"version": "1.2.0", "notes": "...", "download_url": "..."}
    """
    win = tk.Toplevel(root)
    win.title("Update Available")
    win.configure(bg="#14172a")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    W, H = 420, 240
    sx = root.winfo_screenwidth()
    sy = root.winfo_screenheight()
    win.geometry(f"{W}x{H}+{(sx-W)//2}+{(sy-H)//2}")

    # Header
    hdr = tk.Frame(win, bg="#1877f2", pady=12)
    hdr.pack(fill="x")
    tk.Label(hdr, text="🚀  Update Available!",
             bg="#1877f2", fg="#ffffff",
             font=("Segoe UI", 14, "bold")).pack()

    # Body
    body = tk.Frame(win, bg="#14172a", pady=16, padx=20)
    body.pack(fill="both", expand=True)

    version = update_info.get("version", "?")
    notes   = update_info.get("notes", "Bug fixes and improvements")

    tk.Label(body, text=f"New version: {version}",
             bg="#14172a", fg="#ffffff",
             font=("Segoe UI", 12, "bold")).pack(anchor="w")
    tk.Label(body, text=notes,
             bg="#14172a", fg="#94a3b8",
             font=("Segoe UI", 10),
             wraplength=380, justify="left").pack(anchor="w", pady=(4, 12))

    # Progress bar (hidden until download starts)
    progress_frame = tk.Frame(body, bg="#14172a")
    progress_lbl = tk.Label(progress_frame, text="Downloading...",
                            bg="#14172a", fg="#94a3b8",
                            font=("Segoe UI", 9))
    progress_lbl.pack(anchor="w")
    progress_bg = tk.Frame(progress_frame, bg="#1e2236", height=8)
    progress_bg.pack(fill="x", pady=(2, 0))
    progress_bar = tk.Frame(progress_bg, bg="#1877f2", height=8, width=0)
    progress_bar.place(x=0, y=0, height=8)

    # Buttons
    btn_row = tk.Frame(body, bg="#14172a")
    btn_row.pack(fill="x")

    def start_update():
        btn_update.config(state="disabled", text="Downloading...")
        btn_skip.config(state="disabled")
        progress_frame.pack(fill="x", pady=(0, 8))

        def on_progress(pct):
            w = int(380 * pct / 100)
            try:
                progress_bar.config(width=w)
                progress_lbl.config(text=f"Downloading... {pct}%")
            except Exception:
                pass

        def on_done():
            try:
                progress_lbl.config(text="✅ Restarting...")
                progress_bar.config(bg="#22c55e", width=380)
            except Exception:
                pass

        def on_error(msg):
            try:
                progress_lbl.config(text=f"❌ Error: {msg}", fg="#ef4444")
                btn_skip.config(state="normal", text="Close")
            except Exception:
                pass

        on_update(
            on_progress=lambda p: win.after(0, lambda: on_progress(p)),
            on_done=lambda: win.after(0, on_done),
            on_error=lambda m: win.after(0, lambda: on_error(m)),
        )

    btn_update = tk.Button(btn_row, text="⬇  Update Now",
                           bg="#1877f2", fg="#ffffff",
                           font=("Segoe UI", 10, "bold"),
                           relief="flat", cursor="hand2",
                           padx=16, pady=6,
                           command=start_update)
    btn_update.pack(side="left")

    btn_skip = tk.Button(btn_row, text="Later",
                         bg="#14172a", fg="#64748b",
                         font=("Segoe UI", 10),
                         relief="flat", cursor="hand2",
                         padx=12, pady=6,
                         command=lambda: (win.destroy(), on_skip()))
    btn_skip.pack(side="left", padx=(8, 0))

    win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), on_skip()))