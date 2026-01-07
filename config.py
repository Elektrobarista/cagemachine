"""Konfiguration für die Rage Cage Anwendung"""
import os

# Timer-Konfiguration
# Kann über Umgebungsvariable RAGE_CAGE_TEST_MODE überschrieben werden
# Setze auf False für Produktion (5-20 Minuten Timer)
# Setze auf True für Tests (10-20 Sekunden Timer)
# Default: True (für Tests)
TEST_MODE = os.getenv("RAGE_CAGE_TEST_MODE", "True").lower() in ("true", "1", "yes")

# Spielmodi-Konfiguration
GAME_MODES = {
    "RND": {
        "name": "Random Timer",
        "rounds": 5,
        "description": "Zufällige Timer zwischen den Runden"
    },
    "SOLI": {
        "name": "Soli",
        "rounds": None,  # Wird dynamisch basierend auf Spieleranzahl gesetzt
        "description": "Eine Runde pro Spieler, geheime Positionen"
    },
    "THUNDERSTORM": {
        "name": "Thunderstorm",
        "rounds": 4,
        "description": "4 Back to Back Runden"
    }
}


def get_audio_paths():
    """
    Gibt die Audio-Pfade zurück mit Fallback-Logik (.ogg → .mp3)
    
    Returns:
        tuple: (intro_path, loop_path)
    """
    intro_path = "static/RageCage_Intro.ogg"
    loop_path = "static/RageCage_Gas.ogg"
    
    # Fallback zu .mp3 wenn .ogg nicht existiert
    if not os.path.exists(intro_path):
        intro_path = "static/RageCage_Intro.mp3"
    if not os.path.exists(loop_path):
        loop_path = "static/RageCage_Gas.mp3"
    
    return intro_path, loop_path

