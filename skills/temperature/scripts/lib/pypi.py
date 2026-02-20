"""PyPI Downloads source — daily download counts for PyPI packages.

Tier 1 (free, no auth). Covers dev_ecosystem dimension.
Uses pypistats.org API for daily download counts with mirrors excluded.
Validates package existence via PyPI JSON API.
Filters datapoints to requested window_days (pypistats returns up to 180 days).
"""

import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from . import http
from .http import HTTPError
from .schema import SourceError, TrendDataPoint, TrendSignal

# --- Protocol constants ---

SOURCE_NAME = "pypi"
DISPLAY_NAME = "PyPI Downloads"
SOURCE_TIER = 1
SOURCE_DIMENSION = "dev_ecosystem"


def is_available(config: dict) -> bool:
    """Always available — no auth required."""
    return True


def should_search(topic: str) -> bool:
    """Returns True for all topics; search() handles package resolution."""
    return True


def search(topic: str, window_days: int, config: dict) -> Optional[TrendSignal]:
    """Search PyPI for package download data.

    Tries each query variant as a package name (lowercased, hyphen-normalized).
    Returns TrendSignal with daily download datapoints (mirrors excluded),
    or None if no package found.
    """
    variants = [v.strip() for v in topic.split("|||") if v.strip()]
    if not variants:
        return None

    # Try each variant as a package name
    package = None
    for variant in variants:
        # Normalize: lowercase, strip whitespace
        candidate = variant.lower().strip()
        try:
            if _package_exists(candidate):
                package = candidate
                break
        except HTTPError:
            continue  # Try next variant on non-404 errors

    if package is None:
        return None

    # Fetch daily downloads
    datapoints = _fetch_downloads(package, config)

    if not datapoints:
        return None

    # Filter to requested window_days
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=window_days)).isoformat()
    datapoints = [dp for dp in datapoints if dp.timestamp >= cutoff]

    if not datapoints:
        return None

    # Compute current_value (last datapoint) and period_avg
    values = [dp.value for dp in datapoints]
    current_value = values[-1] if values else None
    period_avg = sum(values) / len(values) if values else None

    return TrendSignal(
        source=SOURCE_NAME,
        metric_name="downloads",
        metric_unit="downloads/day",
        dimension=SOURCE_DIMENSION,
        datapoints=datapoints,
        current_value=current_value,
        period_avg=period_avg,
        metadata={"package": package},
    )


def _package_exists(package: str) -> bool:
    """Validate package exists via PyPI JSON API.

    Returns True if package exists (200), False if not (404).
    Raises HTTPError for other errors.
    """
    encoded = urllib.parse.quote(package, safe="")
    url = f"https://pypi.org/pypi/{encoded}/json"
    try:
        http.get(url, timeout=5)
        return True
    except HTTPError as e:
        if e.status_code == 404:
            return False
        raise


def _fetch_downloads(package: str, config: dict) -> List[TrendDataPoint]:
    """Fetch daily PyPI download counts (mirrors excluded).

    Args:
        package: Package name (will be URL-encoded)
        config: Configuration dict

    Returns:
        List of TrendDataPoint filtered to 'without_mirrors' category,
        sorted by timestamp ascending.

    Raises:
        SourceError: If response is missing required fields
    """
    encoded = urllib.parse.quote(package, safe="")
    url = f"https://pypistats.org/api/packages/{encoded}/overall?mirrors=false"
    timeout = config.get("per_source_timeout", 8)
    data = http.get(url, timeout=timeout)

    items = data.get("data")
    if items is None:
        raise SourceError("pypi", "Response missing 'data' field")

    datapoints = []
    for entry in items:
        if entry.get("category") == "without_mirrors":
            datapoints.append(
                TrendDataPoint(
                    timestamp=entry["date"],
                    value=float(entry["downloads"]),
                    raw=entry,
                )
            )

    # Sort by timestamp ascending
    datapoints.sort(key=lambda dp: dp.timestamp)
    return datapoints
