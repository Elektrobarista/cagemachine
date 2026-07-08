"""Business-Logik für Abend- und Spieler-Management (SQLite-basiert)"""
import os
import random
import sqlite3
import uuid
from datetime import datetime

import db

# Ohne verwechselbare Zeichen (kein 0/O, 1/I/L)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 4

# Standard-Audio: eine Datei mit Intro + Loop, Timecodes in Sekunden
DEFAULT_AUDIO = {
    "file": "/static/Cage-Loop-concat.ogg",
    "intro_end": 337.806,   # 5:37.806 – hier endet das Intro
    "loop_start": 337.806,  # Loop-Segment ...
    "loop_end": 475.299,    # ... bis 7:55.299
}

# Spielmodi – ein neuer Modus ist ein Eintrag hier:
#   label          Anzeige im UI
#   description    Tooltip/Erklärung im UI
#   start_position Einstiegspunkt in der Audio-Datei (Sekunden, 0 = von vorn)
#   time_limit     Runde endet automatisch nach X Sekunden (None = kein Limit)
#   round_count    Anzahl direkt aufeinanderfolgender Runden (1 = normale Einzelrunde)
#   audio          Audio-Datei mit Loop-Punkten (eigene Datei pro Modus möglich)
GAME_MODES = {
    "classic": {
        "label": "Classic",
        "description": "Intro + Endlos-Loop von vorn",
        "start_position": 0,
        "time_limit": None,
        "round_count": 1,
        "audio": DEFAULT_AUDIO,
    },
    "bullrush": {
        "label": "Bullrush",
        "description": "3 Runden direkt hintereinander – nach jedem Stop startet sofort das nächste Intro",
        "start_position": 0,
        "time_limit": None,
        "round_count": 3,
        "audio": DEFAULT_AUDIO,
    },
}

# Chance, dass ein normaler Rundenstart zum Bullrush wird, wenn der Abend
# "Zufalls-Bullrush" aktiviert hat (per Env-Var übersteuerbar, z. B. 1.0 in Tests)
BULLRUSH_CHANCE = float(os.getenv("BULLRUSH_CHANCE", "0.15"))

# Frühestens nach dieser Zeit darf der Zufalls-Bullrush am selben Abend
# erneut zuschlagen (Sekunden, per Env-Var übersteuerbar)
BULLRUSH_COOLDOWN = float(os.getenv("BULLRUSH_COOLDOWN", str(3.5 * 60 * 60)))

# Boolesche Abend-Einstellungen (Spaltennamen in der evening-Tabelle)
EVENING_SETTINGS = ("random_bullrush",)

# Länger kann eine echte Runde nicht dauern; verwaiste Runden (Browser
# geschlossen statt Stop) bekommen beim Aufräumen keine Dauer, damit sie
# die Zeitstatistik nicht verfälschen
MAX_ROUND_DURATION = 2 * 60 * 60  # 2 Stunden


