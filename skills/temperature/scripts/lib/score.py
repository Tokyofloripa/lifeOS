"""Scoring engine for the temperature skill.

Provides per-signal normalization, week-over-week velocity, direction
classification, sentiment normalization, breakout detection, dimension
aggregation, overall temperature computation, convergence detection,
and the top-level score_signals() pipeline function.

All functions are pure: data in, data out. No mutation of input TrendSignals
except where explicitly documented (velocity/direction fields).
"""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from .schema import (
    DimensionScore,
    TemperatureReport,
    TrendDataPoint,
    TrendSignal,
    get_temperature_label,
)


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


# --- Dimension Aggregation ---


def group_by_dimension(
    signals: Dict[str, TrendSignal],
) -> Dict[str, List[TrendSignal]]:
    """Group signals by dimension name, applying DIMENSION_MAP remapping.

    Sentiment signals get remapped to media dimension via DIMENSION_MAP.
    """
    groups: Dict[str, List[TrendSignal]] = defaultdict(list)
    for signal in signals.values():
        dim = DIMENSION_MAP.get(signal.dimension, signal.dimension)
        groups[dim].append(signal)
    return dict(groups)


def _renormalize_weights(available: Dict[str, float]) -> Dict[str, float]:
    """Re-normalize source weights to sum to 1.0 for available sources only.

    When some sources in a dimension are missing, redistribute weight
    proportionally among present sources.
    """
    total = sum(available.values())
    if total == 0:
        n = len(available)
        return {k: 1.0 / n for k in available} if n > 0 else {}
    return {k: v / total for k, v in available.items()}


def _source_key(signal: TrendSignal) -> str:
    """Derive the weight-lookup key for a signal.

    GDELT composite signals use 'source_metric_name' pattern (e.g.
    'gdelt_news_volume'). Other sources use plain source name.
    """
    if signal.source == "gdelt":
        return f"{signal.source}_{signal.metric_name}"
    return signal.source


def score_dimension(
    signals: List[TrendSignal],
    source_weights: Dict[str, float],
) -> DimensionScore:
    """Aggregate multiple signals into a single dimension score.

    Re-normalizes source weights for available sources within the dimension.
    Missing sources get their weight redistributed proportionally.

    Args:
        signals: List of TrendSignal objects within this dimension.
        source_weights: Configured weights for sources in this dimension
            (e.g. {"npm": 0.50, "pypi": 0.50}).

    Returns:
        DimensionScore with weighted composite score, direction, sparkline.
    """
    if not signals:
        return DimensionScore(name="unknown", score=0)

    dim_name = DIMENSION_MAP.get(signals[0].dimension, signals[0].dimension)

    # Compute velocity/direction for each signal
    for sig in signals:
        sig.velocity = compute_velocity(sig.datapoints)
        sig.direction = compute_direction(sig.velocity)

    # Build available weights (only for sources we actually have)
    available: Dict[str, float] = {}
    for sig in signals:
        key = _source_key(sig)
        weight = source_weights.get(key, 1.0 / len(signals))
        available[key] = weight

    # Re-normalize to sum to 1.0
    normalized = _renormalize_weights(available)

    # Compute weighted score and velocity
    weighted_score = 0.0
    weighted_velocity = 0.0
    for sig in signals:
        key = _source_key(sig)
        w = normalized.get(key, 0.0)
        sig_score = normalize_signal(sig)
        weighted_score += w * sig_score
        weighted_velocity += w * sig.velocity

    # Direction from weighted velocity
    direction = compute_direction(weighted_velocity)

    # Sparkline from signal with most datapoints
    sparkline_values: List[float] = []
    best_count = 0
    for sig in signals:
        if len(sig.datapoints) > best_count:
            best_count = len(sig.datapoints)
            sparkline_values = [dp.value for dp in sig.datapoints]

    return DimensionScore(
        name=dim_name,
        score=int(clamp(weighted_score, 0.0, 100.0)),
        direction=direction,
        velocity=weighted_velocity,
        signals=signals,
        active_sources=len(signals),
        max_sources=len(source_weights) if source_weights else len(signals),
        sparkline=sparkline_values,
    )


# --- Temperature Computation ---


def compute_temperature(
    dimensions: Dict[str, DimensionScore],
    weights: Dict[str, float] = None,
) -> Tuple[int, str]:
    """Combine dimension scores into overall 0-100 temperature.

    Default weights: 20% each for 5 dimensions.
    Missing dimensions contribute 0 (no re-normalization at overall level).

    Args:
        dimensions: name -> DimensionScore dict.
        weights: Optional custom dimension weights. Defaults to equal 20%.

    Returns:
        (temperature, label) tuple.
    """
    w = weights or DEFAULT_DIMENSION_WEIGHTS

    total = 0.0
    for dim_name, dim_weight in w.items():
        dim = dimensions.get(dim_name)
        if dim is not None:
            total += dim_weight * dim.score

    temperature = int(clamp(total, 0.0, 100.0))
    label = get_temperature_label(temperature)
    return temperature, label


