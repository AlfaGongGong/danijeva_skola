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
from database import get_lesson_content, save_lesson_data, get_questions, save_questions
from utils import extract_json, find_atlas_image, get_atlas_index

lessons_bp = Blueprint("lessons", __name__)

# --- PROMPTOVI ---
PROMPT_TEACHER = """
ULOGA: Ti si stari, cinični roker i instruktor bubnjeva s 30 godina iskustva na sceni. Tvoj učenik Dani svira bubnjeve u bendu i mora naučiti ovo gradivo za školu. Ti mu pomažeš tako što gradivo povezuješ s glazbom, bubnjevima, bendom, koncertima i rock'n'roll životom.

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
3. Gdje god je moguće, napravi analogiju s bubnjevima/glazbom (npr. frekvencija = tempo, kemijska reakcija = jam session, kosti = okvir bubnja).
4. Dodaj 7 blic pitanja (kartica za ponavljanje) koje pokrivaju sve module.

VRATI ISKLJUČIVO JSON (bez dodatnog teksta):
{{ "modules": [{{ "title": "Naziv modula", "content": "Opširan sadržaj modula s muzičkim analogijama..." }}], "cards": [["Pitanje?", "Točan odgovor"]] }}
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


def ai_generate_json(prompt):
    if not ai_client:
        return None
    try:
        response = ai_client.models.generate_content(model=MODEL_ID, contents=prompt)
        if not response.text:
            return None
        return extract_json(response.text)
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return None


@lessons_bp.route("/api/content")
def api_content():
    p = request.args.get("p", "")
    l = request.args.get("l", "")
    m = request.args.get("mode", "")

    db_data = get_lesson_content(p, l)

    # 1. Ako imamo u bazi (i sadržaj je pravi, ne [WAITING])
    if db_data and len(db_data["content"]) > 50:
        if m == "TEST":
            return jsonify(db_data["questions"])
        elif m == "LEARN":
            try:
                modules = json.loads(db_data["content"])
            except Exception:
                modules = [{"title": "Lekcija", "content": db_data["content"]}]

            return jsonify(
                {
                    "modules": modules,
                    "cards": [[q["q"], q["a"]] for q in db_data["questions"]],
                    "local_image": db_data["image_path"],
                }
            )

    # 2. Ako nema, AI generira
    print(f"🤖 NEMA U BAZI. GENERIRAM: {l}")
    info_text = db_data.get("content", "") if db_data else ""
    ai_data = None

    if m == "LEARN":
        prompt = PROMPT_TEACHER.format(l=l, p=p, info=info_text)
        ai_data = ai_generate_json(prompt)
        if ai_data:
            ai_data["local_image"] = None
            if "Anatomija" in p or "Anatomy" in p:
                atlas_img = find_atlas_image(l, get_atlas_index())
                if atlas_img:
                    ai_data["local_image"] = atlas_img
            try:
                save_lesson_data(p, l, ai_data)
            except Exception:
                pass

    elif m == "TEST":
        prompt = PROMPT_EXAMINER.format(l=l, p=p)
        ai_data = ai_generate_json(prompt)
        if ai_data:
            try:
                save_lesson_data(p, l, ai_data)
            except Exception:
                pass

    if ai_data:
        return jsonify(ai_data)
    return jsonify(
        {
            "error": "AI Timeout",
            "modules": [{"title": "Greška", "content": "Pokušaj ponovno."}],
        }
    )


@lessons_bp.route("/api/generate_test", methods=["POST"])
def api_generate_test():
    """
    Generates a test for a given subject/lesson.
    Uses cached questions from DB if available.
    """
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
    ai_data = ai_generate_json(prompt)

    if not ai_data or not isinstance(ai_data, list) or len(ai_data) < 5:
        logging.error(f"Test generation failed for {subject} - {lesson}")
        return jsonify({"ok": False, "msg": "Generacija testa nije uspjela. Pokušaj ponovo."})

    # Save to DB
    try:
        save_questions(subject, lesson, ai_data)
    except Exception as e:
        logging.error(f"Failed to save questions: {e}")

    return jsonify({
        "ok": True,
        "questions": ai_data,
        "source": "generated"
    })
