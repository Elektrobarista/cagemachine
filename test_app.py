#!/usr/bin/env python3
"""
Test-Suite für die Cagemachine API
Testet Abend-, Spieler-, Auslosungs- und Runden-Endpoints
(Server muss laufen, BASE_URL ggf. anpassen)
"""
import os
import time

import requests

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:3000")


def test_create_evening():
    print("\n[TEST 1] Abend anlegen...")
    r = requests.post(f"{BASE_URL}/api/evening")
    assert r.status_code == 200, f"Erwartet 200, bekam {r.status_code}"
    evening = r.json()["evening"]
    assert len(evening["code"]) == 4, "Code sollte 4 Zeichen haben"
    assert evening["players"] == []
    assert evening["open_round"] is None
    print(f"  ✓ Abend {evening['code']} angelegt")
    return evening["code"]


def test_resume_evening(code):
    print("\n[TEST 2] Abend per Code laden (auch kleingeschrieben)...")
    r = requests.get(f"{BASE_URL}/api/evening/{code.lower()}")
    assert r.status_code == 200
    assert r.json()["evening"]["code"] == code
    r = requests.get(f"{BASE_URL}/api/evening/XXXX")
    assert r.status_code == 404, "Unbekannter Code sollte 404 liefern"
    print("  ✓ Wiederaufnahme funktioniert, unbekannter Code -> 404")


def test_players(code):
    print("\n[TEST 3] Spieler verwalten...")
    for name in ["Anna", "Ben", "Chris"]:
        r = requests.post(f"{BASE_URL}/api/evening/{code}/players", json={"name": name})
        assert r.status_code == 200, f"{name}: {r.status_code}"

    r = requests.post(f"{BASE_URL}/api/evening/{code}/players", json={"name": "anna"})
    assert r.status_code == 400, "Duplikat-Name sollte 400 liefern"

    r = requests.post(f"{BASE_URL}/api/evening/{code}/players", json={"name": "X" * 60})
    assert r.status_code == 400, "Überlanger Name sollte 400 liefern"

    players = requests.get(f"{BASE_URL}/api/evening/{code}").json()["evening"]["players"]
    assert [p["name"] for p in players] == ["Anna", "Ben", "Chris"]
    print("  ✓ Hinzufügen, Duplikat- und Längen-Check")
    return players


def test_remove_player(code):
    print("\n[TEST 5] Nie gespielten Spieler hart entfernen...")
    players = requests.get(f"{BASE_URL}/api/evening/{code}").json()["evening"]["players"]
    victim = next(p for p in players if p["name"] == "Ben")
    r = requests.delete(f"{BASE_URL}/api/evening/{code}/players/{victim['id']}")
    assert r.status_code == 200
    remaining = [p["name"] for p in r.json()["evening"]["players"]]
    assert remaining == ["Anna", "Chris"], "Ben sollte hart entfernt sein"
    print("  ✓ Hart entfernt (nie gespielt)")


def test_rounds(code):
    print("\n[TEST 6] Runde starten und beenden...")
    r = requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})
    assert r.status_code == 200
    assert r.json()["evening"]["open_round"] is not None, "Runde sollte offen sein"

    time.sleep(1)
    r = requests.post(f"{BASE_URL}/api/evening/{code}/round/end")
    assert r.status_code == 200
    assert r.json()["evening"]["open_round"] is None, "Runde sollte geschlossen sein"

    r = requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "gibtsnicht"})
    assert r.status_code == 400, "Unbekannter Modus sollte 400 liefern"
    print("  ✓ Runde offen/geschlossen, Modus-Validierung")


