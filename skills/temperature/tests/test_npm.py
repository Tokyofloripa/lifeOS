"""Tests for npm Downloads source module.

Tests npm.py: package existence validation, daily download parsing,
scoped package URL encoding, and full search integration.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, call

import pytest

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.schema import TrendSignal, TrendDataPoint, SourceError
from lib.http import HTTPError
from lib import npm


# --- Fixtures ---

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


# --- Protocol Compliance ---


class TestProtocolCompliance:
    """Verify npm module implements the 4-constant + 3-function protocol."""

    def test_has_source_name(self):
        assert hasattr(npm, "SOURCE_NAME")
        assert npm.SOURCE_NAME == "npm"

    def test_has_display_name(self):
        assert hasattr(npm, "DISPLAY_NAME")
        assert npm.DISPLAY_NAME == "npm Downloads"

    def test_has_source_tier(self):
        assert hasattr(npm, "SOURCE_TIER")
        assert npm.SOURCE_TIER == 1

    def test_has_source_dimension(self):
        assert hasattr(npm, "SOURCE_DIMENSION")
        assert npm.SOURCE_DIMENSION == "dev_ecosystem"

    def test_has_is_available(self):
        assert callable(getattr(npm, "is_available", None))

    def test_has_should_search(self):
        assert callable(getattr(npm, "should_search", None))

    def test_has_search(self):
        assert callable(getattr(npm, "search", None))

    def test_is_available_always_true(self):
        assert npm.is_available({}) is True

    def test_should_search_returns_true(self):
        assert npm.should_search("react") is True
        assert npm.should_search("anything") is True


# --- Package Exists ---


class TestPackageExists:
    """Verify _package_exists validates packages via the npm point endpoint."""

    def test_existing_package_returns_true(self):
        with patch("lib.npm.http.get", return_value={"downloads": 1000}):
            assert npm._package_exists("react") is True

    def test_nonexistent_package_returns_false(self):
        with patch("lib.npm.http.get", side_effect=HTTPError("404", status_code=404)):
            assert npm._package_exists("nonexistent-pkg-12345") is False

    def test_other_http_error_raises(self):
        with patch("lib.npm.http.get", side_effect=HTTPError("500", status_code=500)):
            with pytest.raises(HTTPError):
                npm._package_exists("some-package")


# --- Download Parsing ---


class TestDownloadParsing:
    """Verify _fetch_downloads correctly parses npm range API responses."""

    def test_parses_fixture_data(self):
        fixture = _load_fixture("npm_react.json")
        with patch("lib.npm.http.get", return_value=fixture):
            datapoints = npm._fetch_downloads("react", "2025-11-22", "2026-02-19", {})

        assert len(datapoints) == 90
        assert all(isinstance(dp, TrendDataPoint) for dp in datapoints)
        # All timestamps should be YYYY-MM-DD
        for dp in datapoints:
            assert len(dp.timestamp) == 10
            assert dp.timestamp[4] == "-"
        # Values should be positive floats
        assert all(dp.value > 0 for dp in datapoints)

    def test_missing_downloads_field_raises_source_error(self):
        with patch("lib.npm.http.get", return_value={"package": "react"}):
            with pytest.raises(SourceError, match="downloads"):
                npm._fetch_downloads("react", "2025-11-22", "2026-02-19", {})


# --- Search Integration ---


class TestSearchIntegration:
    """Full search() with mocked HTTP — validates TrendSignal construction."""

    def test_search_returns_trend_signal(self):
        fixture = _load_fixture("npm_react.json")
        with patch("lib.npm.http.get") as mock_get:
            # First call: _package_exists (point endpoint)
            # Second call: _fetch_downloads (range endpoint)
            mock_get.side_effect = [
                {"downloads": 1000},  # package exists
                fixture,               # download data
            ]
            signal = npm.search("react", 90, {})

        assert signal is not None
        assert isinstance(signal, TrendSignal)
        assert signal.source == "npm"
        assert signal.metric_name == "downloads"
        assert signal.metric_unit == "downloads/day"
        assert signal.dimension == "dev_ecosystem"
        assert len(signal.datapoints) == 90
        assert signal.current_value is not None
        assert signal.period_avg is not None
        assert signal.metadata.get("package") == "react"

    def test_nonexistent_package_returns_none(self):
        with patch("lib.npm.http.get", side_effect=HTTPError("404", status_code=404)):
            signal = npm.search("nonexistent-pkg-xyz", 90, {})
        assert signal is None

    def test_query_variants_tried(self):
        """Triple-pipe delimited variants should be tried in order."""
        fixture = _load_fixture("npm_react.json")
        with patch("lib.npm.http.get") as mock_get:
            # First variant fails (404), second succeeds
            mock_get.side_effect = [
                HTTPError("404", status_code=404),  # "reactjs" doesn't exist
                {"downloads": 1000},                  # "react" exists
                fixture,                               # download data
            ]
            signal = npm.search("reactjs|||react", 90, {})

        assert signal is not None
        assert signal.metadata.get("package") == "react"


# --- Scoped Packages ---


class TestScopedPackages:
    """Verify scoped packages (@scope/name) are properly URL-encoded."""

    def test_scoped_package_url_encoding(self):
        fixture = _load_fixture("npm_react.json")
        with patch("lib.npm.http.get") as mock_get:
            mock_get.side_effect = [
                {"downloads": 1000},  # package exists
                fixture,               # download data
            ]
            npm.search("@tanstack/react-query", 90, {})

        # Check that the first call (package_exists) used URL-encoded path
        first_call_url = mock_get.call_args_list[0][0][0]
        assert "%40tanstack" in first_call_url or "%40" in first_call_url
        assert "%2F" in first_call_url or "%2f" in first_call_url
