import csv
import io
import os
import uuid
import zipfile

from flask import Flask, render_template, jsonify, request, make_response, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from game_manager import GameManager, EveningNotFound, GAME_MODES, EVENING_SETTINGS
from utils import format_duration

app = Flask(__name__)

# GameManager-Instanz erstellen (initialisiert die SQLite-DB)
game_manager = GameManager()

# Rate-Limiting pro IP. Der Abend-Code ist der einzige Zugangsschutz; ohne
# Drosselung ließe sich der 4-Zeichen-Raum durchprobieren (Enumeration).
# In-Memory-Speicher genügt für die Single-Prozess-Instanz.
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["600 per hour"],
    storage_uri="memory://",
)

# Codes probieren = teuer machen; Limit per Env-Var übersteuerbar (Tests: hoch)
CODE_LOOKUP_LIMIT = os.getenv("CODE_LOOKUP_LIMIT", "20 per minute")

VISITOR_COOKIE = "cagemachine_visitor"


@app.errorhandler(429)
def ratelimit_handler(e):
    """Rate-Limit als JSON, damit das Frontend eine saubere Fehlermeldung bekommt"""
    return jsonify({"error": "Zu viele Anfragen – bitte kurz warten."}), 429


def _visitor_response(payload, evening_code):
    """Antwort mit Geräte-Cookie; merkt den Abend für die Übersicht vor.
    Das Cookie identifiziert nur das Gerät – der Abend-Code bleibt der Schlüssel."""
    visitor_id = request.cookies.get(VISITOR_COOKIE) or str(uuid.uuid4())
    game_manager.record_access(evening_code, visitor_id)
    response = make_response(jsonify(payload), 200)
    response.set_cookie(
        VISITOR_COOKIE, visitor_id,
        max_age=365 * 24 * 3600, httponly=True, samesite="Lax",
    )
    return response


@app.route("/")
def index():
    """Hauptseite rendern"""
    return render_template("index.html")


@app.route("/abend/<code>")
def evening_page(code):
    """Hauptseite mit vorausgewähltem Abend (Wiederaufnahme per Link)"""
    return render_template("index.html")


@app.route("/statistics")
@app.route("/statistics/<code>")
def statistics(code=None):
    """Statistik-Seite rendern (Code kommt clientseitig aus der URL)"""
    return render_template("statistics.html")


@app.route("/api/modes", methods=["GET"])
def get_modes():
    """Verfügbare Spielmodi (das UI rendert die Auswahl daraus)"""
    return jsonify({
        "modes": [{"id": mode_id, **mode} for mode_id, mode in GAME_MODES.items()]
    }), 200


# Evening-API-Endpunkte
@app.route("/api/evening", methods=["POST"])
def create_evening():
    """Erstellt einen neuen Abend und liefert dessen Code"""
    try:
        evening = game_manager.create_evening()
        return _visitor_response({"evening": evening}, evening["code"])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evening/<code>", methods=["GET"])
@limiter.limit(lambda: CODE_LOOKUP_LIMIT)
def get_evening(code):
    """Lädt einen Abend über seinen Code (Wiederaufnahme)"""
    try:
        evening = game_manager.get_evening(code)
        return _visitor_response({"evening": evening}, evening["code"])
    except EveningNotFound as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evenings", methods=["GET"])
