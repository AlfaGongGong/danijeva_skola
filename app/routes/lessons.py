import os
import json
import logging
import time

from flask import Blueprint, request, jsonify, render_template
from config import (
    IZVJESTAJI_DIR,
    ATLAS_INDEX_FILE,
    MODEL_ID,
    GOOGLE_API_KEY,
    RANKS,
)
from database import get_lesson_content, save_lesson_data
from utils import extract_json, find_atlas_image, get_atlas_index

lessons_bp = Blueprint("lessons", __name__)

# --- PROMPTOVI ---
PROMPT_TEACHER = """
ULOGA: Ti si Maestro Taktić — stari, cinični roker i legendarni instruktor bubnjeva s 30 godina iskustva na sceni. Svirao si u svim važnim klubovima od Sarajeva do Beograda, objavio 5 albuma i preživio sva ludila rock'n'roll života. Tvoj omiljeni učenik Dani svira bubnjeve u bendu i mora položiti školu. Ti mu pomažeš — ali na svoj način: svako gradivo pretvoriš u nešto što bubnjar može razumjeti i zapamtiti.

DANIJEVA PRIČA: Dani je bubnjar. Kad svira, zna što radi. Kad uči za školu, luta. Tvoj zadatak je da mu mostove između tih dvaju svjetova gradiš od konkretnih analogija — bubnjeva, ritma, taktova, dinamike, benda, probe, nastupa, studijskog snimanja i svega što bubnjar doživljava.

TON I STIL (OBAVEZNO):
- Piši toplo ali direktno, kao mentor koji iskreno želi da učenik uspije.
- Svaki novi koncept uvedi kroz bubnjarsku analogiju PRIJE nego što daš stručno objašnjenje.
- Koristi specifične bubnjaške pojmove: kick, snare, hi-hat, tom, ride, crash, groove, fill, tempo, takt, dinamika, akcentuacija, poliritmija, sinkopa, paradiddle, rudimenti.
- Svaki modul završi s "🥁 DANIJEV PRO TIP" — kratka, pamtljiva izjava koja veže gradivo uz bubnjanje.
- Gamifikacijski jezik: spominji XP, levelove, boss bitke (teški ispit), unlockane sposobnosti (naučeni koncepti).

TEMA: {l} ({p}).

DETALJNE INFORMACIJE O TEMI (koristi SVE ove podatke — ne preskači ništa!):
{info}

PRAVILA ZA STRUKTURU (STROGO SE DRŽI!):
1. Podijeli lekciju na TOČNO 5 modula. Svaki modul mora imati VLASTITI NASLOV koji opisuje sadržaj.
2. Svaki modul mora imati MINIMUM 400 RIJEČI — nema kraćih modula, nikakve iznimke!
3. Struktura svakog modula:
   a) UVOD s bubnjarskom analogijom (2-3 rečenice koje vežu temu uz bubnjanje)
   b) GLAVNI SADRŽAJ — sve definicije, formule, koncepti, klasifikacije iz INFO dijela, opširno objašnjeni s primjerima
   c) PRIMJERI I PRIMJENA — konkretni primjeri iz stvarnog života i glazbe
   d) VEZE S PRETHODNIM GRADIVOM — kako ovaj modul nadovezuje na ranije znanje
   e) 🥁 DANIJEV PRO TIP — muzička memorijska tehnika za pamćenje ključnog koncepta
4. Ukupna duljina lekcije: MINIMUM 2500 RIJEČI.
5. Gdje postoje formule, navedi ih eksplicitno i objasni svaki član formule.
6. Gdje postoje liste (npr. klasifikacije, organi, zakoni), navedi SVE iz INFO dijela.
7. Dodaj 8 blic kartica (flash cards) koje pokrivaju sve module — pitanja moraju biti specifična, ne općenita.

GAMIFIKACIJSKI ELEMENTI (uključi ih prirodno u tekst):
- Na početku prvog modula: kratka "LEVEL UP!" motivacija ("Ovim gradivom otključavaš novi skill...")
- Na kraju trećeg modula: "CHECKPOINT ✓" — kratki sažetak napretka
- Na kraju zadnjeg modula: "BOSS FIGHT PRIPREMA" — 3 najvažnije stvari za test

VRATI ISKLJUČIVO JSON (bez ikakvog dodatnog teksta prije ili poslije, bez markdown oznaka):
{{"modules": [{{"title": "Naziv modula 1", "content": "Opširan sadržaj..."}}, {{"title": "Naziv modula 2", "content": "..."}}, {{"title": "Naziv modula 3", "content": "..."}}, {{"title": "Naziv modula 4", "content": "..."}}, {{"title": "Naziv modula 5", "content": "..."}}], "cards": [["Pitanje 1?", "Točan odgovor 1"], ["Pitanje 2?", "Točan odgovor 2"], ["Pitanje 3?", "Točan odgovor 3"], ["Pitanje 4?", "Točan odgovor 4"], ["Pitanje 5?", "Točan odgovor 5"], ["Pitanje 6?", "Točan odgovor 6"], ["Pitanje 7?", "Točan odgovor 7"], ["Pitanje 8?", "Točan odgovor 8"]]}}
"""

