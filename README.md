# cagemachine

## Installation

### 1. Python Virtual Environment erstellen

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Dependencies installieren

```bash
pip install -r requirements.txt
```

### 3. Audio-Datei

Die Wiedergabe nutzt eine einzige zusammengeschnittene Datei:

- `static/Cage-Loop-concat.ogg` - Intro + Loop in einer Datei

Die Loop-Punkte (`loopStart`/`loopEnd`) sind in `templates/index.html` fest auf diese Datei abgestimmt. Wird die Datei ausgetauscht, müssen die Timecodes dort angepasst werden.

## Verwendung

### Server starten

```bash
source .venv/bin/activate   # Falls noch nicht aktiviert
python app.py
```

Der Server läuft dann auf `http://127.0.0.1:3000` (Host/Port über `FLASK_HOST`/`FLASK_PORT` konfigurierbar).

Alternativ mit Docker:

```bash
docker compose up
```

### Im Browser öffnen

Öffnen Sie `http://127.0.0.1:3000` in Ihrem Browser.

### Steuerung

- **Start-Button:** Startet Intro → Loop Sequenz
- **Pause-Button:** Pausiert/Setzt fort
- **Stop-Button:** Stoppt mit Fade-Out (2 Sekunden)

### Hotkeys

- **Space:** Start/Pause (Toggle)
- **S:** Stop

## API-Endpunkte

Die Wiedergabe läuft clientseitig im Browser; die Audio-Endpunkte dienen dem Statistik-Tracking:

- `POST /api/start` - Trackt Audio-Start
- `POST /api/pause` - Trackt Pause
- `POST /api/resume` - Trackt Fortsetzen
- `POST /api/stop` - Trackt Stop
- `GET /api/status` - Gibt aktuellen Status zurück
- `GET /api/statistics/audio` - Gibt Audio-Statistiken zurück

Dazu kommen die Endpunkte des GameManagers für Abende, Runden und Spieler (siehe `app.py`).

## Technische Details

### Nahtloser Loop

Die Audio-Wiedergabe läuft clientseitig im Browser über die Web Audio API. Eine zusammengeschnittene Datei (Intro + Loop) wird als `AudioBuffer` geladen; das Looping erfolgt sample-genau über `loop`, `loopStart` und `loopEnd` des `AudioBufferSourceNode`. Die Server-API dient nur noch dem Statistik-Tracking.

## Fehlerbehebung

### Audio-Datei wird nicht gefunden

- Stellen Sie sicher, dass `static/Cage-Loop-concat.ogg` existiert
- Prüfen Sie die Dateiberechtigungen

### Kein Audio-Output

- Prüfen Sie die System-Lautstärke
- Prüfen Sie die Audio-Dateien (Format, Codec)
- Die Wiedergabe startet erst nach einer Nutzer-Interaktion (Browser-Autoplay-Richtlinie)

## Lizenz

Siehe LICENSE Datei.
