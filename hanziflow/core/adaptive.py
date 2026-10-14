"""
core/adaptive.py — Adaptivni learning engine.

SM-2 + probabilistički model + multi-faktor težina (brzina + tačnost + istorija).
"""
from __future__ import annotations
import math, random
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Word, UserProfile

try:
    from ..xp_config import (
        xp_for_level, compute_level, compute_arena_points as _cfg_arena_pts
    )
    _XP_CONFIG_LOADED = True
except ImportError:
    _XP_CONFIG_LOADED = False

EASE_MIN   = 1.3
EASE_START = 2.5
INTERVALS  = [0, 1, 6]
PERFORMANCE_WINDOW = 20

# ─── SM-2 update ──────────────────────────────────────────────────────────────

def sm2_update(word: "Word", quality: int, response_time: float = 5.0) -> "Word":
    """
    SM-2 sa bonus/malus za brzinu odgovora.
    quality 0-5. response_time u sekundama.
    """
    word.total_seen += 1

    # Ažuriraj prosečno vreme odgovora (exponential moving average)
    alpha = 0.3
    word.avg_response_time = (
        alpha * response_time + (1 - alpha) * word.avg_response_time
        if word.avg_response_time > 0 else response_time
    )

    if quality >= 3:
        word.total_correct += 1
        word.consecutive_wrong = 0
    else:
        word.consecutive_wrong += 1

    word.ease = max(EASE_MIN,
                    word.ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))

    if quality < 3:
        word.step = 0
        word.interval = 0
    elif word.step == 0:
        word.interval = INTERVALS[1]; word.step = 1
    elif word.step == 1:
        word.interval = INTERVALS[2]; word.step = 2
    else:
        word.interval = max(1, round(word.interval * word.ease))
        word.step += 1

    word.next_review = (date.today() + timedelta(days=word.interval)).isoformat()
    return word


# ─── Arena scoring ────────────────────────────────────────────────────────────

def compute_arena_points(correct: bool, response_time: float, combo: int,
                         word_xp: int = 15) -> int:
    if _XP_CONFIG_LOADED:
        return _cfg_arena_pts(correct, response_time, combo, word_xp)
    if not correct:
        return 0
    base       = word_xp
    time_bonus = max(0, int((10.0 - min(response_time, 10.0)) * 5))
    combo_mult = 1.0 + (min(combo, 20) * 0.15)
    return max(1, round((base + time_bonus) * combo_mult))


# ─── Probabilistički odabir ───────────────────────────────────────────────────

def compute_urgency(word: "Word") -> float:
    try:
        overdue = max(0, (date.today() - date.fromisoformat(word.next_review)).days)
    except ValueError:
        overdue = 0
    return (
        math.log1p(overdue) * 3.0 +
        (1.0 - word.accuracy) * 4.0 +
        word.consecutive_wrong * 2.0 +
        max(0, (3 - word.step)) * 1.5 +
        0.1
    )


def softmax_sample(words: list["Word"], n: int) -> list["Word"]:
    if not words: return []
    n = min(n, len(words))
    urgencies = [compute_urgency(w) for w in words]
    exps  = [math.exp(u / 1.5) for u in urgencies]
    total = sum(exps)
    probs = [e / total for e in exps]

    chosen, result = set(), []
    for _ in range(n * 3):
        if len(result) >= n: break
        idx = random.choices(range(len(words)), weights=probs, k=1)[0]
        if idx not in chosen:
            chosen.add(idx); result.append(words[idx])

    remaining = [w for i, w in enumerate(words) if i not in chosen]
    while len(result) < n and remaining:
        result.append(remaining.pop(0))
    return result


# ─── WeaknessDetector ────────────────────────────────────────────────────────

class WeaknessDetector:
    def __init__(self, profile: "UserProfile"):
        self.profile = profile
        self.words   = profile.get_words()

    def weak_words(self, threshold: float = 0.5) -> list["Word"]:
        return sorted(
            [w for w in self.words if w.total_seen >= 3 and w.accuracy < threshold],
            key=lambda w: w.accuracy
        )

    def should_suggest_practice(self) -> bool:
        m = self.profile.get_mistakes()
        return len(m["words"]) + len(m["sentences"]) >= 5 or len(self.weak_words()) >= 3

    def recommended_mode_weights(self) -> dict[str, int]:
        window  = self.profile.performance_window[-PERFORMANCE_WINDOW:]
        avg_acc = sum(window) / len(window) if window else 0.5
        avg_spd = (sum(self.profile.response_times[-10:]) /
                   len(self.profile.response_times[-10:])
                   if self.profile.response_times else 5.0)

        # Brz i tačan → više izazovnih modova
        # Spor i netačan → više kucanja (osnova)
        if avg_acc < 0.4:
            return {"type": 5, "draw": 1, "listen": 1, "meaning": 3}
        elif avg_acc < 0.6 or avg_spd > 8:
            return {"type": 4, "draw": 2, "listen": 2, "meaning": 2}
        elif avg_acc < 0.8:
            return {"type": 3, "draw": 2, "listen": 3, "meaning": 2}
        else:
            return {"type": 2, "draw": 3, "listen": 3, "meaning": 2}

    def difficulty_label(self) -> str:
        window = self.profile.performance_window[-10:]
        avg = sum(window) / len(window) if window else 0.5
        if avg < 0.4:    return "🔴 Hard"
        elif avg < 0.65: return "🟡 Medium"
        else:            return "🟢 Easy"

    def ai_difficulty_prompt(self) -> str:
        """Generiše performance string za Gemini grammar prompt."""
        window  = self.profile.performance_window[-10:]
        avg_acc = sum(window) / len(window) if window else 0.5
        avg_spd = (sum(self.profile.response_times[-5:]) /
                   len(self.profile.response_times[-5:])
                   if self.profile.response_times else 5.0)
        mistakes_count = (len(self.profile.mistakes.get("words", [])) +
                          len(self.profile.mistakes.get("sentences", [])))

        if avg_acc >= 0.85 and avg_spd < 4:
            diff = "very high — user is performing excellently, use complex grammar and rare words"
        elif avg_acc >= 0.7:
            diff = "high — user is doing well, use moderate difficulty"
        elif avg_acc >= 0.5:
            diff = "medium — user struggles occasionally, keep it balanced"
        else:
            diff = f"low — user makes many mistakes ({mistakes_count} pending), use simple short sentences"

        return f"Performance: accuracy={avg_acc:.0%}, avg_response={avg_spd:.1f}s. Difficulty: {diff}."

    def record_answer(self, correct: bool, response_time: float = 5.0) -> None:
        self.profile.performance_window.append(1.0 if correct else 0.0)
        self.profile.response_times.append(response_time)
        if len(self.profile.performance_window) > PERFORMANCE_WINDOW * 2:
            self.profile.performance_window = self.profile.performance_window[-PERFORMANCE_WINDOW:]
        if len(self.profile.response_times) > 50:
            self.profile.response_times = self.profile.response_times[-50:]


XP_BASE  = 200
XP_SCALE = 1.35

if not _XP_CONFIG_LOADED:
    def xp_for_level(lvl: int) -> int:
        return round(XP_BASE * (XP_SCALE ** (lvl - 1)))

    def compute_level(total_xp: int) -> tuple[int, int, int]:
        lvl, remaining = 1, total_xp
        while True:
            needed = xp_for_level(lvl)
            if remaining < needed:
                return lvl, remaining, needed
            remaining -= needed
            lvl += 1