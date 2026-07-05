from flask import Flask, render_template, jsonify, request
from game_manager import GameManager, EveningNotFound
from utils import format_duration

app = Flask(__name__)

# GameManager-Instanz erstellen (initialisiert die SQLite-DB)
game_manager = GameManager()


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


# Evening-API-Endpunkte
@app.route("/api/evening", methods=["POST"])
def create_evening():
    """Erstellt einen neuen Abend und liefert dessen Code"""
    try:
        evening = game_manager.create_evening()
        return jsonify({"evening": evening}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evening/<code>", methods=["GET"])
def get_evening(code):
    """Lädt einen Abend über seinen Code (Wiederaufnahme)"""
    try:
        evening = game_manager.get_evening(code)
        return jsonify({"evening": evening}), 200
    except EveningNotFound as e:
        return jsonify({"error": str(e)}), 404
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
def get_evening_statistics(code):
    """Statistik eines Abends: Zusammenfassung, Spieler-Auswertung, Rundenliste"""
    try:
        stats = game_manager.get_statistics(code)

        stats["summary"]["total_duration_formatted"] = format_duration(stats["summary"]["total_duration"])
        stats["summary"]["longest_round_formatted"] = format_duration(stats["summary"]["longest_round"])
        for player in stats["players"]:
            player["total_duration_formatted"] = format_duration(player["total_duration"])
        for r in stats["rounds"]:
            r["duration_formatted"] = format_duration(r["duration"]) if r["duration"] is not None else "–"

        return jsonify(stats), 200
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