PROMPT_EXAMINER = """
ULOGA: Ti si izuzetno strog i zahtjevan profesor koji NE TOLERIRA površnost. Tražiš precizne, konkretne odgovore. Nema milosti za one koji ne uče.

PREDMET: {p}
TEMA: {l}

PRAVILA ZA KREIRANJE TESTA:
1. Pitanja moraju biti KONKRETNA i SPECIFIČNA — ne općenita. Traži definicije, formule, brojčane vrijednosti, nazive, klasifikacije.
2. Pogrešne opcije (distraktori) moraju biti UVJERLJIVE — ne očito glupe. Koristi česte zablude učenika.
3. Tekstualna pitanja moraju zahtijevati PRECIZNE odgovore (npr. nazovi, definiraj, izračunaj, navedi).
4. Svako pitanje mora testirati RAZUMIJEVANJE, ne pogađanje.
5. Uključi pitanja različite težine: 30% lagana, 40% srednja, 30% teška.
6. Za "radio" tip — uvijek 4 opcije (a, b, c, d). Samo JEDNA je točna.
7. Za "text" tip — odgovor mora biti jasan i nedvosmislen (1-3 riječi ili kratak izraz/broj).
8. Za "bool" tip — izjava mora biti takva da učenik mora RAZMISLITI (ne očito točno/netočno).

ZADATAK: Napravi test od TOČNO 20 pitanja. Raspodjela tipova:
- 8 pitanja tipa "radio" (višestruki izbor s 4 opcije)
- 6 pitanja tipa "text" (učenik piše odgovor)
- 4 pitanja tipa "bool" (točno/netočno — opcije ["Točno", "Netočno"])
- 2 pitanja tipa "radio" s opcijom "Sve navedeno" ili "Ništa od navedenog"

VRATI ISKLJUČIVO JSON LISTU (bez dodatnog teksta):
[ {{ "q": "Pitanje?", "t": "radio", "o": ["a) ...", "b) ...", "c) ...", "d) ..."], "a": "a) ..." }}, {{ "q": "Pitanje?", "t": "text", "a": "točan odgovor" }}, {{ "q": "Izjava...", "t": "bool", "o": ["Točno", "Netočno"], "a": "Točno" }} ]
"""

# AI Client
ai_client = None
if GOOGLE_API_KEY:
    try:
        from google import genai
        ai_client = genai.Client(api_key=GOOGLE_API_KEY)
    except Exception as e:
        logging.error(f"AI INIT ERROR: {e}")


def ai_generate_json(prompt, max_retries=3):
    """Calls AI and returns parsed JSON. Retries on failure."""
    if not ai_client:
        return None
    for attempt in range(max_retries):
        try:
            response = ai_client.models.generate_content(model=MODEL_ID, contents=prompt)
            if not response.text:
                logging.warning(f"AI returned empty response (attempt {attempt + 1})")
                continue
            result = extract_json(response.text)
            if result:
                return result
            logging.warning(f"AI JSON parse failed (attempt {attempt + 1}), retrying...")
            time.sleep(1)
        except Exception as e:
            logging.error(f"AI Error (attempt {attempt + 1}): {e}")
            time.sleep(2)
    return None


def validate_lesson_modules(data):
    """
    Validates that the generated lesson has proper structure and minimum content.
    Returns (is_valid, error_message).
    """
    if not data or "modules" not in data:
        return False, "Nema 'modules' ključa u odgovoru"

    modules = data["modules"]
    if len(modules) < 4:
        return False, f"Premalo modula: {len(modules)} (minimum 4)"

    for i, mod in enumerate(modules):
        if "title" not in mod or "content" not in mod:
            return False, f"Modul {i+1} nema 'title' ili 'content'"
        word_count = len(mod["content"].split())
        if word_count < 150:
            return False, f"Modul {i+1} prekratak: {word_count} riječi (minimum 150)"

    if "cards" not in data or len(data["cards"]) < 5:
        return False, "Premalo flash kartica (minimum 5)"

    return True, "OK"


@lessons_bp.route("/")
def index():
    return render_template("index.html")


