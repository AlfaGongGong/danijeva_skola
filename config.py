import os
import sys
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IZVJESTAJI_DIR = os.path.join(BASE_DIR, "izvjestaji")
STATS_FILE = os.path.join(BASE_DIR, "ucenik_stats.json")
GRADIVO_FILE = os.path.join(BASE_DIR, "gradivo.json")
ATLAS_DIR = os.path.join(BASE_DIR, "atlas_processed", "images")
ATLAS_INDEX_FILE = os.path.join(BASE_DIR, "atlas_processed", "atlas_index.json")

# --- AUTH ---
NGROK_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not ACCESS_PASSWORD or not ADMIN_PASSWORD:
    if os.getenv("FLASK_ENV") == "development" or os.getenv("DEBUG") == "1":
        ACCESS_PASSWORD = ACCESS_PASSWORD or "dev"
        ADMIN_PASSWORD = ADMIN_PASSWORD or "dev"
    else:
        raise RuntimeError(
            "ACCESS_PASSWORD i ADMIN_PASSWORD moraju biti postavljeni u .env fajlu!"
        )

NGROK_DOMAIN = os.getenv("NGROK_DOMAIN", "")

# --- AI ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_ID = "models/gemma-3-27b-it"
API_KEYS_LIST = [GOOGLE_API_KEY] if GOOGLE_API_KEY else []

# --- GAMIFICATION ---
RANKS = {
    0: "PODRUMAR (LVL 1)",
    500: "ULIČNI SVIRAČ (LVL 2)",
    1200: "GAŽER (LVL 3)",
    2500: "PREDGRUPA (LVL 4)",
    5000: "STUDIO MUZIČAR (LVL 5)",
    10000: "ROCK ZVIJEZDA (LVL 10)",
    99999: "LEGENDA (MAX)",
}

MEDALS = {
    "FIRST_BLOOD": {
        "name": "Prvi Korak",
        "icon": "👣",
        "desc": "Završio prvu lekciju.",
    },
    "NERD": {"name": "Štreber", "icon": "🤓", "desc": "Riješio test sa 100% točnosti."},
    "SURVIVOR": {
        "name": "Preživjeli",
        "icon": "🩹",
        "desc": "Prošao test s točno 51%.",
    },
    "SPEED_DEMON": {
        "name": "Brzi Gonzales",
        "icon": "⚡",
        "desc": "Riješio izuzetno brzo.",
    },
    # --- PROMJENA OVDJE: 3000 XP ---
    "BOOKWORM": {"name": "Knjiški Moljac", "icon": "📚", "desc": "Skupio 3000 XP-a."},
    "IRON_MAN": {
        "name": "Iron Man",
        "icon": "🤖",
        "desc": "Nije izašao iz taba tijekom testa.",
    },
    # Negativne
    "SPEEDING_TICKET": {
        "name": "Kazna za Brzinu",
        "icon": "🚓",
        "desc": "Zabušavao i klikao bez čitanja.",
        "type": "bad",
    },
    "BROKEN_STICK": {
        "name": "Slomljena Palica",
        "icon": "🥢",
        "desc": "Pao test s manje od 20%.",
        "type": "bad",
    },
    "SLEEPING_BEAUTY": {
        "name": "Trnoružica",
        "icon": "💤",
        "desc": "Zaspao usred lekcije.",
        "type": "bad",
    },
    "CHEATER": {
        "name": "Prevarant",
        "icon": "🦹",
        "desc": "Uhvaćen kako izlazi iz taba.",
        "type": "bad",
    },
}

DEFAULT_GRADIVO = {}

# Atlas OCR alati — cross-platform defaults
if sys.platform == "win32":
    _default_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    _default_poppler = r"C:\Program Files\poppler-24\Library\bin"
else:
    _default_tesseract = "tesseract"
    _default_poppler = ""

TESSERACT_CMD = os.getenv("TESSERACT_CMD", _default_tesseract)
POPPLER_PATH = os.getenv("POPPLER_PATH", _default_poppler)
INPUT_PDF = os.getenv("INPUT_PDF", os.path.join(BASE_DIR, "sobotta-anatomski-atlas.pdf"))
BASE_OUTPUT_DIR = os.path.join(BASE_DIR, "atlas_processed")
