import json
import logging
import time
import re

from flask import Blueprint, request, jsonify
from config import (
    IZVJESTAJI_DIR,
    ATLAS_INDEX_FILE,
    MODEL_ID,
    GOOGLE_API_KEY,
    RANKS,
    GRADIVO_FILE,
)
from database import get_lesson_content, save_lesson_data

# =====================================================================
# INICIJALIZACIJA
# =====================================================================
lessons_bp = Blueprint("lessons", __name__)
logger = logging.getLogger("LessonsAPI")
logger.setLevel(logging.INFO)

# =====================================================================
# PROMPTOVI
# =====================================================================
PROMPT_TEACHER = """
ULOGA: Ti si stari, cinični roker i instruktor bubnjeva s 30 godina iskustva na sceni.
Tvoj učenik Dani svira bubnjeve u bendu i mora naučiti ovo gradivo za školu.
Ti mu pomažeš tako što gradivo povezuješ s glazbom, bubnjevima, bendom, koncertima i rock'n'roll životom.
TON I STIL:
- Koristi sleng glazbenika, metafore iz svijeta muzike i usporedbe s bubnjevima/bendom gdje god ima smisla.
- Budi opširan i detaljan — svaki modul mora imati NAJMANJE 4-5 paragrafa (svaki paragraf min. 3-4 rečenice).
- Objasni svaki koncept temeljito, s primjerima i analogijama iz glazbe.
- Na kraju svakog modula daj "Pro tip" — kratki savjet kako to zapamtiti koristeći muzičku analogiju.
- Budi cool ali informativan — učenik mora STVARNO naučiti gradivo iz tvog objašnjenja.

TEMA: {l} ({p}).
DETALJNE INFORMACIJE O TEMI (koristi SVE ove podatke u svom objašnjenju):
{info}

ZADATAK:
1. Podijeli lekciju na 4-5 logičnih modula (ne 3!). Svaki modul mora biti OPŠIRAN — minimum 300 riječi po modulu.
2. U svakom modulu koristi konkretne primjere, formule, definicije i objašnjenja iz INFO dijela.
3. Gdje god je moguće, napravi analogiju s bubnjevima/glazbom.
4. Dodaj 7 blic pitanja (kartica za ponavljanje) koje pokrivaju sve module.

VRATI ISKLJUČIVO JSON (bez dodatnog teksta, bez markdown blokova):
{{"modules": [{{"title": "Naziv modula", "content": "Opširan sadržaj..."}}], "cards": [["Pitanje?", "Točan odgovor"]]}}
"""

PROMPT_EXAMINER = """
ULOGA: Ti si izuzetno strog i zahtjevan profesor koji NE TOLERIRA površnost.
Tražiš precizne, konkretne odgovore. Nema milosti za one koji ne uče.
PREDMET: {p}
TEMA: {l}

PRAVILA ZA KREIRANJE TESTA:
1. Pitanja moraju biti KONKRETNA i SPECIFIČNA — ne općenita.
2. Pogrešne opcije moraju biti UVJERLJIVE — ne očito glupe.
3. Svako pitanje mora testirati RAZUMIJEVANJE, ne pogađanje.
4. Uključi pitanja različite težine: 30% lagana, 40% srednja, 30% teška.
5. Za "radio" tip — uvijek 4 opcije (a, b, c, d). Samo JEDNA je točna.
6. Za "text" tip — odgovor mora biti jasan i nedvosmislen (1-3 riječi ili kratak izraz).
7. Za "bool" tip — izjava mora biti takva da učenik mora RAZMISLITI.

ZADATAK: Napravi test od TOČNO 20 pitanja:
- 8 pitanja tipa "radio" (višestruki izbor s 4 opcije)
- 6 pitanja tipa "text" (učenik piše odgovor)
- 4 pitanja tipa "bool" (opcije ["Točno", "Netočno"])
- 2 pitanja tipa "radio" s opcijom "Sve navedeno" ili "Ništa od navedenog"

VRATI ISKLJUČIVO JSON LISTU (bez dodatnog teksta, bez markdown blokova):
[{{"q": "Pitanje?", "t": "radio", "o": ["a) ...", "b) ...", "c) ...", "d) ..."], "a": "a) ..."}}, {{"q": "Pitanje?", "t": "text", "a": "točan odgovor"}}, {{"q": "Izjava...", "t": "bool", "o": ["Točno", "Netočno"], "a": "Točno"}}]
"""

