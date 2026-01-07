from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from audio_controller import AudioController
from config import get_audio_paths, GAME_MODES
from game_manager import GameManager
from utils import format_duration, get_game_mode_name
from timer_service import TimerService

# Lade Umgebungsvariablen aus .env Datei
load_dotenv()

app = Flask(__name__)

# AudioController-Instanz erstellen
intro_path, loop_path = get_audio_paths()
audio = AudioController(intro_path=intro_path, loop_path=loop_path)

# GameManager-Instanz erstellen
game_manager = GameManager()

# TimerService-Instanz erstellen
timer_service = TimerService(audio)
timer_service.start()  # Starte Timer-Service


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
        audio.start()
        status = audio.get_status()
        return jsonify(status), 200
    except FileNotFoundError as e:
        return jsonify({"status": "error", "message": str(e)}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


@app.route("/api/start_at", methods=["POST"])
def start_at():
    """Startet Audio ab einer bestimmten Position (in Sekunden)"""
    try:
        data = request.get_json() or {}
        position = data.get("position", 0)
        
        # Stelle sicher, dass position eine Zahl ist
        try:
            position = float(position)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "Ungültige Position"}), 400
        
        audio.start_at_position(position)
        status = audio.get_status()
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
        audio.stop()
        status = audio.get_status()
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


