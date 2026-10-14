"""
diagnose_fp.py - Find why FriendsPanel button doesn't show
Run from the project root.
"""
from pathlib import Path

ROOT = Path(__file__).parent
fp = ROOT / "hanziflow" / "ui" / "friends_panel.py"
text = fp.read_text(encoding="utf-8")

print("=" * 60)
print("friends_panel.py diagnosis")
print("=" * 60)
print(f"Lines: {text.count(chr(10))}")
print()

# Check key methods exist
methods = [
    "__init__", "_build_btn", "_build_persistent_panel",
    "_setup_cbs", "_setup_minimize_cbs", "show",
    "_repos_btn", "_open_panel", "_close", "_fade_out",
    "_draw_btn", "_toggle"
]
print("Methods present:")
for m in methods:
    found = f"def {m}(" in text
    print(f"  {'OK' if found else 'MISSING'}: {m}")

print()

# Check __init__ body
idx = text.find("def __init__(self, root")
end = text.find("\n    def ", idx + 1)
init_body = text[idx:end]
print("__init__ body:")
for line in init_body.split("\n"):
    if line.strip():
        print(f"  {line}")

print()

# Check show() body
idx2 = text.find("    def show(self):")
end2 = text.find("\n    def ", idx2 + 1)
print("show() body:")
for line in text[idx2:end2].split("\n"):
    if line.strip():
        print(f"  {line}")

print()

# Check if app.py calls show correctly
app = ROOT / "hanziflow" / "ui" / "app.py"
app_text = app.read_text(encoding="utf-8")
print("app.py FriendsPanel usage:")
for i, line in enumerate(app_text.split("\n")):
    if "FriendsPanel" in line or ("chat_fl" in line and "show" in line):
        print(f"  line {i+1}: {line.strip()}")
