#!/usr/bin/env python3
"""
Test-Suite für die Cagemachine Audio-App
Testet alle API-Endpoints und State-Transitions
"""
import requests
import time
import json

BASE_URL = "http://127.0.0.1:8000"

def test_status():
    """Test 1: Status-Endpoint"""
    print("\n[TEST 1] Status-Endpoint testen...")
    try:
        response = requests.get(f"{BASE_URL}/api/status")
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.json()}")
        assert response.status_code == 200, f"Erwartet 200, bekam {response.status_code}"
        assert "status" in response.json(), "Response sollte 'status' enthalten"
        print("  ✓ Status-Endpoint funktioniert")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False

def test_start():
    """Test 2: Start-Endpoint"""
    print("\n[TEST 2] Start-Endpoint testen...")
    try:
        response = requests.post(f"{BASE_URL}/api/start")
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.json()}")
        assert response.status_code == 200, f"Erwartet 200, bekam {response.status_code}"
        data = response.json()
        assert data["status"] in ["intro", "looping"], f"Status sollte 'intro' oder 'looping' sein, bekam: {data['status']}"
        print("  ✓ Start-Endpoint funktioniert")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False

def test_status_after_start():
    """Test 3: Status nach Start prüfen"""
    print("\n[TEST 3] Status nach Start prüfen...")
    try:
        time.sleep(0.5)  # Kurz warten
        response = requests.get(f"{BASE_URL}/api/status")
        data = response.json()
        print(f"  Status: {data['status']}")
        print(f"  Message: {data['message']}")
        assert data["status"] in ["intro", "looping"], "Status sollte 'intro' oder 'looping' sein"
        print("  ✓ Status nach Start korrekt")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False

def test_pause():
    """Test 4: Pause-Endpoint"""
    print("\n[TEST 4] Pause-Endpoint testen...")
    try:
        response = requests.post(f"{BASE_URL}/api/pause")
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.json()}")
        assert response.status_code == 200, f"Erwartet 200, bekam {response.status_code}"
        data = response.json()
        assert data["status"] == "paused", f"Status sollte 'paused' sein, bekam: {data['status']}"
        print("  ✓ Pause-Endpoint funktioniert")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False

def test_resume():
    """Test 5: Resume-Endpoint"""
    print("\n[TEST 5] Resume-Endpoint testen...")
    try:
        response = requests.post(f"{BASE_URL}/api/resume")
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.json()}")
        assert response.status_code == 200, f"Erwartet 200, bekam {response.status_code}"
        data = response.json()
        assert data["status"] in ["intro", "looping"], f"Status sollte 'intro' oder 'looping' sein, bekam: {data['status']}"
        print("  ✓ Resume-Endpoint funktioniert")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False

def test_stop():
    """Test 6: Stop-Endpoint"""
    print("\n[TEST 6] Stop-Endpoint testen...")
    try:
        response = requests.post(f"{BASE_URL}/api/stop")
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.json()}")
        assert response.status_code == 200, f"Erwartet 200, bekam {response.status_code}"
        data = response.json()
        assert data["status"] in ["stopping", "stopped"], f"Status sollte 'stopping' oder 'stopped' sein, bekam: {data['status']}"
        print("  ✓ Stop-Endpoint funktioniert")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False

def test_stop_after_stop():
    """Test 7: Stop nach bereits gestoppt (Edge Case)"""
    print("\n[TEST 7] Stop nach bereits gestoppt (Edge Case)...")
    try:
        time.sleep(2.5)  # Warte auf Fade-Out
        response = requests.post(f"{BASE_URL}/api/stop")
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.json()}")
        assert response.status_code == 200, "Sollte auch bei bereits gestoppt 200 zurückgeben"
        print("  ✓ Stop nach bereits gestoppt funktioniert")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False

def test_start_after_stop():
    """Test 8: Start nach Stop (Neustart)"""
    print("\n[TEST 8] Start nach Stop (Neustart)...")
    try:
        response = requests.post(f"{BASE_URL}/api/start")
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.json()}")
        assert response.status_code == 200, f"Erwartet 200, bekam {response.status_code}"
        data = response.json()
        assert data["status"] in ["intro", "looping"], f"Status sollte 'intro' oder 'looping' sein, bekam: {data['status']}"
        print("  ✓ Neustart funktioniert")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False

