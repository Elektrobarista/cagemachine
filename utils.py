"""Helper-Funktionen für die Anwendung"""
from datetime import datetime


def format_duration(seconds):
    """
    Formatiert Sekunden zu einem lesbaren Zeitformat (MM:SS oder HH:MM:SS)
    
    Args:
        seconds: Dauer in Sekunden (float oder int)
    
    Returns:
        str: Formatierte Zeit als "MM:SS" oder "HH:MM:SS"
    """
    if seconds is None or seconds < 0:
        return "00:00"
    
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def calculate_duration(started_at, ended_at):
    """
    Berechnet die Dauer zwischen zwei Zeitpunkten in Sekunden
    
    Args:
        started_at: Start-Zeitpunkt (datetime)
        ended_at: End-Zeitpunkt (datetime)
    
    Returns:
        float: Dauer in Sekunden
    """
    if started_at is None or ended_at is None:
        return 0.0
    
    delta = ended_at - started_at
    return delta.total_seconds()



