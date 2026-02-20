"""Scoring engine primitives for the temperature skill.

Provides per-signal normalization, week-over-week velocity, direction
classification, sentiment normalization, and breakout detection.

All functions are pure: data in, data out. No mutation of input TrendSignals
except where explicitly documented (velocity/direction fields).
"""

from typing import Dict, List, Optional, Tuple

from .schema import TrendDataPoint, TrendSignal, DimensionScore, get_temperature_label


# --- Constants ---

# Default equal weights (20% each). Overridable via config dict.
DEFAULT_DIMENSION_WEIGHTS: Dict[str, float] = {
    "search_interest": 0.20,
    "media":           0.20,
    "dev_ecosystem":   0.20,
    "financial":       0.20,
    "academic":        0.20,
}

# Within-dimension source weights (v1 Tier 1 sources only).
SOURCE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "search_interest": {"wikipedia": 1.0},
    "media":           {"gdelt_news_volume": 0.60, "gdelt_news_sentiment": 0.40},
    "dev_ecosystem":   {"npm": 0.50, "pypi": 0.50},
    "financial":       {},  # No v1 financial sources
    "academic":        {"semantic_scholar": 1.0},
}

# Direction thresholds: (min_velocity, label). First match wins.
DIRECTION_THRESHOLDS: List[Tuple[Optional[float], str]] = [
    (50.0,  "surging"),
    (15.0,  "rising"),
    (-15.0, "stable"),
    (-50.0, "declining"),
    (None,  "crashing"),
]

# Fold sentiment dimension into media during grouping.
DIMENSION_MAP: Dict[str, str] = {
    "sentiment": "media",
}


# --- Helpers ---


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi] range."""
    return max(lo, min(hi, value))


# --- Core Functions ---


def normalize_signal(signal: TrendSignal) -> float:
    """Compute 0-100 score for a single signal based on current vs period average.

    Score of 50 means "at period average". Higher = above average.
    Purely level-based -- velocity does NOT adjust the score.

    Special routing: signals with metric_name == "news_sentiment" go through
    normalize_sentiment() instead, using current_value as the tone.
    """
    # Route sentiment signals to dedicated normalizer
    if signal.metric_name == "news_sentiment":
        tone = signal.current_value if signal.current_value is not None else 0.0
        return normalize_sentiment(tone)

    # Handle missing current_value
    if signal.current_value is None:
        return 0.0

    # Handle zero or missing baseline
    if signal.period_avg is None or signal.period_avg == 0:
        if signal.current_value > 0:
            return 75.0  # Has data but no baseline -> assume above average
        return 0.0

    # Ratio-based: 1.0x avg = 50, 2.0x = 100, 0.5x = 25
    ratio = signal.current_value / signal.period_avg
    score = ratio * 50.0
    return clamp(score, 0.0, 100.0)


def normalize_sentiment(tone: float) -> float:
    """Map GDELT tone (-100 to +100, practical range -10 to +10) to 0-100 score.

    For temperature: positive sentiment = hotter (more buzz, excitement).
    Negative sentiment = cooler (controversy cools interest).

    Linear map: -10 -> 0, 0 -> 50, +10 -> 100.
    """
    clamped = clamp(tone, -10.0, 10.0)
    return clamp((clamped + 10.0) * 5.0, 0.0, 100.0)


def compute_velocity(datapoints: List[TrendDataPoint]) -> float:
    """Week-over-week percentage change.

    - 14+ datapoints: compare avg of last 7 vs previous 7
    - 2-13 datapoints: split in half, compare averages
    - 0-1 datapoints: return 0.0

    Returns percentage (e.g., 25.0 means +25%).
    """
    if len(datapoints) < 2:
        return 0.0

    values = [dp.value for dp in datapoints]

    # Determine windows
    if len(values) >= 14:
        recent = values[-7:]
        previous = values[-14:-7]
    else:
        midpoint = len(values) // 2
        previous = values[:midpoint]
        recent = values[midpoint:]

    avg_recent = sum(recent) / len(recent)
    avg_previous = sum(previous) / len(previous)

    if avg_previous == 0:
        if avg_recent > 0:
            return 100.0  # From zero to something
        return 0.0

    return ((avg_recent - avg_previous) / avg_previous) * 100.0


def compute_direction(velocity: float) -> str:
    """Map velocity to one of 5 direction labels.

    Uses DIRECTION_THRESHOLDS: first threshold where velocity >= min_velocity wins.
    """
    for threshold, label in DIRECTION_THRESHOLDS:
        if threshold is None:
            return label
        if velocity >= threshold:
            return label
    return "stable"  # Fallback (shouldn't reach here)


def detect_breakout(signals: Dict[str, TrendSignal]) -> bool:
    """Return True if this is a brand-new topic.

    ALL signals must have < 7 datapoints for breakout to be True.
    Any signal with >= 7 datapoints means the topic is established.
    Empty signals dict returns False.
    """
    if not signals:
        return False

    max_datapoints = max(
        len(s.datapoints) for s in signals.values()
    )
    return max_datapoints < 7
