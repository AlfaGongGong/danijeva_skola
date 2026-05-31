import os
import json
import re
import time
import logging
import sqlite3
import glob as glob_module

from flask import Blueprint, request, jsonify, render_template
from config import IZVJESTAJI_DIR, RANKS, MEDALS

stats_bp = Blueprint("stats", __name__)

DB_FILE = "skola.db"


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


def get_user_stats_from_db(username="Dani"):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM user_stats WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()

        if row:
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


def generate_dani_warning(log_data):
    """Pretvara log u brutalnu i provokativnu ocjenu za Danija."""
    score = float(log_data.get("score_percent", 0))
    duration = int(log_data.get("duration", 0))
    subject = log_data.get("subject", "Nepoznato")
    telemetry = log_data.get("telemetry", [])

    warnings = len([t for t in telemetry if t.get("type") in ["WARNING", "DANGER"]])
    mins, secs = divmod(duration, 60)

    if score < 40:
        status = "KATASTROFA. Stari će ti popizditi kad ovo vidi. Bolje ti je da se primiš knjige."
    elif score < 70:
        status = "PROSJEČNO. Nije loše, al' znaš i sam da zabušavaš i da možeš puno bolje."
    else:
        status = "SUMNJIVO DOBRO. Stari će biti zadovoljan... ako ti povjeruje da nisi varao."

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


@stats_bp.route("/")
def index():
    gradivo = load_gradivo_from_db()
    stats = get_user_stats_from_db("Dani")
    completed = stats.get("completed_lessons", [])
    return render_template("index.html", podaci=gradivo, completed=completed)


@stats_bp.route("/api/stats")
def api_stats():
    stats = get_user_stats_from_db("Dani")
    current_rank = "PODRUMAR"
    for xp_req, title in sorted(RANKS.items()):
        if stats.get("xp", 0) >= xp_req:
            current_rank = title
    stats["rank_title"] = current_rank
    return jsonify(stats)


@stats_bp.route("/api/gradivo")
def api_gradivo():
    return jsonify(load_gradivo_from_db())


@stats_bp.route("/api/save", methods=["POST"])
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
        fname = os.path.basename(fname)
        log_path = os.path.join(IZVJESTAJI_DIR, fname)
        log_data = d.copy()
        log_data.update({"xp_gained": xp_gained, "rushed": is_rushed})
        with open(log_path, "w", encoding="utf-8") as f:
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


@stats_bp.route("/get_analytics", methods=["POST"])
def get_analytics():
    logs = []
    for f in sorted(glob_module.glob(os.path.join(IZVJESTAJI_DIR, "LOG_*.txt"))):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                logs.append({
                    "date": os.path.basename(f)[4:19],
                    "subject": data.get("subject", ""),
                    "score": data.get("score_percent", 0),
                    "xp": data.get("xp_gained", 0),
                    "mode": data.get("mode", ""),
                    "duration": data.get("duration", 0),
                })
        except (json.JSONDecodeError, KeyError):
            continue
    return jsonify({"ok": True, "logs": logs})


# --- ADMIN ROUTES ---
@stats_bp.route("/api/admin/save", methods=["POST"])
def api_admin_save():
    return jsonify({"ok": True})


@stats_bp.route("/api/admin/gradivo/delete", methods=["POST"])
def api_admin_del():
    d = request.json
    p = d.get("predmet")
    l = d.get("lekcija")
    if p and l:
        c = get_db().cursor()
        c.execute("DELETE FROM lessons WHERE subject=? AND topic=?", (p, l))
        c.connection.commit()
        c.connection.close()
    return jsonify({"ok": True})


@stats_bp.route("/api/admin/logs/list", methods=["POST"])
def api_admin_ll():
    try:
        f = [x for x in os.listdir(IZVJESTAJI_DIR) if x.endswith(".txt")]
        f.sort(reverse=True)
        return jsonify({"ok": True, "files": f})
    except Exception:
        return jsonify({"ok": False})


@stats_bp.route("/api/admin/logs/read", methods=["POST"])
def api_admin_lr():
    try:
        fn = request.json.get("filename")
        if not fn or "/" in fn or "\\" in fn or ".." in fn:
            return jsonify({"ok": False})
        safe_fn = os.path.basename(fn)
        if not safe_fn or not safe_fn.endswith(".txt"):
            return jsonify({"ok": False})
        abs_dir = os.path.abspath(IZVJESTAJI_DIR)
        filepath = os.path.join(abs_dir, safe_fn)
        if not filepath.startswith(abs_dir):
            return jsonify({"ok": False})
        with open(filepath, "r", encoding="utf-8") as f:
            return jsonify({"ok": True, "data": json.load(f)})
    except Exception:
        return jsonify({"ok": False})


@stats_bp.route("/api/admin/stats/update", methods=["POST"])
def api_admin_update_stats():
    d = request.json or {}
    val = d.get("set_xp")
    if val is None:
        return jsonify({"ok": False})
    try:
        new_xp = int(val)
        c = get_db().cursor()
        c.execute(
            "UPDATE user_stats SET xp=?, lvl=? WHERE username='Dani'",
            (new_xp, 1 + new_xp // 500),
        )
        c.connection.commit()
        c.connection.close()
        return jsonify({"ok": True})
    except Exception:
        return jsonify({"ok": False})
