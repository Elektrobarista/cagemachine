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


def test_draw(code):
    print("\n[TEST 4] Positionen auslosen...")
    r = requests.post(f"{BASE_URL}/api/evening/{code}/draw")
    assert r.status_code == 200
    players = r.json()["evening"]["players"]
    assert sorted(p["position"] for p in players) == [1, 2, 3]
    print(f"  ✓ Auslosung: {[(p['position'], p['name']) for p in players]}")


def test_remove_player_compaction(code):
    print("\n[TEST 5] Spieler entfernen schließt Positionslücke...")
    players = requests.get(f"{BASE_URL}/api/evening/{code}").json()["evening"]["players"]
    victim = next(p for p in players if p["position"] == 2)
    r = requests.delete(f"{BASE_URL}/api/evening/{code}/players/{victim['id']}")
    assert r.status_code == 200
    remaining = r.json()["evening"]["players"]
    assert [p["position"] for p in remaining] == [1, 2], "Positionen sollten verdichtet sein"
    print("  ✓ Positionen lückenlos verdichtet")


def test_rounds(code):
    print("\n[TEST 6] Runde starten und beenden...")
    r = requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "classic"})
    assert r.status_code == 200
    assert r.json()["evening"]["open_round"] is not None, "Runde sollte offen sein"

    r = requests.post(f"{BASE_URL}/api/evening/{code}/draw")
    assert r.status_code == 400, "Auslosen während laufender Runde sollte 400 liefern"

    time.sleep(1)
    r = requests.post(f"{BASE_URL}/api/evening/{code}/round/end")
    assert r.status_code == 200
    assert r.json()["evening"]["open_round"] is None, "Runde sollte geschlossen sein"

    r = requests.post(f"{BASE_URL}/api/evening/{code}/round/start", json={"mode": "gibtsnicht"})
    assert r.status_code == 400, "Unbekannter Modus sollte 400 liefern"
    print("  ✓ Runde offen/geschlossen, Draw-Sperre, Modus-Validierung")


def test_statistics():
    print("\n[TEST 7] Statistik...")
    r = requests.get(f"{BASE_URL}/api/statistics/audio")
    assert r.status_code == 200
    data = r.json()
    assert data["total_starts"] >= 1
    assert len(data["completed_events"]) >= 1
    print(f"  ✓ {data['total_starts']} Runde(n), Gesamtdauer {data['total_duration_formatted']}")


if __name__ == "__main__":
    code = test_create_evening()
    test_resume_evening(code)
    test_players(code)
    test_draw(code)
    test_remove_player_compaction(code)
    test_rounds(code)
    test_statistics()
    print("\nAlle Tests bestanden ✓")
