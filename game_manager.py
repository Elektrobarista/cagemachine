"""Business-Logik für Abend- und Spieler-Management (SQLite-basiert)"""
import random
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
        with db.connect() as conn:
            for _ in range(20):
                code = _generate_code()
                exists = conn.execute(
                    "SELECT 1 FROM evening WHERE code = ?", (code,)
                ).fetchone()
                if not exists:
                    break
            else:
                raise RuntimeError("Konnte keinen freien Abend-Code erzeugen")

            evening_id = str(uuid.uuid4())
            now = _now()
            conn.execute(
                "INSERT INTO evening (id, code, created_at, last_used_at) VALUES (?, ?, ?, ?)",
                (evening_id, code, now, now),
            )
        return self.get_evening(code)

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

        with db.connect() as conn:
            evening_id = conn.execute(
                "SELECT id FROM evening WHERE code = ?", (evening["code"],)
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO player (id, evening_id, name, active, added_at)"
                " VALUES (?, ?, ?, 1, ?)",
                (str(uuid.uuid4()), evening_id, name, _now()),
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
        return self.get_evening(code)
