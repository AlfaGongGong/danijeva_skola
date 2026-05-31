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
ULOGA: Ti si stari, cinični roker i instruktor bubnjeva. Tvoj učenik Dani svira bubnjeve u bendu, ali mora naučiti ovo gradivo za školu.
TON: Koristi sleng glazbenika, usporedbe s bubnjevima. Budi kratak, jasan i "cool".
TEMA: {l} ({p}). INFO: {info}.
ZADATAK: Podijeli lekciju na 3 logična dijela (modula). Dodaj 5 blic pitanja.
VRATI JSON: {{ "modules": [{{ "title": "...", "content": "..." }}], "cards": [["Pitanje", "Odgovor"]] }}
"""

PROMPT_EXAMINER = """
ULOGA: Ti si vrlo strog profesor. PREDMET: {p}, TEMA: {l}
ZADATAK: Napravi test od 20 pitanja (random radio, text, tačno/netačno, a,b,c,sve navedeno, dopuni rečenicu, identifikuj).
VRATI JSON LISTU: [ {{ "q": "...", "t": "radio", "o": ["A","B"], "a": "A" }}, {{ "q": "...", "t": "text", "a": "..." }} ]
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
        from google import genai
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
