from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import zoneinfo

try:
    IST_TZ = zoneinfo.ZoneInfo("Asia/Kolkata")
except Exception:
    IST_TZ = timezone(timedelta(hours=5, minutes=30))

from jarvis.data.schemas import SessionContext

class SessionEngine:
    """Calculates active trading sessions, prime volume hours, and global market open/closed status."""
    
    @staticmethod
    def get_current_session(dt: Optional[datetime] = None) -> SessionContext:
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

    @staticmethod
    def get_market_trading_status(symbol: str = "XAUUSD", dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Determines exact market operational status, weekend closure, and opening schedules in IST & UTC.
        """
        if dt is None:
            dt = datetime.now(timezone.utc)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        sym_upper = (symbol or "XAUUSD").upper()
        
        # 1. Crypto assets operate 24/7 continuously
        if "BTC" in sym_upper or "ETH" in sym_upper or "SOL" in sym_upper or "CRYPTO" in sym_upper:
            return {
                "symbol": symbol,
                "is_open": True,
                "market_type": "CRYPTO_24_7",
                "status": "OPEN",
                "status_badge": "🟢 24/7 LIVE MARKET",
                "status_text": "Market is OPEN (Continuous 24/7 Crypto Trading)",
                "next_event": "Continuous 24/7 Trading",
                "next_open_ist": "Always Open",
                "countdown_seconds": 0,
                "countdown_formatted": "Live Now"
            }

        # 2. Forex & Spot Metals (Gold / Currencies / Indices)
        # Global market schedule:
        # Closes: Friday 21:00 UTC (17:00 EDT / Saturday 02:30 AM IST)
        # Opens:  Sunday 21:00 UTC (17:00 EDT / Monday 02:30 AM IST)
        weekday = dt.weekday()  # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
        hour = dt.hour
        minute = dt.minute

        is_weekend_closed = False
        if weekday == 4 and (hour > 21 or (hour == 21 and minute >= 0)):
            is_weekend_closed = True
        elif weekday == 5:
            is_weekend_closed = True
        elif weekday == 6 and hour < 21:
            is_weekend_closed = True

        if is_weekend_closed:
            # Calculate next Sunday 21:00 UTC
            days_to_sunday = (6 - weekday) % 7
            if weekday == 6:
                target_date = dt.date()
            else:
                target_date = dt.date() + timedelta(days=days_to_sunday)

            next_open_utc = datetime(target_date.year, target_date.month, target_date.day, 21, 0, 0, tzinfo=timezone.utc)
            diff_sec = max(0, (next_open_utc - dt).total_seconds())

            hours = int(diff_sec // 3600)
            mins = int((diff_sec % 3600) // 60)
            days = hours // 24
            rem_hours = hours % 24

            countdown_str = f"{days}d {rem_hours}h {mins}m" if days > 0 else f"{hours}h {mins}m"
            next_open_ist_dt = next_open_utc.astimezone(IST_TZ)
            next_open_ist_str = next_open_ist_dt.strftime("%a %b %d, %I:%M %p IST")

            return {
                "symbol": symbol,
                "is_open": False,
                "market_type": "FOREX_METALS_24_5",
                "status": "CLOSED_WEEKEND",
                "status_badge": "🔴 MARKET CLOSED (WEEKEND)",
                "status_text": f"Market is CLOSED for the weekend. Re-opens {next_open_ist_str} (in {countdown_str}).",
                "next_event": f"Re-opens {next_open_ist_str}",
                "next_open_ist": next_open_ist_str,
                "next_open_utc": next_open_utc.isoformat(),
                "countdown_seconds": int(diff_sec),
                "countdown_formatted": countdown_str,
                "reason": "Global Forex & Spot Metals markets are closed on weekends (Friday 21:00 UTC to Sunday 21:00 UTC / Saturday 02:30 AM IST to Monday 02:30 AM IST)."
            }
        else:
            # Market is open on weekdays
            days_to_friday = (4 - weekday) % 7
            target_date = dt.date() + timedelta(days=days_to_friday)
            next_close_utc = datetime(target_date.year, target_date.month, target_date.day, 21, 0, 0, tzinfo=timezone.utc)
            diff_sec = max(0, (next_close_utc - dt).total_seconds())

            hours = int(diff_sec // 3600)
            mins = int((diff_sec % 3600) // 60)
            days = hours // 24
            rem_hours = hours % 24
            countdown_str = f"{days}d {rem_hours}h {mins}m" if days > 0 else f"{hours}h {mins}m"
            next_close_ist_dt = next_close_utc.astimezone(IST_TZ)
            next_close_ist_str = next_close_ist_dt.strftime("%a %b %d, %I:%M %p IST")

            return {
                "symbol": symbol,
                "is_open": True,
                "market_type": "FOREX_METALS_24_5",
                "status": "OPEN",
                "status_badge": "🟢 MARKET OPEN (24/5)",
                "status_text": f"Market is OPEN (Closes {next_close_ist_str} in {countdown_str})",
                "next_event": f"Closes {next_close_ist_str}",
                "next_open_ist": "Currently Open",
                "next_open_utc": "",
                "countdown_seconds": int(diff_sec),
                "countdown_formatted": countdown_str
            }
