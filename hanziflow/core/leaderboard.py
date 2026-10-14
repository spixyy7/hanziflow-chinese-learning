"""
core/leaderboard.py — Leaderboard sa OneDrive sync.

Lokalni leaderboard se čuva u leaderboard.json.
OneDrive sync koristi Microsoft Graph API (OAuth2 device flow).
Ako OneDrive nije konfigurisan, radi samo lokalno.
"""
from __future__ import annotations
import json, logging, os, shutil, threading, time
from datetime import date, datetime
from typing import Optional

from .models import UserProfile, get_rank

logger = logging.getLogger("HanziFlow.Leaderboard")

LOCAL_FILE   = "leaderboard.json"
ONEDRIVE_ENV = "HANZIFLOW_ONEDRIVE_TOKEN"  # Bearer token za Graph API
GRAPH_URL    = "https://graph.microsoft.com/v1.0/me/drive/root:/hanziflow_leaderboard.json"


class Leaderboard:
    """
    Leaderboard singleton.

    Struktura leaderboard.json:
    {
      "entries": [
        {"username": "alice", "arena_score": 5000, "xp": 1200, "level": 8,
         "rank_name": "Sentence Master", "rank_icon": "💠", "last_updated": "2025-01-15"}
      ],
      "last_sync": "2025-01-15T10:30:00"
    }
    """

    _instance: Optional["Leaderboard"] = None

    def __new__(cls) -> "Leaderboard":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = {"entries": [], "last_sync": ""}
            cls._instance._lock = threading.Lock()
            cls._instance._load_local()
        return cls._instance

    # ── Lokalni I/O ───────────────────────────────────────────────────────────

    def _load_local(self) -> None:
        if os.path.exists(LOCAL_FILE):
            try:
                with open(LOCAL_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.warning(f"Leaderboard load failed: {e}")

    def _save_local(self) -> None:
        tmp = LOCAL_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp, LOCAL_FILE)

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, profile: UserProfile) -> None:
        """Ažurira ili dodaje korisnika u leaderboard."""
        rank = get_rank(profile.arena_score)
        entry = {
            "username":    profile.username,
            "arena_score": profile.arena_score,
            "xp":          profile.xp,
            "level":       profile.level,
            "rank_name":   rank["name"],
            "rank_icon":   rank["icon"],
            "last_updated": date.today().isoformat(),
        }
        with self._lock:
            entries = self._data.setdefault("entries", [])
            for i, e in enumerate(entries):
                if e.get("username") == profile.username:
                    entries[i] = entry
                    break
            else:
                entries.append(entry)
            # Sortiraj po arena_score desc
            self._data["entries"] = sorted(entries,
                                           key=lambda x: x.get("arena_score", 0),
                                           reverse=True)
            self._save_local()

        # Async OneDrive sync
        threading.Thread(target=self._sync_to_onedrive, daemon=True).start()

    def get_top(self, n: int = 20) -> list[dict]:
        """Vraća top N igrača sa rank brojem."""
        with self._lock:
            entries = self._data.get("entries", [])[:n]
        return [dict(e, rank_num=i + 1) for i, e in enumerate(entries)]

    def get_user_rank(self, username: str) -> Optional[int]:
        with self._lock:
            for i, e in enumerate(self._data.get("entries", [])):
                if e.get("username") == username:
                    return i + 1
        return None

    # ── OneDrive sync ─────────────────────────────────────────────────────────

    def _sync_to_onedrive(self) -> None:
        token = os.environ.get(ONEDRIVE_ENV, "")
        if not token:
            return
        try:
            import requests
            with self._lock:
                content = json.dumps(self._data, ensure_ascii=False, indent=2).encode()
            r = requests.put(
                f"{GRAPH_URL}:/content",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                data=content,
                timeout=10,
            )
            if r.status_code in (200, 201):
                logger.info("Leaderboard synced to OneDrive")
                with self._lock:
                    self._data["last_sync"] = datetime.now().isoformat()
                    self._save_local()
            else:
                logger.warning(f"OneDrive sync failed: {r.status_code}")
        except Exception as e:
            logger.warning(f"OneDrive sync exception: {e}")

    def fetch_from_onedrive(self) -> bool:
        """Povlači leaderboard sa OneDrive (ako postoji token)."""
        token = os.environ.get(ONEDRIVE_ENV, "")
        if not token:
            return False
        try:
            import requests
            r = requests.get(
                f"{GRAPH_URL}:/content",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if r.status_code == 200:
                remote = r.json()
                with self._lock:
                    # Merge: za svakog korisnika uzmi bolji score
                    remote_entries = {e["username"]: e for e in remote.get("entries", [])}
                    local_entries  = {e["username"]: e for e in self._data.get("entries", [])}
                    merged = {}
                    for u, e in {**remote_entries, **local_entries}.items():
                        if u in remote_entries and u in local_entries:
                            merged[u] = max(remote_entries[u], local_entries[u],
                                           key=lambda x: x.get("arena_score", 0))
                        else:
                            merged[u] = e
                    self._data["entries"] = sorted(merged.values(),
                                                   key=lambda x: x.get("arena_score", 0),
                                                   reverse=True)
                    self._save_local()
                return True
        except Exception as e:
            logger.warning(f"OneDrive fetch exception: {e}")
        return False