def test_modes():
    print("\n[TEST 8] Spielmodi...")
    r = requests.get(f"{BASE_URL}/api/modes")
    assert r.status_code == 200
    modes = {m["id"]: m for m in r.json()["modes"]}
    assert "classic" in modes
    assert modes["classic"]["start_position"] == 0
    assert modes["classic"]["round_count"] == 1
    assert modes["bullrush"]["round_count"] == 3

    # Jeder Modus braucht die volle Definition
    for m in modes.values():
        assert "label" in m and "description" in m
        assert "time_limit" in m  # None erlaubt
        assert m["round_count"] >= 1
        audio = m["audio"]
        assert audio["file"].startswith("/static/")
        assert audio["loop_start"] < audio["loop_end"]
        assert 0 <= m["start_position"] < audio["loop_end"]
    print(f"  ✓ {len(modes)} Modi: {', '.join(m['label'] for m in modes.values())}")


def test_random_bullrush():
    print("\n[TEST 9] Zufalls-Bullrush (Abend-Einstellung)...")
    # Eigener frischer Abend, damit die übrigen Tests unbeeinflusst bleiben
    code = requests.post(f"{BASE_URL}/api/evening").json()["evening"]["code"]
    assert requests.get(f"{BASE_URL}/api/evening/{code}").json()["evening"]["random_bullrush"] is False

    r = requests.post(f"{BASE_URL}/api/evening/{code}/settings", json={"random_bullrush": True})
    assert r.status_code == 200
    assert r.json()["evening"]["random_bullrush"] is True

    r = requests.post(f"{BASE_URL}/api/evening/{code}/settings", json={"random_bullrush": "ja"})
    assert r.status_code == 400, "Nicht-boolescher Wert sollte 400 liefern"
    r = requests.post(f"{BASE_URL}/api/evening/{code}/settings", json={})
    assert r.status_code == 400, "Fehlender Wert sollte 400 liefern"
    r = requests.post(f"{BASE_URL}/api/evening/XXXX/settings", json={"random_bullrush": True})
    assert r.status_code == 404, "Unbekannter Code sollte 404 liefern"

    # Trigger nur deterministisch prüfbar, wenn der Server mit
    # BULLRUSH_CHANCE=1.0 läuft (Env-Var auch dem Test mitgeben)
    if os.getenv("BULLRUSH_CHANCE") == "1.0":
        r = requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})
        assert r.json()["evening"]["open_round"]["mode"] == "bullrush", \
            "Bei Chance 1.0 muss die Classic-Runde zum Bullrush werden"
        # Folgerunden werden als bullrush gemeldet und nicht erneut verwürfelt
        r = requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "bullrush"})
        assert r.json()["evening"]["open_round"]["mode"] == "bullrush"
        requests.post(f"{BASE_URL}/api/evening/{code}/round/end")

        # Cooldown: trotz Chance 1.0 darf der Trigger nicht sofort wieder zuschlagen
        r = requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})
        assert r.json()["evening"]["open_round"]["mode"] == "classic", \
            "Zweiter Trigger innerhalb des Cooldowns muss ausbleiben"
        requests.post(f"{BASE_URL}/api/evening/{code}/round/end")
        print("  ✓ Toggle, Validierung, Trigger und Cooldown (BULLRUSH_CHANCE=1.0)")
    else:
        print("  ✓ Toggle und Validierung (Trigger-Test übersprungen, BULLRUSH_CHANCE nicht 1.0)")