# --- Convergence Detection ---


def detect_convergence(dimensions: Dict[str, DimensionScore]) -> str:
    """Classify cross-dimension directional agreement.

    Returns one of:
    - "strongly converging up" -- all active rising/surging, avg |velocity| > 30
    - "converging up" -- all active rising/surging
    - "strongly converging down" -- all active declining/crashing, avg |velocity| > 30
    - "converging down" -- all active declining/crashing
    - "diverging" -- some positive, some negative directions present
    - "mixed" -- none of the above (e.g. all stable)
    - "n/a" -- fewer than 2 active dimensions

    Active dimensions have score > 0.
    """
    active = [d for d in dimensions.values() if d.score > 0]

    if len(active) < 2:
        return "n/a"

    directions = [d.direction for d in active]
    velocities = [d.velocity for d in active]

    positive = {"surging", "rising"}
    negative = {"declining", "crashing"}

    pos_count = sum(1 for d in directions if d in positive)
    neg_count = sum(1 for d in directions if d in negative)
    total = len(directions)

    if pos_count == total:
        avg_vel = sum(abs(v) for v in velocities) / total
        if avg_vel > 30:
            return "strongly converging up"
        return "converging up"
    elif neg_count == total:
        avg_vel = sum(abs(v) for v in velocities) / total
        if avg_vel > 30:
            return "strongly converging down"
        return "converging down"
    elif pos_count > 0 and neg_count > 0:
        return "diverging"
    else:
        return "mixed"


# --- Pipeline Helpers ---


def _aggregate_direction(dimensions: Dict[str, DimensionScore]) -> str:
    """Derive overall direction from dimension directions.

    Weight-averaged velocity across active dimensions, then classify.
    """
    active = [d for d in dimensions.values() if d.score > 0]
    if not active:
        return "stable"

    total_velocity = sum(d.velocity for d in active) / len(active)
    return compute_direction(total_velocity)


def _find_hottest(dimensions: Dict[str, DimensionScore]) -> str:
    """Return the name of the dimension with the highest score."""
    if not dimensions:
        return ""
    best = max(dimensions.values(), key=lambda d: d.score)
    return best.name


def _find_fastest(dimensions: Dict[str, DimensionScore]) -> str:
    """Return the name of the dimension with the highest absolute velocity."""
    if not dimensions:
        return ""
    best = max(dimensions.values(), key=lambda d: abs(d.velocity))
    return best.name


# --- Top-Level Pipeline ---


def score_signals(
    signals: Dict[str, TrendSignal],
    dimension_weights: Dict[str, float] = None,
) -> TemperatureReport:
    """Score all signals into a TemperatureReport.

    Full pipeline: compute velocity/direction per signal -> group by dimension
    -> score dimensions -> compute temperature -> detect convergence ->
    detect breakout -> build TemperatureReport.

    Args:
        signals: name -> TrendSignal dict from sources.run_sources().
        dimension_weights: Override default equal weights.

    Returns:
        Populated TemperatureReport (topic/timestamp/window_days left empty
        for the orchestrator to fill).
    """
    # Step 1: Compute velocity and direction for each signal
    for signal in signals.values():
        signal.velocity = compute_velocity(signal.datapoints)
        signal.direction = compute_direction(signal.velocity)

    # Step 2: Group signals by dimension (with sentiment -> media remapping)
    by_dimension = group_by_dimension(signals)

    # Step 3: Score each dimension
    dimensions: Dict[str, DimensionScore] = {}
    for dim_name, dim_signals in by_dimension.items():
        source_wts = SOURCE_WEIGHTS.get(dim_name, {})
        dimensions[dim_name] = score_dimension(dim_signals, source_wts)

    # Step 4: Compute overall temperature
    temperature, label = compute_temperature(dimensions, dimension_weights)

    # Step 5: Detect convergence
    convergence = detect_convergence(dimensions)

    # Step 6: Check for breakout (new topic)
    is_new = detect_breakout(signals)
    overall_direction = _aggregate_direction(dimensions)
    if is_new:
        overall_direction = "new"

    return TemperatureReport(
        topic="",  # Filled by orchestrator
        timestamp="",  # Filled by orchestrator
        window_days=0,  # Filled by orchestrator
        temperature=temperature,
        label=label,
        direction=overall_direction,
        dimensions=dimensions,
        convergence=convergence,
        hottest_dimension=_find_hottest(dimensions),
        fastest_mover=_find_fastest(dimensions),
        all_signals=list(signals.values()),
    )
