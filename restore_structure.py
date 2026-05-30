import sqlite3


def upgrade():
    conn = sqlite3.connect("skola.db")
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE lessons ADD COLUMN image_path TEXT")
        conn.commit()
        print("✅ Kolona 'image_path' uspješno dodana u bazu!")
    except sqlite3.OperationalError:
        print("ℹ️ Kolona 'image_path' već postoji.")
    conn.close()


if __name__ == "__main__":
    upgrade()
