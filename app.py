from flask import Flask, render_template, jsonify, request
from audio_controller import AudioController
from config import get_audio_paths
from game_manager import GameManager
from utils import format_duration

app = Flask(__name__)

# AudioController-Instanz erstellen
intro_path, loop_path = get_audio_paths()
audio = AudioController(intro_path=intro_path, loop_path=loop_path)

# GameManager-Instanz erstellen
game_manager = GameManager()

# Audio-Events für Statistiken tracken
audio_events = []  # Liste von {"started_at": datetime, "ended_at": datetime, "duration": float}


@app.route("/")
def index():
    """Hauptseite rendern"""
    return render_template("index.html")


@app.route("/statistics")
def statistics():
    """Statistik-Seite rendern"""
    return render_template("statistics.html")


# Audio-API-Endpunkte
@app.route("/api/start", methods=["POST"])
def start():
    """Startet Audio (Intro → Loop)"""
    try:
        from datetime import datetime
        audio.start()
        status = audio.get_status()
        # Track Audio-Start für Statistiken
        audio_events.append({"started_at": datetime.now(), "ended_at": None, "duration": None})
        return jsonify(status), 200
    except FileNotFoundError as e:
        return jsonify({"status": "error", "message": str(e)}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/start_at", methods=["POST"])
def start_at():
    """Startet Audio ab einer bestimmten Position (in Sekunden)"""
    try:
        from datetime import datetime
        data = request.get_json() or {}
        position = data.get("position", 0)
        
        # Stelle sicher, dass position eine Zahl ist
        try:
            position = float(position)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "Ungültige Position"}), 400
        
        audio.start_at_position(position)
        status = audio.get_status()
        # Track Audio-Start für Statistiken
        audio_events.append({"started_at": datetime.now(), "ended_at": None, "duration": None})
        return jsonify(status), 200
    except FileNotFoundError as e:
        return jsonify({"status": "error", "message": str(e)}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/pause", methods=["POST"])
def pause():
    """Pausiert Audio"""
    try:
        audio.pause()
        status = audio.get_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/resume", methods=["POST"])
def resume():
    """Setzt Audio fort"""
    try:
        audio.resume()
        status = audio.get_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/stop", methods=["POST"])
def stop():
    """Stoppt Audio mit Fade-Out"""
    try:
        from datetime import datetime
        from utils import calculate_duration
        audio.stop()
        status = audio.get_status()
        # Track Audio-Ende für Statistiken
        if audio_events:
            last_event = audio_events[-1]
            if last_event["ended_at"] is None:
                last_event["ended_at"] = datetime.now()
                if last_event["started_at"]:
                    last_event["duration"] = calculate_duration(last_event["started_at"], last_event["ended_at"])
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/status", methods=["GET"])
def status():
    """Gibt aktuellen Status zurück"""
    try:
        status = audio.get_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/position", methods=["GET"])
def position():
    """Gibt aktuelle Position zurück"""
    try:
        pos = audio.get_position()
        duration = audio.get_duration()
        status_data = audio.get_status()
        
        return jsonify({
            "position": pos,
            "duration": duration,
            "intro_duration": audio.intro_duration,
            "loop_duration": audio.loop_duration,
            "is_looping": status_data["status"] == "looping"
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


# Evening-API-Endpunkte
@app.route("/api/evening/create", methods=["POST"])
def create_evening():
    """Erstellt einen neuen Abend"""
    try:
        evening = game_manager.create_evening()
        return jsonify({"evening": evening.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evening/current", methods=["GET"])
def get_current_evening():
    """Gibt den aktuellen Abend zurück"""
    try:
        evening = game_manager.get_current_evening()
        if evening:
            return jsonify({"evening": evening.to_dict()}), 200
        return jsonify({"evening": None}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evening/<evening_id>", methods=["GET"])
def get_evening(evening_id):
    """Gibt einen spezifischen Abend zurück"""
    try:
        evening = game_manager.get_evening(evening_id)
        if evening:
            return jsonify({"evening": evening.to_dict()}), 200
        return jsonify({"error": "Abend nicht gefunden"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evening/<evening_id>/sessions", methods=["GET"])
def get_sessions_by_evening(evening_id):
    """Gibt alle Sessions eines Abends zurück"""
    try:
        sessions = game_manager.get_sessions_by_evening(evening_id)
        return jsonify({"sessions": [s.to_dict() for s in sessions]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Session-API-Endpunkte
@app.route("/api/session/create", methods=["POST"])
def create_session():
    """Erstellt eine neue Session"""
    try:
        data = request.get_json() or {}
        evening_id = data.get("evening_id")
        session = game_manager.create_session(evening_id=evening_id)
        return jsonify({"session_id": session.id, "session": session.to_dict()}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/session/current", methods=["GET"])
def get_current_session():
    """Gibt die aktuelle Session zurück (für zukünftige Erweiterungen)"""
    # Aktuell gibt es keine "aktuelle Session" - könnte später implementiert werden
    return jsonify({"session": None}), 200


@app.route("/api/session/<session_id>", methods=["GET"])
def get_session(session_id):
    """Gibt eine Session zurück"""
    try:
        session = game_manager.get_session(session_id)
        if session:
            return jsonify({"session": session.to_dict()}), 200
        return jsonify({"error": "Session nicht gefunden"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/session/<session_id>/players", methods=["POST"])
def add_player(session_id):
    """Fügt einen Spieler zur Session hinzu"""
    try:
        data = request.get_json() or {}
        player_name = data.get("name", "").strip()
        
        if not player_name:
            return jsonify({"error": "Spielername darf nicht leer sein"}), 400
        
        session = game_manager.add_player_to_session(session_id, player_name)
        return jsonify({"session": session.to_dict()}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/session/<session_id>/players/<player_id>", methods=["DELETE"])
def remove_player(session_id, player_id):
    """Entfernt einen Spieler aus der Session"""
    try:
        session = game_manager.remove_player_from_session(session_id, player_id)
        return jsonify({"session": session.to_dict()}), 200
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
