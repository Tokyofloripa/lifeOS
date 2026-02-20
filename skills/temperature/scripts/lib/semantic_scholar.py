"""Semantic Scholar source — paper count and citation data for academic topics.

Tier 1 (free, unauthenticated). Covers academic dimension.
Uses Semantic Scholar Graph API v1 for paper search with year filtering.
Sets confidence='low' because yearly granularity is too coarse for 90-day trends.
Supports optional API key via SEMANTIC_SCHOLAR_KEY for higher rate limits.
"""

import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import http
from .http import HTTPError
from .schema import SourceError, TrendDataPoint, TrendSignal

# --- Protocol constants ---

SOURCE_NAME = "semantic_scholar"
DISPLAY_NAME = "Semantic Scholar"
SOURCE_TIER = 1
SOURCE_DIMENSION = "academic"


def is_available(config: dict) -> bool:
    """Always available — unauthenticated access is supported."""
    return True


def should_search(topic: str) -> bool:
    """Returns True for all topics."""
    return True


def search(topic: str, window_days: int, config: dict) -> Optional[TrendSignal]:
    """Search Semantic Scholar for papers matching the topic.

    Returns TrendSignal with paper counts grouped by year, or None
    if no papers found. Sets confidence='low' due to coarse yearly granularity.

    Raises:
        SourceError: On 429 rate limit (do NOT retry per research guidance).
    """
    # Parse first query variant
    variants = [v.strip() for v in topic.split("|||") if v.strip()]
    if not variants:
        return None
    query = variants[0]

    # Compute year range
    year_range = _compute_year_range(window_days)

    # Fetch papers
    try:
        data = _search_papers(query, year_range, config)
    except HTTPError as e:
        if e.status_code == 429:
            raise SourceError(
                "semantic_scholar",
                "Rate limited (shared pool contention)",
            )
        raise

    total = data.get("total", 0)
    papers = data.get("data", [])

    if total == 0 or not papers:
        return None

    # Group papers by year
    year_counts: Dict[int, int] = defaultdict(int)
    for paper in papers:
        year = paper.get("year")
        if year is not None:
            year_counts[year] += 1

    if not year_counts:
        return None

    # Build datapoints from year counts
    datapoints = []
    for year in sorted(year_counts.keys()):
        datapoints.append(
            TrendDataPoint(
                timestamp=str(year),
                value=float(year_counts[year]),
                raw={"year": year, "count": year_counts[year]},
            )
        )

    # Current value = papers in most recent year
    most_recent_year = max(year_counts.keys())
    current_value = float(year_counts[most_recent_year])

    # Period average
    values = [float(c) for c in year_counts.values()]
    period_avg = sum(values) / len(values) if values else None

    return TrendSignal(
        source=SOURCE_NAME,
        metric_name="paper_count",
        metric_unit="papers",
        dimension=SOURCE_DIMENSION,
        datapoints=datapoints,
        current_value=current_value,
        period_avg=period_avg,
        confidence="low",
        metadata={
            "total": total,
            "year_range": year_range,
            "query": query,
        },
    )


def _compute_year_range(window_days: int) -> str:
    """Compute Semantic Scholar year range string from window_days.

    For window <= 365: current year only (e.g., "2026-2026").
    For window > 365: compute start year, use "{start_year}-{current_year}".
    """
    now = datetime.now(timezone.utc)
    current_year = now.year

    if window_days <= 365:
        return f"{current_year}-{current_year}"

    start_date = now - timedelta(days=window_days)
    start_year = start_date.year
    return f"{start_year}-{current_year}"


def _search_papers(query: str, year_range: str, config: dict) -> dict:
    """Search Semantic Scholar Graph API for papers.

    Args:
        query: Search query string
        year_range: e.g., "2025-2026" or "2026-2026"
        config: Configuration dict (may contain SEMANTIC_SCHOLAR_KEY)

    Returns:
        API response dict with 'total' and 'data' fields

    Raises:
        HTTPError: On request failure
    """
    params = urllib.parse.urlencode({
        "query": query,
        "year": year_range,
        "fields": "year,citationCount",
        "limit": 100,
    })
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"

    headers = {}
    api_key = config.get("SEMANTIC_SCHOLAR_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    timeout = config.get("per_source_timeout", 10)
    return http.get(url, headers=headers, timeout=timeout)
