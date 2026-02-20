"""Tests for PyPI Downloads source module.

Tests pypi.py: package existence validation, mirror filtering,
window filtering, and full search integration.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.schema import TrendSignal, TrendDataPoint, SourceError
from lib.http import HTTPError
from lib import pypi


# --- Fixtures ---

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


# --- Protocol Compliance ---


class TestProtocolCompliance:
    """Verify pypi module implements the 4-constant + 3-function protocol."""

    def test_has_source_name(self):
        assert hasattr(pypi, "SOURCE_NAME")
        assert pypi.SOURCE_NAME == "pypi"

    def test_has_display_name(self):
        assert hasattr(pypi, "DISPLAY_NAME")
        assert pypi.DISPLAY_NAME == "PyPI Downloads"

    def test_has_source_tier(self):
        assert hasattr(pypi, "SOURCE_TIER")
        assert pypi.SOURCE_TIER == 1

    def test_has_source_dimension(self):
        assert hasattr(pypi, "SOURCE_DIMENSION")
        assert pypi.SOURCE_DIMENSION == "dev_ecosystem"

    def test_has_is_available(self):
        assert callable(getattr(pypi, "is_available", None))

    def test_has_should_search(self):
        assert callable(getattr(pypi, "should_search", None))

    def test_has_search(self):
        assert callable(getattr(pypi, "search", None))

    def test_is_available_always_true(self):
        assert pypi.is_available({}) is True

    def test_should_search_returns_true(self):
        assert pypi.should_search("requests") is True
        assert pypi.should_search("anything") is True


# --- Package Exists ---


class TestPackageExists:
    """Verify _package_exists validates packages via PyPI JSON API."""

    def test_existing_package_returns_true(self):
        with patch("lib.pypi.http.get", return_value={"info": {"name": "requests"}}):
            assert pypi._package_exists("requests") is True

    def test_nonexistent_package_returns_false(self):
        with patch("lib.pypi.http.get", side_effect=HTTPError("404", status_code=404)):
            assert pypi._package_exists("nonexistent-pkg-12345") is False

    def test_other_http_error_raises(self):
        with patch("lib.pypi.http.get", side_effect=HTTPError("500", status_code=500)):
            with pytest.raises(HTTPError):
                pypi._package_exists("some-package")


# --- Download Parsing ---


class TestDownloadParsing:
    """Verify _fetch_downloads correctly parses pypistats.org responses."""

    def test_parses_fixture_data(self):
        fixture = _load_fixture("pypi_requests.json")
        with patch("lib.pypi.http.get", return_value=fixture):
            datapoints = pypi._fetch_downloads("requests", {})

        # Fixture has 90 days x 2 categories = 180 entries
        # Only "without_mirrors" should be returned = 90 entries
        assert len(datapoints) == 90
        assert all(isinstance(dp, TrendDataPoint) for dp in datapoints)
        # Timestamps should be YYYY-MM-DD
        for dp in datapoints:
            assert len(dp.timestamp) == 10
            assert dp.timestamp[4] == "-"
        # Values should be positive floats
        assert all(dp.value > 0 for dp in datapoints)

    def test_only_without_mirrors_returned(self):
        """Verify with_mirrors entries are filtered out."""
        fixture = _load_fixture("pypi_requests.json")
        with patch("lib.pypi.http.get", return_value=fixture):
            datapoints = pypi._fetch_downloads("requests", {})

        # Each raw entry should have category "without_mirrors"
        for dp in datapoints:
            assert dp.raw.get("category") == "without_mirrors"

    def test_sorted_by_timestamp(self):
        fixture = _load_fixture("pypi_requests.json")
        with patch("lib.pypi.http.get", return_value=fixture):
            datapoints = pypi._fetch_downloads("requests", {})

        timestamps = [dp.timestamp for dp in datapoints]
        assert timestamps == sorted(timestamps)

    def test_missing_data_field_raises_source_error(self):
        with patch("lib.pypi.http.get", return_value={"package": "requests"}):
            with pytest.raises(SourceError, match="data"):
                pypi._fetch_downloads("requests", {})


# --- Search Integration ---


class TestSearchIntegration:
    """Full search() with mocked HTTP — validates TrendSignal construction."""

    def test_search_returns_trend_signal(self):
        fixture = _load_fixture("pypi_requests.json")
        with patch("lib.pypi.http.get") as mock_get:
            mock_get.side_effect = [
                {"info": {"name": "requests"}},  # package exists
                fixture,                            # download data
            ]
            signal = pypi.search("requests", 90, {})

        assert signal is not None
        assert isinstance(signal, TrendSignal)
        assert signal.source == "pypi"
        assert signal.metric_name == "downloads"
        assert signal.metric_unit == "downloads/day"
        assert signal.dimension == "dev_ecosystem"
        assert len(signal.datapoints) > 0
        assert signal.current_value is not None
        assert signal.period_avg is not None
        assert signal.metadata.get("package") == "requests"

    def test_nonexistent_package_returns_none(self):
        with patch("lib.pypi.http.get", side_effect=HTTPError("404", status_code=404)):
            signal = pypi.search("nonexistent-pkg-xyz", 90, {})
        assert signal is None

    def test_query_variants_tried(self):
        """Triple-pipe delimited variants should be tried in order."""
        fixture = _load_fixture("pypi_requests.json")
        with patch("lib.pypi.http.get") as mock_get:
            mock_get.side_effect = [
                HTTPError("404", status_code=404),     # "python-requests" doesn't exist
                {"info": {"name": "requests"}},         # "requests" exists
                fixture,                                 # download data
            ]
            signal = pypi.search("python-requests|||requests", 90, {})

        assert signal is not None
        assert signal.metadata.get("package") == "requests"


# --- Window Filtering ---


class TestWindowFiltering:
    """Verify that datapoints outside window_days are excluded."""

    def test_window_filtering(self):
        fixture = _load_fixture("pypi_requests.json")
        with patch("lib.pypi.http.get") as mock_get:
            mock_get.side_effect = [
                {"info": {"name": "requests"}},  # package exists
                fixture,                            # 90 days of data
            ]
            # Request only 30 days
            signal = pypi.search("requests", 30, {})

        assert signal is not None
        # Should have <= 30 datapoints (only the last 30 days)
        assert len(signal.datapoints) <= 31  # Allow 1 day margin for date boundary
        assert len(signal.datapoints) > 0
