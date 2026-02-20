"""Tests for gdelt.py — GDELT DOC 2.0 source module (dual-signal: volume + sentiment).

Tests protocol compliance, timeline parsing, dual-signal return, partial failure,
window clamping, date aggregation, and sources.py list-return handling.
"""

import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.schema import TrendSignal, TrendDataPoint, SourceError


# --- Fixture loading ---

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


# ============================================================
# Class 1: TestProtocolCompliance
# ============================================================

class TestProtocolCompliance:
    """Verify 4 constants + 3 functions exist with correct values."""

    def test_has_source_name(self):
        from lib.gdelt import SOURCE_NAME
        assert SOURCE_NAME == "gdelt"

    def test_has_display_name(self):
        from lib.gdelt import DISPLAY_NAME
        assert DISPLAY_NAME == "GDELT News"

    def test_has_source_tier(self):
        from lib.gdelt import SOURCE_TIER
        assert SOURCE_TIER == 1

    def test_has_source_dimension(self):
        from lib.gdelt import SOURCE_DIMENSION
        assert SOURCE_DIMENSION == "media"

    def test_is_available_callable(self):
        from lib.gdelt import is_available
        assert callable(is_available)

    def test_should_search_callable(self):
        from lib.gdelt import should_search
        assert callable(should_search)

    def test_search_callable(self):
        from lib.gdelt import search
        assert callable(search)

    def test_is_available_returns_true(self):
        from lib.gdelt import is_available
        assert is_available({}) is True

    def test_should_search_returns_true(self):
        from lib.gdelt import should_search
        assert should_search("anything") is True


# ============================================================
# Class 2: TestTimelineParsing
# ============================================================

class TestTimelineParsing:
    """Test timeline response parsing with fixture data."""

    def test_volume_timeline_produces_datapoints(self):
        """Volume fixture produces correct number of daily TrendDataPoints."""
        from lib import gdelt
        fixture = _load_fixture("gdelt_climate_vol.json")
        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.return_value = fixture
            dps = gdelt._fetch_timeline("climate change", "timelinevolraw", "90d", {})
        assert len(dps) == 90

    def test_volume_dates_in_correct_format(self):
        """All timestamps should be YYYY-MM-DD format."""
        from lib import gdelt
        fixture = _load_fixture("gdelt_climate_vol.json")
        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.return_value = fixture
            dps = gdelt._fetch_timeline("climate change", "timelinevolraw", "90d", {})
        for dp in dps:
            assert len(dp.timestamp) == 10
            assert dp.timestamp[4] == "-"
            assert dp.timestamp[7] == "-"

    def test_volume_values_are_positive_floats(self):
        """Volume values should be positive floats."""
        from lib import gdelt
        fixture = _load_fixture("gdelt_climate_vol.json")
        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.return_value = fixture
            dps = gdelt._fetch_timeline("climate change", "timelinevolraw", "90d", {})
        for dp in dps:
            assert isinstance(dp.value, float)
            assert dp.value >= 0

    def test_tone_timeline_produces_datapoints(self):
        """Tone fixture produces correct number of daily TrendDataPoints."""
        from lib import gdelt
        fixture = _load_fixture("gdelt_climate_tone.json")
        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.return_value = fixture
            dps = gdelt._fetch_timeline("climate change", "timelinetone", "90d", {})
        assert len(dps) == 90

    def test_tone_values_can_be_negative(self):
        """Tone values use raw scale (-100 to +100), can be negative."""
        from lib import gdelt
        fixture = _load_fixture("gdelt_climate_tone.json")
        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.return_value = fixture
            dps = gdelt._fetch_timeline("climate change", "timelinetone", "90d", {})
        values = [dp.value for dp in dps]
        has_negative = any(v < 0 for v in values)
        assert has_negative, "Tone values should include negative values (raw GDELT scale)"

    def test_empty_timeline_returns_empty_list(self):
        """Empty or missing timeline returns empty list."""
        from lib import gdelt
        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.return_value = {"timeline": []}
            dps = gdelt._fetch_timeline("test", "timelinevolraw", "90d", {})
        assert dps == []

    def test_missing_timeline_key_returns_empty(self):
        """Response without 'timeline' key returns empty list."""
        from lib import gdelt
        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.return_value = {}
            dps = gdelt._fetch_timeline("test", "timelinevolraw", "90d", {})
        assert dps == []


