import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IZVJESTAJI_DIR = os.path.join(BASE_DIR, "izvjestaji")
STATS_FILE = os.path.join(
    BASE_DIR, "ucenik_stats.json"
)  # Zadržano radi kompatibilnosti, ali se ne koristi
GRADIVO_FILE = os.path.join(BASE_DIR, "gradivo.json")  # Zadržano
ATLAS_DIR = os.path.join(BASE_DIR, "atlas_processed", "images")
ATLAS_INDEX_FILE = os.path.join(BASE_DIR, "atlas_processed", "atlas_index.json")

# --- AUTH ---
NGROK_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "komostas")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
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

DEFAULT_GRADIVO = {}  # Nije više bitno jer koristimo DB
