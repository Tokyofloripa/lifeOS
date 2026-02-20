"""GDELT DOC 2.0 source — news volume and sentiment tone timelines.

Returns TWO TrendSignals: news_volume (media dimension) and
news_sentiment (sentiment dimension). Uses GDELT's timelinevolraw
and timelinetone modes.
"""

import collections
import urllib.parse
from typing import Dict, List, Optional

from . import http
from .schema import SourceError, TrendDataPoint, TrendSignal

# --- Protocol constants ---

SOURCE_NAME = "gdelt"
DISPLAY_NAME = "GDELT News"
SOURCE_TIER = 1
SOURCE_DIMENSION = "media"  # Primary dimension; sentiment is secondary

# Maximum window GDELT supports (~3 months rolling)
_MAX_WINDOW_DAYS = 90


def is_available(config: dict) -> bool:
    """Always available — Tier 1, no auth needed."""
    return True


def should_search(topic: str) -> bool:
    """GDELT covers all news topics."""
    return True


def search(
    topic: str, window_days: int, config: dict
) -> Optional[List[TrendSignal]]:
    """Fetch GDELT news volume and sentiment timelines.

    Returns a list of TrendSignals (volume + sentiment) or None if both fail.
    This is a multi-signal source — run_sources() flattens the list.
    """
    query = _pick_variant(topic)
    clamped_days = min(window_days, _MAX_WINDOW_DAYS)
    timespan = f"{clamped_days}d"

    # Fetch volume and tone timelines
    volume_dps = _fetch_timeline(query, "timelinevolraw", timespan, config)
    tone_dps = _fetch_timeline(query, "timelinetone", timespan, config)

    signals = []

    if volume_dps:
        values = [dp.value for dp in volume_dps]
        signals.append(TrendSignal(
            source="gdelt",
            metric_name="news_volume",
            metric_unit="articles/day",
            dimension="media",
            datapoints=volume_dps,
            current_value=values[-1] if values else None,
            period_avg=sum(values) / len(values) if values else None,
        ))

    if tone_dps:
        values = [dp.value for dp in tone_dps]
        signals.append(TrendSignal(
            source="gdelt",
            metric_name="news_sentiment",
            metric_unit="tone_score",
            dimension="sentiment",
            datapoints=tone_dps,
            current_value=values[-1] if values else None,
            period_avg=sum(values) / len(values) if values else None,
            confidence="medium",
        ))

    return signals if signals else None


def _pick_variant(topic: str) -> str:
    """Pick the first query variant from triple-pipe delimited topic."""
    return topic.split("|||")[0].strip()


def _fetch_timeline(
    query: str, mode: str, timespan: str, config: dict
) -> List[TrendDataPoint]:
    """Fetch a GDELT timeline (volume or tone).

    Args:
        query: Search query string
        mode: "timelinevolraw" for volume, "timelinetone" for sentiment
        timespan: e.g. "90d" for 90 days

    Returns:
        List of TrendDataPoint aggregated to daily granularity.
    """
    encoded = urllib.parse.quote(query)
    url = (
        f"https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={encoded}&mode={mode}&format=json&timespan={timespan}"
    )
    timeout = config.get("per_source_timeout", 12)

    try:
        data = http.get(url, timeout=timeout)
    except Exception:
        return []

    timeline = data.get("timeline")
    if not timeline or len(timeline) == 0:
        return []

    # First series contains our data
    series_data = timeline[0].get("data", [])
    if not series_data:
        return []

    # Aggregate by date (handles sub-daily granularity)
    is_tone = (mode == "timelinetone")
    daily = _aggregate_by_date(series_data, average=is_tone)

    return daily


def _aggregate_by_date(
    entries: List[dict], average: bool = False
) -> List[TrendDataPoint]:
    """Aggregate sub-daily GDELT entries into daily TrendDataPoints.

    Args:
        entries: Raw data entries from GDELT API
        average: If True, average values per day (for tone). If False, sum (for volume).

    Returns:
        Sorted list of TrendDataPoint, one per date.
    """
    # Group by date
    date_values: Dict[str, List[float]] = collections.defaultdict(list)
    date_raws: Dict[str, list] = collections.defaultdict(list)

    for entry in entries:
        date_field = entry.get("date", "")
        date_str = date_field[:10]  # Truncate to YYYY-MM-DD
        if len(date_str) < 10:
            continue
        value = float(entry.get("value", 0))
        date_values[date_str].append(value)
        date_raws[date_str].append(entry)

    # Build datapoints
    datapoints = []
    for date_str in sorted(date_values.keys()):
        vals = date_values[date_str]
        if average:
            agg_value = sum(vals) / len(vals)
        else:
            agg_value = sum(vals)
        datapoints.append(TrendDataPoint(
            timestamp=date_str,
            value=agg_value,
            raw={"entries": len(vals)},
        ))

    return datapoints
