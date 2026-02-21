"""Output rendering for temperature skill.

Provides 4 output formats (narrative, compact, JSON, context) for
TemperatureReport objects. Each format function takes a report and
returns a string. The render() dispatcher routes by format name.

Formats:
- narrative: Full visual report with gauge, dimension table, sparklines
- compact: Single-line summary for quick scanning
- json: Raw JSON matching TemperatureReport.to_dict() schema
- context: Token-efficient key-value format for Claude pipelines
"""

import json
from typing import Dict, List

from .schema import DimensionScore, TemperatureReport
from .sparkline import sparkline


# --- Constants ---

DIRECTION_ARROWS: Dict[str, str] = {
    "surging": "\u2b06",     # ⬆
    "rising": "\u2191",      # ↑
    "stable": "\u2192",      # →
    "declining": "\u2193",   # ↓
    "crashing": "\u2b07",    # ⬇
    "new": "\U0001f195",     # 🆕
}

DIM_ABBREV: Dict[str, str] = {
    "search_interest": "search",
    "media": "media",
    "dev_ecosystem": "dev",
    "financial": "fin",
    "academic": "acad",
}


# --- Helpers ---


def _render_gauge(score: int, width: int = 28) -> str:
    """Render horizontal score gauge using Unicode blocks.

    Args:
        score: Temperature score 0-100.
        width: Total character width of gauge.

    Returns:
        String of filled and empty block characters.
    """
    filled = int(score / 100 * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def _get_arrow(direction: str) -> str:
    """Get direction arrow character."""
    return DIRECTION_ARROWS.get(direction, "\u2192")  # default →


def _get_dim_name(name: str) -> str:
    """Get display name for a dimension."""
    return DIM_ABBREV.get(name, name)


def _active_dimensions(
    dimensions: Dict[str, DimensionScore],
) -> List[DimensionScore]:
    """Get active dimensions (score > 0) sorted by score descending."""
    return sorted(
        [d for d in dimensions.values() if d.score > 0],
        key=lambda d: d.score,
        reverse=True,
    )


def _count_active_sources(report: TemperatureReport) -> int:
    """Count total active sources across all dimensions."""
    return sum(d.active_sources for d in report.dimensions.values())


def _count_failed_sources(report: TemperatureReport) -> int:
    """Count failed sources from report errors."""
    return len(report.errors) if report.errors else 0


# --- Format Functions ---


def render_narrative(report: TemperatureReport) -> str:
    """Render full narrative output with gauge, table, signals, status.

    Sections: gauge -> dimension table -> key signals -> convergence -> source status.

    Args:
        report: TemperatureReport to render.

    Returns:
        Multi-line narrative string.
    """
    lines: List[str] = []
    arrow = _get_arrow(report.direction)
    gauge = _render_gauge(report.temperature)

    # 1. Header gauge
    lines.append(
        f"\U0001f321\ufe0f {report.temperature}/100 {gauge} {report.label} {arrow} {report.direction}"
    )
    lines.append("")

    # 2. Dimension table
    active = _active_dimensions(report.dimensions)
    if active:
        lines.append(
            f"{'Dimension':<16} {'Score':>5}  {'Trend':<20}  Dir"
        )
        lines.append("\u2500" * 55)
        for dim in active:
            dim_name = _get_dim_name(dim.name)
            dim_arrow = _get_arrow(dim.direction)
            spark = sparkline(dim.sparkline, width=20) if dim.sparkline else ""
            lines.append(
                f"{dim_name:<16} {dim.score:>5}  {spark:<20}  {dim_arrow} {dim.direction}"
            )
    else:
        lines.append("No dimension data available.")

    lines.append("")

    # 3. Key signals
    if report.hottest_dimension:
        lines.append(f"Hottest: {report.hottest_dimension}")
    if report.fastest_mover:
        lines.append(f"Fastest mover: {report.fastest_mover}")

    # 4. Convergence
    if report.convergence and report.convergence != "n/a":
        lines.append(f"Convergence: {report.convergence}")

    lines.append("")

    # 5. Source status footer
    active_count = _count_active_sources(report)
    failed_count = _count_failed_sources(report)
    lines.append(f"Sources: {active_count} active, {failed_count} failed")
    if report.errors:
        for source, error in report.errors.items():
            lines.append(f"  \u2717 {source}: {error}")

    return "\n".join(lines)


def render_compact(report: TemperatureReport) -> str:
    """Render single-line compact summary.

    Format: 🌡️ Topic: score/100 Label arrow | dim1:score dim2:score | N sources

    Args:
        report: TemperatureReport to render.

    Returns:
        Single-line string.
    """
    arrow = _get_arrow(report.direction)

    # Dimension scores (active only, sorted by score desc)
    active = _active_dimensions(report.dimensions)
    dim_parts = []
    for dim in active:
        abbrev = _get_dim_name(dim.name)
        dim_parts.append(f"{abbrev}:{dim.score}")
    dim_str = " ".join(dim_parts)

    # Source count
    source_count = _count_active_sources(report)

    return (
        f"\U0001f321\ufe0f {report.topic}: {report.temperature}/100 "
        f"{report.label} {arrow} | {dim_str} | {source_count} sources"
    )


def render_json(report: TemperatureReport) -> str:
    """Render report as indented JSON.

    Args:
        report: TemperatureReport to render.

    Returns:
        JSON string with 2-space indent.
    """
    return json.dumps(report.to_dict(), indent=2)


def render_context(report: TemperatureReport) -> str:
    """Render token-efficient context format for Claude pipelines.

    Key-value lines with minimal formatting. No sparklines or decorative elements.

    Args:
        report: TemperatureReport to render.

    Returns:
        Multi-line key-value string.
    """
    lines: List[str] = []

    lines.append(f"topic: {report.topic}")
    lines.append(
        f"temperature: {report.temperature} ({report.label}, {report.direction})"
    )

    # Dimensions (active only)
    active = _active_dimensions(report.dimensions)
    if active:
        dim_parts = []
        for dim in active:
            abbrev = _get_dim_name(dim.name)
            dim_arrow = _get_arrow(dim.direction)
            dim_parts.append(f"{abbrev}={dim.score}{dim_arrow}")
        lines.append(f"dimensions: {' '.join(dim_parts)}")
    else:
        lines.append("dimensions: none")

    lines.append(f"convergence: {report.convergence}")

    # Source summary
    active_count = _count_active_sources(report)
    failed_count = _count_failed_sources(report)
    lines.append(f"sources: {active_count} active, {failed_count} failed")

    return "\n".join(lines)


# --- Dispatcher ---


def render(report: TemperatureReport, format: str = "narrative") -> str:
    """Dispatch to the appropriate format renderer.

    Args:
        report: TemperatureReport to render.
        format: One of "narrative", "compact", "json", "context".

    Returns:
        Rendered string in the requested format.

    Raises:
        ValueError: If format is not recognized.
    """
    formats = {
        "narrative": render_narrative,
        "compact": render_compact,
        "json": render_json,
        "context": render_context,
    }
    if format not in formats:
        raise ValueError(
            f"Unknown format: {format}. Choose from: {', '.join(formats)}"
        )
    return formats[format](report)
