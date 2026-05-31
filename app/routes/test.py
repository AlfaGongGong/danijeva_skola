import json
import logging

from flask import Blueprint, request, jsonify
from config import MODEL_ID, GOOGLE_API_KEY
from utils import extract_json

test_bp = Blueprint("test", __name__)

PROMPT_GRADER = """
ULOGA: Ti si iskusni i pravedni profesor. Tvoj cilj je ocijeniti RAZUMIJEVANJE gradiva, a ne sposobnost memoriziranja točnih riječi.

ULAZNI PODACI:
- Pitanje: {q}
- Točan odgovor (referenca): {a}
- Učenikov odgovor: {u}

PRAVILA OCJENJIVANJA (PAŽLJIVO PROČITAJ):
1. SEMANTIKA IZNAD SINTAKSE: Odgovor NE MORA biti identičan referenci. Traži suštinsko značenje. Ako je učenik objasnio točan koncept svojim riječima, to je TOČNO.
2. SINONIMI I JEZIK: Priznaj sinonime, stručne termine (npr. latinski vs hrvatski), dijalekte ili opisna objašnjenja ako su točna.
3. TIPFELERI: Zanemari gramatičke greške i tipfelere (npr. "akcelercija" umjesto "akceleracija") ako je jasno što je učenik mislio.
4. ESEJSKI ODGOVORI: Ako je odgovor duži tekst, traži ključne informacije iz reference. Ako su prisutne, daj bodove bez obzira na "višak" teksta.

BODOVANJE (Strogo 0.0, 0.5 ili 1.0):
- 1.0 (TOČNO): Suština je pogođena. Koncept je jasan.
- 0.5 (DJELOMIČNO): Spomenut je dio točnog odgovora, ali je nepotpun ili malo neprecizan.
- 0.0 (NETOČNO): Odgovor je faktografski pogrešan ili nema veze s pitanjem.

VAŽNO: Vrati SAMO JSON format, bez ikakvog dodatnog teksta.
PRIMJER IZLAZA: {{ "score": 1.0 }}
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


@test_bp.route("/api/grade", methods=["POST"])
def api_grade():
    d = request.json or {}
    prompt = PROMPT_GRADER.format(q=d.get("q"), a=d.get("a"), u=d.get("u"))
    score = 0.0
    data = ai_generate_json(prompt)
    if data and "score" in data:
        try:
            score = float(data["score"])
        except Exception:
            pass
    return jsonify({"score": score})
