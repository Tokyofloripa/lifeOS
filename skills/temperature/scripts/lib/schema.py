"""Data schemas for the temperature skill.

Defines the core data model: TrendDataPoint -> TrendSignal -> DimensionScore
-> TemperatureReport. All dataclasses implement to_dict() for JSON serialization.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# --- Temperature Labels ---

TEMPERATURE_LABELS = {
    (0, 15): "Frozen",
    (16, 30): "Cold",
    (31, 45): "Cool",
    (46, 60): "Warm",
    (61, 75): "Hot",
    (76, 90): "On Fire",
    (91, 100): "Supernova",
}


def get_temperature_label(score: int) -> str:
    """Return the temperature label for a given score (0-100).

    Args:
        score: Integer temperature score, 0-100.

    Returns:
        Human-readable label (e.g. "Warm", "On Fire").
    """
    for (lo, hi), label in TEMPERATURE_LABELS.items():
        if lo <= score <= hi:
            return label
    return "Unknown"


# --- Dataclasses ---


@dataclass
class TrendDataPoint:
    """Single observation at a point in time."""
    timestamp: str              # YYYY-MM-DD
    value: float                # The metric value
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {"timestamp": self.timestamp, "value": self.value}
        if self.raw:
            d["raw"] = self.raw
        return d


@dataclass
class TrendSignal:
    """Time-series signal from a single source."""
    source: str                 # "wikipedia", "gdelt", "npm", etc.
    metric_name: str            # "pageviews", "news_volume", etc.
    metric_unit: str            # "views/day", "articles/day", etc.
    dimension: str              # "search_interest", "media", etc.
    datapoints: List[TrendDataPoint] = field(default_factory=list)
    current_value: Optional[float] = None
    period_avg: Optional[float] = None
    direction: str = "stable"
    velocity: float = 0.0
    confidence: str = "medium"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "metric_name": self.metric_name,
            "metric_unit": self.metric_unit,
            "dimension": self.dimension,
            "datapoints": [dp.to_dict() for dp in self.datapoints],
            "current_value": self.current_value,
            "period_avg": self.period_avg,
            "direction": self.direction,
            "velocity": self.velocity,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class DimensionScore:
    """Aggregated score for a single dimension (e.g. search_interest)."""
    name: str
    score: int = 0              # 0-100
    direction: str = "stable"
    velocity: float = 0.0
    signals: List[TrendSignal] = field(default_factory=list)
    active_sources: int = 0
    max_sources: int = 0
    sparkline: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": self.score,
            "direction": self.direction,
            "velocity": self.velocity,
            "signals": [s.to_dict() for s in self.signals],
            "active_sources": self.active_sources,
            "max_sources": self.max_sources,
            "sparkline": self.sparkline,
        }


@dataclass
class TemperatureReport:
    """Complete temperature report for a topic."""
    topic: str
    timestamp: str              # ISO 8601
    window_days: int
    temperature: int = 0        # 0-100
    label: str = ""
    direction: str = "stable"
    dimensions: Dict[str, DimensionScore] = field(default_factory=dict)
    convergence: str = ""
    hottest_dimension: str = ""
    fastest_mover: str = ""
    all_signals: List[TrendSignal] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)
    config_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "timestamp": self.timestamp,
            "window_days": self.window_days,
            "temperature": self.temperature,
            "label": self.label,
            "direction": self.direction,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "convergence": self.convergence,
            "hottest_dimension": self.hottest_dimension,
            "fastest_mover": self.fastest_mover,
            "all_signals": [s.to_dict() for s in self.all_signals],
            "errors": self.errors,
            "config_summary": self.config_summary,
        }


# --- Exceptions ---


class SourceError(Exception):
    """Raised when a source is broken (not just unavailable).

    Distinguishes "source is broken" from "no data for this topic".
    Source modules return None for no-data, raise SourceError for broken.
    """

    def __init__(self, source: str, message: str):
        self.source = source
        self.message = message
        super().__init__(f"{source}: {message}")
