import os, sys, subprocess, shutil
from pathlib import Path

# Podešavanja putanja
ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"

print("=" * 55)
print("  HanziFlow — Windows EXE Builder (Final AI Fix)")
print("=" * 55)

# ── 1. ČIŠĆENJE ──────────────────────────────────────────────────────
# Rešava "Access Denied" grešku
for folder in [DIST, BUILD]:
    if folder.exists():
        print(f"Brisanje {folder.name}...")
        try:
            shutil.rmtree(folder)
        except Exception as e:
            print(f"GRESKA: Ne mogu da obrišem {folder}. Zatvori program! {e}")
            sys.exit(1)

# ── 2. PYINSTALLER KOMANDA ───────────────────────────────────────────
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",              # Pakuje sve u jedan .exe
    "--windowed",             # Sakriva crni terminal
    "--name=HanziFlow",       # Ime fajla
    "--clean",                # Čisti keš
    "--noconfirm",            # Ne traži potvrdu za prepisivanje
]

# ── 3. DODAVANJE FAJLOVA (DATAS) ─────────────────────────────────────
# Secrets and runtime user data must never be bundled.

# Pakujemo Assets i Sounds
for folder in ["assets", "sounds", "hanziflow/assets", "hanziflow/sounds"]:
    p = ROOT / folder
    if p.exists():
        # Format: putanja_na_disku;ime_u_exe
        cmd.append(f"--add-data={p}{os.pathsep}{folder}")
        print(f"OK: Dodat folder {folder}")

# ── 4. DODATNE BIBLIOTEKE ────────────────────────────────────────────
# Prisilno uključujemo pygame module jer ih AI klijent koristi
cmd.extend(["--collect-submodules", "pygame"])
cmd.extend(["--hidden-import", "pygame.mixer"])
cmd.extend(["--hidden-import", "gtts"])
cmd.extend(["--hidden-import", "requests"])

# Izbacujemo nepotrebne velike biblioteke da EXE bude manji
for ex in ["matplotlib", "numpy", "pandas", "IPython", "notebook"]:
    cmd.extend(["--exclude-module", ex])

# Putanja do glavnog fajla
cmd.append(f"--add-data={ROOT / 'LICENSE'}{os.pathsep}.")
for name in ("changelog.json", "version.json"):
    cmd.append(f"--add-data={ROOT / 'hanziflow' / name}{os.pathsep}hanziflow")
cmd.append(str(ROOT / "main.py"))

# ── 5. POKRETANJE BUILDA ─────────────────────────────────────────────
print("\n>>> Pokrećem PyInstaller. Ovo traje 1-3 minuta...")
result = subprocess.run(cmd)

if result.returncode == 0:
    print("\n" + "="*55)
    print("  ✅ USPJEŠNO! EXE se nalazi u 'dist' folderu.")
    print("  Sada možeš poslati HanziFlow.exe bilo kome!")
    print("="*55)
else:
    print(f"\n❌ GREŠKA: Build nije uspeo (Kod: {result.returncode})")