"""
updater.py — HanziFlow Auto-Updater
Stavi u: hanziflow_app/hanziflow/core/updater.py

Kako radi:
1. App provjeri GitHub version.txt pri svakom pokretanju
2. Ako ima novija verzija → ponudi update
3. Korisnik klikne "Update" → skida novi exe u pozadini
4. Kad završi → restart na novu verziju
"""
from __future__ import annotations
import json, logging, os, sys, threading, subprocess
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("HanziFlow.Updater")

# ── KONFIGURACIJA — promijeni ovo ──────────────────────────────────────────────
from ..config import secret

UPDATE_REPOSITORY = secret("HANZIFLOW_UPDATE_REPOSITORY")
CURRENT_VERSION = "1.0.0"
RAW_BASE = f"https://raw.githubusercontent.com/{UPDATE_REPOSITORY}/main" if UPDATE_REPOSITORY else ""
VERSION_URL = f"{RAW_BASE}/hanziflow/version.json" if RAW_BASE else ""
DOWNLOAD_URL = f"https://github.com/{UPDATE_REPOSITORY}/releases/latest/download/HanziFlow.exe" if UPDATE_REPOSITORY else ""


def updates_enabled() -> bool:
    import re
    return secret("HANZIFLOW_ENABLE_UPDATES") == "1" and bool(
        re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", UPDATE_REPOSITORY)
    )



def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0, 0, 0)


def check_for_update() -> Optional[dict]:
    """
    Provjeri da li postoji nova verzija.
    Vraća dict sa info o novoj verziji ili None.
    """
    if not updates_enabled():
        return None
    try:
        import urllib.request
        with urllib.request.urlopen(VERSION_URL, timeout=5) as r:
            data = json.loads(r.read().decode())
        remote = data.get("version", "0.0.0")
        if _parse_version(remote) > _parse_version(CURRENT_VERSION):
            return {
                "version":     remote,
                "notes":       data.get("notes", ""),
                "download_url": data.get("download_url", DOWNLOAD_URL),
            }
    except Exception as e:
        logger.debug(f"Update check failed: {e}")
    return None


def download_and_apply(
    download_url: str,
    on_progress:  Callable[[int], None] = None,
    on_done:      Callable = None,
    on_error:     Callable[[str], None] = None,
):
    """
    Skida novi exe u pozadini i restartuje app.
    on_progress(percent 0-100)
    on_done() — called before restart
    on_error(message)
    """
    if not updates_enabled():
        if on_error:
            on_error("Automatic updates are disabled; install releases manually.")
        return
    # Never accept an arbitrary download destination from remote metadata.
    if download_url != DOWNLOAD_URL:
        if on_error:
            on_error("Unexpected update download URL.")
        return

    def _do():
        try:
            import urllib.request

            # Gdje snimiti novi exe
            if getattr(sys, "frozen", False):
                # Pokrenuto kao PyInstaller exe
                current_exe = Path(sys.executable)
                new_exe     = current_exe.parent / "HanziFlow_new.exe"
                bat_path    = current_exe.parent / "_update.bat"
            else:
                # Development mode — samo simuliraj
                logger.info("Dev mode: simuliram download")
                if on_progress: on_progress(100)
                if on_done: on_done()
                return

            logger.info(f"Downloading update from {download_url}")

            # Download sa progress
            with urllib.request.urlopen(download_url, timeout=60) as response:
                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk = 8192
                with open(new_exe, "wb") as f:
                    while True:
                        data = response.read(chunk)
                        if not data:
                            break
                        f.write(data)
                        downloaded += len(data)
                        if total and on_progress:
                            on_progress(int(downloaded / total * 100))

            if on_progress: on_progress(100)
            logger.info(f"Downloaded to {new_exe}")

            # Napravi .bat koji:
            # 1. Čeka da se stara app zatvori
            # 2. Zamijeni exe
            # 3. Pokrene novu verziju
            bat_content = f"""@echo off
ping 127.0.0.1 -n 3 > nul
move /Y "{new_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
"""
            bat_path.write_text(bat_content, encoding="utf-8")
            logger.info("Update ready, restarting...")

            if on_done: on_done()

            # Pokreni bat i zatvori se
            subprocess.Popen(
                ["cmd", "/c", str(bat_path)],
                creationflags=subprocess.CREATE_NO_WINDOW
                              | subprocess.DETACHED_PROCESS,
                close_fds=True,
            )
            os.kill(os.getpid(), 9)

        except Exception as e:
            logger.error(f"Update failed: {e}")
            if on_error: on_error(str(e))

    threading.Thread(target=_do, daemon=True).start()