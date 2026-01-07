"""Business-Logik für Abend- und Session-Management"""
from typing import Optional, List
from datetime import datetime
from models import Evening, Session, Player
import threading


class GameManager:
    """Verwaltet Abende und Sessions"""
    
    def __init__(self):
        """Initialisiert den GameManager mit leeren Storage-Dictionaries"""
        self.evenings = {}  # evening_id -> Evening
        self.sessions = {}  # session_id -> Session
        self.current_evening_id = None
        # RLock für thread-sicheren Zugriff
        self._lock = threading.RLock()
    
    # Evening-Management
    def create_evening(self) -> Evening:
        """Erstellt einen neuen Abend und setzt ihn als aktuellen Abend"""
        evening = Evening.create()
        self.evenings[evening.id] = evening
        self.current_evening_id = evening.id
        return evening
    
    def get_current_evening(self) -> Optional[Evening]:
        """Gibt den aktuellen Abend zurück"""
        if self.current_evening_id and self.current_evening_id in self.evenings:
            return self.evenings[self.current_evening_id]
        return None
    
    def get_evening(self, evening_id: str) -> Optional[Evening]:
        """Gibt einen spezifischen Abend zurück"""
        return self.evenings.get(evening_id)
    
    def get_sessions_by_evening(self, evening_id: str) -> List[Session]:
        """Gibt alle Sessions eines Abends zurück"""
        evening = self.get_evening(evening_id)
        if not evening:
            return []
        
        sessions = []
        for session_id in evening.sessions:
            if session_id in self.sessions:
                sessions.append(self.sessions[session_id])
        return sessions
    
    # Session-Management
    def create_session(self, evening_id: Optional[str] = None) -> Session:
        """
        Erstellt eine neue Session
        
        Args:
            evening_id: ID des Abends, zu dem die Session gehört (optional)
        
        Returns:
            Session: Die erstellte Session
        """
        with self._lock:
            session = Session.create(evening_id=evening_id)
            self.sessions[session.id] = session
            
            # Füge Session zum Abend hinzu, falls evening_id angegeben
            if evening_id and evening_id in self.evenings:
                evening = self.evenings[evening_id]
                if session.id not in evening.sessions:
                    evening.sessions.append(session.id)
                # Setze als aktuelle Session, falls noch keine gesetzt
                if not evening.current_session_id:
                    evening.current_session_id = session.id
            
            return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Gibt eine Session zurück"""
        return self.sessions.get(session_id)
    
    def add_player_to_session(self, session_id: str, player_name: str) -> Session:
        """
        Fügt einen Spieler zu einer Session hinzu
        
        Args:
            session_id: ID der Session
            player_name: Name des Spielers
        
        Returns:
            Session: Die aktualisierte Session
        """
        with self._lock:
            if session_id not in self.sessions:
                raise ValueError(f"Session {session_id} nicht gefunden")
            
            session = self.sessions[session_id]
            
            # Prüfe ob Spielername bereits existiert
            if any(p.name == player_name for p in session.players):
                raise ValueError(f"Spielername '{player_name}' bereits vorhanden")
            
            player = Player.create(player_name)
            session.players.append(player)
            
            return session
    
    def remove_player_from_session(self, session_id: str, player_id: str) -> Session:
        """
        Entfernt einen Spieler aus einer Session
        
        Args:
            session_id: ID der Session
            player_id: ID des Spielers
        
        Returns:
            Session: Die aktualisierte Session
        """
        with self._lock:
            if session_id not in self.sessions:
                raise ValueError(f"Session {session_id} nicht gefunden")
            
            session = self.sessions[session_id]
            session.players = [p for p in session.players if p.id != player_id]
            
            return session