# =====================================================================
# AI KLIJENT
# =====================================================================
ai_client = None
if GOOGLE_API_KEY:
    try:
        from google import genai

        ai_client = genai.Client(api_key=GOOGLE_API_KEY)
        logger.info("[+] GenerativeAI klijent uspješno inicijalizovan.")
    except Exception as e:
        logger.error(f"[-] AI INIT ERROR: {e}")


# =====================================================================
# POMOĆNE FUNKCIJE
# =====================================================================


def safe_extract_json(text):
    """
    Ekstrahuje JSON iz AI odgovora kroz 4 faze:
    1. Direktno parsiranje
    2. Markdown ```json blok
    3. Bilo koji ``` blok
    4. Heuristika — prvi { } ili [ ] blok
    """
    if not text or not text.strip():
        logger.warning("[safe_extract_json] Prazan ulazni tekst.")
        return None

    cleaned = text.strip()

    # Faza 1: Direktno
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Faza 2: ```json ... ```
    match = re.search(r"```json\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError as e:
            logger.warning(f"[safe_extract_json] Faza 2 neuspješna: {e}")

    # Faza 3: ``` ... ```
    match = re.search(r"```\s*([\s\S]*?)\s*```", cleaned)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError as e:
            logger.warning(f"[safe_extract_json] Faza 3 neuspješna: {e}")

    # Faza 4: Heuristika
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = cleaned.find(start_char)
        end_idx = cleaned.rfind(end_char)
        if start_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(cleaned[start_idx : end_idx + 1])
            except json.JSONDecodeError as e:
                logger.warning(
                    f"[safe_extract_json] Faza 4 ({start_char}) neuspješna: {e}"
                )

    logger.error("[safe_extract_json] Sve faze neuspješne.")
    return None


def dohvati_kontekst_iz_gradiva(predmet, tema):
    """Čita gradivo.json i vraća sirovi kontekst za datu temu."""
    try:
        with open(GRADIVO_FILE, "r", encoding="utf-8") as f:
            gradivo_baza = json.load(f)
            if predmet in gradivo_baza and tema in gradivo_baza[predmet]:
                logger.info(
                    f"[dohvati_kontekst] Kontekst pronađen za '{predmet}' / '{tema}'."
                )
                return gradivo_baza[predmet][tema]
            logger.warning(f"[dohvati_kontekst] Tema '{tema}' nije u '{predmet}'.")
            return "Nema dodatnih specifičnih informacija za ovu temu."
    except FileNotFoundError:
        logger.error(f"[dohvati_kontekst] {GRADIVO_FILE} nije pronađen.")
        return "Nema dostupnog konteksta."
    except Exception as e:
        logger.error(f"[dohvati_kontekst] Greška: {e}")
        return "Nema dostupnog konteksta."


def ai_generate_json(prompt):
    """Šalje prompt Gemini modelu i vraća parsiran JSON."""
    if not ai_client:
        logger.warning("[ai_generate_json] AI klijent nije dostupan.")
        return None

    start_time = time.time()
    try:
        logger.info("[ai_generate_json] Šaljem zahtjev prema Gemini API-ju...")
        response = ai_client.models.generate_content(model=MODEL_ID, contents=prompt)
        elapsed = time.time() - start_time

        if not response.text:
            logger.warning(f"[ai_generate_json] Prazan odgovor ({elapsed:.2f}s).")
            return None

        logger.info(
            f"[ai_generate_json] Odgovor primljen ({elapsed:.2f}s, {len(response.text)} znakova)."
        )
        result = safe_extract_json(response.text)

        if result is None:
            logger.error("[ai_generate_json] safe_extract_json nije uspio.")
        else:
            logger.info(f"[ai_generate_json] JSON OK, tip: {type(result).__name__}.")

        return result

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[ai_generate_json] Greška ({elapsed:.2f}s): {e}")
        return None


# =====================================================================
# GLAVNI ENDPOINT
# =====================================================================
@lessons_bp.route("/api/content", methods=["GET", "POST"])
def api_content():
    req_id = int(time.time() * 1000)

    if request.method == "GET":
        subject = request.args.get("p")
        topic = request.args.get("l")
        mode = request.args.get("mode")
    else:
        payload = request.json or {}
        subject = payload.get("p")
        topic = payload.get("l")
        mode = payload.get("mode")

    logger.info(
        f"[{req_id}] Zahtjev -> Predmet: '{subject}', Tema: '{topic}', Modus: '{mode}'"
    )

    if not subject or not topic or not mode:
        return jsonify({"error": "Nedostaju obavezni parametri (p, l, mode)."}), 400

    try:
        # ==========================================
        # MODUS UČENJA (LEARN)
        # ==========================================
        if mode == "LEARN":
            # Korak A: Provjera baze — get_lesson_content sad vraća SAMO validan AI dict ili None
            t0 = time.time()
            cached = get_lesson_content(subject, topic)
            db_latency = time.time() - t0

            if cached is not None:
                logger.info(
                    f"[{req_id}] [DB HIT] Validan AI sadržaj iz baze ({db_latency:.3f}s)."
                )
                return jsonify(cached)

            logger.info(
                f"[{req_id}] [DB MISS/INVALID] Pokrćem AI generisanje ({db_latency:.3f}s)..."
            )

            # Korak B: AI generisanje
            kontekst = dohvati_kontekst_iz_gradiva(subject, topic)
            prompt = PROMPT_TEACHER.format(p=subject, l=topic, info=kontekst)
            ai_data = ai_generate_json(prompt)

            if not ai_data:
                logger.error(f"[{req_id}] AI generisanje neuspješno.")
                return (
                    jsonify(
                        {"error": "AI nije uspio generisati lekciju. Pokušajte ponovo."}
                    ),
                    500,
                )

            # Provjeri da AI stvarno vratio modules i cards
            if (
                not isinstance(ai_data, dict)
                or "modules" not in ai_data
                or "cards" not in ai_data
            ):
                logger.error(
                    f"[{req_id}] AI vratio neočekivanu strukturu: {list(ai_data.keys()) if isinstance(ai_data, dict) else type(ai_data)}"
                )
                return (
                    jsonify(
                        {"error": "AI je vratio neispravan format. Pokušajte ponovo."}
                    ),
                    500,
                )

            # Korak C: Spremi u bazu (prepisat će stari sirovi tekst)
            logger.info(f"[{req_id}] Spašavam AI podatke u bazu.")
            save_lesson_data(subject, topic, json.dumps(ai_data, ensure_ascii=False))
            return jsonify(ai_data)

        # ==========================================
        # MODUS TESTIRANJA (TEST)
        # ==========================================
        elif mode == "TEST":
            logger.info(f"[{req_id}] Pokrećem AI generisanje za TEST...")
            prompt = PROMPT_EXAMINER.format(p=subject, l=topic)
            test_data = ai_generate_json(prompt)

            if test_data:
                return jsonify(test_data)
            else:
                logger.error(f"[{req_id}] AI generisanje testa neuspješno.")
                return (
                    jsonify(
                        {"error": "AI nije uspio generisati test. Pokušajte ponovo."}
                    ),
                    500,
                )

        else:
            return (
                jsonify(
                    {"error": f"Nepoznat modus: '{mode}'. Dozvoljeni: LEARN, TEST."}
                ),
                400,
            )

    except Exception as e:
        logger.exception(f"[{req_id}] Kritična greška: {e}")
        return jsonify({"error": "Interna serverska greška."}), 500
