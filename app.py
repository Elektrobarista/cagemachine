from flask import Flask, render_template, jsonify, request
from audio_controller import AudioController
import os

app = Flask(__name__)

# AudioController-Instanz erstellen
# Prüfe ob .ogg oder .mp3 Dateien vorhanden sind
intro_path = "static/RageCage_Intro.ogg"
loop_path = "static/RageCage_Gas.ogg"

if not os.path.exists(intro_path):
    # Versuche .mp3 als Fallback
    intro_path = "static/RageCage_Intro.mp3"
if not os.path.exists(loop_path):
    loop_path = "static/RageCage_Gas.mp3"

audio = AudioController(intro_path=intro_path, loop_path=loop_path)


@app.route("/")
def index():
    """Hauptseite rendern"""
    return render_template("index.html")


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




if __name__ == "__main__":
    # host=0.0.0.0, damit es auch im WLAN auf anderen Geräten geht (optional)
    app.run(host="127.0.0.1", port=8000, debug=False)