def test_draw_on_start():
    print("\n[TEST 10] Auslosung bei jedem Rundenstart...")
    code = requests.post(f"{BASE_URL}/api/evening").json()["evening"]["code"]
    for name in ["Dora", "Emil", "Fritz", "Gerd"]:
        requests.post(f"{BASE_URL}/api/evening/{code}/players", json={"name": name})

    # Jeder Rundenstart lost aus: Positionen sind eine Permutation von 1..4
    r = requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})
    evening = r.json()["evening"]
    assert sorted(p["position"] for p in evening["players"]) == [1, 2, 3, 4], \
        "Rundenstart sollte alle Positionen auslosen"

    # Becher 1 ist immer Position 1, Becher 2 zirkulär gegenüber:
    # bei 4 Spielern Position 3
    assert evening["open_round"]["start_pos2"] == 3, \
        "Bei 4 Spielern muss der zweite Startbecher auf Position 3 liegen"
    requests.post(f"{BASE_URL}/api/evening/{code}/round/end")

    # Bei 7 Spielern (ungerade): so nah am Gegenüber wie möglich (Position 4)
    code7 = requests.post(f"{BASE_URL}/api/evening").json()["evening"]["code"]
    for name in ["P1", "P2", "P3", "P4", "P5", "P6", "P7"]:
        requests.post(f"{BASE_URL}/api/evening/{code7}/players", json={"name": name})
    r = requests.post(f"{BASE_URL}/api/evening/{code7}/round/start", json={"mode": "classic"})
    assert r.json()["evening"]["open_round"]["start_pos2"] == 4, \
        "Bei 7 Spielern muss der zweite Startbecher auf Position 4 liegen"
    requests.post(f"{BASE_URL}/api/evening/{code7}/round/end")

    # Auch der nächste Start lost (wieder vollständige Permutation)
    r = requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})
    assert sorted(p["position"] for p in r.json()["evening"]["players"]) == [1, 2, 3, 4]
    requests.post(f"{BASE_URL}/api/evening/{code}/round/end")

    # Snapshot der Runde trägt die gelosten Teilnehmer
    stats = requests.get(f"{BASE_URL}/api/evening/{code}/statistics").json()
    assert stats["rounds"][-1]["player_count"] == 4
    print("  ✓ Auslosung bei jedem Rundenstart, Snapshot-Teilnehmer")


def test_readd_player():
    print("\n[TEST 11] Entfernte Spieler wieder hinzufügen...")
    code = requests.post(f"{BASE_URL}/api/evening").json()["evening"]["code"]
    for name in ["Rita", "Sven", "Tom"]:
        requests.post(f"{BASE_URL}/api/evening/{code}/players", json={"name": name})

    # Eine Runde spielen, damit Rita Statistik hat
    requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})
    requests.post(f"{BASE_URL}/api/evening/{code}/round/end")

    players = requests.get(f"{BASE_URL}/api/evening/{code}").json()["evening"]["players"]
    rita = next(p for p in players if p["name"] == "Rita")
    # Rita hat gespielt -> nur Deaktivieren moeglich
    requests.post(f"{BASE_URL}/api/evening/{code}/players/{rita['id']}/deactivate")

    stats = requests.get(f"{BASE_URL}/api/evening/{code}/statistics").json()
    rita_stats = next(p for p in stats["players"] if p["name"] == "Rita")
    assert rita_stats["active"] is False, "Deaktivierte Spielerin sollte inaktiv sein"

    # Wieder hinzufügen (andere Schreibweise): reaktiviert dieselbe Spielerin
    r = requests.post(f"{BASE_URL}/api/evening/{code}/players", json={"name": "rita"})
    assert r.status_code == 200
    players = r.json()["evening"]["players"]
    readded = next(p for p in players if p["name"].lower() == "rita")
    assert readded["id"] == rita["id"], "Reaktivierung statt neuer Spielerin erwartet"

    stats = requests.get(f"{BASE_URL}/api/evening/{code}/statistics").json()
    ritas = [p for p in stats["players"] if p["name"].lower() == "rita"]
    assert len(ritas) == 1, "Es darf nur eine Rita in der Statistik geben"
    assert ritas[0]["active"] is True and ritas[0]["rounds_played"] == 1, \
        "Statistik muss nach Reaktivierung weiterlaufen"
    print("  ✓ Entfernen + Wieder-Hinzufügen reaktiviert dieselbe Spielerin samt Statistik")


