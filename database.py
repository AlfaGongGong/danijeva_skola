import sqlite3
import json
import os

DB_FILE = "skola.db"


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        topic TEXT NOT NULL,
        content TEXT,
        image_path TEXT,
        UNIQUE(subject, topic)
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_id INTEGER,
        question TEXT,
        answer TEXT,
        options TEXT,
        keywords TEXT,
        q_type TEXT,
        FOREIGN KEY(lesson_id) REFERENCES lessons(id)
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS user_stats (
        username TEXT PRIMARY KEY,
        xp INTEGER DEFAULT 0,
        lvl INTEGER DEFAULT 1,
        medals TEXT,
        completed_lessons TEXT
    )"""
    )
    conn.commit()
    conn.close()
    seed_lessons_from_gradivo()


def seed_lessons_from_gradivo():
    """Seed lessons from gradivo.json into the database if they don't exist yet."""
    import logging
    gradivo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gradivo.json")
    if not os.path.exists(gradivo_path):
        return
    try:
        with open(gradivo_path, "r", encoding="utf-8") as f:
            gradivo = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.warning(f"Could not load gradivo.json for seeding: {e}")
        return

    conn = get_db()
    c = conn.cursor()
    for subject, lessons in gradivo.items():
        for topic, content_info in lessons.items():
            c.execute(
                "SELECT id FROM lessons WHERE subject = ? AND topic = ?",
                (subject, topic),
            )
            if not c.fetchone():
                c.execute(
                    "INSERT INTO lessons (subject, topic, content) VALUES (?, ?, ?)",
                    (subject, topic, content_info),
                )
    conn.commit()
    conn.close()


def get_lesson_content(subject, topic):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id, content, image_path FROM lessons WHERE subject = ? AND topic = ?",
        (subject, topic),
    )
    row = c.fetchone()

    if row:
        res = {
            "id": row["id"],
            "content": row["content"],
            "image_path": row["image_path"],
            "questions": [],
        }
        c.execute(
            "SELECT question, answer, options, q_type FROM questions WHERE lesson_id = ?",
            (row["id"],),
        )
        for q in c.fetchall():
            try:
                options = json.loads(q["options"]) if q["options"] else []
            except (json.JSONDecodeError, TypeError):
                options = []
            res["questions"].append(
                {
                    "q": q["question"],
                    "a": q["answer"],
                    "o": options,
                    "t": q["q_type"],
                }
            )
        conn.close()
        return res
    conn.close()
    return None


def save_lesson_data(subject, topic, data):
    conn = get_db()
    c = conn.cursor()
    try:
        content = ""
        questions = []
        # Hvatanje slike iz AI odgovora
        img = data.get("local_image")

        if isinstance(data, dict):
            if "modules" in data:
                content = json.dumps(data["modules"], ensure_ascii=False)
            questions = data.get("cards") or data.get("questions") or []

        # Update ili Insert lekcije s image_path
        c.execute(
            "SELECT id FROM lessons WHERE subject = ? AND topic = ?", (subject, topic)
        )
        row = c.fetchone()

        if row:
            lesson_id = row["id"]
            c.execute(
                "UPDATE lessons SET content = ?, image_path = ? WHERE id = ?",
                (content, img, lesson_id),
            )
        else:
            c.execute(
                "INSERT INTO lessons (subject, topic, content, image_path) VALUES (?, ?, ?, ?)",
                (subject, topic, content, img),
            )
            lesson_id = c.lastrowid

        if questions:
            c.execute("DELETE FROM questions WHERE lesson_id = ?", (lesson_id,))
            for q in questions:
                q_text, a_text = (
                    (q[0], q[1]) if isinstance(q, list) else (q.get("q"), q.get("a"))
                )
                opts = json.dumps(q.get("o", [])) if isinstance(q, dict) else "[]"
                q_type = q.get("t", "text") if isinstance(q, dict) else "text"
                c.execute(
                    "INSERT INTO questions (lesson_id, question, answer, options, q_type) VALUES (?,?,?,?,?)",
                    (lesson_id, q_text, a_text, opts, q_type),
                )
        conn.commit()
    finally:
        conn.close()


# User Stats Helpers
def get_user_stats_from_db(username="Dani"):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM user_stats WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            medals = json.loads(row["medals"]) if row["medals"] else []
        except (json.JSONDecodeError, TypeError):
            medals = []
        try:
            completed = json.loads(row["completed_lessons"]) if row["completed_lessons"] else []
        except (json.JSONDecodeError, TypeError):
            completed = []
        return {
            "xp": row["xp"] or 0,
            "lvl": row["lvl"] or 1,
            "medals": medals,
            "completed_lessons": completed,
        }
    return {"xp": 0, "lvl": 1, "medals": [], "completed_lessons": []}


def update_user_stats_db(username, xp, lvl, medals, completed):
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


try:
    init_db()
except Exception:
    import logging as _logging
    _logging.warning("Database initialization failed at module load. Will retry in app context.")
