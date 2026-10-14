"""Read-only checks for publishing a clean source tree; never prints secrets."""
import ast
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", "venv", ".git"}
PRIVATE_DIRS = {"users", "audio_cache", "build", "dist", "release", "website", ".claude", ".idea", ".vscode", ".codex", ".agents"}
PRIVATE_FILES = {"session.json", "leaderboard.json", "_plan.json"}
PATTERNS = {
    "API credential": re.compile(rb"(?:sk-or-v1-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    "private Windows home path": re.compile(rb"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s\"']+", re.I),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def check(root=ROOT):
    issues = []
    count = 0
    for folder, dirs, names in os.walk(root, followlinks=False):
        base = Path(folder)
        for name in list(dirs):
            path = base / name
            if name in SKIP or name.startswith("hanziflow-test-"):
                dirs.remove(name)
            elif path.is_symlink():
                issues.append((path.relative_to(root), "symlink directory"))
                dirs.remove(name)
            elif name in PRIVATE_DIRS or name == "__pycache__":
                issues.append((path.relative_to(root), "private/generated directory"))
                dirs.remove(name)
        for name in names:
            path = base / name
            relative = path.relative_to(root)
            if path.is_symlink():
                issues.append((relative, "symlink file"))
                continue
            if (
                name in PRIVATE_FILES or name == ".env"
                or (name.startswith(".env.") and name not in {".env.template", ".env.example"})
                or path.suffix.lower() in {".log", ".pyc", ".pyo", ".exe", ".zip", ".tmp"}
                or ".bak" in name
            ):
                issues.append((relative, "private/generated file"))
            content = path.read_bytes()
            count += 1
            for label, pattern in PATTERNS.items():
                if pattern.search(content):
                    issues.append((relative, label))
            if path.suffix in {".py", ".spec"}:
                try:
                    ast.parse(content.decode("utf-8-sig"), filename=str(relative))
                except (SyntaxError, UnicodeError):
                    issues.append((relative, "invalid Python syntax/encoding"))
            if name in {".env.template", ".env.example"}:
                for line in content.decode("utf-8-sig").splitlines():
                    if line.strip().startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if any(part in key.upper() for part in ("KEY", "TOKEN", "SECRET")) and value.strip():
                        issues.append((relative, "credential value in environment template"))
    return count, issues


if __name__ == "__main__":
    count, issues = check()
    for path, reason in issues:
        print(f"FAIL {path}: {reason}")
    print(f"Scanned {count} project files; {len(issues)} findings. Virtual environments, temporary test directories and Git history are excluded.")
    sys.exit(bool(issues))