def list_evenings():
    """Abende, die dieses Gerät kennt (für die Statistik-Übersicht)"""
    try:
        visitor_id = request.cookies.get(VISITOR_COOKIE)
        evenings = game_manager.list_evenings(visitor_id) if visitor_id else []
        return jsonify({"evenings": evenings}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evening/<code>/players", methods=["POST"])
def add_player(code):
    """Fügt einen Spieler zum Abend hinzu"""
    try:
        data = request.get_json(silent=True) or {}
        player_name = data.get("name", "").strip()

        if not player_name:
            return jsonify({"error": "Spielername darf nicht leer sein"}), 400
        if len(player_name) > 50:
            return jsonify({"error": "Spielername darf maximal 50 Zeichen lang sein"}), 400

        evening = game_manager.add_player(code, player_name)
        return jsonify({"evening": evening}), 200
    except EveningNotFound as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evening/<code>/draw", methods=["POST"])
def draw_positions(code):
    """Lost die Sitzpositionen aus (1 = Startbecher)"""
    try:
        evening = game_manager.draw_positions(code)
        return jsonify({"evening": evening}), 200
    except EveningNotFound as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evening/<code>/players/<player_id>", methods=["DELETE"])
def remove_player(code, player_id):
    """Deaktiviert einen Spieler (bleibt für Statistik erhalten)"""
    try:
        evening = game_manager.deactivate_player(code, player_id)
        return jsonify({"evening": evening}), 200
    except EveningNotFound as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evening/<code>/settings", methods=["POST"])
def update_settings(code):
    """Abend-Einstellungen ändern (random_bullrush, draw_on_start)"""
    try:
        data = request.get_json(silent=True) or {}
        requested = {key: data[key] for key in EVENING_SETTINGS if key in data}
        if not requested:
            return jsonify({"error": f"Erwartet eine Einstellung aus: {', '.join(EVENING_SETTINGS)}"}), 400
        for key, enabled in requested.items():
            if not isinstance(enabled, bool):
                return jsonify({"error": f"{key} muss true oder false sein"}), 400

        for key, enabled in requested.items():
            evening = game_manager.set_setting(code, key, enabled)
        return jsonify({"evening": evening}), 200
    except EveningNotFound as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Runden-API-Endpunkte
@app.route("/api/evening/<code>/round/start", methods=["POST"])
def start_round(code):
    """Startet eine Runde mit Snapshot der aktiven Spieler"""
    try:
        data = request.get_json(silent=True) or {}
        mode = data.get("mode") or "classic"
        evening = game_manager.start_round(code, mode=mode)
        return jsonify({"evening": evening}), 200
    except EveningNotFound as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evening/<code>/round/end", methods=["POST"])
def end_round(code):
    """Beendet die laufende Runde"""
    try:
        evening = game_manager.end_round(code)
        return jsonify({"evening": evening}), 200
    except EveningNotFound as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Statistik-API
@app.route("/api/evening/<code>/statistics", methods=["GET"])
@limiter.limit(lambda: CODE_LOOKUP_LIMIT)
def get_evening_statistics(code):
    """Statistik eines Abends: Zusammenfassung, Spieler-Auswertung, Rundenliste"""
    try:
        stats = game_manager.get_statistics(code)

        stats["summary"]["total_duration_formatted"] = format_duration(stats["summary"]["total_duration"])
        stats["summary"]["longest_round_formatted"] = format_duration(stats["summary"]["longest_round"])
        stats["summary"]["avg_duration_formatted"] = format_duration(stats["summary"]["avg_duration"])
        for player in stats["players"]:
            player["total_duration_formatted"] = format_duration(player["total_duration"])
        for r in stats["rounds"]:
            r["duration_formatted"] = format_duration(r["duration"]) if r["duration"] is not None else "–"

        # Auch der Statistik-Aufruf per Code zählt als Geräte-Zugriff
        return _visitor_response(stats, stats["evening"]["code"])
    except EveningNotFound as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _csv_bytes(header, rows):
    """CSV als Bytes; Komma-getrennt + UTF-8-BOM (Excel erkennt Umlaute).
    Werte mit Komma werden vom csv-Modul automatisch gequotet."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


@app.route("/api/evening/<code>/export", methods=["GET"])
@limiter.limit(lambda: CODE_LOOKUP_LIMIT)
def export_statistics(code):
    """Abend-Statistik als ZIP mit zwei CSVs (Spieler-Auswertung + Rundenliste)"""
    try:
        stats = game_manager.get_statistics(code)
        code_up = stats["evening"]["code"]

        players_csv = _csv_bytes(
            ["Name", "Runden", "Spielzeit (Sek.)", "Spielzeit",
             "Startbecher", "Teilnahme (%)", "Status"],
            [[p["name"], p["rounds_played"], round(p["total_duration"]),
              format_duration(p["total_duration"]), p["start_cups"],
              p["participation"], "aktiv" if p["active"] else "entfernt"]
             for p in stats["players"]],
        )
        rounds_csv = _csv_bytes(
            ["Nr", "Gestartet am", "Modus", "Dauer (Sek.)", "Dauer", "Mitspieler"],
            [[i, r["started_at"],
              GAME_MODES.get(r["mode"], {}).get("label", r["mode"]),
              round(r["duration"]) if r["duration"] is not None else "",
              format_duration(r["duration"]) if r["duration"] is not None else "",
              r["player_count"]]
             for i, r in enumerate(stats["rounds"], start=1)],
        )

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"spieler_{code_up}.csv", players_csv)
            zf.writestr(f"runden_{code_up}.csv", rounds_csv)
        mem.seek(0)

        return send_file(
            mem, mimetype="application/zip", as_attachment=True,
            download_name=f"cagemachine_{code_up}.zip",
        )
    except EveningNotFound as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    import os
    # In Docker auf 0.0.0.0 laufen lassen, lokal auf 127.0.0.1
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "3000"))
    app.run(host=host, port=port, debug=False)
