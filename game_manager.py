"""Business-Logik für Abend- und Spieler-Management (SQLite-basiert)"""
import os
import random
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta

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

# Zufalls-Bullrush: Trigger-Chance und Cooldown (Env-Var überschreibbar)
BULLRUSH_CHANCE = float(os.getenv("BULLRUSH_CHANCE", "0.15"))
BULLRUSH_COOLDOWN = float(os.getenv("BULLRUSH_COOLDOWN", str(3.5 * 60 * 60)))

# Boolesche Abend-Einstellungen (Spaltennamen in evening)
EVENING_SETTINGS = ("random_bullrush",)

# Verwaiste Runden darüber gelten als ungültig (keine Dauer)
MAX_ROUND_DURATION = 2 * 60 * 60  # 2 Stunden

# Abende, die so lange nicht genutzt wurden, werden automatisch gelöscht
RETENTION_DAYS = float(os.getenv("RETENTION_DAYS", "14"))


class EveningNotFound(Exception):
    """Abend zu einem Code existiert nicht"""


class PlayerNotFound(Exception):
    """Spieler-ID existiert im Abend nicht"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _evening_id(conn, code):
    return conn.execute("SELECT id FROM evening WHERE code = ?", (code,)).fetchone()["id"]


def _next_position(players):
    """Nächste freie Position (hinten anhängen); None, wenn noch nie gelost"""
    positions = [p["position"] for p in players if p["position"]]
    return max(positions) + 1 if positions else None


def _delete_evening_rows(conn, evening_id):
    """Löscht einen Abend samt Kindern (Reihenfolge wegen Fremdschlüsseln)"""
    conn.execute(
        "DELETE FROM round_player WHERE round_id IN"
        " (SELECT id FROM round WHERE evening_id = ?)",
        (evening_id,),
    )
    conn.execute("DELETE FROM round WHERE evening_id = ?", (evening_id,))
    conn.execute("DELETE FROM player WHERE evening_id = ?", (evening_id,))
    conn.execute("DELETE FROM evening_access WHERE evening_id = ?", (evening_id,))
    conn.execute("DELETE FROM evening WHERE id = ?", (evening_id,))


def _compact_positions(conn, players, exclude_id):
    """Verbleibende Positionen (ohne exclude_id) lückenlos auf 1..n verdichten"""
    remaining = [
        p for p in players if p["id"] != exclude_id and p["position"] is not None
    ]
    for position, player in enumerate(remaining, start=1):
        conn.execute(
            "UPDATE player SET position = ? WHERE id = ?", (position, player["id"])
        )


def _duration_seconds(start_iso, end_iso):
    return (datetime.fromisoformat(end_iso) - datetime.fromisoformat(start_iso)).total_seconds()


def _generate_code():
    # secrets statt random (Code nicht aus PRNG-Zustand vorhersagbar)
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


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
        "active": bool(row["active"]),
        "played": bool(row["played"]),
    }


class GameManager:
    """Verwaltet Abende und Spieler in SQLite"""

    def __init__(self):
        db.init_db()
        self.cleanup_expired()

    def cleanup_expired(self):
        """Löscht Abende, die länger als RETENTION_DAYS nicht genutzt wurden.
        get_evening aktualisiert last_used_at – aktive Abende verfallen also nie."""
        cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds")
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT id FROM evening WHERE last_used_at < ?", (cutoff,)
            ).fetchall()
            for row in rows:
                _delete_evening_rows(conn, row["id"])
        return len(rows)

    def create_evening(self):
        """Erstellt einen neuen Abend mit eindeutigem Code"""
        self.cleanup_expired()
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
        """Lädt einen Abend samt aller Spieler (aktiv + deaktiviert); aktualisiert last_used_at"""
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
                "SELECT *, EXISTS(SELECT 1 FROM round_player rp"
                "   WHERE rp.player_id = player.id) AS played"
                " FROM player WHERE evening_id = ?"
                " ORDER BY active DESC, position IS NULL, position, added_at",
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
            "name": evening["name"] or "",
            "created_at": evening["created_at"],
            "random_bullrush": bool(evening["random_bullrush"]),
            "players": [_player_dict(p) for p in players],
            "open_round": dict(open_round) if open_round else None,
        }

    def set_name(self, code, name):
        """Setzt den optionalen Abend-Namen (leer = kein Name)"""
        name = (name or "").strip()
        if len(name) > 60:
            raise ValueError("Abend-Name darf maximal 60 Zeichen lang sein")
        evening = self.get_evening(code)
        with db.connect() as conn:
            conn.execute(
                "UPDATE evening SET name = ? WHERE code = ?",
                (name or None, evening["code"]),
            )
        return self.get_evening(code)

    def delete_evening(self, code):
        """Löscht einen Abend samt aller zugehörigen Daten (Spieler, Runden,
        Snapshots, Zugriffe). Unumkehrbar."""
        code = code.strip().upper()
        with db.connect() as conn:
            evening = conn.execute(
                "SELECT id FROM evening WHERE code = ?", (code,)
            ).fetchone()
            if not evening:
                raise EveningNotFound(f"Kein Abend mit Code '{code}' gefunden")
            _delete_evening_rows(conn, evening["id"])

    def record_access(self, code, visitor_id):
        """Merkt sich, dass ein Gerät (Cookie) diesen Abend geöffnet hat –
        Grundlage für die geräte-gebundene Abend-Übersicht"""
        with db.connect() as conn:
            evening = conn.execute(
                "SELECT id FROM evening WHERE code = ?", (code.strip().upper(),)
            ).fetchone()
            if not evening:
                return
            conn.execute(
                "INSERT OR REPLACE INTO evening_access (evening_id, visitor_id, last_used_at)"
                " VALUES (?, ?, ?)",
                (evening["id"], visitor_id, _now()),
            )

    def list_evenings(self, visitor_id, limit=20):
        """Abende, die dieses Gerät geöffnet hat (neueste zuerst) –
        Codes fremder Abende bleiben so geheim"""
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT e.code, e.name, e.created_at, a.last_used_at,"
                " (SELECT COUNT(*) FROM player p"
                "   WHERE p.evening_id = e.id AND p.active = 1) AS player_count,"
                " (SELECT COUNT(*) FROM round r"
                "   WHERE r.evening_id = e.id) AS round_count"
                " FROM evening_access a"
                " JOIN evening e ON e.id = a.evening_id"
                " WHERE a.visitor_id = ?"
                " ORDER BY a.last_used_at DESC LIMIT ?",
                (visitor_id, limit),
            ).fetchall()
        return [{**dict(row), "name": row["name"] or ""} for row in rows]

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
        if any(p["active"] and p["name"].lower() == name.lower() for p in evening["players"]):
            raise ValueError(f"Spielername '{name}' bereits vorhanden")

        # Wurde schon gelost, wird der Neue hinten angehängt
        position = _next_position(evening["players"])

        with db.connect() as conn:
            evening_id = _evening_id(conn, evening["code"])

            # Bereits mitgespielte Spieler reaktivieren statt duplizieren
            removed = conn.execute(
                "SELECT id FROM player WHERE evening_id = ? AND active = 0"
                " AND lower(name) = lower(?) ORDER BY added_at DESC LIMIT 1",
                (evening_id, name),
            ).fetchone()
            if removed:
                conn.execute(
                    "UPDATE player SET active = 1, position = ? WHERE id = ?",
                    (position, removed["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO player (id, evening_id, name, position, active, added_at)"
                    " VALUES (?, ?, ?, ?, 1, ?)",
                    (str(uuid.uuid4()), evening_id, name, position, _now()),
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

            # Zufalls-Bullrush: Einzelrunde ggf. zum Bullrush machen (1×/Cooldown)
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

            # Nur aktive Spieler nehmen an der Runde teil
            players = [p for p in evening["players"] if p["active"]]

            # Sitzpositionen vor jedem Rundenstart neu auslosen
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
            for player in players:
                conn.execute(
                    "INSERT INTO round_player (round_id, player_id, position) VALUES (?, ?, ?)",
                    (round_id, player["id"], player["position"]),
                )
        return self.get_evening(code)

    def end_round(self, code):
        """Beendet die laufende Runde (kein Fehler, wenn keine offen ist)"""
        evening = self.get_evening(code)
        with db.connect() as conn:
            self._close_open_rounds(conn, _evening_id(conn, evening["code"]), _now())
        return self.get_evening(code)

    def get_statistics(self, code):
        """Statistik eines Abends: Runden, Spieler-Auswertung, Zusammenfassung"""
        evening = self.get_evening(code)
        with db.connect() as conn:
            evening_id = _evening_id(conn, evening["code"])

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
        timed_rounds = 0
        cup2_by_round = {r["id"]: r["start_pos2"] for r in rounds}
        for r in rounds:
            mode_counts[r["mode"]] = mode_counts.get(r["mode"], 0) + 1
            if r["duration"] is not None:
                total_duration += r["duration"]
                timed_rounds += 1
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
                "start_cups": 0,
            }
            for p in all_players
        }
        for row in participants:
            stats = player_stats[row["player_id"]]
            stats["rounds_played"] += 1
            if row["duration"] is not None:
                stats["total_duration"] += row["duration"]
            if row["position"] is not None:
                # Startbecher: Position 1 immer, Becher 2 laut Runde
                if row["position"] == 1 or row["position"] == cup2_by_round.get(row["round_id"]):
                    stats["start_cups"] += 1

        players_out = [
            s for s in player_stats.values()
            if s["active"] or s["rounds_played"] > 0
        ]
        players_out.sort(key=lambda s: (-s["rounds_played"], s["name"].lower()))

        total_rounds = len(rounds_out)
        for s in players_out:
            s["participation"] = (
                round(100 * s["rounds_played"] / total_rounds) if total_rounds else 0
            )

        # Abend-Zeitraum: erste Runde bis Ende der letzten (bzw. deren Start,
        # solange sie noch läuft)
        first_round_at = rounds[0]["started_at"] if rounds else None
        last_round_at = (
            (rounds[-1]["ended_at"] or rounds[-1]["started_at"]) if rounds else None
        )

        return {
            "evening": {"code": evening["code"], "name": evening.get("name", ""),
                        "created_at": evening["created_at"]},
            "summary": {
                "total_rounds": total_rounds,
                "total_duration": total_duration,
                "longest_round": longest_round,
                "avg_duration": total_duration / timed_rounds if timed_rounds else None,
                "first_round_at": first_round_at,
                "last_round_at": last_round_at,
                "modes": mode_counts,
            },
            "players": players_out,
            "rounds": rounds_out,
        }

    def deactivate_player(self, code, player_id):
        """Deaktiviert einen Spieler (bleibt für Statistik erhalten)"""
        evening = self.get_evening(code)
        if not any(p["id"] == player_id for p in evening["players"]):
            raise PlayerNotFound("Spieler nicht gefunden")
        if evening["open_round"]:
            raise ValueError("Deaktivieren ist nicht möglich, solange eine Runde läuft")

        with db.connect() as conn:
            conn.execute(
                "UPDATE player SET active = 0, position = NULL WHERE id = ?",
                (player_id,),
            )
            # Lücke schließen: verbleibende Positionen auf 1..n verdichten
            _compact_positions(conn, evening["players"], player_id)
        return self.get_evening(code)

    def reactivate_player(self, code, player_id):
        """Reaktiviert einen deaktivierten Spieler; Position hinten anhängen"""
        evening = self.get_evening(code)
        player = next((p for p in evening["players"] if p["id"] == player_id), None)
        if player is None:
            raise PlayerNotFound("Spieler nicht gefunden")
        if player["active"]:
            return evening
        if evening["open_round"]:
            raise ValueError("Reaktivieren ist nicht möglich, solange eine Runde läuft")

        position = _next_position(evening["players"])
        with db.connect() as conn:
            conn.execute(
                "UPDATE player SET active = 1, position = ? WHERE id = ?",
                (position, player_id),
            )
        return self.get_evening(code)

    def delete_player(self, code, player_id):
        """Entfernt einen Spieler hart – nur erlaubt, wenn er nie gespielt hat"""
        evening = self.get_evening(code)
        player = next((p for p in evening["players"] if p["id"] == player_id), None)
        if player is None:
            raise PlayerNotFound("Spieler nicht gefunden")
        if player["played"]:
            raise ValueError(
                f"'{player['name']}' hat schon gespielt und kann nur deaktiviert werden"
            )

        with db.connect() as conn:
            conn.execute("DELETE FROM player WHERE id = ?", (player_id,))
            # Lücke schließen: verbleibende Positionen auf 1..n verdichten
            _compact_positions(conn, evening["players"], player_id)
        return self.get_evening(code)
