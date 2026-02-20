"""Tests for temperature skill schema module."""

import json
import sys
import unittest
from pathlib import Path

# Match last60days test convention for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.schema import (
    DimensionScore,
    SourceError,
    TemperatureReport,
    TrendDataPoint,
    TrendSignal,
    get_temperature_label,
    TEMPERATURE_LABELS,
)


class TestTrendDataPoint(unittest.TestCase):
    """Test TrendDataPoint dataclass."""

    def test_instantiation_with_all_fields(self):
        dp = TrendDataPoint(
            timestamp="2026-01-15",
            value=1234.0,
            raw={"views": 1234},
        )
        self.assertEqual(dp.timestamp, "2026-01-15")
        self.assertEqual(dp.value, 1234.0)
        self.assertEqual(dp.raw, {"views": 1234})

    def test_default_raw_is_empty_dict(self):
        dp = TrendDataPoint(timestamp="2026-01-15", value=100.0)
        self.assertEqual(dp.raw, {})

    def test_to_dict_includes_raw_when_present(self):
        dp = TrendDataPoint(
            timestamp="2026-01-15", value=42.0, raw={"key": "val"}
        )
        d = dp.to_dict()
        self.assertEqual(d["timestamp"], "2026-01-15")
        self.assertEqual(d["value"], 42.0)
        self.assertEqual(d["raw"], {"key": "val"})

    def test_to_dict_omits_empty_raw(self):
        dp = TrendDataPoint(timestamp="2026-01-15", value=42.0)
        d = dp.to_dict()
        self.assertNotIn("raw", d)

    def test_json_roundtrip(self):
        dp = TrendDataPoint(
            timestamp="2026-01-15", value=99.5, raw={"src": "wiki"}
        )
        json_str = json.dumps(dp.to_dict())
        parsed = json.loads(json_str)
        self.assertEqual(parsed["timestamp"], "2026-01-15")
        self.assertEqual(parsed["value"], 99.5)


class TestTrendSignal(unittest.TestCase):
    """Test TrendSignal dataclass."""

    def test_instantiation_with_all_fields(self):
        dp = TrendDataPoint(timestamp="2026-01-15", value=100.0)
        sig = TrendSignal(
            source="wikipedia",
            metric_name="pageviews",
            metric_unit="views/day",
            dimension="search_interest",
            datapoints=[dp],
            current_value=150.0,
            period_avg=120.0,
            direction="rising",
            velocity=0.25,
            confidence="high",
            metadata={"article": "React_(JavaScript_library)"},
        )
        self.assertEqual(sig.source, "wikipedia")
        self.assertEqual(sig.metric_name, "pageviews")
        self.assertEqual(sig.metric_unit, "views/day")
        self.assertEqual(sig.dimension, "search_interest")
        self.assertEqual(len(sig.datapoints), 1)
        self.assertEqual(sig.current_value, 150.0)
        self.assertEqual(sig.period_avg, 120.0)
        self.assertEqual(sig.direction, "rising")
        self.assertEqual(sig.velocity, 0.25)
        self.assertEqual(sig.confidence, "high")

    def test_defaults(self):
        sig = TrendSignal(
            source="npm",
            metric_name="downloads",
            metric_unit="downloads/day",
            dimension="developer_adoption",
        )
        self.assertEqual(sig.datapoints, [])
        self.assertIsNone(sig.current_value)
        self.assertIsNone(sig.period_avg)
        self.assertEqual(sig.direction, "stable")
        self.assertEqual(sig.velocity, 0.0)
        self.assertEqual(sig.confidence, "medium")
        self.assertEqual(sig.metadata, {})

    def test_to_dict_serializes_datapoints(self):
        dp = TrendDataPoint(timestamp="2026-01-15", value=50.0)
        sig = TrendSignal(
            source="npm",
            metric_name="downloads",
            metric_unit="downloads/day",
            dimension="developer_adoption",
            datapoints=[dp],
        )
        d = sig.to_dict()
        self.assertEqual(len(d["datapoints"]), 1)
        self.assertEqual(d["datapoints"][0]["timestamp"], "2026-01-15")

    def test_json_roundtrip(self):
        dp = TrendDataPoint(timestamp="2026-01-15", value=50.0)
        sig = TrendSignal(
            source="npm",
            metric_name="downloads",
            metric_unit="downloads/day",
            dimension="developer_adoption",
            datapoints=[dp],
            current_value=60.0,
        )
        json_str = json.dumps(sig.to_dict())
        parsed = json.loads(json_str)
        self.assertEqual(parsed["source"], "npm")
        self.assertEqual(parsed["current_value"], 60.0)
        self.assertEqual(len(parsed["datapoints"]), 1)