class EveningNotFound(Exception):
    """Abend zu einem Code existiert nicht"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _duration_seconds(start_iso, end_iso):
    return (datetime.fromisoformat(end_iso) - datetime.fromisoformat(start_iso)).total_seconds()


def _generate_code():
    return "".join(random.choices(CODE_ALPHABET, k=CODE_LENGTH))


def _second_start_position(n):
    """Position des zweiten Startbechers: Becher 1 ist immer Position 1,
    Becher 2 liegt zirkulär gegenüber (bei ungerader Spielerzahl so nah
    wie möglich) – maximal fairer Abstand in beide Laufrichtungen"""
    if n < 2:
        return None
    return 1 + n // 2


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
            open_round = conn.execute(
                "SELECT id, mode, started_at, start_pos2 FROM round"
                " WHERE evening_id = ? AND ended_at IS NULL"
                " ORDER BY started_at DESC LIMIT 1",
                (evening["id"],),
            ).fetchone()

        return {
            "code": evening["code"],
            "created_at": evening["created_at"],
            "random_bullrush": bool(evening["random_bullrush"]),
            "players": [_player_dict(p) for p in players],
            "open_round": dict(open_round) if open_round else None,
        }

    def set_setting(self, code, setting, enabled):
        """Schaltet eine boolesche Abend-Einstellung an/aus"""
        if setting not in EVENING_SETTINGS:
            raise ValueError(f"Unbekannte Einstellung '{setting}'")
        evening = self.get_evening(code)
        with db.connect() as conn:
            # setting ist gegen die Allowlist geprüft, daher sicher im SQL
            conn.execute(
                f"UPDATE evening SET {setting} = ? WHERE code = ?",
                (1 if enabled else 0, evening["code"]),
            )
        return self.get_evening(code)

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

    def _close_open_rounds(self, conn, evening_id, now):
        """Schließt alle offenen Runden eines Abends (Absicherung gegen
        Verbindungsabbrüche: es sollte nie mehr als eine offen sein)"""
        rows = conn.execute(
            "SELECT id, started_at FROM round WHERE evening_id = ? AND ended_at IS NULL",
            (evening_id,),
        ).fetchall()
        for row in rows:
            duration = _duration_seconds(row["started_at"], now)
            if duration > MAX_ROUND_DURATION:
                duration = None
            conn.execute(
                "UPDATE round SET ended_at = ?, duration = ? WHERE id = ?",
                (now, duration, row["id"]),
            )
        return len(rows)

    def start_round(self, code, mode="classic"):
        """Startet eine Runde mit Snapshot der aktiven Spieler"""
        if mode not in GAME_MODES:
            raise ValueError(f"Unbekannter Spielmodus '{mode}'")

        evening = self.get_evening(code)
        now = _now()
        with db.connect() as conn:
            row = conn.execute(
                "SELECT id, random_bullrush, last_bullrush_at FROM evening WHERE code = ?",
                (evening["code"],),
            ).fetchone()
            evening_id = row["id"]

            # Zufalls-Bullrush: normale Einzelrunden können überraschend zum
            # Bullrush werden – höchstens einmal pro Cooldown und nie bei
            # einem manuell gestarteten Bullrush
            cooldown_over = (
                row["last_bullrush_at"] is None
                or _duration_seconds(row["last_bullrush_at"], now) >= BULLRUSH_COOLDOWN
            )
            if (
                row["random_bullrush"]
                and GAME_MODES[mode]["round_count"] == 1
                and cooldown_over
                and random.random() < BULLRUSH_CHANCE
            ):
                mode = "bullrush"
                conn.execute(
                    "UPDATE evening SET last_bullrush_at = ? WHERE id = ?",
                    (now, evening_id),
                )

            # Läuft laut DB noch eine Runde, wird sie automatisch geschlossen
            self._close_open_rounds(conn, evening_id, now)

            # Die Sitzpositionen werden vor jedem Rundenstart neu ausgelost
            # (auch Bullrush-Folgerunden), damit der Runden-Snapshot bereits
            # die neue Ordnung enthält
            players = evening["players"]
            if len(players) >= 2:
                player_ids = [p["id"] for p in players]
                random.shuffle(player_ids)
                new_positions = {pid: pos for pos, pid in enumerate(player_ids, start=1)}
                for player_id, position in new_positions.items():
                    conn.execute(
                        "UPDATE player SET position = ? WHERE id = ?",
                        (position, player_id),
                    )
                for player in players:
                    player["position"] = new_positions[player["id"]]

            round_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO round (id, evening_id, mode, started_at, start_pos2)"
                " VALUES (?, ?, ?, ?, ?)",
                (round_id, evening_id, mode, now, _second_start_position(len(players))),
            )
            for player in evening["players"]:
                conn.execute(
                    "INSERT INTO round_player (round_id, player_id, position) VALUES (?, ?, ?)",
                    (round_id, player["id"], player["position"]),
                )
        return self.get_evening(code)

    def end_round(self, code):
        """Beendet die laufende Runde (kein Fehler, wenn keine offen ist)"""
        evening = self.get_evening(code)
        with db.connect() as conn:
            evening_id = conn.execute(
                "SELECT id FROM evening WHERE code = ?", (evening["code"],)
            ).fetchone()["id"]
            self._close_open_rounds(conn, evening_id, _now())
        return self.get_evening(code)

    def get_statistics(self, code):
        """Statistik eines Abends: Runden, Spieler-Auswertung, Zusammenfassung"""
        evening = self.get_evening(code)
        with db.connect() as conn:
            evening_id = conn.execute(
                "SELECT id FROM evening WHERE code = ?", (evening["code"],)
            ).fetchone()["id"]

            rounds = conn.execute(
                "SELECT * FROM round WHERE evening_id = ? ORDER BY started_at",
                (evening_id,),
            ).fetchall()
            participants = conn.execute(
                "SELECT rp.round_id, rp.position, r.duration, r.started_at,"
                "       p.id AS player_id, p.name, p.active"
                " FROM round_player rp"
                " JOIN round r ON r.id = rp.round_id"
                " JOIN player p ON p.id = rp.player_id"
                " WHERE r.evening_id = ?"
                " ORDER BY r.started_at",
                (evening_id,),
            ).fetchall()
            all_players = conn.execute(
                "SELECT * FROM player WHERE evening_id = ?", (evening_id,)
            ).fetchall()

        by_round = {}
        for row in participants:
            by_round.setdefault(row["round_id"], []).append(row)

        rounds_out = []
        mode_counts = {}
        total_duration = 0.0
        longest_round = None
        for r in rounds:
            mode_counts[r["mode"]] = mode_counts.get(r["mode"], 0) + 1
            if r["duration"] is not None:
                total_duration += r["duration"]
                if longest_round is None or r["duration"] > longest_round:
                    longest_round = r["duration"]
            rounds_out.append({
                "started_at": r["started_at"],
                "ended_at": r["ended_at"],
                "mode": r["mode"],
                "duration": r["duration"],
                "player_count": len(by_round.get(r["id"], [])),
            })

        # Spieler-Auswertung: auch deaktivierte Spieler mit gespielten Runden
        player_stats = {
            p["id"]: {
                "name": p["name"],
                "active": bool(p["active"]),
                "rounds_played": 0,
                "total_duration": 0.0,
                "last_position": p["position"],
            }
            for p in all_players
        }
        for row in participants:
            stats = player_stats[row["player_id"]]
            stats["rounds_played"] += 1
            if row["duration"] is not None:
                stats["total_duration"] += row["duration"]
            if row["position"] is not None:
                stats["last_position"] = row["position"]

        players_out = [
            s for s in player_stats.values()
            if s["active"] or s["rounds_played"] > 0
        ]
        players_out.sort(key=lambda s: (-s["rounds_played"], s["name"].lower()))

        return {
            "evening": {"code": evening["code"], "created_at": evening["created_at"]},
            "summary": {
                "total_rounds": len(rounds_out),
                "total_duration": total_duration,
                "longest_round": longest_round,
                "modes": mode_counts,
            },
            "players": players_out,
            "rounds": rounds_out,
        }

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
