"""Datenmodelle für die Anwendung"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import uuid


@dataclass
class Player:
    """Spieler-Modell"""
    id: str
    name: str
    added_at: datetime
    
    @classmethod
    def create(cls, name: str):
        """Erstellt einen neuen Spieler"""
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            added_at=datetime.now()
        )
    
    def to_dict(self):
        """Konvertiert Player zu Dictionary für JSON-Serialisierung"""
        return {
            "id": self.id,
            "name": self.name,
            "added_at": self.added_at.isoformat()
        }


@dataclass
class Session:
    """Session-Modell für Spieler-Management"""
    id: str
    players: List[Player] = field(default_factory=list)
    game_mode: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def create(cls):
        """Erstellt eine neue Session"""
        return cls(id=str(uuid.uuid4()))
    
    def to_dict(self):
        """Konvertiert Session zu Dictionary für JSON-Serialisierung"""
        return {
            "id": self.id,
            "players": [p.to_dict() for p in self.players],
            "game_mode": self.game_mode,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class Evening:
    """Abend-Modell"""
    id: str
    created_at: datetime
    games: List[str] = field(default_factory=list)  # Liste von Game-IDs
    current_game_id: Optional[str] = None
    
    @classmethod
    def create(cls):
        """Erstellt einen neuen Abend"""
        return cls(
            id=str(uuid.uuid4()),
            created_at=datetime.now()
        )
    
    def to_dict(self):
        """Konvertiert Evening zu Dictionary für JSON-Serialisierung"""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "games": self.games,
            "current_game_id": self.current_game_id
        }


@dataclass
class Game:
    """Spiel-Modell"""
    id: str
    evening_id: str
    game_mode: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration: Optional[float] = None
    status: str = "active"  # "active" oder "completed"
    total_rounds: int = 0
    session_id: Optional[str] = None  # Session-ID, die zum Spiel gehört
    
    @classmethod
    def create(cls, evening_id: str, game_mode: str, total_rounds: int = 0, session_id: Optional[str] = None):
        """Erstellt ein neues Spiel"""
        return cls(
            id=str(uuid.uuid4()),
            evening_id=evening_id,
            game_mode=game_mode,
            started_at=datetime.now(),
            total_rounds=total_rounds,
            session_id=session_id
        )
    
    def to_dict(self):
        """Konvertiert Game zu Dictionary für JSON-Serialisierung"""
        return {
            "id": self.id,
            "evening_id": self.evening_id,
            "game_mode": self.game_mode,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration": self.duration,
            "status": self.status,
            "total_rounds": self.total_rounds,
            "session_id": self.session_id
        }


@dataclass
class Round:
    """Runden-Modell"""
    id: str
    game_id: str
    round_number: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    timer_duration: Optional[float] = None  # Timer-Dauer in Sekunden
    timer_ends_at: Optional[datetime] = None  # Wann der Timer abläuft
    
    @classmethod
    def create(cls, game_id: str, round_number: int, timer_duration: Optional[float] = None):
        """Erstellt eine neue Runde"""
        from datetime import timedelta
        round_obj = cls(
            id=str(uuid.uuid4()),
            game_id=game_id,
            round_number=round_number,
            started_at=datetime.now(),
            timer_duration=timer_duration
        )
        if timer_duration:
            round_obj.timer_ends_at = datetime.now() + timedelta(seconds=timer_duration)
        return round_obj
    
    def to_dict(self):
        """Konvertiert Round zu Dictionary für JSON-Serialisierung"""
        return {
            "id": self.id,
            "game_id": self.game_id,
            "round_number": self.round_number,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "timer_duration": self.timer_duration,
            "timer_ends_at": self.timer_ends_at.isoformat() if self.timer_ends_at else None
        }