def test_statistics(code):
    print("\n[TEST 7] Abend-Statistik...")
    r = requests.get(f"{BASE_URL}/api/evening/{code}/statistics")
    assert r.status_code == 200
    data = r.json()
    assert data["evening"]["code"] == code
    assert data["summary"]["total_rounds"] >= 1
    assert len(data["rounds"]) == data["summary"]["total_rounds"]

    # Spieler mit Runden stehen vorn; Snapshot-Teilnehmer müssen gezählt sein
    top = data["players"][0]
    assert top["rounds_played"] >= 1, "Top-Spieler sollte mindestens eine Runde haben"
    assert data["rounds"][0]["player_count"] >= 1, "Runde sollte Teilnehmer haben"

    # Der vor der Runde entfernte Spieler hat keine Runden und taucht nicht auf
    names = [p["name"] for p in data["players"]]
    assert len(names) == 2 and set(names) <= {"Anna", "Ben", "Chris"}

    # Erweiterte Auswertung: Ø-Dauer, Zeitraum, Startbecher, Teilnahme-Quote
    assert data["summary"]["avg_duration"] is not None
    assert "avg_duration_formatted" in data["summary"]
    assert data["summary"]["first_round_at"] is not None
    assert data["summary"]["last_round_at"] is not None
    assert top["participation"] == 100, "Top-Spieler war in jeder Runde dabei"
    # Eine Runde mit 2 Spielern: beide Startbecher vergeben (Position 1 und 2)
    assert sum(p["start_cups"] for p in data["players"]) == 2

    r = requests.get(f"{BASE_URL}/api/evening/XXXX/statistics")
    assert r.status_code == 404, "Statistik zu unbekanntem Code sollte 404 liefern"
    print(f"  ✓ {data['summary']['total_rounds']} Runde(n), "
          f"Top-Spieler {top['name']} mit {top['rounds_played']} Runde(n)")


def test_evening_overview():
    print("\n[TEST 12] Geräte-gebundene Abend-Übersicht...")
    device_a = requests.Session()
    device_b = requests.Session()

    r = device_a.post(f"{BASE_URL}/api/evening")
    code = r.json()["evening"]["code"]
    assert "cagemachine_visitor" in device_a.cookies, "Cookie sollte gesetzt werden"
    device_a.post(f"{BASE_URL}/api/evening/{code}/players", json={"name": "Udo"})

    # Gerät A sieht seinen Abend samt Zählern
    evenings = device_a.get(f"{BASE_URL}/api/evenings").json()["evenings"]
    entry = next(e for e in evenings if e["code"] == code)
    assert entry["player_count"] == 1 and entry["round_count"] == 0

    # Gerät B kennt den Code nicht -> Abend taucht nicht auf
    evenings_b = device_b.get(f"{BASE_URL}/api/evenings").json()["evenings"]
    assert all(e["code"] != code for e in evenings_b), \
        "Fremdes Gerät darf den Abend nicht sehen"

    # Erst nach dem Öffnen per Code erscheint er auch auf Gerät B
    device_b.get(f"{BASE_URL}/api/evening/{code}")
    evenings_b = device_b.get(f"{BASE_URL}/api/evenings").json()["evenings"]
    assert any(e["code"] == code for e in evenings_b)
    print("  ✓ Übersicht nur für Geräte, die den Abend per Code geöffnet haben")


def test_csv_export():
    print("\n[TEST 14] CSV-Export als ZIP...")
    import io
    import zipfile

    code = requests.post(f"{BASE_URL}/api/evening").json()["evening"]["code"]
    for name in ["Xen", "Yara"]:
        requests.post(f"{BASE_URL}/api/evening/{code}/players", json={"name": name})
    requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})
    requests.post(f"{BASE_URL}/api/evening/{code}/round/end")

    r = requests.get(f"{BASE_URL}/api/evening/{code}/export")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/zip"
    assert code in r.headers.get("Content-Disposition", "")

    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert any(n.startswith("spieler_") for n in names)
    assert any(n.startswith("runden_") for n in names)

    players_csv = zf.read(f"spieler_{code}.csv").decode("utf-8-sig")
    assert players_csv.splitlines()[0].startswith("Name,Runden")
    assert "Xen" in players_csv and "Yara" in players_csv

    rounds_csv = zf.read(f"runden_{code}.csv").decode("utf-8-sig")
    assert "Classic" in rounds_csv

    r = requests.get(f"{BASE_URL}/api/evening/XXXX/export")
    assert r.status_code == 404, "Export zu unbekanntem Code sollte 404 liefern"
    print("  ✓ ZIP mit spieler_/runden_-CSV, Inhalte korrekt, 404 bei Unbekannt")


