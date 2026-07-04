from flask import Flask, render_template, jsonify, request
from game_manager import GameManager, EveningNotFound
from utils import format_duration

app = Flask(__name__)

# GameManager-Instanz erstellen (initialisiert die SQLite-DB)
game_manager = GameManager()

# Audio-Events für Statistiken tracken
audio_events = []  # Liste von {"started_at": datetime, "ended_at": datetime, "duration": float}


@app.route("/")
def index():
    """Hauptseite rendern"""
    return render_template("index.html")


@app.route("/abend/<code>")
def evening_page(code):
    """Hauptseite mit vorausgewähltem Abend (Wiederaufnahme per Link)"""
    return render_template("index.html")


@app.route("/statistics")
def statistics():
    """Statistik-Seite rendern"""
    return render_template("statistics.html")


# Audio-API-Endpunkte (stats-only, playback is client-side)
@app.route("/api/start", methods=["POST"])
def start():
    """Tracks audio start for statistics (playback is client-side)"""
    try:
        from datetime import datetime
        # Track Audio-Start für Statistiken
        audio_events.append({"started_at": datetime.now(), "ended_at": None, "duration": None})
        # Return status as if audio started (client handles actual playback)
        return jsonify({"status": "intro", "message": "Intro läuft …"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/start_at", methods=["POST"])
def start_at():
    """Tracks audio start at position for statistics (playback is client-side)"""
    try:
        from datetime import datetime
        data = request.get_json(silent=True) or {}
        position = data.get("position", 0)
        
        # Stelle sicher, dass position eine Zahl ist
        try:
            position = float(position)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "Ungültige Position"}), 400
        
        # Track Audio-Start für Statistiken
        audio_events.append({"started_at": datetime.now(), "ended_at": None, "duration": None})
        # Return status as if audio started (client handles actual playback)
        return jsonify({"status": "intro", "message": "Intro läuft …"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/pause", methods=["POST"])
def pause():
    """Tracks audio pause (playback is client-side)"""
    try:
        # Return status as if audio paused (client handles actual playback)
        return jsonify({"status": "paused", "message": "pausiert"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/resume", methods=["POST"])
def resume():
    """Tracks audio resume (playback is client-side)"""
    try:
        # Return status as if audio resumed (client handles actual playback)
        return jsonify({"status": "intro", "message": "Intro läuft …"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/stop", methods=["POST"])
def stop():
    """Tracks audio stop for statistics (playback is client-side)"""
    try:
        from datetime import datetime
        from utils import calculate_duration
        # Track Audio-Ende für Statistiken
        if audio_events:
            last_event = audio_events[-1]
            if last_event["ended_at"] is None:
                last_event["ended_at"] = datetime.now()
                if last_event["started_at"]:
                    last_event["duration"] = calculate_duration(last_event["started_at"], last_event["ended_at"])
        # Return status as if audio stopped (client handles actual playback)
        return jsonify({"status": "stopped", "message": "bereit"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/status", methods=["GET"])
def status():
    """Returns default status (client handles actual playback)"""
    try:
        # Return default stopped status (client manages actual state)
        return jsonify({"status": "stopped", "message": "bereit"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/position", methods=["GET"])
def position():
    """Returns default position (client handles actual playback)"""
    try:
        # Return default values (client manages actual position)
        return jsonify({
            "position": 0,
            "duration": None,
            "intro_duration": None,
            "loop_duration": None,
            "is_looping": False
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


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


# Statistik-API
@app.route("/api/statistics/audio", methods=["GET"])
def get_statistics_audio():
    """Gibt Audio-Statistiken zurück"""
    try:
        from utils import calculate_duration
        
        # Berechne Statistiken aus audio_events
        total_starts = len(audio_events)
        total_duration = 0.0
        completed_events = []
        
        for event in audio_events:
            if event["duration"] is not None:
                total_duration += event["duration"]
                completed_events.append({
                    "started_at": event["started_at"].isoformat() if event["started_at"] else None,
                    "ended_at": event["ended_at"].isoformat() if event["ended_at"] else None,
                    "duration": event["duration"],
                    "duration_formatted": format_duration(event["duration"])
                })
        
        return jsonify({
            "total_starts": total_starts,
            "total_duration": total_duration,
            "total_duration_formatted": format_duration(total_duration),
            "completed_events": completed_events
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    import os
    # In Docker auf 0.0.0.0 laufen lassen, lokal auf 127.0.0.1
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "3000"))
    app.run(host=host, port=port, debug=False)
