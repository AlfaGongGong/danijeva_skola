import sqlite3
import json
import os
import logging

DB_FILE = "skola.db"
logger = logging.getLogger("Database")


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        topic TEXT NOT NULL,
        content TEXT,
        image_path TEXT,
        UNIQUE(subject, topic)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_id INTEGER,
        question TEXT,
        answer TEXT,
        options TEXT,
        keywords TEXT,
        q_type TEXT,
        FOREIGN KEY(lesson_id) REFERENCES lessons(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_stats (
        username TEXT PRIMARY KEY,
        xp INTEGER DEFAULT 0,
        lvl INTEGER DEFAULT 1,
        medals TEXT,
        completed_lessons TEXT
    )""")
    conn.commit()
    conn.close()
    seed_lessons_from_gradivo()


def seed_lessons_from_gradivo():
    """Seed lessons from gradivo.json into the database if they don't exist yet."""
    gradivo_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "gradivo.json"
    )
    if not os.path.exists(gradivo_path):
        return
    try:
        with open(gradivo_path, "r", encoding="utf-8") as f:
            gradivo = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not load gradivo.json for seeding: {e}")
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
                # Pohrani SAMO tekst (sirovi kontekst) — NE kao AI JSON
                # get_lesson_content će ga prepoznati kao "nema AI sadržaja"
                c.execute(
                    "INSERT INTO lessons (subject, topic, content) VALUES (?, ?, ?)",
                    (subject, topic, content_info),
                )
    conn.commit()
    conn.close()


def _is_valid_ai_content(content_str):
    """
    Provjerava je li content string validan AI-generisan sadržaj
    s modules i cards strukturom.
    Vraća (is_valid: bool, parsed: dict|None)
    """
    if not content_str or not isinstance(content_str, str):
        return False, None

    # Mora počinjati s { da bi bio dict (ne lista, ne sirovi tekst)
    stripped = content_str.strip()
    if not stripped.startswith("{"):
        return False, None

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict) and "modules" in parsed and "cards" in parsed:
            modules = parsed["modules"]
            cards = parsed["cards"]
            # Osnovna provjera strukture
            if (
                isinstance(modules, list)
                and len(modules) > 0
                and isinstance(cards, list)
            ):
                return True, parsed
        return False, None
    except (json.JSONDecodeError, Exception):
        return False, None


def get_lesson_content(subject, topic):
    """
    Dohvaća sadržaj lekcije iz baze.
    Vraća dict {"modules": [...], "cards": [...]} ako je AI sadržaj dostupan.
    Vraća None ako sadržaj nije AI-generisan (sirovi tekst, stari format, itd.)
    — signal da treba pokrenuti AI generisanje.
    """
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "SELECT content FROM lessons WHERE subject = ? AND topic = ?",
            (subject, topic),
        )
        row = c.fetchone()
        conn.close()

        if row is None:
            logger.info(
                f"[get_lesson_content] Tema nije pronađena u bazi: {subject}/{topic}"
            )
            return None

        content_str = row["content"]
        is_valid, parsed = _is_valid_ai_content(content_str)

        if is_valid:
            logger.info(
                f"[get_lesson_content] Validan AI sadržaj pronađen za: {subject}/{topic}"
            )
            return parsed
        else:
            # Sirovi tekst iz gradivo.json, stari format liste, ili prazno
            logger.info(
                f"[get_lesson_content] Sadržaj nije AI format za: {subject}/{topic} "
                f"(tip: {type(content_str).__name__}, "
                f"preview: {str(content_str)[:60] if content_str else 'PRAZAN'})"
            )
            return None

    except Exception as e:
        logger.error(f"[get_lesson_content] DB greška: {e}")
        return None


def save_lesson_data(subject, topic, content_json_str):
    """
    Spašava AI-generisan sadržaj lekcije u bazu.
    content_json_str mora biti JSON string s modules i cards.
    """
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            """INSERT INTO lessons (subject, topic, content)
               VALUES (?, ?, ?)
               ON CONFLICT(subject, topic)
               DO UPDATE SET content = excluded.content""",
            (subject, topic, content_json_str),
        )
        conn.commit()
        conn.close()
        logger.info(f"[save_lesson_data] Spašeno za: {subject}/{topic}")
    except Exception as e:
        logger.error(f"[save_lesson_data] DB greška: {e}")
