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
    evening_id: Optional[str] = None  # Direkte Zuordnung zu Evening
    created_at: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def create(cls, evening_id: Optional[str] = None):
        """Erstellt eine neue Session"""
        return cls(id=str(uuid.uuid4()), evening_id=evening_id)
    
    def to_dict(self):
        """Konvertiert Session zu Dictionary für JSON-Serialisierung"""
        return {
            "id": self.id,
            "players": [p.to_dict() for p in self.players],
            "evening_id": self.evening_id,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class Evening:
    """Abend-Modell"""
    id: str
    created_at: datetime
    sessions: List[str] = field(default_factory=list)  # Liste von Session-IDs
    current_session_id: Optional[str] = None
    
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
            "sessions": self.sessions,
            "current_session_id": self.current_session_id
        }