# ============================================================
# Class 3: TestSearchDualSignal
# ============================================================

class TestSearchDualSignal:
    """Test that search() returns a list of exactly 2 TrendSignals."""

    def test_search_returns_two_signals(self):
        """search() returns list of 2 TrendSignals (volume + sentiment)."""
        from lib import gdelt
        vol_fixture = _load_fixture("gdelt_climate_vol.json")
        tone_fixture = _load_fixture("gdelt_climate_tone.json")

        call_count = [0]
        def mock_get(url, **kwargs):
            call_count[0] += 1
            if "timelinevolraw" in url:
                return vol_fixture
            elif "timelinetone" in url:
                return tone_fixture
            return {}

        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.side_effect = mock_get
            result = gdelt.search("climate change", 90, {})

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2

    def test_first_signal_is_volume(self):
        """First signal has metric_name='news_volume', dimension='media'."""
        from lib import gdelt
        vol_fixture = _load_fixture("gdelt_climate_vol.json")
        tone_fixture = _load_fixture("gdelt_climate_tone.json")

        def mock_get(url, **kwargs):
            if "timelinevolraw" in url:
                return vol_fixture
            return tone_fixture

        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.side_effect = mock_get
            result = gdelt.search("climate change", 90, {})

        volume_signal = result[0]
        assert volume_signal.metric_name == "news_volume"
        assert volume_signal.dimension == "media"
        assert volume_signal.metric_unit == "articles/day"
        assert len(volume_signal.datapoints) == 90

    def test_second_signal_is_sentiment(self):
        """Second signal has metric_name='news_sentiment', dimension='sentiment'."""
        from lib import gdelt
        vol_fixture = _load_fixture("gdelt_climate_vol.json")
        tone_fixture = _load_fixture("gdelt_climate_tone.json")

        def mock_get(url, **kwargs):
            if "timelinevolraw" in url:
                return vol_fixture
            return tone_fixture

        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.side_effect = mock_get
            result = gdelt.search("climate change", 90, {})

        sentiment_signal = result[1]
        assert sentiment_signal.metric_name == "news_sentiment"
        assert sentiment_signal.dimension == "sentiment"
        assert sentiment_signal.metric_unit == "tone_score"
        assert sentiment_signal.confidence == "medium"
        assert len(sentiment_signal.datapoints) == 90

    def test_sentiment_values_are_raw_tone(self):
        """Sentiment values use raw GDELT tone scale, not normalized."""
        from lib import gdelt
        vol_fixture = _load_fixture("gdelt_climate_vol.json")
        tone_fixture = _load_fixture("gdelt_climate_tone.json")

        def mock_get(url, **kwargs):
            if "timelinevolraw" in url:
                return vol_fixture
            return tone_fixture

        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.side_effect = mock_get
            result = gdelt.search("climate change", 90, {})

        sentiment = result[1]
        values = [dp.value for dp in sentiment.datapoints]
        # Raw tone values should include negatives (not 0-100 range)
        has_negative = any(v < 0 for v in values)
        assert has_negative, "Raw tone values should include negatives"


# ============================================================
# Class 4: TestSearchPartialFailure
# ============================================================

