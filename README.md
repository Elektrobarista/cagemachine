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

**Hinweis zu pygame:** pygame benötigt möglicherweise zusätzliche System-Bibliotheken:

- **macOS:** Sollte normalerweise ohne zusätzliche Installation funktionieren
- **Linux (Ubuntu/Debian):** 
  ```bash
  sudo apt-get install python3-dev libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
  ```
- **Windows:** Sollte über pip installierbar sein

### 3. Audio-Dateien hinzufügen

Legen Sie Ihre Audio-Dateien in den `static/` Ordner:

- `static/intro.ogg` (oder `intro.mp3`) - Intro-Musik
- `static/loop.ogg` (oder `loop.mp3`) - Loop-Musik für Endlosschleife

**Wichtig für nahtlose Loops:** Die Loop-Datei sollte so geschnitten sein, dass Anfang und Ende nahtlos ineinander übergehen.

## Verwendung

### Server starten

```bash
source .venv/bin/activate   # Falls noch nicht aktiviert
python app.py
```

Der Server läuft dann auf `http://127.0.0.1:8000`

### Im Browser öffnen

Öffnen Sie `http://127.0.0.1:8000` in Ihrem Browser.

### Steuerung

- **Start-Button:** Startet Intro → Loop Sequenz
- **Pause-Button:** Pausiert/Setzt fort
- **Stop-Button:** Stoppt mit Fade-Out (2 Sekunden)

### Hotkeys

- **Space:** Start/Pause (Toggle)
- **S:** Stop

## API-Endpunkte

Die Anwendung stellt folgende REST-API-Endpunkte bereit:

- `POST /api/start` - Startet Audio (Intro → Loop)
- `POST /api/pause` - Pausiert Audio
- `POST /api/resume` - Setzt Audio fort
- `POST /api/stop` - Stoppt Audio mit Fade-Out
- `GET /api/status` - Gibt aktuellen Status zurück

## Technische Details

### Nahtloser Loop

Der AudioController verwendet `pygame.mixer.music.queue()` für nahtlosen Übergang von Intro zu Loop. Ein Thread überwacht den Intro-Progress und bereitet den Loop vor, sodass der Übergang ohne hörbare Unterbrechung erfolgt.

### Fade-Out

Beim Stop wird `pygame.mixer.music.fadeout(2000)` verwendet, um die Musik über 2 Sekunden auszublenden.

### Thread-Safety

Alle Audio-Operationen sind thread-safe mit `threading.Lock()` geschützt.

## Fehlerbehebung

### Audio-Dateien werden nicht gefunden

- Stellen Sie sicher, dass die Dateien im `static/` Ordner liegen
- Dateinamen müssen exakt `intro.ogg`/`intro.mp3` und `loop.ogg`/`loop.mp3` sein
- Prüfen Sie die Dateiberechtigungen

### pygame Installation schlägt fehl

- Installieren Sie die erforderlichen System-Bibliotheken (siehe Installation)
- Versuchen Sie: `pip install --upgrade pygame`

### Kein Audio-Output

- Prüfen Sie die System-Lautstärke
- Stellen Sie sicher, dass pygame korrekt initialisiert wurde
- Prüfen Sie die Audio-Dateien (Format, Codec)

## Lizenz

Siehe LICENSE Datei.
