"""Local configuration. Secrets are supplied by the operator, never bundled."""
import os
import sys
from pathlib import Path


def application_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def load_environment() -> None:
    """Read only the application's external .env; existing variables win."""
    path = application_dir() / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name in {
            "OPENROUTER_API_KEY", "GEMINI_API_KEY", "HANZIFLOW_ONEDRIVE_TOKEN",
            "HANZIFLOW_ENABLE_LAN", "HANZIFLOW_ENABLE_UPDATES",
            "HANZIFLOW_UPDATE_REPOSITORY",
        }:
            os.environ.setdefault(name, value.strip().strip('"').strip("'"))


def secret(name: str) -> str:
    load_environment()
    return os.environ.get(name, "").strip()


def validate_username(username: str) -> str:
    """Reject traversal and names that collide with internal JSON files."""
    reserved = (
        "_friends", "_messages", "_outbox", "_notifications", "_notif_pos",
        "_writing_cache",
    )
    if (
        not isinstance(username, str) or not 1 <= len(username) <= 64
        or not username[0].isalnum()
        or not all(c.isalnum() or c in "-_" for c in username)
        or username.casefold().endswith(reserved)
        or username.casefold().split(".")[0] in {
            "con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
            *(f"lpt{i}" for i in range(1, 10)),
        }
    ):
        raise ValueError("Use 1-64 letters, digits, hyphens or underscores; reserved names are unavailable.")
    return username
