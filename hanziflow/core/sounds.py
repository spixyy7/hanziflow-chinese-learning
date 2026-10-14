"""
core/sounds.py — UI zvukovi generisani proceduralno.

Bez eksternih fajlova — sve se generiše matematički u memoriji.
Koristi numpy + pygame za instant playback.

Zvukovi:
  - click      : kratki "tick" klik
  - correct    : pozitivni "ding" (uzlazni ton)
  - wrong      : negativni "buzz" (silazni ton)
  - level_up   : pobednička fanfara
  - xp_gain    : brzi "pop"
  - achievement: zadovoljavajući "reward chime"
  - hover      : tihi "swish" (opciono)
"""
from __future__ import annotations
import io, logging, math, struct, threading, wave
from typing import Optional

logger = logging.getLogger("HanziFlow.Sound")

try:
    import pygame
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False
    logger.warning("pygame not available — UI sounds disabled")

try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

_enabled = [True]
_SAMPLE_RATE = 22050


def set_enabled(v: bool) -> None:
    _enabled[0] = v

def is_enabled() -> bool:
    return _enabled[0]


# ── Waveform generators ───────────────────────────────────────────────────────

def _sine(freq: float, duration: float, volume: float = 0.4,
          sample_rate: int = _SAMPLE_RATE) -> bytes:
    n = int(sample_rate * duration)
    if NUMPY_OK:
        t   = np.linspace(0, duration, n, False)
        wave_data = np.sin(2 * np.pi * freq * t) * volume
        # Fade in/out to prevent clicks
        fade = min(200, n // 4)
        wave_data[:fade]  *= np.linspace(0, 1, fade)
        wave_data[-fade:] *= np.linspace(1, 0, fade)
        samples = (wave_data * 32767).astype(np.int16)
        return samples.tobytes()
    else:
        # Pure Python fallback
        samples = []
        for i in range(n):
            t = i / sample_rate
            v = math.sin(2 * math.pi * freq * t) * volume
            fade_in  = min(1.0, i / max(200, 1))
            fade_out = min(1.0, (n - i) / max(200, 1))
            v *= fade_in * fade_out
            samples.append(int(v * 32767))
        return struct.pack(f"<{n}h", *samples)


def _tone_sequence(freqs_durs: list[tuple[float, float]],
                   volume: float = 0.4) -> bytes:
    """Spoji više tonova u sekvencu."""
    parts = [_sine(f, d, volume) for f, d in freqs_durs]
    return b"".join(parts)


def _make_wav(pcm: bytes, sample_rate: int = _SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _decay(freq: float, duration: float, volume: float = 0.4,
           decay_power: float = 3.0) -> bytes:
    """Ton koji se gasi eksponencijalno (kao zvono)."""
    n = int(_SAMPLE_RATE * duration)
    if NUMPY_OK:
        t   = np.linspace(0, duration, n, False)
        env = np.exp(-decay_power * t / duration)
        wave_data = np.sin(2 * np.pi * freq * t) * env * volume
        samples = (wave_data * 32767).astype(np.int16)
        return samples.tobytes()
    else:
        samples = []
        for i in range(n):
            t   = i / _SAMPLE_RATE
            env = math.exp(-decay_power * t / duration)
            v   = math.sin(2 * math.pi * freq * t) * env * volume
            samples.append(int(v * 32767))
        return struct.pack(f"<{n}h", *samples)


# ── Sound definitions ─────────────────────────────────────────────────────────

def _build_click() -> bytes:
    # Kratki klik: brzi visoki ton
    return _make_wav(_sine(800, 0.05, 0.25))


def _build_hover() -> bytes:
    # Tihi swish
    return _make_wav(_sine(600, 0.03, 0.12))


def _build_correct() -> bytes:
    # Uzlazna dva tona — "ding ding"
    pcm = _tone_sequence([(523, 0.08), (659, 0.08), (784, 0.15)], volume=0.4)
    return _make_wav(pcm)


def _build_wrong() -> bytes:
    # Silazni ton — "buzz"
    pcm = _tone_sequence([(300, 0.12), (220, 0.18)], volume=0.35)
    return _make_wav(pcm)


def _build_xp_gain() -> bytes:
    # Brzi "pop" — uzlazni
    pcm = _tone_sequence([(440, 0.04), (550, 0.08)], volume=0.3)
    return _make_wav(pcm)


def _build_level_up() -> bytes:
    # Epska fanfara — rastuća sa harmonicima i crescendom
    n = int(_SAMPLE_RATE * 1.2)
    if NUMPY_OK:
        t = np.linspace(0, 1.2, n, False)
        # Melodija: C4 E4 G4 C5 — pobjednički akord
        freqs = [(262, 0.0), (330, 0.18), (392, 0.36), (523, 0.54), (659, 0.72), (1047, 0.90)]
        wave_data = np.zeros(n)
        for freq, start in freqs:
            start_i = int(start * _SAMPLE_RATE)
            seg_len = n - start_i
            if seg_len <= 0:
                continue
            seg_t = np.linspace(0, (n - start_i) / _SAMPLE_RATE, seg_len, False)
            seg = (np.sin(2 * np.pi * freq * seg_t) * 0.35 +
                   np.sin(2 * np.pi * freq * 2 * seg_t) * 0.15)
            env = np.exp(-2.5 * seg_t)
            wave_data[start_i:] += seg * env
        # Crescendo fade-in na početku
        fade = min(800, n // 4)
        wave_data[:fade] *= np.linspace(0, 1, fade)
        # Normalizuj
        mx = np.max(np.abs(wave_data))
        if mx > 0:
            wave_data = wave_data / mx * 0.7
        samples = (wave_data * 32767).astype(np.int16)
        pcm = samples.tobytes()
    else:
        notes = [(262,0.1),(330,0.1),(392,0.1),(523,0.1),(659,0.1),(1047,0.4)]
        pcm = _tone_sequence(notes, volume=0.5)
    return _make_wav(pcm)


def _build_achievement() -> bytes:
    # Reward chime — bogat zvuk sa harmonicima
    n = int(_SAMPLE_RATE * 0.8)
    if NUMPY_OK:
        t = np.linspace(0, 0.8, n, False)
        # Tri harmonika = bogatiji zvuk
        wave_data = (
            np.sin(2 * np.pi * 659 * t) * 0.4 +
            np.sin(2 * np.pi * 880 * t) * 0.25 +
            np.sin(2 * np.pi * 1047 * t) * 0.15
        )
        env = np.exp(-3.5 * t / 0.8)
        wave_data *= env
        # Fade in
        fade = min(400, n // 4)
        wave_data[:fade] *= np.linspace(0, 1, fade)
        samples = (wave_data * 32767).astype(np.int16)
        pcm = samples.tobytes()
    else:
        pcm = _decay(659, 0.8, volume=0.5)
    return _make_wav(pcm)


def _build_streak() -> bytes:
    # Streak sound — crescendo
    notes = [(440, 0.06), (494, 0.06), (523, 0.06), (587, 0.06), (659, 0.20)]
    return _make_wav(_tone_sequence(notes, volume=0.38))


def _build_coach() -> bytes:
    """Coach notification — kratak, moderan, privlači pažnju bez ometanja."""
    n = int(_SAMPLE_RATE * 0.35)
    if NUMPY_OK:
        t = np.linspace(0, 0.35, n, False)
        wave_data = (
            np.sin(2 * np.pi * 740 * t) * 0.35 +
            np.sin(2 * np.pi * 1109 * t) * 0.2
        )
        env = np.exp(-5 * t / 0.35)
        wave_data *= env
        fade = min(200, n // 6)
        wave_data[:fade] *= np.linspace(0, 1, fade)
        samples = (wave_data * 32767).astype(np.int16)
        pcm = samples.tobytes()
    else:
        pcm = _decay(740, 0.35, volume=0.4)
    return _make_wav(pcm)


# ── Cache ─────────────────────────────────────────────────────────────────────

_SOUNDS: dict[str, bytes] = {}
_LOCK = threading.Lock()
_sound_channel: Optional[object] = None


def _get_sound(name: str) -> Optional[bytes]:
    if name not in _SOUNDS:
        builders = {
            "click":       _build_click,
            "hover":       _build_hover,
            "correct":     _build_correct,
            "wrong":       _build_wrong,
            "xp_gain":     _build_xp_gain,
            "level_up":    _build_level_up,
            "achievement": _build_achievement,
            "streak":      _build_streak,
            "coach":       _build_coach,
        }
        builder = builders.get(name)
        if builder:
            _SOUNDS[name] = builder()
    return _SOUNDS.get(name)


# ── Playback ──────────────────────────────────────────────────────────────────

def _init_pygame():
    global _sound_channel
    if not PYGAME_OK: return
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=_SAMPLE_RATE, size=-16, channels=1, buffer=256)
        if _sound_channel is None:
            pygame.mixer.set_num_channels(8)
            _sound_channel = pygame.mixer.Channel(7)  # Dedicated channel for UI sounds
    except Exception as e:
        logger.debug(f"Sound init: {e}")


def play(name: str) -> None:
    """Pušta UI zvuk. Non-blocking, instant."""
    if not _enabled[0] or not PYGAME_OK:
        return

    def do():
        try:
            _init_pygame()
            wav = _get_sound(name)
            if not wav:
                return
            buf   = io.BytesIO(wav)
            sound = pygame.mixer.Sound(buf)
            if _sound_channel:
                _sound_channel.play(sound)
            else:
                sound.play()
        except Exception as e:
            logger.debug(f"Sound play '{name}': {e}")

    threading.Thread(target=do, daemon=True).start()


def preload_all() -> None:
    """Pregeneriši sve zvukove unapred (pozovi pri startu)."""
    for name in ["click", "correct", "wrong", "xp_gain",
                 "level_up", "achievement", "streak"]:
        _get_sound(name)