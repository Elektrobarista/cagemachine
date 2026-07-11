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

Abende, die länger als 14 Tage nicht genutzt wurden, werden automatisch samt
aller Daten gelöscht (Frist über `RETENTION_DAYS` konfigurierbar; geprüft beim
Serverstart und bei jedem Anlegen eines Abends).

Der Debug-Link „Ich weiß was ich mache!" (Headstart-Sprünge im Audio) ist
standardmäßig ausgeblendet; `HEADSTART_ENABLED=1` blendet ihn ein.

### Betrieb hinter nginx (Reverse-Proxy)

Läuft cagemachine hinter einem Reverse-Proxy (eigene Domain, HTTPS), wertet die
App die vom Proxy gesetzten `X-Forwarded-*`-Header aus (`ProxyFix`). Dadurch
enthalten teilbare Links und QR-Codes die echte öffentliche Adresse, und das
Rate-Limiting sieht die echte Client-IP statt nur den Proxy.

Eine fertige Beispiel-Konfiguration liegt in [`nginx.example.conf`](nginx.example.conf)
(`proxy_pass`-Ziel an die eigene Topologie anpassen). Wichtig sind die
weitergereichten Header:

```nginx
location / {
    proxy_pass http://APP_HOST:3000;   # localhost oder private-Netz-Adresse der App
    proxy_set_header Host              $host;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host  $host;
}
```

**Wichtig für die Sicherheit:** Da die App den Forwarded-Headern vertraut, darf
sie **nur über den Reverse-Proxy** erreichbar sein – sonst könnte ein Client die
Header direkt fälschen und Rate-Limiting bzw. den echten Host aushebeln. Je nach
Topologie:

- **nginx auf demselben Host wie die App:** App nur an localhost binden –
  ohne Docker `FLASK_HOST=127.0.0.1`, mit Docker das Port-Mapping in
  `docker-compose.yml` auf `127.0.0.1:3000:3000` beschränken.
- **nginx auf einem eigenen Server (App im privaten Netz):** Die App muss für
  den Proxy über das Netz erreichbar sein (also nicht localhost). Hier sorgt die
  Netzwerk-Ebene für die Absicherung – nur der Proxy-Host darf zum App-Port
  (Firewall/Security-Group/Subnetz); das Docker-Mapping bleibt `3000:3000`.

Vertraut wird standardmäßig genau ein Proxy-Hop; bei einer Proxy-Kette lässt sich
das über die Umgebungsvariable `PROXY_HOPS` anpassen.

### Ablauf eines Abends

1. **Abend starten:** "Neuen Abend starten" erzeugt einen 4-stelligen **Abend-Code**
   (z. B. `K7FQ`). Mit dem Code lässt sich der Abend jederzeit fortsetzen – per
   Eingabefeld oder direkt über den Link `/abend/<code>`.
2. **Spieler hinzufügen** und mit **"Positionen auslosen"** die Sitzreihenfolge
   bestimmen. Nachzügler werden hinten
   angehängt; wird ein Spieler entfernt, rücken die anderen auf. Bei jedem
   **Rundenstart wird die Sitzordnung automatisch neu ausgelost** – der Button
   dient nur der Auslosung vor der ersten Runde. Pro Runde gibt es **zwei
   Startbecher**: Becher 1 ist immer Position 1 (die Nummern laufen von dort
   im Uhrzeigersinn), Becher 2 liegt zirkulär gegenüber – maximal fairer
   Abstand in beide Laufrichtungen. Die Tisch-Ansicht zeigt die Sitzordnung
   im Oval und dreht sich pro Runde zufällig. Das Intro ist die Zeit, die
   neuen Plätze einzunehmen.
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
- `DELETE /api/evening/<code>` - Abend samt aller Daten löschen (unumkehrbar)
- `POST /api/evening/<code>/players` - Spieler hinzufügen (`{"name": "..."}`)
- `DELETE /api/evening/<code>/players/<id>` - Spieler entfernen (bleibt in alten Runden erhalten)
- `POST /api/evening/<code>/draw` - Startposition auslosen
- `POST /api/evening/<code>/name` - Abend benennen (`{"name": "..."}`, leer = kein Name)
- `POST /api/evening/<code>/settings` - Abend-Einstellungen (`{"random_bullrush": true}`)
- `GET /api/evening/<code>/qr` - QR-Code (SVG) des teilbaren Abend-Links
- `POST /api/evening/<code>/round/start` - Runde starten (`{"mode": "classic"}`, Spieler-Snapshot)
- `POST /api/evening/<code>/round/end` - Laufende Runde beenden
- `GET /api/evening/<code>/statistics` - Abend-Statistik (Spieler-Auswertung, Rundenliste)
- `GET /api/evening/<code>/export` - Statistik als ZIP mit zwei CSVs (Spieler + Runden)
- `GET /api/evenings` - Abende, die dieses Gerät geöffnet hat (anonymes Cookie;
  Grundlage der Übersicht auf `/statistics` ohne Code)
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
