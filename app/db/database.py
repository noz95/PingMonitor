import sqlite3
import sys
import threading
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


DB_PATH = get_base_dir() / 'data' / 'monitor.db'

_local = threading.local()


def get_db() -> sqlite3.Connection:
    if not hasattr(_local, 'conn'):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=True, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn = conn
    return _local.conn


def close_db():
    if hasattr(_local, 'conn'):
        _local.conn.close()
        del _local.conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS probes (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            name                 TEXT NOT NULL,
            host                 TEXT NOT NULL,
            type                 TEXT NOT NULL CHECK(type IN ('ping','http','https')),
            group_id             INTEGER REFERENCES groups(id) ON DELETE SET NULL,
            interval             INTEGER NOT NULL DEFAULT 60,
            timeout              INTEGER NOT NULL DEFAULT 5,
            failure_threshold    INTEGER NOT NULL DEFAULT 3,
            enabled              INTEGER NOT NULL DEFAULT 1,
            status               TEXT NOT NULL DEFAULT 'unknown',
            last_check           TIMESTAMP,
            last_latency         REAL,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS probe_results (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            probe_id  INTEGER NOT NULL REFERENCES probes(id) ON DELETE CASCADE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status    TEXT NOT NULL,
            latency   REAL,
            error     TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_results_probe_ts ON probe_results(probe_id, timestamp);
    """)

    defaults = [
        ('smtp_host',       ''),
        ('smtp_port',       '465'),
        ('smtp_user',       ''),
        ('smtp_password',   ''),
        ('smtp_from',       ''),
        ('smtp_to',         ''),
        ('alert_enabled',   '0'),
        ('retention_days',  '720'),
        ('web_port',        '5000'),
        ('web_host',        '0.0.0.0'),
    ]
    cur.executemany("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", defaults)
    conn.commit()
    conn.close()
