"""
core/models.py — Data classes v2.
Novo: 40+ achievements (hidden + Gemini), novi profile atributi.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional
import hashlib, secrets, hmac


# ─── Rank sistem (Arena) ──────────────────────────────────────────────────────

RANKS = [
    {"name": "Word Rookie",     "min_score": 0,     "color": "#CD7F32", "icon": "🥉"},
    {"name": "Stroke Student",  "min_score": 500,   "color": "#A8A9AD", "icon": "⚔️"},
    {"name": "Hanzi Hunter",    "min_score": 1500,  "color": "#FFD700", "icon": "🥇"},
    {"name": "Sentence Master", "min_score": 4000,  "color": "#50C8FF", "icon": "💠"},
    {"name": "Fluency King",    "min_score": 10000, "color": "#B44FE8", "icon": "👑"},
    {"name": "Dragon Scholar",  "min_score": 25000, "color": "#FF4F4F", "icon": "🐉"},
]


def get_rank(arena_score: int) -> dict:
    r = RANKS[0]
    for rank in RANKS:
        if arena_score >= rank["min_score"]:
            r = rank
    return r


def get_next_rank(arena_score: int) -> Optional[dict]:
    for rank in RANKS:
        if arena_score < rank["min_score"]:
            return rank
    return None


# ─── Achievements — 40+ (uključuje hidden) ────────────────────────────────────

ACHIEVEMENTS = [
    # ── Vocabulary ────────────────────────────────────────────────────────────
    {"id": "first_word",       "name": "First Steps",         "desc": "Add your first word",               "icon": "📖",  "xp": 20,  "hidden": False},
    {"id": "five_words",       "name": "Word Hoarder",        "desc": "Add 5 words",                       "icon": "📚",  "xp": 25,  "hidden": False},
    {"id": "ten_words",        "name": "Vocabulary Builder",  "desc": "Add 10 words",                      "icon": "📚",  "xp": 50,  "hidden": False},
    {"id": "twenty_five_words","name": "Growing Lexicon",     "desc": "Add 25 words",                      "icon": "🗂️",  "xp": 80,  "hidden": False},
    {"id": "fifty_words",      "name": "Word Enthusiast",     "desc": "Add 50 words",                      "icon": "📦",  "xp": 120, "hidden": False},
    {"id": "hundred_words",    "name": "Word Collector",      "desc": "Add 100 words",                     "icon": "🗂️",  "xp": 200, "hidden": False},
    {"id": "two_hundred_words","name": "Dictionary Mode",     "desc": "Add 200 words",                     "icon": "📕",  "xp": 400, "hidden": False},

    # ── Correct answers ───────────────────────────────────────────────────────
    {"id": "first_correct",    "name": "First Win",           "desc": "Answer correctly for the first time","icon": "✅",  "xp": 10,  "hidden": False},
    {"id": "correct_10",       "name": "On a Roll",           "desc": "10 correct answers",                "icon": "🎯",  "xp": 30,  "hidden": False},
    {"id": "correct_50",       "name": "Half Century",        "desc": "50 correct answers",                "icon": "🏅",  "xp": 60,  "hidden": False},
    {"id": "correct_100",      "name": "Century",             "desc": "100 correct answers",               "icon": "💯",  "xp": 100, "hidden": False},
    {"id": "correct_500",      "name": "Answer Machine",      "desc": "500 correct answers",               "icon": "🤖",  "xp": 250, "hidden": False},
    {"id": "correct_1000",     "name": "Master of Answers",   "desc": "1000 correct answers",              "icon": "👑",  "xp": 500, "hidden": False},

    # ── Streak ────────────────────────────────────────────────────────────────
    {"id": "streak_3",         "name": "Hat Trick",           "desc": "3-day streak",                      "icon": "🔥",  "xp": 30,  "hidden": False},
    {"id": "streak_7",         "name": "Week Warrior",        "desc": "7-day streak",                      "icon": "⚡",  "xp": 100, "hidden": False},
    {"id": "streak_14",        "name": "Two Weeks Strong",    "desc": "14-day streak",                     "icon": "💪",  "xp": 200, "hidden": False},
    {"id": "streak_30",        "name": "Monthly Master",      "desc": "30-day streak",                     "icon": "🏆",  "xp": 500, "hidden": False},
    {"id": "streak_60",        "name": "Iron Will",           "desc": "60-day streak",                     "icon": "🛡️",  "xp": 800, "hidden": False},
    {"id": "streak_100",       "name": "Centurion",           "desc": "100-day streak",                    "icon": "🌟",  "xp": 1500,"hidden": False},

    # ── Levels ────────────────────────────────────────────────────────────────
    {"id": "level_5",          "name": "Rising Star",         "desc": "Reach level 5",                     "icon": "⭐",  "xp": 50,  "hidden": False},
    {"id": "level_10",         "name": "Dedicated Learner",   "desc": "Reach level 10",                    "icon": "🌟",  "xp": 150, "hidden": False},
    {"id": "level_20",         "name": "Seasoned Student",    "desc": "Reach level 20",                    "icon": "🎓",  "xp": 300, "hidden": False},
    {"id": "level_30",         "name": "Scholar",             "desc": "Reach level 30",                    "icon": "🏛️",  "xp": 500, "hidden": False},

    # ── Session quality ───────────────────────────────────────────────────────
    {"id": "perfect_round",    "name": "Perfect Round",       "desc": "100% accuracy in a session",        "icon": "⭐",  "xp": 75,  "hidden": False},
    {"id": "marathon",         "name": "Marathon",            "desc": "Complete a 20-question session",    "icon": "🏃",  "xp": 60,  "hidden": False},
    {"id": "speed_demon",      "name": "Speed Demon",         "desc": "Answer in under 2 seconds",         "icon": "⚡",  "xp": 25,  "hidden": False},
    {"id": "lightning",        "name": "Lightning Bolt",      "desc": "Answer in under 1 second",          "icon": "⚡",  "xp": 50,  "hidden": True},

    # ── Arena ─────────────────────────────────────────────────────────────────
    {"id": "arena_100",        "name": "Arena Rookie",        "desc": "Score 100+ in Word Arena",          "icon": "🏟️",  "xp": 20,  "hidden": False},
    {"id": "arena_500",        "name": "Arena Victor",        "desc": "Score 500+ in Word Arena",          "icon": "🏟️",  "xp": 50,  "hidden": False},
    {"id": "arena_1000",       "name": "Arena Champion",      "desc": "Score 1000+ in Word Arena",         "icon": "🥇",  "xp": 120, "hidden": False},
    {"id": "arena_5000",       "name": "Arena Legend",        "desc": "Score 5000+ in Word Arena",         "icon": "🐉",  "xp": 500, "hidden": False},
    {"id": "combo_5",          "name": "Combo King",          "desc": "5x combo in Word Arena",            "icon": "🔥",  "xp": 40,  "hidden": False},
    {"id": "combo_10",         "name": "Combo Master",        "desc": "10x combo in Word Arena",           "icon": "🔥",  "xp": 80,  "hidden": False},
    {"id": "combo_20",         "name": "Unstoppable",         "desc": "20x combo in Word Arena",           "icon": "💥",  "xp": 200, "hidden": True},

    # ── Grammar / Speaking ────────────────────────────────────────────────────
    {"id": "first_sentence",   "name": "Sentence Builder",    "desc": "Complete your first sentence",      "icon": "📝",  "xp": 20,  "hidden": False},
    {"id": "grammar_master",   "name": "Grammar Master",      "desc": "Complete 10 sentence builders",     "icon": "📝",  "xp": 80,  "hidden": False},
    {"id": "grammar_legend",   "name": "Grammar Legend",      "desc": "Complete 50 sentence builders",     "icon": "📜",  "xp": 250, "hidden": False},
    {"id": "speaking_ok",      "name": "Good Pronunciation",  "desc": "Score 75+ in speaking",             "icon": "🎤",  "xp": 30,  "hidden": False},
    {"id": "speaking_pro",     "name": "Pronunciation Pro",   "desc": "Score 90+ in speaking",             "icon": "🎤",  "xp": 75,  "hidden": False},
    {"id": "speaking_perfect", "name": "Native Speaker",      "desc": "Score 99+ in speaking",             "icon": "🏆",  "xp": 200, "hidden": True},

    # ── Goal / Daily ──────────────────────────────────────────────────────────
    {"id": "daily_goal",       "name": "Goal Getter",         "desc": "Complete daily goal",               "icon": "🎯",  "xp": 30,  "hidden": False},
    {"id": "goal_week",        "name": "Week Achiever",       "desc": "Complete daily goal 7 times",       "icon": "📅",  "xp": 100, "hidden": False},
    {"id": "goal_month",       "name": "Monthly Achiever",    "desc": "Complete daily goal 30 times",      "icon": "🗓️",  "xp": 300, "hidden": False},

    # ── Rank / Other ──────────────────────────────────────────────────────────
    {"id": "rank_up",          "name": "Rank Up!",            "desc": "Achieve a new rank",                "icon": "📈",  "xp": 60,  "hidden": False},
    {"id": "no_mistakes",      "name": "Clean Slate",         "desc": "Clear all mistakes",                "icon": "🧹",  "xp": 50,  "hidden": False},
    {"id": "bilingual_learner","name": "Bilingual Learner",   "desc": "Use the app in both languages",     "icon": "🌐",  "xp": 40,  "hidden": False},

    # ── Hidden achievements ───────────────────────────────────────────────────
    {"id": "night_owl",        "name": "Night Owl",           "desc": "Study after midnight",              "icon": "🦉",  "xp": 30,  "hidden": True},
    {"id": "early_bird",       "name": "Early Bird",          "desc": "Study before 7am",                  "icon": "🌅",  "xp": 30,  "hidden": True},
    {"id": "perfectionist",    "name": "Perfectionist",       "desc": "???",                               "icon": "💎",  "xp": 150, "hidden": True},
    {"id": "week_one_done",    "name": "First Week!",         "desc": "???",                               "icon": "🎉",  "xp": 75,  "hidden": True},
    {"id": "grinder",          "name": "Grinder",             "desc": "???",                               "icon": "⚙️",  "xp": 60,  "hidden": True},
]

ACHIEVEMENT_MAP = {a["id"]: a for a in ACHIEVEMENTS}


# ─── Word ─────────────────────────────────────────────────────────────────────

@dataclass
class Word:
    hanzi:      str
    pinyin:     str
    meaning_sr: str
    meaning_en: str
    xp:         int   = 15
    interval:   int   = 0
    step:       int   = 0
    ease:       float = 2.5
    next_review: str  = field(default_factory=lambda: date.today().isoformat())
    total_seen:  int  = 0
    total_correct: int = 0
    consecutive_wrong: int = 0
    avg_response_time: float = 0.0

    @property
    def accuracy(self) -> float:
        return (self.total_correct / self.total_seen) if self.total_seen else 0.0

    @property
    def is_due(self) -> bool:
        return self.next_review <= date.today().isoformat()

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "Word":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─── Mistake ──────────────────────────────────────────────────────────────────

@dataclass
class Mistake:
    type:       str
    hanzi:      str
    pinyin:     str
    meaning_sr: str
    meaning_en: str
    xp:         int = 15
    correct:    str = ""
    scrambled:  str = ""
    count:      int = 1
    last_seen:  str = field(default_factory=lambda: date.today().isoformat())

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "Mistake":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─── UserProfile ──────────────────────────────────────────────────────────────

@dataclass
class UserProfile:
    username:      str
    email:         str
    password_hash: str

    xp:            int  = 0
    level:         int  = 1
    streak:        int  = 0
    daily_xp:      int  = 0
    last_date:     str  = ""
    daily_goal:    int  = 100
    goal_setup_done: bool = False

    completed_days:   list = field(default_factory=list)
    daily_xp_history: dict = field(default_factory=dict)
    last_goal_check:  str  = ""

    vocab:    list = field(default_factory=list)
    mistakes: dict = field(default_factory=lambda: {"words": [], "sentences": []})

    lang: str = "en"

    performance_window:   list = field(default_factory=list)
    response_times:       list = field(default_factory=list)
    preferred_quiz_modes: dict = field(default_factory=lambda: {
        "type": 3, "draw": 2, "listen": 2, "meaning": 2
    })

    arena_score:       int  = 0
    total_correct:     int  = 0
    total_answered:    int  = 0
    grammar_completed: int  = 0
    achievements:      list = field(default_factory=list)
    daily_bonus_claimed: str = ""
    audio_enabled:     bool = True
    theme:             str  = "system"
    longest_streak:      int  = 0
    streak_shields:      int  = 2
    last_shield_earn:    str  = ""
    xp_at_login:         dict = field(default_factory=dict)
    avatar_path:         str  = ""
    banner_path:         str  = ""
    streak_earned_today: str  = ""

    # Visibility settings
    show_rank:         bool = True
    show_nickname:     bool = True

    # Gemini hidden achievement support
    last_gemini_achievement_check: str  = ""
    gemini_achievements_pending:   list = field(default_factory=list)

    @staticmethod
    def hash_password(pw: str, salt: str = "") -> str:
        if len(pw.encode("utf-8")) > 1024:
            raise ValueError("Password is too long.")
        salt = salt or secrets.token_hex(16)
        iterations = 600_000
        digest = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), iterations).hex()
        return f"pbkdf2_sha256${iterations}${salt}${digest}"

    @staticmethod
    def verify_password_hash(pw: str, stored_hash: str) -> bool:
        if not isinstance(stored_hash, str) or len(pw.encode("utf-8")) > 1024:
            return False
        try:
            if stored_hash.startswith("pbkdf2_sha256$"):
                _, rounds, salt, expected = stored_hash.split("$")
                iterations = int(rounds)
                if not 100_000 <= iterations <= 2_000_000 or len(salt) != 32 or len(expected) != 64:
                    return False
                digest = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), iterations).hex()
            elif "$" in stored_hash:
                salt, expected = stored_hash.split("$", 1)
                digest = hashlib.sha256((salt + pw).encode()).hexdigest()
            else:
                expected = stored_hash
                digest = hashlib.sha256(pw.encode()).hexdigest()
            return hmac.compare_digest(digest, expected)
        except (ValueError, TypeError):
            return False

    def get_words(self) -> list[Word]:
        return [Word.from_dict(w) for w in self.vocab]

    def get_mistakes(self) -> dict[str, list[Mistake]]:
        return {
            "words":     [Mistake.from_dict(m) for m in self.mistakes.get("words", [])],
            "sentences": [Mistake.from_dict(m) for m in self.mistakes.get("sentences", [])],
        }

    def get_rank(self) -> dict:
        return get_rank(self.arena_score)

    def get_next_rank(self) -> Optional[dict]:
        return get_next_rank(self.arena_score)

    def has_achievement(self, aid: str) -> bool:
        return aid in self.achievements

    def award_session_streak(self) -> bool:
        """
        Dodjeljuje streak za danas. Pozivati jednom po sesiji (quiz/grammar/speaking/writing/arena...).

        FIX (v2): Više ne koristi last_date kao fallback — last_date se mijenja svaki login
                  i uzrokovao je da streak nikad nije rastao (if last == today: return False).
                  Sada koristi ISKLJUČIVO streak_earned_today za praćenje.
        """
        today = date.today().isoformat()

        # Već nagrađeno danas
        if self.streak_earned_today == today:
            return False

        yesterday   = (date.today() - timedelta(days=1)).isoformat()
        last_earned = self.streak_earned_today  # kada je zadnji put streak dodijeljen

        if not last_earned:
            # Nikad ranije — počinjemo streak
            self.streak = max(self.streak, 0) + 1
        elif last_earned == yesterday:
            # Savršen niz — nastavljamo
            self.streak += 1
        else:
            # Propušten dan(i)
            if self.streak_shields > 0:
                self.streak_shields -= 1
                self.streak += 1   # shield čuva streak I dodaje +1 za danas
            else:
                self.streak = 1    # reset na 1 (današnji dan)

        self.streak_earned_today = today
        if self.streak > self.longest_streak:
            self.longest_streak = self.streak
        return True

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "UserProfile":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─── SessionStats ─────────────────────────────────────────────────────────────

@dataclass
class SessionStats:
    total:      int = 0
    correct:    int = 0
    xp_gained:  int = 0
    start_time: datetime = field(default_factory=datetime.now)
    response_times: list = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return (self.correct / self.total * 100) if self.total else 0.0

    @property
    def avg_response(self) -> float:
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0

    @property
    def duration_seconds(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()