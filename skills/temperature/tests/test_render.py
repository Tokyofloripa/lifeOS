"""Tests for render module — 4 output formats + dispatcher."""

import json
import sys
import os

# Add scripts dir to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib.schema import DimensionScore, TemperatureReport, TrendSignal
from lib.render import (
    render,
    render_narrative,
    render_compact,
    render_json,
    render_context,
)


def _make_report() -> TemperatureReport:
    """Build a standard test report with 3 dimensions."""
    dimensions = {
        "search_interest": DimensionScore(
            name="search_interest",
            score=65,
            direction="rising",
            velocity=20.0,
            signals=[],
            active_sources=1,
            max_sources=1,
            sparkline=[100, 120, 130, 140, 150],
        ),
        "media": DimensionScore(
            name="media",
            score=80,
            direction="surging",
            velocity=55.0,
            signals=[],
            active_sources=2,
            max_sources=2,
            sparkline=[50, 60, 70, 80, 90],
        ),
        "academic": DimensionScore(
            name="academic",
            score=30,
            direction="stable",
            velocity=2.0,
            signals=[],
            active_sources=1,
            max_sources=1,
            sparkline=[10, 10, 11, 10, 10],
        ),
    }
    return TemperatureReport(
        topic="React",
        timestamp="2026-02-20T00:00:00Z",
        window_days=30,
        temperature=72,
        label="Hot",
        direction="rising",
        dimensions=dimensions,
        convergence="converging up",
        hottest_dimension="media",
        fastest_mover="media",
        errors={"financial_source": "API timeout"},
    )


def _make_empty_report() -> TemperatureReport:
    """Build an empty report with no dimensions."""
    return TemperatureReport(
        topic="UnknownTopic",
        timestamp="2026-02-20T00:00:00Z",
        window_days=30,
        temperature=0,
        label="Frozen",
        direction="stable",
        dimensions={},
        convergence="n/a",
    )


def _make_report_with_zero_dim() -> TemperatureReport:
    """Build a report with a zero-score dimension (dev_ecosystem)."""
    report = _make_report()
    report.dimensions["dev_ecosystem"] = DimensionScore(
        name="dev_ecosystem",
        score=0,
        direction="stable",
        velocity=0.0,
        signals=[],
        active_sources=0,
        max_sources=2,
        sparkline=[],
    )
    return report


# --- TestRenderNarrative ---


class TestRenderNarrative:
    def test_contains_gauge(self):
        output = render_narrative(_make_report())
        assert "72/100" in output
        assert "Hot" in output
        assert "\u2191" in output  # ↑ rising arrow

    def test_contains_dimension_table(self):
        output = render_narrative(_make_report())
        # All 3 dimension names should appear
        assert "search" in output.lower()
        assert "media" in output.lower()
        assert "acad" in output.lower() or "academic" in output.lower()
        # Scores should appear
        assert "65" in output
        assert "80" in output
        assert "30" in output

    def test_dimensions_sorted_by_score_desc(self):
        output = render_narrative(_make_report())
        # media (80) should appear before search (65) before academic (30)
        media_pos = output.lower().find("media")
        search_pos = output.lower().find("search")
        acad_pos = max(output.lower().find("acad"), output.lower().find("academic"))
        assert media_pos < search_pos < acad_pos, (
            f"Expected media ({media_pos}) < search ({search_pos}) < academic ({acad_pos})"
        )

    def test_contains_sparklines(self):
        output = render_narrative(_make_report())
        spark_chars = set("\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588")
        found = any(c in output for c in spark_chars)
        assert found, "No sparkline characters found in narrative output"

    def test_contains_key_signals(self):
        output = render_narrative(_make_report())
        output_lower = output.lower()
        assert "hottest" in output_lower or "media" in output_lower
        assert "fastest" in output_lower or "mover" in output_lower

    def test_contains_convergence(self):
        output = render_narrative(_make_report())
        assert "converging up" in output.lower()

    def test_contains_source_status(self):
        output = render_narrative(_make_report())
        assert "failed" in output.lower()
        assert "financial_source" in output
        assert "API timeout" in output

    def test_empty_report(self):
        output = render_narrative(_make_empty_report())
        assert "0/100" in output or "Frozen" in output
        # Should not error