def test_evening_name():
    print("\n[TEST 16] Abend benennen...")
    session = requests.Session()
    code = session.post(f"{BASE_URL}/api/evening").json()["evening"]["code"]
    assert session.get(f"{BASE_URL}/api/evening/{code}").json()["evening"]["name"] == ""

    r = session.post(f"{BASE_URL}/api/evening/{code}/name", json={"name": "  Freitag bei Max  "})
    assert r.status_code == 200
    assert r.json()["evening"]["name"] == "Freitag bei Max", "Name sollte getrimmt werden"

    # Name erscheint in der eigenen Abend-Liste
    evenings = session.get(f"{BASE_URL}/api/evenings").json()["evenings"]
    assert any(e["code"] == code and e["name"] == "Freitag bei Max" for e in evenings)

    # Leeren setzt zurück
    r = session.post(f"{BASE_URL}/api/evening/{code}/name", json={"name": ""})
    assert r.json()["evening"]["name"] == ""

    r = session.post(f"{BASE_URL}/api/evening/{code}/name", json={"name": "X" * 61})
    assert r.status_code == 400, "Zu langer Name sollte 400 liefern"
    r = session.post(f"{BASE_URL}/api/evening/XXXX/name", json={"name": "Y"})
    assert r.status_code == 404, "Unbekannter Code sollte 404 liefern"
    print("  ✓ Name setzen/trimmen/leeren, in Liste sichtbar, Längen- und 404-Check")


def test_evening_qr():
    print("\n[TEST 17] QR-Code des Abend-Links...")
    code = requests.post(f"{BASE_URL}/api/evening").json()["evening"]["code"]
    r = requests.get(f"{BASE_URL}/api/evening/{code}/qr")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["Content-Type"]
    assert b"<svg" in r.content
    assert requests.get(f"{BASE_URL}/api/evening/XXXX/qr").status_code == 404
    print("  ✓ SVG-QR geliefert, 404 bei unbekanntem Code")


def test_delete_evening():
    print("\n[TEST 15] Abend löschen (inkl. aller Daten)...")
    code = requests.post(f"{BASE_URL}/api/evening").json()["evening"]["code"]
    for name in ["Zoe", "Yann"]:
        requests.post(f"{BASE_URL}/api/evening/{code}/players", json={"name": name})
    # Laufende Runde offen lassen – Löschen muss trotzdem gehen
    requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})

    r = requests.delete(f"{BASE_URL}/api/evening/{code}")
    assert r.status_code == 200 and r.json().get("deleted") is True

    # Abend und alle abhängigen Daten sind weg
    assert requests.get(f"{BASE_URL}/api/evening/{code}").status_code == 404
    assert requests.get(f"{BASE_URL}/api/evening/{code}/statistics").status_code == 404

    # Erneutes Löschen -> 404
    assert requests.delete(f"{BASE_URL}/api/evening/{code}").status_code == 404
    print("  ✓ Abend mit offener Runde gelöscht, danach 404")