class TestSearchPartialFailure:
    """Test graceful degradation when one signal fails."""

    def test_volume_only_when_tone_fails(self):
        """Returns list with 1 signal (volume) when tone fails."""
        from lib import gdelt
        vol_fixture = _load_fixture("gdelt_climate_vol.json")

        def mock_get(url, **kwargs):
            if "timelinevolraw" in url:
                return vol_fixture
            # Tone returns empty
            return {"timeline": []}

        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.side_effect = mock_get
            result = gdelt.search("climate change", 90, {})

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].metric_name == "news_volume"

    def test_returns_none_when_both_fail(self):
        """Returns None when both volume and tone fail."""
        from lib import gdelt

        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.return_value = {"timeline": []}
            result = gdelt.search("climate change", 90, {})

        assert result is None

    def test_http_error_returns_none(self):
        """HTTP error on both calls returns None gracefully."""
        from lib import gdelt
        from lib.http import HTTPError

        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.side_effect = HTTPError("Server error", status_code=500)
            result = gdelt.search("climate change", 90, {})

        assert result is None


# ============================================================
# Class 5: TestWindowClamping
# ============================================================

class TestWindowClamping:
    """Test that window_days > 90 is clamped to 90."""

    def test_window_clamped_to_90(self):
        """Window > 90 days is clamped to 90 in GDELT timespan parameter."""
        from lib import gdelt

        captured_urls = []
        def mock_get(url, **kwargs):
            captured_urls.append(url)
            return {"timeline": []}

        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.side_effect = mock_get
            gdelt.search("test", 180, {})

        # Both calls should use 90d, not 180d
        for url in captured_urls:
            assert "timespan=90d" in url, f"Expected 90d in URL: {url}"

    def test_window_under_90_preserved(self):
        """Window <= 90 days is used as-is."""
        from lib import gdelt

        captured_urls = []
        def mock_get(url, **kwargs):
            captured_urls.append(url)
            return {"timeline": []}

        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.side_effect = mock_get
            gdelt.search("test", 30, {})

        for url in captured_urls:
            assert "timespan=30d" in url, f"Expected 30d in URL: {url}"


# ============================================================
# Class 6: TestDateAggregation
# ============================================================

class TestDateAggregation:
    """Test sub-daily data aggregation into daily datapoints."""

    def test_sub_daily_volume_summed(self):
        """Multiple entries for same date should be summed for volume."""
        from lib import gdelt
        sub_daily = {
            "timeline": [{
                "series": "test",
                "data": [
                    {"date": "2026-01-15T00:00:00Z", "value": 100},
                    {"date": "2026-01-15T06:00:00Z", "value": 50},
                    {"date": "2026-01-15T12:00:00Z", "value": 75},
                    {"date": "2026-01-16T00:00:00Z", "value": 200},
                ]
            }]
        }

        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.return_value = sub_daily
            dps = gdelt._fetch_timeline("test", "timelinevolraw", "7d", {})

        assert len(dps) == 2  # 2 unique dates
        # Jan 15: 100 + 50 + 75 = 225
        assert dps[0].timestamp == "2026-01-15"
        assert dps[0].value == 225.0
        # Jan 16: 200
        assert dps[1].timestamp == "2026-01-16"
        assert dps[1].value == 200.0

    def test_sub_daily_tone_averaged(self):
        """Multiple entries for same date should be averaged for tone."""
        from lib import gdelt
        sub_daily = {
            "timeline": [{
                "series": "test",
                "data": [
                    {"date": "2026-01-15T00:00:00Z", "value": -2.0},
                    {"date": "2026-01-15T12:00:00Z", "value": 4.0},
                    {"date": "2026-01-16T00:00:00Z", "value": 1.0},
                ]
            }]
        }

        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.return_value = sub_daily
            dps = gdelt._fetch_timeline("test", "timelinetone", "7d", {})

        assert len(dps) == 2
        # Jan 15: (-2.0 + 4.0) / 2 = 1.0
        assert dps[0].timestamp == "2026-01-15"
        assert dps[0].value == 1.0
        # Jan 16: 1.0
        assert dps[1].timestamp == "2026-01-16"
        assert dps[1].value == 1.0

    def test_sorted_by_date(self):
        """Output datapoints are sorted by date."""
        from lib import gdelt
        unsorted = {
            "timeline": [{
                "series": "test",
                "data": [
                    {"date": "2026-01-17T00:00:00Z", "value": 300},
                    {"date": "2026-01-15T00:00:00Z", "value": 100},
                    {"date": "2026-01-16T00:00:00Z", "value": 200},
                ]
            }]
        }

        with patch.object(gdelt, "http") as mock_http:
            mock_http.get.return_value = unsorted
            dps = gdelt._fetch_timeline("test", "timelinevolraw", "7d", {})

        dates = [dp.timestamp for dp in dps]
        assert dates == sorted(dates)


