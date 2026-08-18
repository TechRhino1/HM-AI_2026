"""
JARVIS AI 3.0 — Trading Session & Timing Intelligence Engine.
Identifies active global market sessions (Asian, London, New York, Overlap) and prime institutional volume windows.
"""
from datetime import datetime, timezone
from jarvis.data.schemas import SessionContext

class SessionEngine:
    """Calculates active trading sessions and prime volume hours in UTC."""
    
    @staticmethod
    def get_current_session(dt: datetime = None) -> SessionContext:
        if dt is None:
            dt = datetime.now(timezone.utc)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        hour = dt.hour
        weekday = dt.weekday()  # 0=Monday, 6=Sunday

        # Session intervals in UTC:
        # Asian: 00:00 - 09:00 UTC (Tokyo/Sydney)
        # London: 07:00 - 16:00 UTC
        # New York: 12:00 - 21:00 UTC
        # London/NY Overlap: 12:00 - 16:00 UTC
        
        session_name = "OFF_HOURS"
        if 12 <= hour < 16:
            session_name = "LONDON_NY_OVERLAP"
        elif 7 <= hour < 16:
            session_name = "LONDON"
        elif 12 <= hour < 21:
            session_name = "NEW_YORK"
        elif 0 <= hour < 9:
            session_name = "ASIAN"

        # Prime volume window is typically 07:00 - 20:00 UTC during weekdays (Monday to Friday)
        is_weekday = weekday < 5
        is_prime = is_weekday and (7 <= hour <= 20)

        return SessionContext(
            current_session=session_name,
            is_prime_session=is_prime,
            utc_hour=hour,
            day_of_week=weekday
        )
