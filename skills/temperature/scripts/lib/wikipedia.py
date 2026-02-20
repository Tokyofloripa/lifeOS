"""Wikipedia Pageviews source — daily pageview counts via Wikimedia API.

Resolves topic to Wikipedia article title via MediaWiki search API with
tech-topic disambiguation heuristics, then fetches daily pageviews.
"""

import urllib.parse
from typing import Dict, List, Optional

from . import http
from .dates import get_date_range, to_wikimedia_format
from .schema import SourceError, TrendDataPoint, TrendSignal

# --- Protocol constants ---

SOURCE_NAME = "wikipedia"
DISPLAY_NAME = "Wikipedia Pageviews"
SOURCE_TIER = 1
SOURCE_DIMENSION = "search_interest"

# Tech-topic disambiguation hints
TECH_HINTS = [
    "programming", "software", "library", "framework", "language",
    "computing", "technology", "web", "tool", "protocol",
    "algorithm", "database", "api",
]


def is_available(config: dict) -> bool:
    """Always available — Tier 1, no auth needed."""
    return True


def should_search(topic: str) -> bool:
    """Wikipedia covers all topics."""
    return True


def search(topic: str, window_days: int, config: dict) -> Optional[TrendSignal]:
    """Fetch daily Wikipedia pageviews for the topic.

    1. Parse query variants from topic (triple-pipe delimiter).
    2. Resolve to Wikipedia article via search API.
    3. Fetch daily pageviews for the resolved article.
    4. Return TrendSignal with datapoints.

    Returns None if no article found for any variant.
    """
    variants = _all_variants(topic)

    # Try each variant until one resolves
    article = None
    for variant in variants:
        article = _resolve_article(variant, config)
        if article is not None:
            break

    if article is None:
        return None

    # Get date range
    from_date, to_date = get_date_range(window_days)
    start = to_wikimedia_format(from_date)
    end = to_wikimedia_format(to_date)

    # Fetch pageviews
    datapoints = _fetch_pageviews(article, start, end, config)

    if not datapoints:
        return None

    # Compute stats
    values = [dp.value for dp in datapoints]
    current_value = values[-1] if values else None
    period_avg = sum(values) / len(values) if values else None

    return TrendSignal(
        source="wikipedia",
        metric_name="pageviews",
        metric_unit="views/day",
        dimension="search_interest",
        datapoints=datapoints,
        current_value=current_value,
        period_avg=period_avg,
        metadata={"article": article},
    )


def _all_variants(topic: str) -> List[str]:
    """Return all query variants from triple-pipe delimited topic."""
    return [v.strip() for v in topic.split("|||") if v.strip()]


def _resolve_article(topic: str, config: dict) -> Optional[str]:
    """Resolve topic to Wikipedia article title via search API.

    Uses heuristic scoring: prefer articles containing programming-related
    disambiguation hints over generic articles.
    """
    encoded = urllib.parse.quote(topic)
    url = (
        f"https://en.wikipedia.org/w/api.php"
        f"?action=query&list=search&srsearch={encoded}"
        f"&srlimit=5&format=json"
    )
    timeout = config.get("per_source_timeout", 8)
    data = http.get(url, timeout=timeout)

    results = data.get("query", {}).get("search", [])
    if not results:
        return None

    # Score results: prefer tech disambiguation
    best_title = results[0]["title"]  # Default: first result
    best_score = 0
    for r in results:
        title = r["title"]
        snippet = r.get("snippet", "").lower()
        score = sum(1 for h in TECH_HINTS if h in title.lower() or h in snippet)
        if score > best_score:
            best_score = score
            best_title = title

    return best_title.replace(" ", "_")


def _fetch_pageviews(
    article: str, start: str, end: str, config: dict
) -> List[TrendDataPoint]:
    """Fetch daily pageviews for a Wikipedia article.

    Args:
        article: URL-safe article title (underscores, not spaces)
        start: YYYYMMDD00 format
        end: YYYYMMDD00 format

    Returns:
        List of TrendDataPoint with daily pageview counts.
    """
    encoded_article = urllib.parse.quote(article, safe="")
    url = (
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
        f"/en.wikipedia.org/all-access/user/{encoded_article}/daily/{start}/{end}"
    )
    timeout = config.get("per_source_timeout", 8)
    data = http.get(url, timeout=timeout)

    items = data.get("items")
    if items is None:
        raise SourceError("wikipedia", "Response missing 'items' field")

    datapoints = []
    for item in items:
        ts = item.get("timestamp", "")  # e.g. "2026011500"
        views = item.get("views", 0)
        date_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        datapoints.append(TrendDataPoint(
            timestamp=date_str,
            value=float(views),
            raw={"views": views},
        ))
    return datapoints
