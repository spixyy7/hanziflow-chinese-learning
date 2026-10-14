"""
core/database.py — Per-user JSON perzistencija.

Svaki korisnik ima sopstveni fajl: users/{username}.json
Master index: users/_index.json (username → password_hash)
"""
from __future__ import annotations
import json, os, shutil, threading
from datetime import date
from typing import Optional
from .models import UserProfile, Word
from ..config import validate_username

USERS_DIR    = "users"
INDEX_FILE   = os.path.join(USERS_DIR, "_index.json")
SESSION_FILE = "session.json"   # remember me


def _ensure_dir():
    os.makedirs(USERS_DIR, exist_ok=True)


def _user_file(username: str) -> str:
    safe = validate_username(username)
    return os.path.join(USERS_DIR, f"{safe}.json")


class Database:
    """Singleton — per-user fajlovi za potpunu izolaciju podataka."""

    _instance: Optional["Database"] = None
    _init_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "Database":
        if cls._instance is None:
            with cls._init_lock:
                # Dvostruka provjera unutar locka (double-checked locking)
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    _ensure_dir()
                    cls._instance._index: dict = cls._instance._load_index()
        return cls._instance

    # ── Index ─────────────────────────────────────────────────────────────────

    def _load_index(self) -> dict:
        if os.path.exists(INDEX_FILE):
            try:
                with open(INDEX_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_index(self) -> None:
        tmp = INDEX_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)
        shutil.move(tmp, INDEX_FILE)

    # ── User I/O ──────────────────────────────────────────────────────────────

    def user_exists(self, username: str) -> bool:
        return any(name.casefold() == username.casefold() for name in self._index)

    def get_user(self, username: str) -> Optional[UserProfile]:
        path = _user_file(username)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return UserProfile.from_dict(json.load(f))
        except Exception:
            return None

    def save_user(self, profile: UserProfile) -> None:
        _ensure_dir()
        path = _user_file(profile.username)
        tmp  = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
        shutil.move(tmp, path)
        # Ažuriraj index
        self._index[profile.username] = profile.password_hash
        self._save_index()

    def create_user(self, username: str, email: str, password: str) -> UserProfile:
        validate_username(username)
        if self.user_exists(username) or os.path.exists(_user_file(username)):
            raise ValueError("Username is unavailable.")
        profile = UserProfile(
            username=username,
            email=email,
            password_hash=UserProfile.hash_password(password),  # generiše novi salt
        )
        self.save_user(profile)
        return profile

    def verify_password(self, username: str, password: str) -> bool:
        stored = self._index.get(username)
        if not stored:
            return False
        valid = UserProfile.verify_password_hash(password, stored)
        if valid and not stored.startswith("pbkdf2_sha256$"):
            profile = self.get_user(username)
            if profile:
                profile.password_hash = UserProfile.hash_password(password)
                self.save_user(profile)
        return valid

    def all_usernames(self) -> list[str]:
        return list(self._index.keys())

    # ── Vocab helpers ─────────────────────────────────────────────────────────

    def add_word(self, username: str, word: Word) -> bool:
        """Vraća True ako je reč nova (nije duplikat)."""
        user = self.get_user(username)
        if not user: return False
        if any(w.get("hanzi") == word.hanzi for w in user.vocab):
            return False
        user.vocab.append(word.to_dict())
        self.save_user(user)
        return True

    def update_word(self, username: str, word: Word) -> None:
        user = self.get_user(username)
        if not user: return
        for i, w in enumerate(user.vocab):
            if w.get("hanzi") == word.hanzi:
                user.vocab[i] = word.to_dict(); break
        self.save_user(user)

    def get_due_words(self, username: str) -> list[Word]:
        user = self.get_user(username)
        if not user: return []
        today = date.today().isoformat()
        return [Word.from_dict(w) for w in user.vocab
                if w.get("next_review", today) <= today]

    # ── Session (remember me) ─────────────────────────────────────────────────

    def save_session(self, username: str) -> None:
        """Sačuvaj korisnika za auto-login (remember me)."""
        try:
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump({"username": username}, f)
        except Exception:
            pass

    def load_session(self) -> Optional[str]:
        """Učitaj zapamćenog korisnika. Vraća username ili None."""
        try:
            if os.path.exists(SESSION_FILE):
                with open(SESSION_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                username = data.get("username", "")
                if username and self.user_exists(username):
                    return username
        except Exception:
            pass
        return None

    def clear_session(self) -> None:
        """Obriši sačuvanu sesiju (sign out)."""
        try:
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
        except Exception:
            pass