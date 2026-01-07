"""Timer-Service für automatische Musikaktivierung"""
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Callable


class TimerService:
    """Verwaltet Timer für automatische Musikaktivierung"""
    
    def __init__(self, audio_controller):
        self.audio_controller = audio_controller
        self.active_timers = {}  # game_id -> Timer-Info
        self.lock = threading.Lock()
        self.timer_thread = None
        self.running = False
    
    def start(self):
        """Startet den Timer-Service"""
        with self.lock:
            if self.running:
                return
            self.running = True
            self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
            self.timer_thread.start()
    
    def stop(self):
        """Stoppt den Timer-Service"""
        with self.lock:
            self.running = False
            self.active_timers.clear()
    
    def set_timer(self, game_id: str, duration_seconds: float, callback: Optional[Callable] = None):
        """
        Setzt einen Timer für ein Spiel
        
        Args:
            game_id: ID des Spiels
            duration_seconds: Dauer in Sekunden
            callback: Optional callback-Funktion, die beim Ablaufen aufgerufen wird
        """
        with self.lock:
            ends_at = datetime.now() + timedelta(seconds=duration_seconds)
            self.active_timers[game_id] = {
                "ends_at": ends_at,
                "duration": duration_seconds,
                "callback": callback
            }
    
    def cancel_timer(self, game_id: str):
        """Bricht einen Timer ab"""
        with self.lock:
            if game_id in self.active_timers:
                del self.active_timers[game_id]
    
    def get_remaining_time(self, game_id: str) -> Optional[float]:
        """Gibt die verbleibende Zeit eines Timers zurück (in Sekunden)"""
        with self.lock:
            if game_id not in self.active_timers:
                return None
            timer_info = self.active_timers[game_id]
            remaining = (timer_info["ends_at"] - datetime.now()).total_seconds()
            return max(0, remaining)
    
    def _timer_loop(self):
        """Hauptschleife für Timer-Überwachung"""
        while self.running:
            time.sleep(0.5)  # Prüfe alle 500ms
            
            with self.lock:
                now = datetime.now()
                expired_timers = []
                
                for game_id, timer_info in list(self.active_timers.items()):  # list() erstellt eine Kopie
                    if now >= timer_info["ends_at"]:
                        expired_timers.append((game_id, timer_info))
            
            # Verarbeite abgelaufene Timer außerhalb des Locks
            for game_id, timer_info in expired_timers:
                # Starte Musik automatisch
                try:
                    self.audio_controller.start()
                except Exception as e:
                    print(f"Fehler beim automatischen Start der Musik: {e}")
                
                # Rufe Callback auf, falls vorhanden
                if timer_info.get("callback"):
                    try:
                        timer_info["callback"](game_id)
                    except Exception as e:
                        print(f"Fehler im Timer-Callback: {e}")
                
                # Entferne Timer (sicher, da außerhalb des Locks)
                with self.lock:
                    if game_id in self.active_timers:  # Prüfe ob noch vorhanden
                        del self.active_timers[game_id]

