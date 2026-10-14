from .models import Word, Mistake, UserProfile, SessionStats, RANKS, ACHIEVEMENTS, ACHIEVEMENT_MAP, get_rank, get_next_rank
from .database import Database
from .adaptive import sm2_update, softmax_sample, WeaknessDetector, compute_level, xp_for_level, compute_arena_points
from .ai_client import gemini
from .achievements import check_achievements
from .audio import (play as play_audio, preload as preload_audio,
                    preload_all as preload_all_audio,
                    set_audio_enabled, is_enabled as is_audio_enabled,
                    set_user as set_audio_user, has_cached as audio_has_cached)
from .leaderboard import Leaderboard
from .sounds import play as play_sound, set_enabled as set_sound_enabled, preload_all as preload_sounds