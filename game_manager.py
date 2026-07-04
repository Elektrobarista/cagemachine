"""Business-Logik für Abend- und Spieler-Management (SQLite-basiert)"""
import random
import sqlite3
import uuid
from datetime import datetime

import db

# Ohne verwechselbare Zeichen (kein 0/O, 1/I/L)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 4


class EveningNotFound(Exception):
    """Abend zu einem Code existiert nicht"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _generate_code():
    return "".join(random.choices(CODE_ALPHABET, k=CODE_LENGTH))


def _player_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "position": row["position"],
        "added_at": row["added_at"],
    }


class GameManager:
    """Verwaltet Abende und Spieler in SQLite"""

    def __init__(self):
        db.init_db()

    def create_evening(self):
        """Erstellt einen neuen Abend mit eindeutigem Code"""
        # Insert mit Retry statt check-then-insert: die UNIQUE-Constraint
        # entscheidet, damit parallele Erstellungen nicht kollidieren
        for _ in range(20):
            code = _generate_code()
            now = _now()
            try:
                with db.connect() as conn:
                    conn.execute(
                        "INSERT INTO evening (id, code, created_at, last_used_at)"
                        " VALUES (?, ?, ?, ?)",
                        (str(uuid.uuid4()), code, now, now),
                    )
                return self.get_evening(code)
            except sqlite3.IntegrityError:
                continue
        raise RuntimeError("Konnte keinen freien Abend-Code erzeugen")

    def get_evening(self, code):
        """Lädt einen Abend samt aktiver Spieler; aktualisiert last_used_at"""
        code = code.strip().upper()
        with db.connect() as conn:
            evening = conn.execute(
                "SELECT * FROM evening WHERE code = ?", (code,)
            ).fetchone()
            if not evening:
                raise EveningNotFound(f"Kein Abend mit Code '{code}' gefunden")

            conn.execute(
                "UPDATE evening SET last_used_at = ? WHERE id = ?",
                (_now(), evening["id"]),
            )
            players = conn.execute(
                "SELECT * FROM player WHERE evening_id = ? AND active = 1"
                " ORDER BY position IS NULL, position, added_at",
                (evening["id"],),
            ).fetchall()

        return {
            "code": evening["code"],
            "created_at": evening["created_at"],
            "players": [_player_dict(p) for p in players],
        }

    def add_player(self, code, name):
        """Fügt einen Spieler zum Abend hinzu (Name eindeutig unter aktiven Spielern)"""
        evening = self.get_evening(code)
        if any(p["name"].lower() == name.lower() for p in evening["players"]):
            raise ValueError(f"Spielername '{name}' bereits vorhanden")

        # Wurde schon gelost, wird der Neue hinten angehängt
        positions = [p["position"] for p in evening["players"] if p["position"]]
        position = max(positions) + 1 if positions else None

        with db.connect() as conn:
            evening_id = conn.execute(
                "SELECT id FROM evening WHERE code = ?", (evening["code"],)
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO player (id, evening_id, name, position, active, added_at)"
                " VALUES (?, ?, ?, ?, 1, ?)",
                (str(uuid.uuid4()), evening_id, name, position, _now()),
            )
        return self.get_evening(code)

    def draw_positions(self, code):
        """Lost die Sitzpositionen der aktiven Spieler aus (1 = Startbecher)"""
        evening = self.get_evening(code)
        players = evening["players"]
        if len(players) < 2:
            raise ValueError("Zum Auslosen werden mindestens zwei Spieler benötigt")

        with db.connect() as conn:
            evening_id = conn.execute(
                "SELECT id FROM evening WHERE code = ?", (evening["code"],)
            ).fetchone()["id"]

            open_round = conn.execute(
                "SELECT 1 FROM round WHERE evening_id = ? AND ended_at IS NULL",
                (evening_id,),
            ).fetchone()
            if open_round:
                raise ValueError("Auslosen ist nicht möglich, solange eine Runde läuft")

            player_ids = [p["id"] for p in players]
            random.shuffle(player_ids)
            for position, player_id in enumerate(player_ids, start=1):
                conn.execute(
                    "UPDATE player SET position = ? WHERE id = ?",
                    (position, player_id),
                )
        return self.get_evening(code)

    def deactivate_player(self, code, player_id):
        """Deaktiviert einen Spieler (bleibt für Statistik erhalten)"""
        evening = self.get_evening(code)
        if not any(p["id"] == player_id for p in evening["players"]):
            raise ValueError("Spieler nicht gefunden")

        with db.connect() as conn:
            conn.execute(
                "UPDATE player SET active = 0, position = NULL WHERE id = ?",
                (player_id,),
            )

            # Lücke schließen: verbleibende Positionen in bestehender
            # Reihenfolge auf 1..n verdichten
            remaining = [
                p for p in evening["players"]
                if p["id"] != player_id and p["position"] is not None
            ]
            for position, player in enumerate(remaining, start=1):
                conn.execute(
                    "UPDATE player SET position = ? WHERE id = ?",
                    (position, player["id"]),
                )
        return self.get_evening(code)