class TestDimensionScore(unittest.TestCase):
    """Test DimensionScore dataclass."""

    def test_instantiation_with_all_fields(self):
        sig = TrendSignal(
            source="wikipedia",
            metric_name="pageviews",
            metric_unit="views/day",
            dimension="search_interest",
        )
        ds = DimensionScore(
            name="search_interest",
            score=72,
            direction="rising",
            velocity=0.15,
            signals=[sig],
            active_sources=3,
            max_sources=5,
            sparkline=[10.0, 20.0, 30.0],
        )
        self.assertEqual(ds.name, "search_interest")
        self.assertEqual(ds.score, 72)
        self.assertEqual(ds.direction, "rising")
        self.assertEqual(ds.velocity, 0.15)
        self.assertEqual(len(ds.signals), 1)
        self.assertEqual(ds.active_sources, 3)
        self.assertEqual(ds.max_sources, 5)
        self.assertEqual(ds.sparkline, [10.0, 20.0, 30.0])

    def test_defaults(self):
        ds = DimensionScore(name="media")
        self.assertEqual(ds.score, 0)
        self.assertEqual(ds.direction, "stable")
        self.assertEqual(ds.velocity, 0.0)
        self.assertEqual(ds.signals, [])
        self.assertEqual(ds.active_sources, 0)
        self.assertEqual(ds.max_sources, 0)
        self.assertEqual(ds.sparkline, [])

    def test_to_dict_serializes_signals(self):
        sig = TrendSignal(
            source="gdelt",
            metric_name="volume",
            metric_unit="articles/day",
            dimension="media",
            datapoints=[TrendDataPoint(timestamp="2026-01-15", value=10.0)],
        )
        ds = DimensionScore(name="media", signals=[sig])
        d = ds.to_dict()
        self.assertEqual(len(d["signals"]), 1)
        self.assertEqual(d["signals"][0]["source"], "gdelt")
        self.assertEqual(len(d["signals"][0]["datapoints"]), 1)

    def test_json_roundtrip(self):
        ds = DimensionScore(
            name="developer_adoption",
            score=85,
            sparkline=[1.0, 2.0, 3.0, 4.0, 5.0],
        )
        json_str = json.dumps(ds.to_dict())
        parsed = json.loads(json_str)
        self.assertEqual(parsed["name"], "developer_adoption")
        self.assertEqual(parsed["score"], 85)
        self.assertEqual(parsed["sparkline"], [1.0, 2.0, 3.0, 4.0, 5.0])


class TestTemperatureReport(unittest.TestCase):
    """Test TemperatureReport dataclass."""

    def _make_full_report(self):
        """Create a full nested report for testing."""
        dp = TrendDataPoint(
            timestamp="2026-01-15", value=1234.0, raw={"views": 1234}
        )
        sig = TrendSignal(
            source="wikipedia",
            metric_name="pageviews",
            metric_unit="views/day",
            dimension="search_interest",
            datapoints=[dp],
            current_value=1500.0,
            period_avg=1200.0,
            direction="rising",
            velocity=0.25,
            confidence="high",
        )
        dim = DimensionScore(
            name="search_interest",
            score=72,
            direction="rising",
            velocity=0.15,
            signals=[sig],
            active_sources=2,
            max_sources=3,
            sparkline=[10.0, 20.0, 30.0, 40.0, 50.0],
        )
        return TemperatureReport(
            topic="React",
            timestamp="2026-01-15T00:00:00Z",
            window_days=60,
            temperature=68,
            label="Hot",
            direction="rising",
            dimensions={"search_interest": dim},
            convergence="aligned",
            hottest_dimension="search_interest",
            fastest_mover="developer_adoption",
            all_signals=[sig],
            errors={"alpha_vantage": "API key not configured"},
            config_summary={"tier1_sources": 5, "tier2_sources": 0},
        )

    def test_instantiation_with_all_fields(self):
        report = self._make_full_report()
        self.assertEqual(report.topic, "React")
        self.assertEqual(report.timestamp, "2026-01-15T00:00:00Z")
        self.assertEqual(report.window_days, 60)
        self.assertEqual(report.temperature, 68)
        self.assertEqual(report.label, "Hot")
        self.assertEqual(report.direction, "rising")
        self.assertIn("search_interest", report.dimensions)
        self.assertEqual(report.convergence, "aligned")
        self.assertEqual(report.hottest_dimension, "search_interest")
        self.assertEqual(report.fastest_mover, "developer_adoption")
        self.assertEqual(len(report.all_signals), 1)
        self.assertIn("alpha_vantage", report.errors)

    def test_defaults(self):
        report = TemperatureReport(
            topic="test", timestamp="2026-01-15", window_days=30
        )
        self.assertEqual(report.temperature, 0)
        self.assertEqual(report.label, "")
        self.assertEqual(report.direction, "stable")
        self.assertEqual(report.dimensions, {})
        self.assertEqual(report.convergence, "")
        self.assertEqual(report.hottest_dimension, "")
        self.assertEqual(report.fastest_mover, "")
        self.assertEqual(report.all_signals, [])
        self.assertEqual(report.errors, {})
        self.assertEqual(report.config_summary, {})

    def test_to_dict_recursive_serialization(self):
        """Verify to_dict() recursively serializes all nested objects."""
        report = self._make_full_report()
        d = report.to_dict()

        # Top level
        self.assertEqual(d["topic"], "React")
        self.assertEqual(d["temperature"], 68)

        # Dimensions dict -> DimensionScore -> TrendSignal -> TrendDataPoint
        dim_dict = d["dimensions"]["search_interest"]
        self.assertEqual(dim_dict["name"], "search_interest")
        self.assertEqual(dim_dict["score"], 72)

        sig_dict = dim_dict["signals"][0]
        self.assertEqual(sig_dict["source"], "wikipedia")

        dp_dict = sig_dict["datapoints"][0]
        self.assertEqual(dp_dict["timestamp"], "2026-01-15")
        self.assertEqual(dp_dict["value"], 1234.0)
        self.assertEqual(dp_dict["raw"], {"views": 1234})

        # all_signals list
        self.assertEqual(len(d["all_signals"]), 1)
        self.assertEqual(d["all_signals"][0]["source"], "wikipedia")

    def test_json_dumps_full_report(self):
        """Verify json.dumps(report.to_dict()) produces valid JSON with no TypeError."""
        report = self._make_full_report()
        json_str = json.dumps(report.to_dict())
        parsed = json.loads(json_str)
        self.assertEqual(parsed["topic"], "React")
        self.assertEqual(parsed["temperature"], 68)
        self.assertIn("search_interest", parsed["dimensions"])
        # Deep nesting check
        dp = parsed["dimensions"]["search_interest"]["signals"][0]["datapoints"][0]
        self.assertEqual(dp["timestamp"], "2026-01-15")

    def test_json_roundtrip_no_type_error(self):
        """Ensure no TypeError from nested serialization."""
        report = self._make_full_report()
        # This must not raise TypeError
        result = json.dumps(report.to_dict(), indent=2)
        self.assertIsInstance(result, str)
        self.assertIn("React", result)