def test_deactivate_reactivate():
    print("\n[TEST 14] Deaktivieren / Reaktivieren ohne Namen neu zu tippen...")
    code = requests.post(f"{BASE_URL}/api/evening").json()["evening"]["code"]
    for name in ["Uwe", "Vera", "Wim"]:
        requests.post(f"{BASE_URL}/api/evening/{code}/players", json={"name": name})

    # Runde spielen, damit Positionen ausgelost sind
    requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})
    requests.post(f"{BASE_URL}/api/evening/{code}/round/end")

    players = requests.get(f"{BASE_URL}/api/evening/{code}").json()["evening"]["players"]
    uwe = next(p for p in players if p["name"] == "Uwe")

    # Deaktivieren: bleibt in der Liste, aber inaktiv und ohne Position
    r = requests.post(f"{BASE_URL}/api/evening/{code}/players/{uwe['id']}/deactivate")
    assert r.status_code == 200
    uwe_after = next(p for p in r.json()["evening"]["players"] if p["id"] == uwe["id"])
    assert uwe_after["active"] is False and uwe_after["position"] is None, \
        "Deaktivierter Spieler bleibt gelistet, inaktiv, ohne Position"

    # Rundenstart darf den Deaktivierten nicht auslosen
    r = requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})
    uwe_round = next(p for p in r.json()["evening"]["players"] if p["id"] == uwe["id"])
    assert uwe_round["active"] is False and uwe_round["position"] is None, \
        "Deaktivierter Spieler darf beim Rundenstart nicht ausgelost werden"
    stats = requests.get(f"{BASE_URL}/api/evening/{code}/statistics").json()
    uwe_stats = next((p for p in stats["players"] if p["name"] == "Uwe"), None)
    assert uwe_stats["rounds_played"] == 1, \
        "Deaktivierter Spieler spielt die neue Runde nicht mit (nur die erste)"

    # Während laufender Runde sind De- und Reaktivieren gesperrt
    r = requests.post(f"{BASE_URL}/api/evening/{code}/players/{uwe['id']}/reactivate")
    assert r.status_code != 200, "Reaktivieren darf während laufender Runde nicht gehen"
    vera = next(p for p in requests.get(f"{BASE_URL}/api/evening/{code}").json()["evening"]["players"]
                if p["name"] == "Vera")
    r = requests.post(f"{BASE_URL}/api/evening/{code}/players/{vera['id']}/deactivate")
    assert r.status_code != 200, "Deaktivieren darf während laufender Runde nicht gehen"
    now = requests.get(f"{BASE_URL}/api/evening/{code}").json()["evening"]["players"]
    assert next(p for p in now if p["id"] == uwe["id"])["active"] is False, \
        "Deaktivierter bleibt während der Runde deaktiviert"
    assert next(p for p in now if p["id"] == vera["id"])["active"] is True, \
        "Aktiver bleibt während der Runde aktiv"
    requests.post(f"{BASE_URL}/api/evening/{code}/round/end")

    # Reaktivieren: wieder aktiv mit Position, ohne Namen neu einzugeben
    r = requests.post(f"{BASE_URL}/api/evening/{code}/players/{uwe['id']}/reactivate")
    assert r.status_code == 200
    uwe_re = next(p for p in r.json()["evening"]["players"] if p["id"] == uwe["id"])
    assert uwe_re["active"] is True and uwe_re["position"] is not None, \
        "Reaktivierter Spieler ist wieder aktiv mit Position"
    print("  ✓ Deaktivieren/Reaktivieren funktioniert, kein Auslosen im deaktivierten Zustand")


def test_hard_remove():
    print("\n[TEST 15] Hartes Entfernen nur ohne Rundenhistorie...")
    code = requests.post(f"{BASE_URL}/api/evening").json()["evening"]["code"]
    for name in ["Xena", "Yanni"]:
        requests.post(f"{BASE_URL}/api/evening/{code}/players", json={"name": name})

    players = requests.get(f"{BASE_URL}/api/evening/{code}").json()["evening"]["players"]
    xena = next(p for p in players if p["name"] == "Xena")

    # Nie gespielt -> hartes Entfernen erlaubt, Spieler verschwindet
    r = requests.delete(f"{BASE_URL}/api/evening/{code}/players/{xena['id']}")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()["evening"]["players"]]
    assert "Xena" not in names, "Nie gespielter Spieler wird hart entfernt"

    # Yanni spielt eine Runde -> hartes Entfernen jetzt blockiert
    requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})
    requests.post(f"{BASE_URL}/api/evening/{code}/round/end")
    players = requests.get(f"{BASE_URL}/api/evening/{code}").json()["evening"]["players"]
    yanni = next(p for p in players if p["name"] == "Yanni")
    r = requests.delete(f"{BASE_URL}/api/evening/{code}/players/{yanni['id']}")
    assert r.status_code == 400, "Spieler mit Rundenhistorie darf nicht hart entfernt werden"
    still = requests.get(f"{BASE_URL}/api/evening/{code}").json()["evening"]["players"]
    assert any(p["id"] == yanni["id"] for p in still), "Yanni bleibt erhalten"
    print("  ✓ Hartes Entfernen nur ohne gespielte Runden")