# --- TestRenderCompact ---


class TestRenderCompact:
    def test_single_line(self):
        output = render_compact(_make_report())
        # Strip trailing newline, then check no internal newlines
        stripped = output.strip()
        assert "\n" not in stripped, f"Compact output has multiple lines: {stripped!r}"

    def test_contains_topic_and_score(self):
        output = render_compact(_make_report())
        assert "React" in output
        assert "72" in output
        assert "Hot" in output

    def test_contains_direction_arrow(self):
        output = render_compact(_make_report())
        assert "\u2191" in output  # ↑ rising

    def test_dimension_abbreviations(self):
        output = render_compact(_make_report())
        assert "search" in output.lower()
        assert "media" in output.lower()
        assert "acad" in output.lower()

    def test_skips_zero_score_dimensions(self):
        report = _make_report_with_zero_dim()
        output = render_compact(report)
        # dev_ecosystem has score=0, should not appear as "dev:0"
        assert "dev:0" not in output.lower()

    def test_contains_source_count(self):
        output = render_compact(_make_report())
        # Should contain a source count (sum of active_sources = 1+2+1 = 4)
        assert "source" in output.lower()

    def test_empty_report(self):
        output = render_compact(_make_empty_report())
        # Should not error, should still be a single line
        assert isinstance(output, str)


# --- TestRenderJson ---


class TestRenderJson:
    def test_valid_json(self):
        output = render_json(_make_report())
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_matches_to_dict(self):
        report = _make_report()
        output = render_json(report)
        data = json.loads(output)
        assert data == report.to_dict()

    def test_has_indent(self):
        output = render_json(_make_report())
        assert "\n" in output
        assert "  " in output  # indented

    def test_empty_report(self):
        output = render_json(_make_empty_report())
        data = json.loads(output)
        assert data["temperature"] == 0


# --- TestRenderContext ---


class TestRenderContext:
    def test_contains_topic(self):
        output = render_context(_make_report())
        assert "React" in output

    def test_contains_temperature(self):
        output = render_context(_make_report())
        assert "72" in output
        assert "Hot" in output
        assert "rising" in output

    def test_contains_dimensions(self):
        output = render_context(_make_report())
        output_lower = output.lower()
        assert "search" in output_lower
        assert "media" in output_lower
        assert "65" in output
        assert "80" in output

    def test_contains_convergence(self):
        output = render_context(_make_report())
        assert "converging up" in output.lower()

    def test_contains_source_summary(self):
        output = render_context(_make_report())
        output_lower = output.lower()
        assert "active" in output_lower
        assert "failed" in output_lower

    def test_no_sparklines(self):
        output = render_context(_make_report())
        spark_chars = set("\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588")
        found = any(c in output for c in spark_chars)
        assert not found, "Context output should NOT contain sparkline characters"

    def test_empty_report(self):
        output = render_context(_make_empty_report())
        assert isinstance(output, str)
        assert "0" in output or "Frozen" in output


# --- TestRenderDispatcher ---


class TestRenderDispatcher:
    def test_narrative_format(self):
        report = _make_report()
        assert render(report, "narrative") == render_narrative(report)

    def test_compact_format(self):
        report = _make_report()
        assert render(report, "compact") == render_compact(report)

    def test_json_format(self):
        report = _make_report()
        assert render(report, "json") == render_json(report)

    def test_context_format(self):
        report = _make_report()
        assert render(report, "context") == render_context(report)

    def test_unknown_format_raises(self):
        import pytest

        with pytest.raises(ValueError):
            render(_make_report(), "unknown")
