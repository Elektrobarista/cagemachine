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