def test_retention_cleanup():
    print("\n[TEST 16] Automatische Löschung nach Aufbewahrungsfrist...")
    # Braucht direkten DB-Zugriff zum Zurückdatieren (DB_PATH wie beim Server setzen)
    db_path = os.getenv("DB_PATH")
    if not db_path or not os.path.exists(db_path):
        print("  ✓ übersprungen (DB_PATH nicht gesetzt/gefunden)")
        return
    import sqlite3

    code = requests.post(f"{BASE_URL}/api/evening").json()["evening"]["code"]
    requests.post(f"{BASE_URL}/api/evening/{code}/players", json={"name": "Old"})
    requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})
    requests.post(f"{BASE_URL}/api/evening/{code}/round/end")

    # Abend auf "vor 15 Tagen zuletzt genutzt" zurückdatieren
    conn = sqlite3.connect(db_path)
    evening_id = conn.execute(
        "SELECT id FROM evening WHERE code = ?", (code,)
    ).fetchone()[0]
    conn.execute(
        "UPDATE evening SET last_used_at = datetime('now', '-15 days') WHERE id = ?",
        (evening_id,),
    )
    conn.commit()

    # Cleanup läuft bei jedem Abend-Anlegen mit
    requests.post(f"{BASE_URL}/api/evening")
    r = requests.get(f"{BASE_URL}/api/evening/{code}")
    assert r.status_code == 404, "Abgelaufener Abend sollte gelöscht sein"

    # Auch die Kind-Tabellen müssen leer sein (keine verwaisten Zeilen)
    for table in ("player", "round", "evening_access"):
        count = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE evening_id = ?", (evening_id,)
        ).fetchone()[0]
        assert count == 0, f"{table} sollte keine verwaisten Zeilen haben"
    conn.close()
    print("  ✓ Abgelaufener Abend samt Spielern/Runden/Zugriffen gelöscht")


def test_rate_limit():
    print("\n[TEST 17] Rate-Limit auf die Code-Abfrage...")
    # Nur aussagekräftig, wenn der Server mit niedrigem Limit läuft
    if os.getenv("CODE_LOOKUP_LIMIT") != "5 per minute":
        print("  ✓ übersprungen (CODE_LOOKUP_LIMIT != '5 per minute')")
        return
    codes = 0
    got_429 = False
    for _ in range(15):
        r = requests.get(f"{BASE_URL}/api/evening/ZZZZ")
        if r.status_code == 429:
            got_429 = True
            assert "error" in r.json(), "429 sollte JSON mit 'error' liefern"
            break
        codes += 1
    assert got_429, "Nach wenigen Anfragen sollte ein 429 kommen"
    print(f"  ✓ 429 nach {codes} Anfragen, als JSON")


if __name__ == "__main__":
    code = test_create_evening()
    test_resume_evening(code)
    test_players(code)
    test_remove_player(code)
    test_rounds(code)
    test_statistics(code)
    test_modes()
    test_random_bullrush()
    test_draw_on_start()
    test_readd_player()
    test_evening_overview()
    test_csv_export()
    test_evening_name()
    test_evening_qr()
    test_delete_evening()
    test_deactivate_reactivate()
    test_hard_remove()
    test_retention_cleanup()
    test_rate_limit()
    print("\nAlle Tests bestanden ✓")
