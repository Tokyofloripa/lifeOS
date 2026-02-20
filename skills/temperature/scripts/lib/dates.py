"""Date utilities for temperature skill."""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple


def get_date_range(days: int = 30) -> Tuple[str, str]:
    """Get the date range for the last N days.

    Returns:
        Tuple of (from_date, to_date) as YYYY-MM-DD strings
    """
    today = datetime.now(timezone.utc).date()
    from_date = today - timedelta(days=days)
    return from_date.isoformat(), today.isoformat()


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse a date string in various formats.

    Supports: YYYY-MM-DD, ISO 8601, Unix timestamp
    """
    if not date_str:
        return None

    # Try Unix timestamp
    try:
        ts = float(date_str)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, TypeError):
        pass

    # Try ISO formats
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def timestamp_to_date(ts: Optional[float]) -> Optional[str]:
    """Convert Unix timestamp to YYYY-MM-DD string."""
    if ts is None:
        return None
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.date().isoformat()
    except (ValueError, TypeError, OSError):
        return None


def days_ago(date_str: Optional[str]) -> Optional[int]:
    """Calculate how many days ago a date is.

    Returns None if date is invalid or missing.
    """
    if not date_str:
        return None

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now(timezone.utc).date()
        delta = today - dt
        return delta.days
    except ValueError:
        return None


def recency_score(date_str: Optional[str], max_days: int = 30) -> int:
    """Calculate recency score (0-100).

    0 days ago = 100, max_days ago = 0, clamped.
    """
    age = days_ago(date_str)
    if age is None:
        return 0  # Unknown date gets worst score

    if age < 0:
        return 100  # Future date (treat as today)
    if age >= max_days:
        return 0

    return int(100 * (1 - age / max_days))


def offset_date(date_str: str, days: int) -> str:
    """Offset a YYYY-MM-DD date string by N days."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (dt + timedelta(days=days)).strftime("%Y-%m-%d")


def to_wikimedia_format(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD00 (Wikimedia Pageviews API format).

    The trailing 00 represents hour 00 (start of day), required by
    the Wikimedia Pageviews API.
    """
    return date_str.replace("-", "") + "00"


def to_gdelt_format(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDDHHMMSS (GDELT DOC 2.0 API format).

    The trailing 000000 represents midnight (00:00:00), required by
    the GDELT DOC 2.0 API.
    """
    return date_str.replace("-", "") + "000000"


def to_api_format(date_str: str) -> str:
    """Return YYYY-MM-DD unchanged (identity function).

    Exists for documentation clarity -- npm, PyPI, and ISO standard APIs
    use this format directly.
    """
    return date_str
