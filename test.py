# test.py - FINALNA VERZIJA (Fixed Pylance Errors)
import os
import threading
import time
import json
import logging
import sqlite3
import re
from dotenv import load_dotenv
from pyngrok import ngrok
from flask import Flask, render_template, request, jsonify, send_from_directory
from google import genai

# Učitavanje konfiguracije
from config import (
    BASE_DIR,
    DEFAULT_GRADIVO,
    IZVJESTAJI_DIR,
    NGROK_DOMAIN,
    NGROK_TOKEN,
    STATS_FILE,
    GRADIVO_FILE,
    ATLAS_DIR,
    ATLAS_INDEX_FILE,
    MODEL_ID,
    GOOGLE_API_KEY,
    RANKS,
    MEDALS,
)

from utils import extract_json, find_atlas_image, requires_auth

# Importamo funkcije za lekcije iz baze (jer one rade),
# ali STATS funkcije ćemo definirati OVDJE da Pylance ne plače.
from database import get_lesson_content, save_lesson_data

# --- KONFIGURACIJA ---
load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("werkzeug")
logger.setLevel(logging.ERROR)

DB_FILE = "skola.db"

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
# --- DATABASE HELPERS (LOCAL DEFINITION FOR SAFETY) ---


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def load_gradivo_from_db():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT subject, topic FROM lessons ORDER BY id ASC")
        rows = c.fetchall()
        conn.close()
        gradivo = {}
        for row in rows:
            sub = row["subject"]
            topic = row["topic"]
            if sub not in gradivo:
                gradivo[sub] = {}
            gradivo[sub][topic] = ""
        return gradivo
    except Exception:
        return {}


# OVE DVIJE FUNKCIJE SU BILE PROBLEM - SAD SU OVDJE I SIGURNE
def get_user_stats_from_db(username="Dani"):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM user_stats WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()

        if row:
            # Sigurno parsiranje JSON-a
            medals = []
            if row["medals"]:
                try:
                    medals = json.loads(row["medals"])
                except Exception:
                    pass

            completed = []
            if row["completed_lessons"]:
                try:
                    completed = json.loads(row["completed_lessons"])
                except Exception:
                    pass

            return {
                "xp": row["xp"] if row["xp"] is not None else 0,
                "lvl": row["lvl"] if row["lvl"] is not None else 1,
                "medals": medals,
                "completed_lessons": completed,
            }
    except Exception as e:
        logging.error(f"DB Error getting stats: {e}")

    # UVIJEK VRATI DICT, NIKAD NONE
    return {"xp": 0, "lvl": 1, "medals": [], "completed_lessons": []}


def update_user_stats_db(username, xp, lvl, medals, completed):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            """INSERT OR REPLACE INTO user_stats (username, xp, lvl, medals, completed_lessons)
                     VALUES (?, ?, ?, ?, ?)""",
            (
                username,
                xp,
                lvl,
                json.dumps(medals, ensure_ascii=False),
                json.dumps(completed, ensure_ascii=False),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"DB Error updating stats: {e}")


