"""
core/audio.py — Persistentni disk cache + instant audio playback.

Arhitektura:
  - Svaka reč ima WAV fajl na disku: audio_cache/{username}/{hanzi}.wav
  - Pri loginu: preuzmi sve reči koje nemaju audio
  - Pri dodavanju reči: odmah preuzmi audio
  - play(): instant iz memorije → disk → API (nikad blokira UI)
  - Memorijski LRU cache za najskorije korišćene reči
"""
from __future__ import annotations
import hashlib, io, logging, os, time as _time, threading, wave
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("HanziFlow.Audio")

try:
    import pygame
    PYGAME_OK = True
except Exception:
    PYGAME_OK = False

try:
    from gtts import gTTS
    GTTS_OK = True
except ImportError:
    GTTS_OK = False

# Globalni audio direktorijum
from ..config import validate_username

AUDIO_DIR = Path("audio_cache")

# Globalni state
_enabled        = [True]
_play_lock      = threading.Lock()
_mem_cache: OrderedDict[str, bytes] = OrderedDict()
_MEM_CACHE_MAX  = 150
_current_user   = [""]


# ─── Disk cache helpers ───────────────────────────────────────────────────────

def _safe_filename(text: str) -> str:
    """Pretvori tekst u bezbedan naziv fajla."""
    h = hashlib.md5(text.encode()).hexdigest()[:8]
    safe = "".join(c for c in text if c.isalnum())[:20]
    return f"{safe}_{h}.wav"


def _user_dir() -> Path:
    d = AUDIO_DIR / validate_username(_current_user[0] or "default")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _disk_path(text: str) -> Path:
    return _user_dir() / _safe_filename(text)


def _disk_has(text: str) -> bool:
    p = _disk_path(text)
    return p.exists() and p.stat().st_size > 500


def _disk_load(text: str) -> Optional[bytes]:
    p = _disk_path(text)
    if p.exists() and p.stat().st_size > 500:
        try:
            return p.read_bytes()
        except Exception:
            pass
    return None


def _disk_save(text: str, data: bytes) -> None:
    try:
        _disk_path(text).write_bytes(data)
    except Exception as e:
        logger.debug(f"Disk save failed for '{text}': {e}")


# ─── Memory cache ─────────────────────────────────────────────────────────────

def _mem_get(text: str) -> Optional[bytes]:
    if text in _mem_cache:
        _mem_cache.move_to_end(text)
        return _mem_cache[text]
    return None


def _mem_put(text: str, data: bytes) -> None:
    _mem_cache[text] = data
    _mem_cache.move_to_end(text)
    if len(_mem_cache) > _MEM_CACHE_MAX:
        _mem_cache.popitem(last=False)


# ─── Fetch audio ──────────────────────────────────────────────────────────────

def _detect_lang(text: str) -> str:
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return "zh" if chinese_chars > 0 else "en"


def _fetch_wav(text: str) -> Optional[bytes]:
    lang = _detect_lang(text)

    if lang == "zh":
        if GTTS_OK:
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    tts = gTTS(text=text, lang="zh", slow=False)
                mp3_tmp = os.path.join(str(_user_dir()), f"_tmp_{abs(hash(text))}.mp3")
                tts.save(mp3_tmp)
                with open(mp3_tmp, "rb") as f:
                    data = f.read()
                try: os.remove(mp3_tmp)
                except Exception: pass
                if data and len(data) > 500:
                    logger.debug(f"gTTS zh OK: '{text}'")
                    return data
            except Exception as e:
                logger.debug(f"gTTS zh failed for '{text}': {e}")

        try:
            from .ai_client import gemini
            wav = gemini.tts(text, lang="zh")
            if wav and len(wav) > 500:
                return wav
        except Exception as e:
            logger.debug(f"Gemini TTS zh failed for '{text}': {e}")

    else:
        try:
            from .ai_client import gemini
            wav = gemini.tts(text, lang="en")
            if wav and len(wav) > 500:
                logger.debug(f"Gemini TTS en OK: '{text}'")
                return wav
        except Exception as e:
            logger.debug(f"Gemini TTS en failed for '{text}': {e}")

        if GTTS_OK:
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    tts = gTTS(text=text, lang="en", tld="us", slow=False)
                mp3_tmp = os.path.join(str(_user_dir()), f"_tmp_{abs(hash(text))}.mp3")
                tts.save(mp3_tmp)
                with open(mp3_tmp, "rb") as f:
                    data = f.read()
                try: os.remove(mp3_tmp)
                except Exception: pass
                if data and len(data) > 500:
                    logger.debug(f"gTTS en OK: '{text}'")
                    return data
            except Exception as e:
                logger.debug(f"gTTS en failed for '{text}': {e}")

    return None