class TestSourceError(unittest.TestCase):
    """Test SourceError exception class."""

    def test_instantiation(self):
        err = SourceError(source="wikipedia", message="API returned 500")
        self.assertEqual(err.source, "wikipedia")
        self.assertEqual(err.message, "API returned 500")

    def test_string_representation(self):
        err = SourceError(source="gdelt", message="timeout")
        self.assertEqual(str(err), "gdelt: timeout")

    def test_can_be_raised_and_caught(self):
        with self.assertRaises(SourceError) as ctx:
            raise SourceError(source="npm", message="rate limited")
        self.assertEqual(ctx.exception.source, "npm")
        self.assertEqual(ctx.exception.message, "rate limited")

    def test_is_exception_subclass(self):
        err = SourceError(source="test", message="test")
        self.assertIsInstance(err, Exception)


class TestGetTemperatureLabel(unittest.TestCase):
    """Test get_temperature_label() for all range boundaries."""

    def test_frozen_range(self):
        self.assertEqual(get_temperature_label(0), "Frozen")
        self.assertEqual(get_temperature_label(15), "Frozen")

    def test_cold_range(self):
        self.assertEqual(get_temperature_label(16), "Cold")
        self.assertEqual(get_temperature_label(30), "Cold")

    def test_cool_range(self):
        self.assertEqual(get_temperature_label(31), "Cool")
        self.assertEqual(get_temperature_label(45), "Cool")

    def test_warm_range(self):
        self.assertEqual(get_temperature_label(46), "Warm")
        self.assertEqual(get_temperature_label(60), "Warm")

    def test_hot_range(self):
        self.assertEqual(get_temperature_label(61), "Hot")
        self.assertEqual(get_temperature_label(75), "Hot")

    def test_on_fire_range(self):
        self.assertEqual(get_temperature_label(76), "On Fire")
        self.assertEqual(get_temperature_label(90), "On Fire")

    def test_supernova_range(self):
        self.assertEqual(get_temperature_label(91), "Supernova")
        self.assertEqual(get_temperature_label(100), "Supernova")

    def test_out_of_range_returns_unknown(self):
        self.assertEqual(get_temperature_label(-1), "Unknown")
        self.assertEqual(get_temperature_label(101), "Unknown")

    def test_all_labels_exist(self):
        """Ensure every score 0-100 maps to a non-Unknown label."""
        for score in range(0, 101):
            label = get_temperature_label(score)
            self.assertNotEqual(label, "Unknown", f"Score {score} returned Unknown")


if __name__ == "__main__":
    unittest.main()
