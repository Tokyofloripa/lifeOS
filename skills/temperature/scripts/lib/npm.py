"""npm Downloads source — daily download counts for npm packages.

Tier 1 (free, no auth). Covers dev_ecosystem dimension.
Uses npm registry downloads API for daily download counts.
Validates package existence to distinguish "no data" from "zero interest".
Handles scoped packages (@scope/name) via URL encoding.
"""

import urllib.parse
from typing import Dict, List, Optional

from . import http
from .dates import get_date_range
from .http import HTTPError
from .schema import SourceError, TrendDataPoint, TrendSignal

# --- Protocol constants ---

SOURCE_NAME = "npm"
DISPLAY_NAME = "npm Downloads"
SOURCE_TIER = 1
SOURCE_DIMENSION = "dev_ecosystem"


def is_available(config: dict) -> bool:
    """Always available — no auth required."""
    return True


def should_search(topic: str) -> bool:
    """Returns True for all topics; search() handles package resolution."""
    return True


def search(topic: str, window_days: int, config: dict) -> Optional[TrendSignal]:
    """Search npm for package download data.

    Tries each query variant as a package name. Returns TrendSignal
    with daily download datapoints, or None if no package found.
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
    start, end = get_date_range(window_days)
    datapoints = _fetch_downloads(package, start, end, config)

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
    """Validate package exists via npm point endpoint.

    Returns True if package exists (200), False if not (404).
    Raises HTTPError for other errors.
    """
    encoded = urllib.parse.quote(package, safe="")
    url = f"https://api.npmjs.org/downloads/point/last-week/{encoded}"
    try:
        http.get(url, timeout=5)
        return True
    except HTTPError as e:
        if e.status_code == 404:
            return False
        raise


def _fetch_downloads(
    package: str, start: str, end: str, config: dict
) -> List[TrendDataPoint]:
    """Fetch daily npm download counts.

    Args:
        package: Package name (will be URL-encoded)
        start: YYYY-MM-DD start date
        end: YYYY-MM-DD end date
        config: Configuration dict

    Returns:
        List of TrendDataPoint with daily downloads

    Raises:
        SourceError: If response is missing required fields
    """
    encoded = urllib.parse.quote(package, safe="")
    url = f"https://api.npmjs.org/downloads/range/{start}:{end}/{encoded}"
    timeout = config.get("per_source_timeout", 5)
    data = http.get(url, timeout=timeout)

    downloads = data.get("downloads")
    if downloads is None:
        raise SourceError("npm", "Response missing 'downloads' field")

    datapoints = []
    for entry in downloads:
        datapoints.append(
            TrendDataPoint(
                timestamp=entry["day"],
                value=float(entry["downloads"]),
                raw=entry,
            )
        )
    return datapoints