# ─── Public API ───────────────────────────────────────────────────────────────

def set_user(username: str) -> None:
    """Postavi trenutnog korisnika (kreira audio_cache/{username}/)."""
    _current_user[0] = username
    _user_dir()  # kreira direktorijum


def set_audio_enabled(enabled: bool) -> None:
    _enabled[0] = enabled


def is_enabled() -> bool:
    return _enabled[0]


def has_cached(text: str) -> bool:
    """Da li postoji audio u memoriji ili na disku."""
    return bool(_mem_get(text)) or _disk_has(text)


def preload(text: str, on_done: Callable = None) -> None:
    """
    Preuzima audio u pozadini:
    1. Provjeri memoriju i disk
    2. Ako nema → fetch od API → sačuvaj na disk i u memoriju
    3. Pozovi on_done() kad završi
    """
    if not text:
        return

    # Već u memoriji
    if _mem_get(text):
        if on_done:
            on_done()
        return

    def do():
        # Provjeri disk
        data = _disk_load(text)
        if data:
            _mem_put(text, data)
            if on_done:
                on_done()
            return
        # Fetch od API
        data = _fetch_wav(text)
        if data:
            _disk_save(text, data)
            _mem_put(text, data)
            logger.debug(f"Audio cached: '{text}'")
        if on_done:
            on_done()

    threading.Thread(target=do, daemon=True).start()


def preload_all(texts: list[str],
                on_progress: Callable[[int, int], None] = None,
                on_done: Callable = None) -> None:
    """
    Preuzima audio sekvencijalno (1 thread, bez 429).
    on_progress(done, total) — poziva se za svaki završeni
    on_done() — poziva se kad sve završi
    """
    if not texts:
        if on_done:
            on_done()
        return

    missing = [t for t in texts if t and not _disk_has(t)]
    total   = len(missing)

    if total == 0:
        def load_from_disk():
            for t in texts:
                if not _mem_get(t):
                    data = _disk_load(t)
                    if data:
                        _mem_put(t, data)
            if on_done:
                on_done()
        threading.Thread(target=load_from_disk, daemon=True).start()
        return

    def fetch_all():
        for i, text in enumerate(missing):
            # Provjeri disk ponovo (možda je već skinut u međuvremenu)
            data = _disk_load(text)
            if not data:
                data = _fetch_wav(text)
                if data:
                    _disk_save(text, data)
            if data:
                _mem_put(text, data)
            if on_progress:
                on_progress(i + 1, total)
            # Mali delay između API poziva da izbjegnemo 429
            # gTTS ne treba delay, ali ako je Gemini koristimo 2s pauzu
            _time.sleep(0.5)

        if on_done:
            on_done()

    threading.Thread(target=fetch_all, daemon=True).start()


def play(text: str, on_done: Callable = None) -> None:
    """
    Pušta audio za tekst — instant ako je u cache-u.

    Redosled:
    1. Memorija (instant)
    2. Disk (brzo)
    3. API fetch (async, malo čeka)
    """
    if not _enabled[0] or not PYGAME_OK or not text:
        if on_done:
            on_done()
        return

    def do():
        # 1. Memorija
        data = _mem_get(text)

        # 2. Disk
        if not data:
            data = _disk_load(text)
            if data:
                _mem_put(text, data)

        # 3. API
        if not data:
            data = _fetch_wav(text)
            if data:
                _disk_save(text, data)
                _mem_put(text, data)

        if not data:
            if on_done:
                on_done()
            return

        try:
            with _play_lock:
                buf = io.BytesIO(data)
                pygame.mixer.music.load(buf)
                pygame.mixer.music.play()
                # Wait for audio to finish, then call on_done
                if on_done:
                    while pygame.mixer.music.get_busy():
                        _time.sleep(0.05)
        except Exception as e:
            logger.debug(f"pygame play error: {e}")

        if on_done:
            try:
                on_done()
            except Exception:
                pass

    threading.Thread(target=do, daemon=True).start()


def stop() -> None:
    if PYGAME_OK:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass


def clear_user_cache(username: str) -> None:
    """Briše sve audio fajlove za korisnika (za debug/reset)."""
    import shutil
    d = AUDIO_DIR / validate_username(username)
    if d.exists():
        shutil.rmtree(d)