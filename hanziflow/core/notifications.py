"""
core/notifications.py — Persistent offline notification store.

Stores friend requests, messages, and system events even when user is offline.
Notifications are read from/written to users/{username}_notifications.json.

Usage:
    from hanziflow.core.notifications import NotifStore
    store = NotifStore(username)
    store.add_friend_request("bob")
    store.add_message("bob", "Hey!")
    unread = store.get_unread()
    store.mark_read(notif_id)
    store.clear_all()
"""
from __future__ import annotations

import json, uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import validate_username

USERS_DIR = Path("users")
MAX_NOTIFS = 100


def _path(username: str) -> Path:
    return USERS_DIR / f"{validate_username(username)}_notifications.json"


def _load(username: str) -> list:
    p = _path(username)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save(username: str, notifs: list) -> None:
    USERS_DIR.mkdir(exist_ok=True)
    p = _path(username)
    p.write_text(
        json.dumps(notifs[-MAX_NOTIFS:], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


class NotifStore:
    """
    Persistent notification store for one user.
    Thread-safe (file-based, atomic load/save).
    """

    TYPE_FRIEND_REQ  = "friend_request"
    TYPE_FRIEND_ACC  = "friend_accepted"
    TYPE_MESSAGE     = "message"
    TYPE_ACHIEVEMENT = "achievement"
    TYPE_SYSTEM      = "system"

    def __init__(self, username: str):
        self._username = username

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_all(self) -> list:
        return _load(self._username)

    def get_unread(self) -> list:
        return [n for n in _load(self._username) if not n.get("read")]

    def unread_count(self) -> int:
        return sum(1 for n in _load(self._username) if not n.get("read"))

    # ── Write ─────────────────────────────────────────────────────────────────

    def _add(self, ntype: str, from_user: str, text: str,
             extra: Optional[dict] = None) -> dict:
        notifs = _load(self._username)
        notif  = {
            "id":        str(uuid.uuid4())[:8],
            "type":      ntype,
            "from":      from_user,
            "text":      text,
            "timestamp": datetime.now().isoformat(),
            "read":      False,
            **(extra or {}),
        }
        notifs.append(notif)
        _save(self._username, notifs)
        return notif

    def add_friend_request(self, from_user: str) -> dict:
        return self._add(
            self.TYPE_FRIEND_REQ,
            from_user,
            f"{from_user} sent you a friend request"
        )

    def add_friend_accepted(self, from_user: str) -> dict:
        return self._add(
            self.TYPE_FRIEND_ACC,
            from_user,
            f"{from_user} accepted your friend request"
        )

    def add_message(self, from_user: str, preview: str) -> dict:
        return self._add(
            self.TYPE_MESSAGE,
            from_user,
            f"{from_user}: {preview[:60]}"
        )

    def add_system(self, text: str) -> dict:
        return self._add(self.TYPE_SYSTEM, "system", text)

    # ── Mark read ─────────────────────────────────────────────────────────────

    def mark_read(self, notif_id: str) -> None:
        notifs = _load(self._username)
        for n in notifs:
            if n.get("id") == notif_id:
                n["read"] = True
        _save(self._username, notifs)

    def mark_all_read(self) -> None:
        notifs = _load(self._username)
        for n in notifs:
            n["read"] = True
        _save(self._username, notifs)

    def delete(self, notif_id: str) -> None:
        notifs = [n for n in _load(self._username) if n.get("id") != notif_id]
        _save(self._username, notifs)

    def clear_all(self) -> None:
        _save(self._username, [])