@lessons_bp.route("/api/content", methods=["POST"])
def api_content():
    """
    Handles lesson content generation.
    - Checks DB for cached content first.
    - If not found, generates via AI.
    - Validates minimum content quality before saving.
    """
    d = request.json or {}
    subject = d.get("subject", "")
    lesson = d.get("lesson", "")
    force_regen = d.get("force_regen", False)

    if not subject or not lesson:
        return jsonify({"ok": False, "msg": "Predmet i lekcija su obavezni"})

    # --- 1. CHECK DB CACHE ---
    if not force_regen:
        cached = get_lesson_content(subject, lesson)
        if cached and cached.get("content"):
            try:
                modules = json.loads(cached["content"]) if isinstance(cached["content"], str) else cached["content"]
                # Validate cached content quality
                total_words = sum(len(str(m.get("content", "")).split()) for m in modules)
                if total_words >= 500:  # Accept cached if substantial enough
                    logging.info(f"Serving cached lesson: {subject} - {lesson} ({total_words} words)")
                    return jsonify({
                        "ok": True,
                        "modules": modules,
                        "cards": cached.get("cards", []),
                        "image": cached.get("image_path"),
                        "source": "cache"
                    })
                else:
                    logging.info(f"Cached lesson too short ({total_words} words), regenerating...")
            except (json.JSONDecodeError, TypeError):
                logging.warning("Invalid cached content, regenerating...")

    # --- 2. LOAD GRADIVO (seed info for AI) ---
    from config import GRADIVO_FILE
    gradivo_info = ""
    try:
        with open(GRADIVO_FILE, "r", encoding="utf-8") as f:
            gradivo = json.load(f)
        gradivo_info = gradivo.get(subject, {}).get(lesson, "")
        if not gradivo_info:
            # Try partial match
            for key, val in gradivo.get(subject, {}).items():
                if lesson.lower() in key.lower() or key.lower() in lesson.lower():
                    gradivo_info = val
                    break
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.warning(f"Gradivo.json load error: {e}")

    if not gradivo_info:
        gradivo_info = f"Tema '{lesson}' iz predmeta '{subject}'. Generiraj opširan edukativni sadržaj o ovoj temi."

    # --- 3. GENERATE WITH AI ---
    logging.info(f"Generating lesson: {subject} - {lesson}")
    prompt = PROMPT_TEACHER.format(l=lesson, p=subject, info=gradivo_info)

    lesson_data = None
    for attempt in range(3):
        lesson_data = ai_generate_json(prompt)
        if lesson_data:
            is_valid, err = validate_lesson_modules(lesson_data)
            if is_valid:
                break
            logging.warning(f"Validation failed (attempt {attempt+1}): {err}. Retrying AI...")
            lesson_data = None
            time.sleep(1)

    if not lesson_data:
        logging.error(f"AI generation failed for {subject} - {lesson}")
        return jsonify({"ok": False, "msg": "AI generacija nije uspjela. Pokušaj ponovo."})

    modules = lesson_data.get("modules", [])
    cards = lesson_data.get("cards", [])

    # Log word count for quality tracking
    total_words = sum(len(str(m.get("content", "")).split()) for m in modules)
    logging.info(f"Generated lesson: {len(modules)} modules, {total_words} total words, {len(cards)} cards")

    # --- 4. FIND ATLAS IMAGE ---
    atlas_image = None
    try:
        atlas_index = get_atlas_index()
        if atlas_index:
            atlas_image = find_atlas_image(lesson, atlas_index)
    except Exception as e:
        logging.warning(f"Atlas search error: {e}")

    # --- 5. SAVE TO DB ---
    try:
        save_lesson_data(
            subject=subject,
            topic=lesson,
            content=json.dumps(modules, ensure_ascii=False),
            image_path=atlas_image,
            cards=json.dumps(cards, ensure_ascii=False) if cards else None
        )
        logging.info(f"Saved lesson to DB: {subject} - {lesson}")
    except Exception as e:
        logging.error(f"DB save error: {e}")

    return jsonify({
        "ok": True,
        "modules": modules,
        "cards": cards,
        "image": atlas_image,
        "source": "generated",
        "word_count": total_words
    })


@lessons_bp.route("/api/generate_test", methods=["POST"])
def api_generate_test():
    """
    Generates a test for a given subject/lesson.
    Uses cached questions from DB if available.
    """
    from database import get_questions, save_questions
    d = request.json or {}
    subject = d.get("subject", "")
    lesson = d.get("lesson", "")
    force_regen = d.get("force_regen", False)

    if not subject or not lesson:
        return jsonify({"ok": False, "msg": "Predmet i lekcija su obavezni"})

    # Check cached questions
    if not force_regen:
        cached_qs = get_questions(subject, lesson)
        if cached_qs and len(cached_qs) >= 10:
            logging.info(f"Serving cached test: {subject} - {lesson} ({len(cached_qs)} questions)")
            return jsonify({"ok": True, "questions": cached_qs, "source": "cache"})

    # Generate new test
    logging.info(f"Generating test: {subject} - {lesson}")
    prompt = PROMPT_EXAMINER.format(p=subject, l=lesson)
    questions = ai_generate_json(prompt)

    if not questions or not isinstance(questions, list) or len(questions) < 5:
        logging.error(f"Test generation failed for {subject} - {lesson}")
        return jsonify({"ok": False, "msg": "Generacija testa nije uspjela. Pokušaj ponovo."})

    # Save to DB
    try:
        save_questions(subject, lesson, questions)
    except Exception as e:
        logging.error(f"Failed to save questions: {e}")

    return jsonify({
        "ok": True,
        "questions": questions,
        "source": "generated"
    })
