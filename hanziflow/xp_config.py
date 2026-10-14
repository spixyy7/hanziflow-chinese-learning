"""
xp_config.py — Centralna konfiguracija XP sistema za HanziFlow.

Ovde menjaj SVE vezano za XP:
  - Koliko XP dobija korisnik po reči, po modu, po combo-u
  - Brzinski bonusi, streak bonusi, dnevni bonus
  - Formula za levele (koliko XP treba za svaki nivo)
  - Maksimalni XP po danu, maksimalni XP po sesiji
  - Grammar rečenica XP
  - Arena poeni i konverzija u XP
  - Speaking XP na osnovu skora
  - Mistake clearing bonus

Fajl se automatski učitava u adaptive.py i svim view fajlovima.
Ne treba da restartuješ aplikaciju ako koristiš reload — ali jednostavno
zatvoriti i ponovo otvoriti aplikaciju je dovoljno da promene stupe na snagu.
"""
from __future__ import annotations


WORD_XP = dict(
    MIN           = 10,
    MAX           = 50,
    DEFAULT       = 15,
)

QUIZ_XP = dict(
    QUALITY_MULTIPLIER = True,

    QUALITY_5_MULT     = 1.0,
    QUALITY_4_MULT     = 0.8,
    QUALITY_3_MULT     = 0.6,
    QUALITY_2_MULT     = 0.0,
    QUALITY_1_MULT     = 0.0,
    QUALITY_0_MULT     = 0.0,

    SPEED_BONUS_UNDER_2S  = 5,
    SPEED_BONUS_UNDER_5S  = 2,
    SPEED_BONUS_UNDER_10S = 0,
)

GRAMMAR_XP = dict(
    SENTENCE_BASE        = 30,
    SENTENCE_MIN         = 10,
    SENTENCE_MAX         = 80,

    TIME_BONUS_ENABLED   = True,
    TIME_BONUS_PER_10S   = 5,
    TIME_BONUS_MAX       = 30,
)

SPEAKING_XP = dict(
    SCORE_100    = 0,
    SCORE_90_99  = 0,
    SCORE_75_89  = 0,
    SCORE_45_74  = 0,

    USE_WORD_XP       = True,
    SCORE_75_PLUS_MULT= 1.0,
    SCORE_45_74_MULT  = 0.5,
    SCORE_UNDER_45    = 0,
)

ARENA_XP = dict(
    BASE_WORD_XP         = True,

    TIME_BONUS_ENABLED   = True,
    TIME_BONUS_PER_SEC   = 5,
    TIME_BONUS_MAX_SEC   = 10.0,

    COMBO_MULT_ENABLED   = True,
    COMBO_MULT_PER_STEP  = 0.15,
    COMBO_MAX_STEPS      = 20,

    SCORE_TO_XP_DIVISOR  = 10,
    SCORE_TO_XP_MIN      = 10,
)

STREAK_XP = dict(
    ENABLED               = True,

    BONUS_PER_STREAK_DAY  = 5,
    STREAK_BONUS_MAX      = 100,

    STREAK_3_BONUS        = 20,
    STREAK_7_BONUS        = 50,
    STREAK_14_BONUS       = 100,
    STREAK_30_BONUS       = 300,
    STREAK_60_BONUS       = 600,
    STREAK_100_BONUS      = 1500,
)

DAILY_BONUS_XP = dict(
    AMOUNT    = 50,
    ENABLED   = True,
)

MISTAKE_CLEAR_BONUS = dict(
    PER_WORD_CLEARED     = 5,
    PER_SENTENCE_CLEARED = 8,
    CLEAR_ALL_BONUS      = 25,
)

ACHIEVEMENT_XP = dict(
    FIRST_WORD    = 20,
    FIVE_WORDS    = 25,
    TEN_WORDS     = 50,
    TWENTY_FIVE   = 80,
    FIFTY_WORDS   = 120,
    HUNDRED_WORDS = 200,
    TWO_HUNDRED   = 400,

    FIRST_CORRECT = 10,
    CORRECT_10    = 30,
    CORRECT_50    = 60,
    CORRECT_100   = 100,
    CORRECT_500   = 250,
    CORRECT_1000  = 500,

    STREAK_3      = 30,
    STREAK_7      = 100,
    STREAK_14     = 200,
    STREAK_30     = 500,
    STREAK_60     = 800,
    STREAK_100    = 1500,

    PERFECT_ROUND = 75,
    SPEED_DEMON   = 25,
    LIGHTNING     = 50,

    COMBO_5       = 40,
    COMBO_10      = 80,
    COMBO_20      = 200,

    LEVEL_5       = 50,
    LEVEL_10      = 150,
    LEVEL_20      = 300,
    LEVEL_30      = 500,

    RANK_UP       = 60,
    NO_MISTAKES   = 50,
    DAILY_GOAL    = 30,
    GOAL_WEEK     = 100,
    GOAL_MONTH    = 300,

    SPEAKING_OK      = 30,
    SPEAKING_PRO     = 75,
    SPEAKING_PERFECT = 200,

    GRAMMAR_MASTER  = 80,
    GRAMMAR_LEGEND  = 250,
    FIRST_SENTENCE  = 20,

    ARENA_100    = 20,
    ARENA_500    = 50,
    ARENA_1000   = 120,
    ARENA_5000   = 500,

    NIGHT_OWL    = 30,
    EARLY_BIRD   = 30,
    PERFECTIONIST= 150,
    GRINDER      = 60,
    BILINGUAL    = 40,
)