def test_multiple_starts():
    """Test 9: Mehrfaches Start (sollte idempotent sein)"""
    print("\n[TEST 9] Mehrfaches Start (idempotent)...")
    try:
        response1 = requests.post(f"{BASE_URL}/api/start")
        time.sleep(0.2)
        response2 = requests.post(f"{BASE_URL}/api/start")
        print(f"  Erster Start: {response1.json()}")
        print(f"  Zweiter Start: {response2.json()}")
        assert response1.status_code == 200
        assert response2.status_code == 200
        print("  ✓ Mehrfaches Start funktioniert (idempotent)")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False

def test_resume_without_pause():
    """Test 10: Resume ohne vorheriges Pause (Edge Case)"""
    print("\n[TEST 10] Resume ohne vorheriges Pause (Edge Case)...")
    try:
        # Stoppe erst, dann versuche Resume
        requests.post(f"{BASE_URL}/api/stop")
        time.sleep(2.5)
        response = requests.post(f"{BASE_URL}/api/resume")
        print(f"  Status Code: {response.status_code}")
        print(f"  Response: {response.json()}")
        # Resume ohne Pause sollte entweder 200 zurückgeben oder den Status nicht ändern
        assert response.status_code == 200
        print("  ✓ Resume ohne Pause behandelt")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False

def test_full_workflow():
    """Test 11: Vollständiger Workflow"""
    print("\n[TEST 11] Vollständiger Workflow (Start → Pause → Resume → Stop)...")
    try:
        # Start
        r1 = requests.post(f"{BASE_URL}/api/start")
        assert r1.status_code == 200
        time.sleep(1)
        
        # Pause
        r2 = requests.post(f"{BASE_URL}/api/pause")
        assert r2.status_code == 200
        assert r2.json()["status"] == "paused"
        time.sleep(0.5)
        
        # Resume
        r3 = requests.post(f"{BASE_URL}/api/resume")
        assert r3.status_code == 200
        assert r3.json()["status"] in ["intro", "looping"]
        time.sleep(1)
        
        # Stop
        r4 = requests.post(f"{BASE_URL}/api/stop")
        assert r4.status_code == 200
        assert r4.json()["status"] in ["stopping", "stopped"]
        time.sleep(2.5)
        
        # Finaler Status
        r5 = requests.get(f"{BASE_URL}/api/status")
        assert r5.status_code == 200
        assert r5.json()["status"] == "stopped"
        
        print("  ✓ Vollständiger Workflow erfolgreich")
        return True
    except Exception as e:
        print(f"  ✗ Fehler: {e}")
        return False

def main():
    """Hauptfunktion - führt alle Tests aus"""
    print("=" * 60)
    print("CAGEMACHINE AUDIO-APP TEST SUITE")
    print("=" * 60)
    
    # Prüfe ob Server läuft
    try:
        response = requests.get(f"{BASE_URL}/api/status", timeout=5)
        print("✓ Server ist erreichbar")
    except requests.exceptions.ConnectionError as e:
        print(f"✗ FEHLER: Server läuft nicht! Bitte starte die App mit: python app.py")
        print(f"  Details: {e}")
        return
    except Exception as e:
        print(f"✗ FEHLER: {e}")
        import traceback
        traceback.print_exc()
        return
    
    tests = [
        test_status,
        test_start,
        test_status_after_start,
        test_pause,
        test_resume,
        test_stop,
        test_stop_after_stop,
        test_start_after_stop,
        test_multiple_starts,
        test_resume_without_pause,
        test_full_workflow,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except KeyboardInterrupt:
            print("\n\nTests abgebrochen durch Benutzer")
            break
        except Exception as e:
            print(f"\n  ✗ Unerwarteter Fehler in {test.__name__}: {e}")
            results.append(False)
    
    # Zusammenfassung
    print("\n" + "=" * 60)
    print("TEST ZUSAMMENFASSUNG")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Erfolgreich: {passed}/{total}")
    print(f"Fehlgeschlagen: {total - passed}/{total}")
    
    if passed == total:
        print("\n✓ ALLE TESTS ERFOLGREICH!")
    else:
        print(f"\n✗ {total - passed} TEST(S) FEHLGESCHLAGEN")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

