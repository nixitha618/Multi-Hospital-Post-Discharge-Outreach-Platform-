from datetime import datetime, timezone, timedelta
from typing import Optional

# Indian Standard Time (IST) is UTC+05:30
IST_OFFSET = timedelta(hours=5, minutes=30)
IST = timezone(IST_OFFSET, name="IST")

def get_ist_now(aware: bool = False) -> datetime:
    """
    Returns current datetime in Indian Standard Time (IST, UTC+05:30).
    By default returns an offset-naive datetime object representing local IST time
    for seamless SQLite and datetime subtraction arithmetic compatibility.
    Pass aware=True for a timezone-aware datetime with +05:30 offset.
    """
    dt = datetime.now(IST)
    return dt if aware else dt.replace(tzinfo=None)

def get_ist_iso() -> str:
    """
    Returns current IST datetime as an ISO-8601 string with +05:30 timezone offset.
    Example: '2026-09-18T18:25:00.123456+05:30'
    """
    return datetime.now(IST).isoformat()

def to_ist(dt: Optional[datetime], aware: bool = False) -> Optional[datetime]:
    """
    Converts any datetime to Indian Standard Time (IST).
    If dt is naive, assumes it represents IST local time.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt_aware = dt.replace(tzinfo=IST)
    else:
        dt_aware = dt.astimezone(IST)
    return dt_aware if aware else dt_aware.replace(tzinfo=None)

def to_ist_iso(dt: Optional[datetime]) -> Optional[str]:
    """
    Converts a datetime to ISO-8601 string with IST (+05:30) timezone offset.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST).isoformat()
    return dt.astimezone(IST).isoformat()

def format_ist(dt: Optional[datetime], fmt: str = "%Y-%m-%d %I:%M:%S %p IST") -> str:
    """
    Formats a datetime as a readable Indian Standard Time string.
    Example: '2026-09-18 06:25:00 PM IST'
    """
    if dt is None:
        return "N/A"
    return to_ist(dt, aware=True).strftime(fmt)
