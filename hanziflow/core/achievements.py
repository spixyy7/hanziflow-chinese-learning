"""
core/achievements.py — Achievement engine v2.
Novo: 40+ achievements, hidden achievements, Gemini personalizovani achievements.
"""
from __future__ import annotations
import threading, logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import UserProfile

from .models import ACHIEVEMENT_MAP, ACHIEVEMENTS

logger = logging.getLogger("HanziFlow.Achievements")


def check_achievements(profile: "UserProfile", event: str = "", **kwargs) -> list[dict]:
    """
    Proverava sve uslove i vraća listu novih achievements.
    Automatski pokreće Gemini hidden achievement check u pozadini
    ako je prošlo dovoljno vremena od poslednjeg.
    """
    new_unlocked = []

    def unlock(aid: str):
        if not profile.has_achievement(aid) and aid in ACHIEVEMENT_MAP:
            profile.achievements.append(aid)
            ach = ACHIEVEMENT_MAP[aid]
            profile.xp += ach.get("xp", 0)
            new_unlocked.append(ach)

    # ── Vocabulary ────────────────────────────────────────────────────────────
    vocab_count = len(profile.vocab)
    if vocab_count >= 1:   unlock("first_word")
    if vocab_count >= 5:   unlock("five_words")
    if vocab_count >= 10:  unlock("ten_words")
    if vocab_count >= 25:  unlock("twenty_five_words")
    if vocab_count >= 50:  unlock("fifty_words")
    if vocab_count >= 100: unlock("hundred_words")
    if vocab_count >= 200: unlock("two_hundred_words")

    # ── Quiz answers ──────────────────────────────────────────────────────────
    if profile.total_correct >= 1:    unlock("first_correct")
    if profile.total_correct >= 10:   unlock("correct_10")
    if profile.total_correct >= 50:   unlock("correct_50")
    if profile.total_correct >= 100:  unlock("correct_100")
    if profile.total_correct >= 500:  unlock("correct_500")
    if profile.total_correct >= 1000: unlock("correct_1000")

    # ── Streak ────────────────────────────────────────────────────────────────
    if profile.streak >= 3:  unlock("streak_3")
    if profile.streak >= 7:  unlock("streak_7")
    if profile.streak >= 14: unlock("streak_14")
    if profile.streak >= 30: unlock("streak_30")
    if profile.streak >= 60: unlock("streak_60")
    if profile.streak >= 100:unlock("streak_100")

    # ── Levels ────────────────────────────────────────────────────────────────
    if profile.level >= 5:   unlock("level_5")
    if profile.level >= 10:  unlock("level_10")
    if profile.level >= 20:  unlock("level_20")
    if profile.level >= 30:  unlock("level_30")

    # ── Arena ─────────────────────────────────────────────────────────────────
    if profile.arena_score >= 100:  unlock("arena_100")
    if profile.arena_score >= 500:  unlock("arena_500")
    if profile.arena_score >= 1000: unlock("arena_1000")
    if profile.arena_score >= 5000: unlock("arena_5000")

    # ── Grammar ───────────────────────────────────────────────────────────────
    if profile.grammar_completed >= 1:  unlock("first_sentence")
    if profile.grammar_completed >= 10: unlock("grammar_master")
    if profile.grammar_completed >= 50: unlock("grammar_legend")

    # ── Event-based ───────────────────────────────────────────────────────────
    if event == "rank_up":
        unlock("rank_up")

    if event == "session_done":
        stats = kwargs.get("stats")
        if stats and stats.total > 0 and stats.correct == stats.total:
            unlock("perfect_round")
        if stats and stats.total >= 20:
            unlock("marathon")

    if event == "answer":
        rt = kwargs.get("response_time", 999)
        if rt < 2.0:  unlock("speed_demon")
        if rt < 1.0:  unlock("lightning")

    if event == "arena_combo":
        combo = kwargs.get("combo", 0)
        if combo >= 5:  unlock("combo_5")
        if combo >= 10: unlock("combo_10")
        if combo >= 20: unlock("combo_20")

    if event == "daily_goal":
        unlock("daily_goal")
        # Check if 7 days of goals met
        completed = getattr(profile, "completed_days", [])
        if len(completed) >= 7:  unlock("goal_week")
        if len(completed) >= 30: unlock("goal_month")

    if event == "speaking":
        score = kwargs.get("score", 0)
        if score >= 75:  unlock("speaking_ok")
        if score >= 90:  unlock("speaking_pro")
        if score >= 99:  unlock("speaking_perfect")

    if event == "mistakes_cleared":
        unlock("no_mistakes")

    if event == "night_session":
        unlock("night_owl")

    if event == "early_session":
        unlock("early_bird")

    # ── Hidden: check time-based events ──────────────────────────────────────
    _check_hidden(profile, unlock, event, kwargs)

    # ── Trigger Gemini hidden achievement check (async, non-blocking) ─────────
    _maybe_trigger_gemini_achievements(profile)

    return new_unlocked