def load_atlas_index():
    if os.path.exists(ATLAS_INDEX_FILE):
        try:
            with open(ATLAS_INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def generate_dani_warning(log_data):
    """Pretvara log u brutalnu i provokativnu ocjenu za Danija."""
    score = float(log_data.get("score_percent", 0))
    duration = int(log_data.get("duration", 0))
    subject = log_data.get("subject", "Nepoznato")
    telemetry = log_data.get("telemetry", [])

    # Brojimo prekršaje (tab switch, idle)
    warnings = len([t for t in telemetry if t.get("type") in ["WARNING", "DANGER"]])
    mins, secs = divmod(duration, 60)

    # Reakcija na rezultat
    if score < 40:
        status = "KATASTROFA. Stari će ti popizditi kad ovo vidi. Bolje ti je da se primiš knjige."
    elif score < 70:
        status = (
            "PROSJEČNO. Nije loše, al' znaš i sam da zabušavaš i da možeš puno bolje."
        )
    else:
        status = "SUMNJIVO DOBRO. Stari će biti zadovoljan... ako ti povjeruje da nisi varao."

    # Reakcija na ponašanje
    if warnings > 3:
        warn_text = f"Zabilježeno čak {warnings} sumnjivih aktivnosti (šaltanje tabova, spavanje). Jesi li zaspao pred ekranom ili igraš igrice?!"
    elif warnings > 0:
        warn_text = f"Imao si {warnings} prekršaj(a). Ne misli da sistem ne prati kad odeš na drugi tab."
    else:
        warn_text = "Nisi imao prekršaja. Svaka čast, za promjenu si bio fokusiran."

    msg = f"<b>PREDMET:</b> {subject}<br>"
    msg += f"<b>AKTIVNO VRIJEME:</b> {mins} min i {secs} sek<br>"
    msg += f"<b>USPJEH:</b> {score:.1f}%<br><br>"
    msg += f"<span style='color:#ef4444; font-weight:bold;'>{status}</span><br><br>"
    msg += f"<span style='color:#eab308; font-weight:bold;'>{warn_text}</span><br><br>"
    msg += "<i style='color:#a1a1aa;'>Ne možeš se sakriti, Dani. Sve se loguje.</i>"

    return msg


# --- AI ---
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


# Init
os.makedirs(IZVJESTAJI_DIR, exist_ok=True)
ATLAS_INDEX = load_atlas_index()
app = Flask(__name__)

ai_client = None
if GOOGLE_API_KEY:
    try:
        ai_client = genai.Client(api_key=GOOGLE_API_KEY)
        print("\n>>> DANIJEVA SKOLICA ONLINE (FINAL) <<<\n")
    except Exception as e:
        logging.error(f"AI INIT ERROR: {e}")

# --- ROUTES ---


@app.route("/")
def index():
    gradivo = load_gradivo_from_db()
    stats = get_user_stats_from_db("Dani")
    completed = stats.get("completed_lessons", [])
    return render_template("index.html", podaci=gradivo, completed=completed)


@app.route("/api/auth", methods=["POST"])
def api_auth():
    d = request.json or {}
    user = d.get("user")
    pw = d.get("pw")
    from config import ADMIN_PASSWORD, ACCESS_PASSWORD

    if user == "admin" and pw == ADMIN_PASSWORD:
        return jsonify({"ok": True, "role": "admin"})
    if request.remote_addr in ["127.0.0.1", "::1"] or pw == ACCESS_PASSWORD:
        return jsonify({"ok": True, "role": "student", "user": "Dani"})
    return jsonify({"ok": False, "role": "student"})


@app.route("/atlas/<path:filename>")
def serve_atlas_image(filename):
    return send_from_directory(ATLAS_DIR, filename)


# --- USER API ---


@app.route("/api/stats")
def api_stats():
    stats = get_user_stats_from_db("Dani")
    current_rank = "PODRUMAR"
    for xp_req, title in sorted(RANKS.items()):
        if stats.get("xp", 0) >= xp_req:
            current_rank = title
    stats["rank_title"] = current_rank
    return jsonify(stats)


@app.route("/api/gradivo")
def api_gradivo():
    return jsonify(load_gradivo_from_db())


@app.route("/api/content")
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
                    "local_image": db_data["image_path"],  # Uzmi sliku direktno iz baze
                }
            )

    # 2. Ako nema, AI generira (kao i do sada)...
    # AI poziv ide ovdje, a save_lesson_data će spremiti i sliku u bazu.

    print(f"🤖 NEMA U BAZI. GENERIRAM: {l}")
    info_text = db_data.get("content", "") if db_data else ""
    ai_data = None

    if m == "LEARN":
        prompt = PROMPT_TEACHER.format(l=l, p=p, info=info_text)
        ai_data = ai_generate_json(prompt)
        if ai_data:
            ai_data["local_image"] = None
            if "Anatomija" in p or "Anatomy" in p:
                atlas_img = find_atlas_image(l, ATLAS_INDEX)
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


@app.route("/api/grade", methods=["POST"])
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


