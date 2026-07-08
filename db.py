"""SQLite-Persistenz für Abende, Spieler und Runden"""
import os
import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS evening (
    id               TEXT PRIMARY KEY,
    code             TEXT UNIQUE NOT NULL,
    created_at       TEXT NOT NULL,
    last_used_at     TEXT NOT NULL,
    random_bullrush  INTEGER NOT NULL DEFAULT 0,
    last_bullrush_at TEXT
);

CREATE TABLE IF NOT EXISTS player (
    id         TEXT PRIMARY KEY,
    evening_id TEXT NOT NULL REFERENCES evening(id),
    name       TEXT NOT NULL,
    position   INTEGER,
    active     INTEGER NOT NULL DEFAULT 1,
    added_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS round (
    id         TEXT PRIMARY KEY,
    evening_id TEXT NOT NULL REFERENCES evening(id),
    mode       TEXT NOT NULL DEFAULT 'classic',
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    duration   REAL,
    start_pos2 INTEGER
);

CREATE TABLE IF NOT EXISTS round_player (
    round_id  TEXT NOT NULL REFERENCES round(id),
    player_id TEXT NOT NULL REFERENCES player(id),
    position  INTEGER,
    PRIMARY KEY (round_id, player_id)
);

CREATE TABLE IF NOT EXISTS evening_access (
    evening_id   TEXT NOT NULL REFERENCES evening(id),
    visitor_id   TEXT NOT NULL,
    last_used_at TEXT NOT NULL,
    PRIMARY KEY (evening_id, visitor_id)
);

CREATE INDEX IF NOT EXISTS idx_player_evening ON player(evening_id);
CREATE INDEX IF NOT EXISTS idx_round_evening ON round(evening_id);
CREATE INDEX IF NOT EXISTS idx_access_visitor ON evening_access(visitor_id);
"""


def get_db_path():
    """Pfad zur SQLite-Datei (über DB_PATH konfigurierbar)"""
    return os.getenv("DB_PATH", os.path.join("data", "cagemachine.db"))


@contextmanager
def connect():
    """Verbindung als Context-Manager: commit bei Erfolg, rollback bei
    Fehler und in beiden Fällen close (sqlite3's eigener Context-Manager
    schließt Verbindungen nicht)"""
    path = get_db_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    """Legt das Schema an, falls es noch nicht existiert"""
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Mini-Migration: Spalten, die nach dem ersten Release dazukamen
        # (CREATE TABLE IF NOT EXISTS fasst bestehende Tabellen nicht an)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(evening)")}
        if "random_bullrush" not in columns:
            conn.execute(
                "ALTER TABLE evening ADD COLUMN random_bullrush INTEGER NOT NULL DEFAULT 0"
            )
        if "last_bullrush_at" not in columns:
            conn.execute("ALTER TABLE evening ADD COLUMN last_bullrush_at TEXT")
        round_columns = {row["name"] for row in conn.execute("PRAGMA table_info(round)")}
        if "start_pos2" not in round_columns:
            conn.execute("ALTER TABLE round ADD COLUMN start_pos2 INTEGER")