# ============================================================
# Class 7: TestSourcesListReturnHandling
# ============================================================

class TestSourcesListReturnHandling:
    """Test run_sources() handling of list returns from multi-signal sources."""

    def _make_signal(self, source, metric_name):
        return TrendSignal(
            source=source,
            metric_name=metric_name,
            metric_unit="units",
            dimension="test",
            datapoints=[TrendDataPoint(timestamp="2026-02-20", value=42.0)],
            current_value=42.0,
            period_avg=40.0,
        )

    def test_list_return_flattened_into_results(self):
        """Source returning list of 2 signals produces 2 entries in results."""
        from lib.sources import run_sources

        sig1 = self._make_signal("mock_multi", "signal_a")
        sig2 = self._make_signal("mock_multi", "signal_b")

        mock_module = types.SimpleNamespace(
            SOURCE_NAME="mock_multi",
            DISPLAY_NAME="Mock Multi",
            SOURCE_TIER=1,
            SOURCE_DIMENSION="test",
            is_available=lambda config: True,
            should_search=lambda topic: True,
            search=lambda topic, window_days, config: [sig1, sig2],
        )

        selected = {"mock_multi": mock_module}
        results, all_results = run_sources(selected, "topic", 30, {})

        assert "mock_multi_signal_a" in results
        assert "mock_multi_signal_b" in results
        assert results["mock_multi_signal_a"] is sig1
        assert results["mock_multi_signal_b"] is sig2

    def test_single_return_still_works(self):
        """Single TrendSignal return (non-list) still works correctly."""
        from lib.sources import run_sources

        sig = self._make_signal("single_src", "metric")
        mock_module = types.SimpleNamespace(
            SOURCE_NAME="single_src",
            DISPLAY_NAME="Single Source",
            SOURCE_TIER=1,
            SOURCE_DIMENSION="test",
            is_available=lambda config: True,
            should_search=lambda topic: True,
            search=lambda topic, window_days, config: sig,
        )

        selected = {"single_src": mock_module}
        results, all_results = run_sources(selected, "topic", 30, {})

        assert "single_src" in results
        assert results["single_src"] is sig

    def test_mixed_single_and_list_sources(self):
        """Mix of single-return and list-return sources both work."""
        from lib.sources import run_sources

        sig_single = self._make_signal("src_single", "metric")
        sig_a = self._make_signal("src_multi", "signal_a")
        sig_b = self._make_signal("src_multi", "signal_b")

        single_module = types.SimpleNamespace(
            SOURCE_NAME="src_single",
            DISPLAY_NAME="Single",
            SOURCE_TIER=1,
            SOURCE_DIMENSION="test",
            is_available=lambda config: True,
            should_search=lambda topic: True,
            search=lambda topic, window_days, config: sig_single,
        )
        multi_module = types.SimpleNamespace(
            SOURCE_NAME="src_multi",
            DISPLAY_NAME="Multi",
            SOURCE_TIER=1,
            SOURCE_DIMENSION="test",
            is_available=lambda config: True,
            should_search=lambda topic: True,
            search=lambda topic, window_days, config: [sig_a, sig_b],
        )

        selected = {"src_single": single_module, "src_multi": multi_module}
        results, all_results = run_sources(selected, "topic", 30, {})

        assert "src_single" in results
        assert "src_multi_signal_a" in results
        assert "src_multi_signal_b" in results
        assert len(results) == 3
