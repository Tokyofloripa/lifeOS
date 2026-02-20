"""Tests for Semantic Scholar source module.

Tests semantic_scholar.py: paper search, year range computation,
confidence='low', optional API key, and rate limit handling.
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
from lib import semantic_scholar


# --- Fixtures ---

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


# --- Protocol Compliance ---


class TestProtocolCompliance:
    """Verify semantic_scholar implements the 4-constant + 3-function protocol."""

    def test_has_source_name(self):
        assert hasattr(semantic_scholar, "SOURCE_NAME")
        assert semantic_scholar.SOURCE_NAME == "semantic_scholar"

    def test_has_display_name(self):
        assert hasattr(semantic_scholar, "DISPLAY_NAME")
        assert semantic_scholar.DISPLAY_NAME == "Semantic Scholar"

    def test_has_source_tier(self):
        assert hasattr(semantic_scholar, "SOURCE_TIER")
        assert semantic_scholar.SOURCE_TIER == 1

    def test_has_source_dimension(self):
        assert hasattr(semantic_scholar, "SOURCE_DIMENSION")
        assert semantic_scholar.SOURCE_DIMENSION == "academic"

    def test_has_is_available(self):
        assert callable(getattr(semantic_scholar, "is_available", None))

    def test_has_should_search(self):
        assert callable(getattr(semantic_scholar, "should_search", None))

    def test_has_search(self):
        assert callable(getattr(semantic_scholar, "search", None))

    def test_is_available_always_true(self):
        assert semantic_scholar.is_available({}) is True

    def test_should_search_returns_true(self):
        assert semantic_scholar.should_search("large language models") is True
        assert semantic_scholar.should_search("anything") is True


# --- Paper Search ---


class TestPaperSearch:
    """Verify _search_papers correctly calls Semantic Scholar API."""

    def test_search_with_fixture(self):
        fixture = _load_fixture("semantic_scholar_llm.json")
        with patch("lib.semantic_scholar.http.get", return_value=fixture):
            result = semantic_scholar._search_papers("large language models", "2025-2026", {})

        assert result["total"] == 1234
        assert len(result["data"]) == 20

    def test_papers_grouped_by_year(self):
        fixture = _load_fixture("semantic_scholar_llm.json")
        with patch("lib.semantic_scholar.http.get", return_value=fixture):
            signal = semantic_scholar.search("large language models", 90, {})

        assert signal is not None
        # Datapoints should be grouped by year
        assert len(signal.datapoints) > 0
        for dp in signal.datapoints:
            # Timestamps are years as strings
            assert len(dp.timestamp) == 4  # "2025" or "2026"
            assert dp.value > 0

    def test_empty_response_returns_none(self):
        with patch("lib.semantic_scholar.http.get", return_value={"total": 0, "data": []}):
            signal = semantic_scholar.search("nonexistent-topic-xyz", 90, {})
        assert signal is None


# --- Search Integration ---


class TestSearchIntegration:
    """Full search() with mocked HTTP — validates TrendSignal construction."""

    def test_returns_trend_signal_with_correct_fields(self):
        fixture = _load_fixture("semantic_scholar_llm.json")
        with patch("lib.semantic_scholar.http.get", return_value=fixture):
            signal = semantic_scholar.search("large language models", 90, {})

        assert signal is not None
        assert isinstance(signal, TrendSignal)
        assert signal.source == "semantic_scholar"
        assert signal.metric_name == "paper_count"
        assert signal.metric_unit == "papers"
        assert signal.dimension == "academic"
        assert signal.confidence == "low"
        assert signal.current_value is not None
        assert "total" in signal.metadata
        assert "year_range" in signal.metadata

    def test_metadata_contains_total_and_year_range(self):
        fixture = _load_fixture("semantic_scholar_llm.json")
        with patch("lib.semantic_scholar.http.get", return_value=fixture):
            signal = semantic_scholar.search("large language models", 90, {})

        assert signal.metadata["total"] == 1234
        assert isinstance(signal.metadata["year_range"], str)


# --- Year Range ---


class TestYearRange:
    """Verify year range computation based on window_days."""

    def test_90_day_window_current_year_only(self):
        """90-day window should produce current-year-only range."""
        from datetime import datetime, timezone

        current_year = datetime.now(timezone.utc).year
        year_range = semantic_scholar._compute_year_range(90)
        assert year_range == f"{current_year}-{current_year}"

    def test_400_day_window_multi_year(self):
        """400-day window should produce multi-year range."""
        from datetime import datetime, timezone

        current_year = datetime.now(timezone.utc).year
        year_range = semantic_scholar._compute_year_range(400)
        # Start year should be before current year
        start_year = int(year_range.split("-")[0])
        assert start_year < current_year


# --- Rate Limit ---


class TestRateLimit:
    """Verify rate limit handling — should raise SourceError, NOT retry."""

    def test_429_raises_source_error(self):
        with patch(
            "lib.semantic_scholar.http.get",
            side_effect=HTTPError("429 Too Many Requests", status_code=429),
        ):
            with pytest.raises(SourceError, match="Rate limited"):
                semantic_scholar.search("large language models", 90, {})


# --- API Key ---


class TestApiKey:
    """Verify optional API key is passed when configured."""

    def test_api_key_passed_in_headers(self):
        fixture = _load_fixture("semantic_scholar_llm.json")
        config = {"SEMANTIC_SCHOLAR_KEY": "test-api-key-123"}
        with patch("lib.semantic_scholar.http.get", return_value=fixture) as mock_get:
            semantic_scholar.search("large language models", 90, config)

        # Verify x-api-key header was passed
        call_kwargs = mock_get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
        assert headers.get("x-api-key") == "test-api-key-123"

    def test_no_api_key_no_header(self):
        fixture = _load_fixture("semantic_scholar_llm.json")
        with patch("lib.semantic_scholar.http.get", return_value=fixture) as mock_get:
            semantic_scholar.search("large language models", 90, {})

        # Verify no x-api-key header
        call_kwargs = mock_get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
        assert "x-api-key" not in headers