def _check_hidden(profile, unlock_fn, event, kwargs):
    """Hidden achievements — desc anonimizovano do otključavanja."""
    from datetime import datetime

    hour = datetime.now().hour
    if hour >= 23 or hour < 4:
        unlock_fn("night_owl")
    if hour >= 5 and hour <= 7:
        unlock_fn("early_bird")

    # Accuracy perfectionist (sve tačno u 10+ sesijama uzastopno)
    perf = getattr(profile, "performance_window", [])
    if len(perf) >= 10 and all(p >= 1.0 for p in perf[-10:]):
        unlock_fn("perfectionist")

    # First week — korisnik je aktivan 7 dana od prvog dana
    if profile.streak >= 7 and profile.total_correct > 0:
        unlock_fn("week_one_done")

    # Polyglot check — ima i srpska i engleska značenja naučena (lang switched)
    if len(profile.vocab) >= 10 and profile.lang in ("en", "sr"):
        unlock_fn("bilingual_learner")

    # Grind — odgovoreno 100 pitanja u jednom danu (daily_xp > 500)
    if getattr(profile, "daily_xp", 0) >= 500:
        unlock_fn("grinder")


def _maybe_trigger_gemini_achievements(profile: "UserProfile"):
    """
    Poziva Gemini API u pozadini (ne blokira UI) da generiše
    personalizovane hidden achievements na osnovu profila.
    Radi max jednom na 24h.
    """
    from datetime import date
    today = date.today().isoformat()
    last = getattr(profile, "last_gemini_achievement_check", "")
    if last == today:
        return  # već proverili danas

    def _run():
        try:
            from . import gemini as _gemini
            ach = _gemini.generate_personal_achievements(profile)
            if ach:
                profile.last_gemini_achievement_check = today
                # Sauvaj u profilu privremeno, biće provereni sledećom sesijom
                existing = getattr(profile, "gemini_achievements_pending", [])
                existing.extend(ach)
                profile.gemini_achievements_pending = existing
                logger.info(f"Gemini generated {len(ach)} personal achievements")
        except Exception as e:
            logger.debug(f"Gemini achievement check skipped: {e}")

    threading.Thread(target=_run, daemon=True).start()


def apply_pending_gemini_achievements(profile: "UserProfile") -> list[dict]:
    """
    Primeni Gemini-generisane achievements iz pending liste.
    Poziva se pri loginu ili početku sesije.
    """
    pending = getattr(profile, "gemini_achievements_pending", [])
    if not pending:
        return []

    new_unlocked = []
    for ach in pending:
        aid = ach.get("id", "")
        if aid and aid not in profile.achievements:
            profile.achievements.append(aid)
            profile.xp += ach.get("xp", 0)
            # Dodaj u ACHIEVEMENT_MAP dinamički
            ACHIEVEMENT_MAP[aid] = ach
            if ach not in ACHIEVEMENTS:
                ACHIEVEMENTS.append(ach)
            new_unlocked.append(ach)

    profile.gemini_achievements_pending = []
    return new_unlocked