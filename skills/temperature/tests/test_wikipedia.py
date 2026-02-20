"""Tests for wikipedia.py — Wikipedia Pageviews source module.

Tests article resolution with tech-topic disambiguation, pageview parsing,
full search integration, and protocol compliance.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, call

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
        from lib.wikipedia import SOURCE_NAME
        assert SOURCE_NAME == "wikipedia"

    def test_has_display_name(self):
        from lib.wikipedia import DISPLAY_NAME
        assert DISPLAY_NAME == "Wikipedia Pageviews"

    def test_has_source_tier(self):
        from lib.wikipedia import SOURCE_TIER
        assert SOURCE_TIER == 1

    def test_has_source_dimension(self):
        from lib.wikipedia import SOURCE_DIMENSION
        assert SOURCE_DIMENSION == "search_interest"

    def test_is_available_callable(self):
        from lib.wikipedia import is_available
        assert callable(is_available)

    def test_should_search_callable(self):
        from lib.wikipedia import should_search
        assert callable(should_search)

    def test_search_callable(self):
        from lib.wikipedia import search
        assert callable(search)

    def test_is_available_returns_true(self):
        from lib.wikipedia import is_available
        assert is_available({}) is True

    def test_should_search_returns_true(self):
        from lib.wikipedia import should_search
        assert should_search("anything") is True


# ============================================================
# Class 2: TestArticleResolution
# ============================================================

class TestArticleResolution:
    """Test article resolution via MediaWiki search API with disambiguation."""

    def test_react_resolves_to_javascript_library(self):
        """'React' should resolve to the JavaScript library, not chemical reaction."""
        from lib import wikipedia
        fixture = _load_fixture("wikipedia_search_react.json")
        with patch.object(wikipedia, "http") as mock_http:
            mock_http.get.return_value = fixture
            article = wikipedia._resolve_article("React", {})
        assert article is not None
        assert "JavaScript" in article or "javascript" in article.lower()
        assert "Chemical" not in article

    def test_empty_search_returns_none(self):
        """Empty search results should return None."""
        from lib import wikipedia
        empty_response = {"query": {"searchinfo": {"totalhits": 0}, "search": []}}
        with patch.object(wikipedia, "http") as mock_http:
            mock_http.get.return_value = empty_response
            article = wikipedia._resolve_article("xyznonexistent12345", {})
        assert article is None

    def test_article_title_uses_underscores(self):
        """Article title should use underscores instead of spaces."""
        from lib import wikipedia
        fixture = _load_fixture("wikipedia_search_react.json")
        with patch.object(wikipedia, "http") as mock_http:
            mock_http.get.return_value = fixture
            article = wikipedia._resolve_article("React", {})
        assert " " not in article
        assert "_" in article  # "React_(JavaScript_library)" has underscores


# ============================================================
# Class 3: TestPageviewParsing
# ============================================================

class TestPageviewParsing:
    """Test pageview response parsing with fixture data."""

    def test_correct_number_of_datapoints(self):
        """Fixture has 90 days of data -> 90 TrendDataPoints."""
        from lib import wikipedia
        fixture = _load_fixture("wikipedia_react.json")
        with patch.object(wikipedia, "http") as mock_http:
            mock_http.get.return_value = fixture
            dps = wikipedia._fetch_pageviews("React_(JavaScript_library)", "2025112200", "2026021900", {})
        assert len(dps) == 90

    def test_timestamps_in_correct_format(self):
        """All timestamps should be YYYY-MM-DD format."""
        from lib import wikipedia
        fixture = _load_fixture("wikipedia_react.json")
        with patch.object(wikipedia, "http") as mock_http:
            mock_http.get.return_value = fixture
            dps = wikipedia._fetch_pageviews("React_(JavaScript_library)", "2025112200", "2026021900", {})
        for dp in dps:
            assert len(dp.timestamp) == 10
            assert dp.timestamp[4] == "-"
            assert dp.timestamp[7] == "-"

    def test_values_are_floats(self):
        """All values should be floats."""
        from lib import wikipedia
        fixture = _load_fixture("wikipedia_react.json")
        with patch.object(wikipedia, "http") as mock_http:
            mock_http.get.return_value = fixture
            dps = wikipedia._fetch_pageviews("React_(JavaScript_library)", "2025112200", "2026021900", {})
        for dp in dps:
            assert isinstance(dp.value, float)
            assert dp.value > 0

    def test_missing_items_raises_source_error(self):
        """Response without 'items' field should raise SourceError."""
        from lib import wikipedia
        bad_response = {"error": "something went wrong"}
        with patch.object(wikipedia, "http") as mock_http:
            mock_http.get.return_value = bad_response
            with pytest.raises(SourceError) as exc_info:
                wikipedia._fetch_pageviews("React_(JavaScript_library)", "2025112200", "2026021900", {})
        assert "wikipedia" in str(exc_info.value).lower()
        assert "items" in str(exc_info.value).lower()


# ============================================================
# Class 4: TestSearchIntegration
# ============================================================

class TestSearchIntegration:
    """Test full search() flow with both search + pageview mocked."""

    def test_search_returns_trend_signal(self):
        """search() with valid data returns TrendSignal."""
        from lib import wikipedia
        search_fixture = _load_fixture("wikipedia_search_react.json")
        pageview_fixture = _load_fixture("wikipedia_react.json")

        call_count = [0]
        def mock_get(url, **kwargs):
            call_count[0] += 1
            if "api.php" in url:
                return search_fixture
            return pageview_fixture

        with patch.object(wikipedia, "http") as mock_http:
            mock_http.get.side_effect = mock_get
            signal = wikipedia.search("React", 90, {})

        assert signal is not None
        assert isinstance(signal, TrendSignal)
        assert signal.source == "wikipedia"
        assert signal.metric_name == "pageviews"
        assert signal.dimension == "search_interest"
        assert len(signal.datapoints) == 90
        assert signal.metadata.get("article") is not None
        assert "JavaScript" in signal.metadata["article"]

    def test_search_returns_none_for_no_results(self):
        """search() returns None when no article found."""
        from lib import wikipedia
        empty_response = {"query": {"searchinfo": {"totalhits": 0}, "search": []}}

        with patch.object(wikipedia, "http") as mock_http:
            mock_http.get.return_value = empty_response
            signal = wikipedia.search("xyznonexistent12345", 90, {})

        assert signal is None

    def test_search_has_current_value_and_period_avg(self):
        """search() sets current_value and period_avg from datapoints."""
        from lib import wikipedia
        search_fixture = _load_fixture("wikipedia_search_react.json")
        pageview_fixture = _load_fixture("wikipedia_react.json")

        def mock_get(url, **kwargs):
            if "api.php" in url:
                return search_fixture
            return pageview_fixture

        with patch.object(wikipedia, "http") as mock_http:
            mock_http.get.side_effect = mock_get
            signal = wikipedia.search("React", 90, {})

        assert signal.current_value is not None
        assert signal.current_value > 0
        assert signal.period_avg is not None
        assert signal.period_avg > 0


# ============================================================
# Class 5: TestQueryVariants
# ============================================================

class TestQueryVariants:
    """Test triple-pipe query variant handling."""

    def test_single_variant(self):
        from lib.wikipedia import _all_variants
        assert _all_variants("React") == ["React"]

    def test_multiple_variants(self):
        from lib.wikipedia import _all_variants
        result = _all_variants("React|||ReactJS|||React.js")
        assert result == ["React", "ReactJS", "React.js"]

    def test_whitespace_stripped(self):
        from lib.wikipedia import _all_variants
        result = _all_variants("React ||| ReactJS ||| React.js")
        assert result == ["React", "ReactJS", "React.js"]

    def test_empty_variants_filtered(self):
        from lib.wikipedia import _all_variants
        result = _all_variants("React||||||ReactJS")
        assert result == ["React", "ReactJS"]

    def test_fallback_to_second_variant(self):
        """If first variant fails, should try second."""
        from lib import wikipedia
        search_fixture = _load_fixture("wikipedia_search_react.json")
        pageview_fixture = _load_fixture("wikipedia_react.json")

        call_count = [0]
        def mock_get(url, **kwargs):
            call_count[0] += 1
            if "api.php" in url:
                if "xyznotfound" in url.lower():
                    return {"query": {"searchinfo": {"totalhits": 0}, "search": []}}
                return search_fixture
            return pageview_fixture

        with patch.object(wikipedia, "http") as mock_http:
            mock_http.get.side_effect = mock_get
            signal = wikipedia.search("xyznotfound|||React", 90, {})

        assert signal is not None
        assert signal.metadata.get("article") is not None
