import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("Config")

# =====================================================================
# PUTANJE
# =====================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IZVJESTAJI_DIR = os.path.join(BASE_DIR, "izvjestaji")
STATS_FILE = os.path.join(BASE_DIR, "ucenik_stats.json")
GRADIVO_FILE = os.path.join(BASE_DIR, "gradivo.json")
ATLAS_DIR = os.path.join(BASE_DIR, "atlas_processed", "images")
ATLAS_INDEX_FILE = os.path.join(BASE_DIR, "atlas_processed", "atlas_index.json")

# Za atlas.py
BASE_OUTPUT_DIR = os.path.join(BASE_DIR, "atlas_processed")
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")
POPPLER_PATH = os.getenv("POPPLER_PATH", "")
INPUT_PDF = os.path.join(
    BASE_DIR, os.getenv("INPUT_PDF", "sobotta-anatomski-atlas.pdf")
)

# =====================================================================
# AUTH
# =====================================================================
NGROK_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
NGROK_DOMAIN = os.getenv("NGROK_DOMAIN", "")
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

# =====================================================================
# AI — MODEL S AUTOMATSKIM FALLBACKOM
# =====================================================================
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
API_KEYS_LIST = [GOOGLE_API_KEY] if GOOGLE_API_KEY else []

# Redoslijed preferenci — prvi koji proradi se koristi
MODEL_CANDIDATES = [
    "gemini-2.5-flash",  # Najnoviji, najinteligentniji
    "gemini-2.0-flash",  # Stabilan, brz, dobar za JSON
    "gemini-2.0-flash-lite",  # Lakši, besplatni tier
    "gemini-1.5-flash",  # Stariji ali pouzdani fallback
]


def _detect_working_model(api_key, candidates):
    """
    Proba svaki model s minimalnim test-promptom.
    Vraća naziv prvog koji odgovori bez greške, ili None.
    Loguje rezultat svakog pokušaja.
    """
    if not api_key:
        logger.warning("[ModelDetect] Nema API ključa — preskačem detekciju.")
        return None

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"[ModelDetect] Ne mogu inicijalizovati genai klijent: {e}")
        return None

    for model in candidates:
        try:
            logger.info(f"[ModelDetect] Testiram: {model} ...")
            resp = client.models.generate_content(
                model=model, contents="Odgovori samo sa: OK"
            )
            if resp and resp.text:
                logger.info(f"[ModelDetect] ✅ Radi: {model}")
                return model
            else:
                logger.warning(f"[ModelDetect] ⚠️  Prazan odgovor: {model}")
        except Exception as e:
            logger.warning(f"[ModelDetect] ❌ Ne radi {model}: {e}")

    logger.error("[ModelDetect] Nijedan model nije prošao provjeru!")
    return None


# Pokušaj detekcije pri importu; pad na prvi kandidat ako sve zakaže
_detected = _detect_working_model(GOOGLE_API_KEY, MODEL_CANDIDATES)
MODEL_ID = _detected if _detected else MODEL_CANDIDATES[0]

print(f"[Config] Aktivan AI model: {MODEL_ID}")

# =====================================================================
# GAMIFICATION
# =====================================================================
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
    "NERD": {
        "name": "Štreber",
        "icon": "🤓",
        "desc": "Riješio test sa 100% točnosti.",
    },
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
    "BOOKWORM": {
        "name": "Knjiški Moljac",
        "icon": "📚",
        "desc": "Skupio 3000 XP-a.",
    },
    "IRON_MAN": {
        "name": "Iron Man",
        "icon": "🤖",
        "desc": "Nije izašao iz taba tijekom testa.",
    },
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
        "icon": "😴",
        "desc": "Zaspao za računalom.",
        "type": "bad",
    },
    "CHEATER": {
        "name": "Prevarant",
        "icon": "🕵️",
        "desc": "Izašao iz taba.",
        "type": "bad",
    },
}
