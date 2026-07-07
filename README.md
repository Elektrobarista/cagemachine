# cagemachine

Webapp für Rage-Cage-Abende: Musik (Intro + nahtloser Endlos-Loop), Spielerverwaltung
mit Sitzplatz-Auslosung und Runden-Statistik pro Abend. Ein Abend ist über einen kurzen
Code jederzeit wiederaufnehmbar – die App muss zwischendurch nicht offen bleiben.
Mehrere Gruppen können parallel mit eigenen Abenden spielen.

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

**Die Audio-Datei liegt nicht im Repository** (zu groß) – nach einem frischen
Clone muss sie von Hand nach `static/` kopiert werden, sonst startet keine Musik.

Die Loop-Punkte sind in `game_manager.py` (`DEFAULT_AUDIO`) auf diese Datei abgestimmt. Wird die Datei ausgetauscht, müssen die Timecodes dort angepasst werden.

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

Abende, Spieler und Runden liegen in einer SQLite-Datei (`data/cagemachine.db`,
über `DB_PATH` konfigurierbar; im Docker-Setup als Volume gemountet).

### Ablauf eines Abends

1. **Abend starten:** "Neuen Abend starten" erzeugt einen 4-stelligen **Abend-Code**
   (z. B. `K7FQ`). Mit dem Code lässt sich der Abend jederzeit fortsetzen – per
   Eingabefeld oder direkt über den Link `/abend/<code>`.
2. **Spieler hinzufügen** und mit **"Positionen auslosen"** die Sitzreihenfolge
   bestimmen: Position 1 sitzt am Startbecher (🍺). Nachzügler werden hinten
   angehängt; wird ein Spieler entfernt, rücken die anderen auf.
3. **Spielmodus wählen** (Classic oder Bullrush) und die Musik starten.
   Jeder Musik-Start ist eine Runde: Wer gerade mitspielt, wird mit Position
   festgehalten und in der Statistik gezählt. Pause zählt nicht als Rundenende.
   **Bullrush** = 3 Runden direkt hintereinander: Nach jedem Stop startet nach
   kurzem Moment automatisch das nächste Intro; zweimal Stop hintereinander
   bricht den ganzen Bullrush ab. Optional lässt sich pro Abend der
   **Zufalls-Bullrush** einschalten (🐂-Toggle): Dann kann jede normale Runde
   überraschend zum Bullrush werden – höchstens einmal alle 3,5 Stunden pro
   Abend (Standard-Chance 15 %; über die Env-Vars `BULLRUSH_CHANCE` und
   `BULLRUSH_COOLDOWN` einstellbar).
4. **Statistik** unter `/statistics/<code>`: Runden und Spielzeit pro Spieler,
   Rundenliste mit Modus und Dauer – auch Tage später noch abrufbar.

### Steuerung

- **Start-Button:** Startet die Musik im gewählten Modus (= Rundenstart)
- **Pause-Button:** Pausiert/Setzt fort (Runde läuft weiter)
- **Stop-Button:** Stoppt die Musik (= Rundenende)
- **Debug-Headstarts** (hinter "Ich weiß was ich mache!"): springen nur in der
  Audio-Datei, starten keine Runde und tauchen nicht in der Statistik auf

### Hotkeys

- **Space:** Start/Pause (Toggle)
- **S:** Stop

## API-Endpunkte

Die Wiedergabe läuft clientseitig im Browser (Web Audio API); die API verwaltet
Abende, Spieler, Runden und Statistik:

- `POST /api/evening` - Abend anlegen, liefert den Code
- `GET /api/evening/<code>` - Abend laden (Spieler, Positionen, laufende Runde)
- `POST /api/evening/<code>/players` - Spieler hinzufügen (`{"name": "..."}`)
- `DELETE /api/evening/<code>/players/<id>` - Spieler entfernen (bleibt in alten Runden erhalten)
- `POST /api/evening/<code>/draw` - Sitzpositionen auslosen (1 = Startbecher)
- `POST /api/evening/<code>/settings` - Abend-Einstellungen (`{"random_bullrush": true}`)
- `POST /api/evening/<code>/round/start` - Runde starten (`{"mode": "classic"}`, Spieler-Snapshot)
- `POST /api/evening/<code>/round/end` - Laufende Runde beenden
- `GET /api/evening/<code>/statistics` - Abend-Statistik (Spieler-Auswertung, Rundenliste)
- `GET /api/modes` - Verfügbare Spielmodi

Integrationstests: Server starten und `python test_app.py` ausführen
(`BASE_URL` per Umgebungsvariable anpassbar).

## Technische Details

### Nahtloser Loop

Die Audio-Wiedergabe läuft clientseitig im Browser über die Web Audio API. Eine zusammengeschnittene Datei (Intro + Loop) wird als `AudioBuffer` geladen; das Looping erfolgt sample-genau über `loop`, `loopStart` und `loopEnd` des `AudioBufferSourceNode`.

### Runden-Tracking

Musik-Start und -Stop melden Rundenstart/-ende an den Server. Jede Runde speichert
einen Snapshot der aktiven Spieler samt Positionen – die Statistik stimmt also auch,
wenn Spieler später dazukommen oder früher gehen. Verwaiste Runden (Browser geschlossen
statt Stop) werden beim nächsten Start automatisch geschlossen; unplausibel lange
Runden (> 2 h) fließen nicht in die Zeitstatistik ein.

### Spielmodi

Die Modi sind zentral in `game_manager.py` (`GAME_MODES`) definiert – ein neuer Modus
ist ein Dict-Eintrag, das UI rendert die Auswahl dynamisch über `/api/modes`. Pro Modus
konfigurierbar:

- `label` / `description` - Anzeige und Tooltip im UI
- `start_position` - Einstiegspunkt in der Audio-Datei (Sekunden, 0 = von vorn)
- `time_limit` - Runde endet automatisch nach X Sekunden (`None` = kein Limit;
  Pause hält das Limit an)
- `round_count` - Anzahl direkt aufeinanderfolgender Runden (1 = normale
  Einzelrunde, Bullrush nutzt 3)
- `audio` - Audio-Datei mit `intro_end`/`loop_start`/`loop_end` (eigene Datei pro
  Modus möglich; `DEFAULT_AUDIO` nutzt `Cage-Loop-concat.ogg`)

Die Loop-Punkte kommen damit aus der Modus-Definition, nicht mehr hartkodiert aus dem
Frontend.

## Fehlerbehebung

### Audio-Datei wird nicht gefunden

- Stellen Sie sicher, dass `static/Cage-Loop-concat.ogg` existiert
- Prüfen Sie die Dateiberechtigungen

### Kein Audio-Output

- Prüfen Sie die System-Lautstärke
- Prüfen Sie die Audio-Dateien (Format, Codec)
- Die Wiedergabe startet erst nach einer Nutzer-Interaktion (Browser-Autoplay-Richtlinie)

### Abend-Code nicht gefunden

- Codes bestehen aus 4 Zeichen ohne 0/O und 1/I/L (Groß-/Kleinschreibung egal)
- Abende liegen in `data/cagemachine.db` – wurde die Datei gelöscht oder ein anderer
  `DB_PATH` gesetzt, sind die Codes weg

## Lizenz

Siehe LICENSE Datei.
