# utils.py
import os
import json
import logging
import re

from functools import wraps

from flask import request, jsonify

from config import ACCESS_PASSWORD, ADMIN_PASSWORD, ATLAS_DIR, ATLAS_INDEX_FILE

_atlas_index_cache = None


def get_atlas_index():
    global _atlas_index_cache
    if _atlas_index_cache is None:
        try:
            with open(ATLAS_INDEX_FILE, "r", encoding="utf-8") as f:
                _atlas_index_cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _atlas_index_cache = []
    return _atlas_index_cache


# utils.py (samo funkcija requires_auth)


def requires_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        d = request.json or {}
        user = d.get("user")
        pw = d.get("pw")

        # Dohvati IP adresu s koje dolazi zahtjev
        client_ip = request.remote_addr

        # 1. LOCALHOST — zahtijeva lozinku
        if client_ip in ["127.0.0.1", "::1"]:
            if user == "admin" and pw == ADMIN_PASSWORD:
                return f(*args, **kwargs)
            elif pw == ACCESS_PASSWORD:
                return jsonify({"ok": True, "role": "student", "user": user})
            return jsonify({"ok": False, "msg": "Pristup odbijen"})

        # 2. STANDARDNA PROVJERA (Ako pristupaš preko Ngroka/Interneta)
        if user == "admin" and pw == ADMIN_PASSWORD:
            return f(*args, **kwargs)
        elif pw == ACCESS_PASSWORD:
            return jsonify({"ok": True, "role": "student", "user": user})

        return jsonify({"ok": False, "role": "student", "msg": "Pristup odbijen"})

    return decorated_function


def extract_json(text):
    try:
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except json.JSONDecodeError:
        logging.warning("Failed to decode JSON from text")
    return None


def find_atlas_image(lesson_name, atlas_index):
    # 1. Pripremi ključne riječi (izbaci "L1:", "lekcija", kratke riječi)
    clean_name = re.sub(r"L\d+:?", "", lesson_name).strip()
    keywords = [w.lower() for w in re.findall(r"\w+", clean_name) if len(w) > 3]

    if not keywords:
        logging.warning(f"Atlas search: Nema ključnih riječi za '{lesson_name}'")
        return None

    logging.info(f"Atlas search keywords: {keywords}")

    best_img = None
    max_score = 0

    for item in atlas_index:
        if not isinstance(item, dict):
            continue

        # Pojam iz atlasa
        term = str(item.get("term", "")).lower()
        img = item.get("image_rel_path", "")

        # Preskačemo prve stranice (sadržaj, uvod)
        if item.get("page", 0) < 5:
            continue

        score = 0
        for kw in keywords:
            # Jaka podudarnost (cijela riječ)
            if kw == term:
                score += 20
            # Srednja podudarnost (korijen riječi, npr. "kost" u "kosti")
            elif kw in term and len(kw) > 4:
                score += 10
            # Slaba podudarnost
            elif term in kw and len(term) > 4:
                score += 5

        if score > max_score:
            max_score = score
            best_img = img

    if best_img:
        # Provjera postoji li fajl fizički
        full_path = os.path.join(ATLAS_DIR, best_img)
        if os.path.exists(full_path):
            logging.info(f"Atlas match found: {best_img} (Score: {max_score})")
            return best_img
        else:
            logging.error(
                f"Atlas match found ({best_img}) but file is missing at {full_path}"
            )

    logging.info(f"Atlas: No match found for {lesson_name}")
    return None