@app.route("/api/save", methods=["POST"])
def api_save():
    d = request.json or {}
    student = d.get("student", "Unknown")
    score_percent = d.get("score_percent", 0)
    mode = d.get("mode", "LEARN")

    try:
        stats = get_user_stats_from_db(student)
        if stats is None:
            stats = {"xp": 0, "lvl": 1, "medals": [], "completed_lessons": []}

        xp_gained = 0
        is_rushed = False

        if mode == "TEST":
            xp_gained = int(score_percent * 5)
            if score_percent == 100 and "NERD" not in stats["medals"]:
                stats["medals"].append("NERD")
                xp_gained += 200
            elif 50 <= score_percent < 60 and "SURVIVOR" not in stats["medals"]:
                stats["medals"].append("SURVIVOR")
            if score_percent < 20 and "BROKEN_STICK" not in stats["medals"]:
                stats["medals"].append("BROKEN_STICK")

        elif mode == "LEARN":
            if not d.get("rushed"):
                xp_gained = 150
            else:
                is_rushed = True
                if "SPEEDING_TICKET" not in stats["medals"]:
                    stats["medals"].append("SPEEDING_TICKET")

        for t in d.get("telemetry", []):
            if t.get("type") == "DANGER":
                xp_gained = 0
                if "CHEATER" not in stats["medals"]:
                    stats["medals"].append("CHEATER")
                break

        stats["xp"] += xp_gained
        stats["lvl"] = 1 + (stats["xp"] // 500)

        if stats["xp"] >= 3000 and "BOOKWORM" not in stats["medals"]:
            stats["medals"].append("BOOKWORM")

        current_rank = "PODRUMAR"
        for xp_req, title in sorted(RANKS.items()):
            if stats["xp"] >= xp_req:
                current_rank = title

        if d.get("lesson") and d.get("lesson") not in stats["completed_lessons"]:
            stats["completed_lessons"].append(d.get("lesson"))

        update_user_stats_db(
            student,
            stats["xp"],
            stats["lvl"],
            stats["medals"],
            stats["completed_lessons"],
        )

        # Generisanje loga i brutalnog izvještaja
        safe_student = re.sub(r'[^a-zA-Z0-9_]', '', student)[:20]
        fname = f"LOG_{safe_student}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        log_data = d.copy()
        log_data.update({"xp_gained": xp_gained, "rushed": is_rushed})
        with open(os.path.join(IZVJESTAJI_DIR, fname), "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=4, ensure_ascii=False)

        report_msg = generate_dani_warning(log_data)

        return jsonify(
            {
                "ok": True,
                "xp_gained": xp_gained,
                "new_lvl": stats["lvl"],
                "new_rank": current_rank,
                "medals": [],
                "rushed": is_rushed,
                "report": report_msg,
            }
        )

    except Exception as e:
        logging.error(f"Save error: {e}")
        return jsonify({"ok": False, "error": "Internal server error"})


# --- ADMIN ROUTES ---
@app.route("/api/admin/save", methods=["POST"])
def api_admin_save():
    return jsonify({"ok": True})


@app.route("/api/admin/gradivo/delete", methods=["POST"])
def api_admin_del():
    d = request.json
    p = d.get("predmet")
    l = d.get("lekcija")
    if p and l:
        conn = get_db()
        try:
            conn.execute("DELETE FROM lessons WHERE subject=? AND topic=?", (p, l))
            conn.commit()
        finally:
            conn.close()
    return jsonify({"ok": True})


@app.route("/api/admin/logs/list", methods=["POST"])
def api_admin_ll():
    try:
        f = [x for x in os.listdir(IZVJESTAJI_DIR) if x.endswith(".txt")]
        f.sort(reverse=True)
        return jsonify({"ok": True, "files": f})
    except Exception:
        return jsonify({"ok": False})


@app.route("/api/admin/logs/read", methods=["POST"])
def api_admin_lr():
    try:
        fn = request.json.get("filename")
        if not fn or "/" in fn or "\\" in fn or ".." in fn:
            return jsonify({"ok": False})
        safe_fn = os.path.basename(fn)
        if not safe_fn or not safe_fn.endswith(".txt"):
            return jsonify({"ok": False})
        filepath = os.path.join(os.path.abspath(IZVJESTAJI_DIR), safe_fn)
        if not filepath.startswith(os.path.abspath(IZVJESTAJI_DIR)):
            return jsonify({"ok": False})
        with open(filepath, "r", encoding="utf-8") as f:
            return jsonify({"ok": True, "data": json.load(f)})
    except Exception:
        return jsonify({"ok": False})


@app.route("/api/admin/stats/update", methods=["POST"])
def api_admin_update_stats():
    d = request.json or {}
    val = d.get("set_xp")
    if val is None:
        return jsonify({"ok": False})
    try:
        new_xp = int(val)
        conn = get_db()
        try:
            conn.execute(
                "UPDATE user_stats SET xp=?, lvl=? WHERE username=?",
                (new_xp, 1 + new_xp // 500, "Dani"),
            )
            conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": True})
    except Exception:
        return jsonify({"ok": False})


def start_ngrok():
    if not NGROK_TOKEN:
        return
    try:
        ngrok.set_auth_token(NGROK_TOKEN)
        if os.name == "nt":
            os.system("taskkill /f /im ngrok.exe >nul 2>&1")
        url = ngrok.connect(addr="5000", domain=NGROK_DOMAIN).public_url
        print(f"\n>>> SISTEM ONLINE NA: {url} <<<\n")
    except Exception:
        pass


if __name__ == "__main__":
    threading.Thread(target=start_ngrok, daemon=True).start()
    app.run(port=5000, use_reloader=False)