# Game-API-Endpunkte
@app.route("/api/game/start", methods=["POST"])
def start_game():
    """Startet ein neues Spiel im aktuellen Abend"""
    try:
        data = request.get_json() or {}
        game_mode = data.get("game_mode", "").upper()
        player_count = data.get("player_count", 0)
        session_id = data.get("session_id")
        
        if not game_mode:
            return jsonify({"error": "Spielmodus muss angegeben werden"}), 400
        
        if game_mode not in GAME_MODES:
            return jsonify({"error": "Ungültiger Spielmodus"}), 400
        
        evening = game_manager.get_current_evening()
        if not evening:
            return jsonify({"error": "Kein aktiver Abend. Bitte erst einen Abend erstellen."}), 400
        
        game = game_manager.start_game(evening.id, game_mode, player_count, session_id)
        return jsonify({"game": game.to_dict()}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/game/<game_id>/end", methods=["POST"])
def end_game(game_id):
    """Beendet ein Spiel manuell"""
    try:
        # Bricht Timer ab, falls aktiv (wichtig: vor dem Beenden des Spiels)
        timer_service.cancel_timer(game_id)
        
        # Beende aktive Runde, falls vorhanden
        try:
            current_round = game_manager.get_current_round(game_id)
            if current_round:
                game_manager.end_round(game_id)
        except ValueError:
            # Keine aktive Runde vorhanden, das ist ok
            pass
        
        game = game_manager.end_game(game_id)
        return jsonify({"game": game.to_dict()}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/game/<game_id>/complete", methods=["POST"])
def complete_game(game_id):
    """Markiert ein Spiel als abgeschlossen (alle Runden gespielt)"""
    try:
        game = game_manager.complete_game(game_id)
        return jsonify({"game": game.to_dict()}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/game/current", methods=["GET"])
def get_current_game():
    """Gibt das aktuelle aktive Spiel zurück"""
    try:
        evening = game_manager.get_current_evening()
        if not evening:
            return jsonify({"game": None}), 200
        
        game = game_manager.get_current_game(evening.id)
        if game:
            return jsonify({"game": game.to_dict()}), 200
        return jsonify({"game": None}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/game/latest", methods=["GET"])
def get_latest_game():
    """Gibt das letzte Spiel eines Abends zurück (auch wenn beendet)"""
    try:
        evening = game_manager.get_current_evening()
        if not evening:
            return jsonify({"game": None}), 200
        
        game = game_manager.get_latest_game(evening.id)
        if game:
            return jsonify({"game": game.to_dict()}), 200
        return jsonify({"game": None}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/evening/<evening_id>/games", methods=["GET"])
def get_games_by_evening(evening_id):
    """Gibt alle Spiele eines Abends zurück"""
    try:
        games = game_manager.get_games_by_evening(evening_id)
        return jsonify({"games": [g.to_dict() for g in games]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Session-API-Endpunkte
@app.route("/api/session/create", methods=["POST"])
def create_session():
    """Erstellt eine neue Session"""
    try:
        session = game_manager.create_session()
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


@app.route("/api/session/<session_id>/game-mode", methods=["POST"])
def set_session_game_mode(session_id):
    """Setzt den Spielmodus für eine Session"""
    try:
        data = request.get_json() or {}
        game_mode = data.get("game_mode", "").upper()
        
        if not game_mode:
            return jsonify({"error": "Spielmodus muss angegeben werden"}), 400
        
        session = game_manager.set_session_game_mode(session_id, game_mode)
        return jsonify({"session": session.to_dict(), "game_mode_info": GAME_MODES[game_mode]}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Game-Modes-API
@app.route("/api/game-modes", methods=["GET"])
def get_game_modes():
    """Gibt alle verfügbaren Spielmodi zurück"""
    return jsonify({"game_modes": GAME_MODES}), 200


# Statistik-API
@app.route("/api/statistics/games", methods=["GET"])
def get_statistics_games():
    """Gibt alle abgeschlossenen Spiele für die Statistik zurück"""
    try:
        games = game_manager.get_completed_games()
        
        # Formatiere Spiele für Frontend
        formatted_games = []
        total_duration = 0.0
        
        for game in games:
            formatted_games.append({
                "id": game.id,
                "game_mode": game.game_mode,
                "game_mode_name": get_game_mode_name(game.game_mode),
                "duration": game.duration,
                "duration_formatted": format_duration(game.duration) if game.duration else "00:00",
                "ended_at": game.ended_at.isoformat() if game.ended_at else None,
                "total_rounds": game.total_rounds
            })
            if game.duration:
                total_duration += game.duration
        
        return jsonify({
            "games": formatted_games,
            "total_games": len(formatted_games),
            "total_duration": total_duration,
            "total_duration_formatted": format_duration(total_duration)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Round-API-Endpunkte
@app.route("/api/game/<game_id>/round/start", methods=["POST"])
def start_round(game_id):
    """Startet eine neue Runde"""
    try:
        round_obj = game_manager.start_round(game_id)
        
        # KEIN Timer beim Rundenstart - Timer wird erst nach Rundenende gesetzt
        # (Erste Runde hat keinen Timer, Timer startet erst nach Ende der ersten Runde)
        
        return jsonify({"round": round_obj.to_dict()}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/game/<game_id>/round/end", methods=["POST"])
def end_round(game_id):
    """Beendet die aktuelle Runde"""
    try:
        # Bricht Timer ab, falls aktiv (wichtig: vor dem Beenden der Runde)
        timer_service.cancel_timer(game_id)
        
        # Beende Runde (berechnet Timer-Dauer für nächste Runde, falls RND-Modus)
        round_obj = game_manager.end_round(game_id)
        
        # Setze Timer, falls vorhanden (nur im RND-Modus, nach Rundenende)
        if round_obj.timer_duration:
            timer_service.set_timer(game_id, round_obj.timer_duration)
        
        return jsonify({"round": round_obj.to_dict()}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/game/<game_id>/round/current", methods=["GET"])
def get_current_round(game_id):
    """Gibt die aktuelle Runde zurück"""
    try:
        round_obj = game_manager.get_current_round(game_id)
        if round_obj:
            # Füge verbleibende Timer-Zeit hinzu
            remaining_time = timer_service.get_remaining_time(game_id)
            round_dict = round_obj.to_dict()
            round_dict["timer_remaining"] = remaining_time
            return jsonify({"round": round_dict}), 200
        return jsonify({"round": None}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/game/<game_id>/rounds", methods=["GET"])
def get_rounds(game_id):
    """Gibt alle Runden eines Spiels zurück"""
    try:
        rounds = game_manager.get_rounds_by_game(game_id)
        return jsonify({"rounds": [r.to_dict() for r in rounds]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/game/<game_id>/timer/remaining", methods=["GET"])
def get_timer_remaining(game_id):
    """Gibt die verbleibende Timer-Zeit zurück"""
    try:
        remaining = timer_service.get_remaining_time(game_id)
        if remaining is not None:
            return jsonify({"remaining": remaining}), 200
        return jsonify({"remaining": None}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
