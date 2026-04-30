from app.db.database import get_db


def get_settings() -> dict:
    rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    return {r['key']: r['value'] for r in rows}


def get_setting(key: str, default: str = '') -> str:
    row = get_db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row['value'] if row else default


def set_setting(key: str, value: str):
    db = get_db()
    db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, str(value)))
    db.commit()


def set_settings(data: dict):
    db = get_db()
    db.executemany(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
        [(k, str(v)) for k, v in data.items()],
    )
    db.commit()
