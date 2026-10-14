import sys
import os
import logging
from hanziflow.config import application_dir, load_environment

os.chdir(application_dir())
load_environment()
for stream in (sys.stdout, sys.stderr):
    if stream is not None and hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler("hanziflow.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("HanziFlow")
logger.info("Aplikacija pokrenuta.")
logger.info(f"OpenRouter ključ učitan: {'DA' if os.environ.get('OPENROUTER_API_KEY') else 'NE'}")
logger.info(f"Gemini ključ učitan: {'DA' if os.environ.get('GEMINI_API_KEY') else 'NE'}")

# ── 4. IMPORT APLIKACIJE ──────────────────────────────────────────────
try:
    from hanziflow.ui.app import App
except ImportError as e:
    logger.error(f"Import Error: {e}")
    sys.exit(1)

if __name__ == "__main__":
    try:
        App()
    except Exception as e:
        logger.exception("Kritična greška u radu:")
        input("Pritisni Enter za izlaz...")