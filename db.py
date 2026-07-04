"""SQLite-Persistenz für Abende, Spieler und Runden"""
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS evening (
    id           TEXT PRIMARY KEY,
    code         TEXT UNIQUE NOT NULL,
    created_at   TEXT NOT NULL,
    last_used_at TEXT NOT NULL
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
    duration   REAL
);

CREATE TABLE IF NOT EXISTS round_player (
    round_id  TEXT NOT NULL REFERENCES round(id),
    player_id TEXT NOT NULL REFERENCES player(id),
    position  INTEGER,
    PRIMARY KEY (round_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_player_evening ON player(evening_id);
CREATE INDEX IF NOT EXISTS idx_round_evening ON round(evening_id);
"""


def get_db_path():
    """Pfad zur SQLite-Datei (über DB_PATH konfigurierbar)"""
    return os.getenv("DB_PATH", os.path.join("data", "cagemachine.db"))


def connect():
    """Öffnet eine neue Verbindung mit Row-Zugriff per Spaltenname"""
    path = get_db_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Legt das Schema an, falls es noch nicht existiert"""
    with connect() as conn:
        conn.executescript(SCHEMA)
