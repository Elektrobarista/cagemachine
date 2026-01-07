"""Business-Logik für Spiel- und Abend-Management"""
from typing import Optional, List
from datetime import datetime
from models import Evening, Game, Session, Player, Round
from utils import calculate_duration
from config import GAME_MODES, TEST_MODE
import random


class GameManager:
    """Verwaltet Abende, Spiele und Sessions"""
    
    def __init__(self):
        """Initialisiert den GameManager mit leeren Storage-Dictionaries"""
        self.evenings = {}  # evening_id -> Evening
        self.games = {}  # game_id -> Game
        self.sessions = {}  # session_id -> Session
        self.current_evening_id = None
        self.rounds = {}  # round_id -> Round
        self.game_rounds = {}  # game_id -> List[round_id]
        self.current_round = {}  # game_id -> round_id
    
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
    
    # Game-Management
    def start_game(self, evening_id: str, game_mode: str, player_count: int = 0, session_id: Optional[str] = None) -> Game:
        """
        Startet ein neues Spiel im angegebenen Abend
        
        Args:
            evening_id: ID des Abends
            game_mode: Spielmodus (RND, SOLI, THUNDERSTORM)
            player_count: Anzahl Spieler (für SOLI-Modus relevant)
            session_id: ID der Session, die zum Spiel gehört (optional)
        
        Returns:
            Game: Das erstellte Spiel
        """
        if evening_id not in self.evenings:
            raise ValueError(f"Abend {evening_id} nicht gefunden")
        
        # Bestimme total_rounds basierend auf Spielmodus
        if game_mode == "SOLI":
            total_rounds = player_count if player_count > 0 else 1
        elif game_mode in GAME_MODES:
            total_rounds = GAME_MODES[game_mode].get("rounds", 0) or 0
        else:
            total_rounds = 0
        
        # Erstelle neues Spiel mit Session-ID
        game = Game.create(evening_id, game_mode, total_rounds, session_id)
        self.games[game.id] = game
        
        # Füge Spiel zum Abend hinzu
        evening = self.evenings[evening_id]
        evening.games.append(game.id)
        evening.current_game_id = game.id
        
        return game
    
    def end_game(self, game_id: str) -> Game:
        """
        Beendet ein Spiel (setzt ended_at, berechnet duration, setzt status auf completed)
        
        Args:
            game_id: ID des Spiels
        
        Returns:
            Game: Das beendete Spiel
        """
        if game_id not in self.games:
            raise ValueError(f"Spiel {game_id} nicht gefunden")
        
        game = self.games[game_id]
        game.ended_at = datetime.now()
        game.duration = calculate_duration(game.started_at, game.ended_at)
        game.status = "completed"
        
        # Entferne current_game_id aus dem Abend
        if game.evening_id in self.evenings:
            evening = self.evenings[game.evening_id]
            if evening.current_game_id == game_id:
                evening.current_game_id = None
        
        return game
    
    def complete_game(self, game_id: str) -> Game:
        """Alias für end_game - markiert Spiel als abgeschlossen"""
        return self.end_game(game_id)
    
    def get_current_game(self, evening_id: str) -> Optional[Game]:
        """Gibt das aktuelle aktive Spiel eines Abends zurück"""
        evening = self.get_evening(evening_id)
        if evening and evening.current_game_id:
            return self.games.get(evening.current_game_id)
        return None
    
    def get_latest_game(self, evening_id: str) -> Optional[Game]:
        """Gibt das letzte Spiel eines Abends zurück (auch wenn beendet)"""
        games = self.get_games_by_evening(evening_id)
        if not games:
            return None
        # Sortiere nach started_at (neueste zuerst) und gib das erste zurück
        games.sort(key=lambda g: g.started_at, reverse=True)
        return games[0] if games else None
    
    def get_games_by_evening(self, evening_id: str) -> List[Game]:
        """Gibt alle Spiele eines Abends zurück"""
        evening = self.get_evening(evening_id)
        if not evening:
            return []
        
        games = []
        for game_id in evening.games:
            if game_id in self.games:
                games.append(self.games[game_id])
        return games
    
    def get_completed_games(self) -> List[Game]:
        """Gibt alle abgeschlossenen Spiele zurück, sortiert nach ended_at (neueste zuerst)"""
        completed = [g for g in self.games.values() if g.status == "completed"]
        completed.sort(key=lambda g: g.ended_at if g.ended_at else datetime.min, reverse=True)
        return completed
    
    # Session-Management
    def create_session(self) -> Session:
        """Erstellt eine neue Session"""
        session = Session.create()
        self.sessions[session.id] = session
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
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} nicht gefunden")
        
        session = self.sessions[session_id]
        session.players = [p for p in session.players if p.id != player_id]
        
        return session
    
    def set_session_game_mode(self, session_id: str, game_mode: str) -> Session:
        """
        Setzt den Spielmodus für eine Session
        
        Args:
            session_id: ID der Session
            game_mode: Spielmodus (RND, SOLI, THUNDERSTORM)
        
        Returns:
            Session: Die aktualisierte Session
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} nicht gefunden")
        
        if game_mode not in GAME_MODES:
            raise ValueError(f"Ungültiger Spielmodus: {game_mode}")
        
        session = self.sessions[session_id]
        session.game_mode = game_mode
        
        return session
    
    # Round-Management
    def start_round(self, game_id: str) -> Round:
        """
        Startet eine neue Runde für ein Spiel
        
        Args:
            game_id: ID des Spiels
        
        Returns:
            Round: Die erstellte Runde
        """
        if game_id not in self.games:
            raise ValueError(f"Spiel {game_id} nicht gefunden")
        
        game = self.games[game_id]
        
        # Bestimme aktuelle Runden-Nummer
        existing_rounds = self.game_rounds.get(game_id, [])
        round_number = len(existing_rounds) + 1
        
        # KEINE Timer-Dauer beim Start - Timer wird erst nach Rundenende gesetzt
        # Erstelle neue Runde OHNE timer_duration
        round_obj = Round.create(game_id, round_number, timer_duration=None)
        self.rounds[round_obj.id] = round_obj
        
        # Füge Runde zum Spiel hinzu
        if game_id not in self.game_rounds:
            self.game_rounds[game_id] = []
        self.game_rounds[game_id].append(round_obj.id)
        self.current_round[game_id] = round_obj.id
        
        return round_obj
    
    def end_round(self, game_id: str) -> Round:
        """
        Beendet die aktuelle Runde eines Spiels und setzt Timer für nächste Runde (falls RND-Modus)
        
        Args:
            game_id: ID des Spiels
        
        Returns:
            Round: Die beendete Runde (mit timer_duration, falls RND-Modus)
        """
        if game_id not in self.current_round:
            raise ValueError(f"Keine aktive Runde für Spiel {game_id}")
        
        round_id = self.current_round[game_id]
        if round_id not in self.rounds:
            raise ValueError(f"Runde {round_id} nicht gefunden")
        
        round_obj = self.rounds[round_id]
        round_obj.ended_at = datetime.now()
        
        # Berechne Timer-Dauer für die NÄCHSTE Runde (nur im RND-Modus)
        game = self.games[game_id]
        if game.game_mode == "RND":
            timer_duration = self._calculate_timer_duration(game.game_mode)
            round_obj.timer_duration = timer_duration
            if timer_duration:
                from datetime import timedelta
                round_obj.timer_ends_at = datetime.now() + timedelta(seconds=timer_duration)
        
        # Entferne aus current_round
        del self.current_round[game_id]
        
        return round_obj
    
    def get_current_round(self, game_id: str) -> Optional[Round]:
        """Gibt die aktuelle Runde eines Spiels zurück"""
        if game_id not in self.current_round:
            return None
        round_id = self.current_round[game_id]
        return self.rounds.get(round_id)
    
    def get_rounds_by_game(self, game_id: str) -> List[Round]:
        """Gibt alle Runden eines Spiels zurück"""
        round_ids = self.game_rounds.get(game_id, [])
        return [self.rounds[rid] for rid in round_ids if rid in self.rounds]
    
    def _calculate_timer_duration(self, game_mode: str) -> Optional[float]:
        """
        Berechnet die Timer-Dauer basierend auf Spielmodus
        
        Args:
            game_mode: Spielmodus (RND, SOLI, THUNDERSTORM)
        
        Returns:
            Timer-Dauer in Sekunden oder None
        """
        if game_mode == "RND":
            if TEST_MODE:
                # Test: 10-20 Sekunden
                return random.uniform(10, 20)
            else:
                # Produktion: 5-20 Minuten (300-1200 Sekunden)
                return random.uniform(300, 1200)
        elif game_mode == "THUNDERSTORM":
            # Back to Back: Kein Timer zwischen Runden
            return None
        elif game_mode == "SOLI":
            # Soli: Kein automatischer Timer (manuell gesteuert)
            return None
        else:
            return None