LEVEL_XP = dict(
    BASE          = 200,
    SCALE         = 1.35,

    MAX_LEVEL     = 999,
)

SESSION_XP = dict(
    MAX_PER_SESSION   = 2000,
    MAX_PER_DAY       = 5000,
)


def compute_quiz_xp(word_xp: int, quality: int, response_time: float = 99.0) -> int:
    """
    Izračunava XP za jedan tačan odgovor u kvizu.

    word_xp       — osnovna XP vrednost reči (WORD_XP.DEFAULT ili custom)
    quality       — SM-2 kvalitet (0-5), 0-2 = pogrešno, 3-5 = tačno
    response_time — vreme odgovora u sekundama
    """
    if quality < 3:
        return 0

    mults = {
        5: QUIZ_XP["QUALITY_5_MULT"],
        4: QUIZ_XP["QUALITY_4_MULT"],
        3: QUIZ_XP["QUALITY_3_MULT"],
    }
    mult = mults.get(quality, 0.0)
    base = max(0, round(word_xp * mult))

    speed_bonus = 0
    if response_time < 2.0:
        speed_bonus = QUIZ_XP["SPEED_BONUS_UNDER_2S"]
    elif response_time < 5.0:
        speed_bonus = QUIZ_XP["SPEED_BONUS_UNDER_5S"]
    else:
        speed_bonus = QUIZ_XP["SPEED_BONUS_UNDER_10S"]

    return base + speed_bonus


def compute_grammar_xp(sentence_xp: int, time_left_seconds: int) -> tuple[int, int]:
    """
    Izračunava XP za tačno složenu rečenicu.
    Vraća (base_xp, time_bonus).
    """
    base = max(GRAMMAR_XP["SENTENCE_MIN"],
               min(GRAMMAR_XP["SENTENCE_MAX"], sentence_xp))

    time_bonus = 0
    if GRAMMAR_XP["TIME_BONUS_ENABLED"] and time_left_seconds > 0:
        raw_bonus = (time_left_seconds // 10) * GRAMMAR_XP["TIME_BONUS_PER_10S"]
        time_bonus = min(raw_bonus, GRAMMAR_XP["TIME_BONUS_MAX"])

    return base, time_bonus


def compute_speaking_xp(word_xp: int, score: int) -> int:
    """
    Izračunava XP za speaking vežbu na osnovu skora (0-100).
    """
    if score >= 75:
        return max(1, round(word_xp * SPEAKING_XP["SCORE_75_PLUS_MULT"]))
    elif score >= 45:
        return max(1, round(word_xp * SPEAKING_XP["SCORE_45_74_MULT"]))
    return SPEAKING_XP["SCORE_UNDER_45"]


def compute_arena_points(correct: bool, response_time: float,
                          combo: int, word_xp: int = 15) -> int:
    """
    Izračunava poene za Word Arena.

    Formula:
      base       = word_xp (ako tačno)
      time_bonus = max(0, (MAX_SEC - response_time)) * PER_SEC  (max ~50)
      combo_mult = 1 + (min(combo, MAX_STEPS) * PER_STEP)
      total      = (base + time_bonus) * combo_mult
    """
    if not correct:
        return 0

    base = word_xp

    time_bonus = 0
    if ARENA_XP["TIME_BONUS_ENABLED"]:
        max_sec = ARENA_XP["TIME_BONUS_MAX_SEC"]
        per_sec = ARENA_XP["TIME_BONUS_PER_SEC"]
        time_bonus = max(0, int((max_sec - min(response_time, max_sec)) * per_sec))

    combo_mult = 1.0
    if ARENA_XP["COMBO_MULT_ENABLED"]:
        steps = min(combo, ARENA_XP["COMBO_MAX_STEPS"])
        combo_mult = 1.0 + steps * ARENA_XP["COMBO_MULT_PER_STEP"]

    return max(1, round((base + time_bonus) * combo_mult))


def arena_score_to_xp(arena_score: int) -> int:
    """Konverzija Arena skora u XP na kraju igre."""
    return max(ARENA_XP["SCORE_TO_XP_MIN"],
               arena_score // ARENA_XP["SCORE_TO_XP_DIVISOR"])


def xp_for_level(lvl: int) -> int:
    """Koliko XP treba za prelazak sa lvl na lvl+1."""
    return round(LEVEL_XP["BASE"] * (LEVEL_XP["SCALE"] ** (lvl - 1)))


def compute_level(total_xp: int) -> tuple[int, int, int]:
    """
    Vraća (current_level, xp_in_level, xp_needed_for_next).
    """
    lvl, remaining = 1, total_xp
    while True:
        needed = xp_for_level(lvl)
        if remaining < needed:
            return lvl, remaining, needed
        remaining -= needed
        lvl += 1