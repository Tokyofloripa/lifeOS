"""Tests for sources.py — source registry, selection, parallel execution, error handling.

Defines the contract for sources.py via TDD RED phase.
"""

import json
import sys
import time
import types
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.schema import TrendSignal, TrendDataPoint, SourceError
from lib.http import HTTPError


# --- Helpers: create mock source modules ---

def _make_source(
    name="test_src",
    display_name="Test Source",
    tier=1,
    dimension="search_interest",
    is_available=True,
    should_search=True,
    search_result=None,  # None = return None, TrendSignal = return it, Exception = raise it
):
    """Create a mock source module as a SimpleNamespace."""
    def _is_available(config):
        return is_available

    def _should_search(topic):
        return should_search

    def _search(topic, window_days, config):
        if isinstance(search_result, Exception):
            raise search_result
        return search_result

    return types.SimpleNamespace(
        SOURCE_NAME=name,
        DISPLAY_NAME=display_name,
        SOURCE_TIER=tier,
        SOURCE_DIMENSION=dimension,
        is_available=_is_available,
        should_search=_should_search,
        search=_search,
    )


def _make_signal(source="test_src", metric="test_metric"):
    """Create a minimal TrendSignal for testing."""
    return TrendSignal(
        source=source,
        metric_name=metric,
        metric_unit="units/day",
        dimension="search_interest",
        datapoints=[TrendDataPoint(timestamp="2026-02-20", value=100.0)],
        current_value=100.0,
        period_avg=80.0,
        direction="rising",
        velocity=0.25,
    )


# ============================================================
# Class 1: TestSourceDiscovery
# ============================================================

class TestSourceDiscovery:
    """Test auto-discovery constants and behavior."""

    def test_skip_files_contains_known_non_source_modules(self):
        """_SKIP_FILES must exclude all known infrastructure modules."""
        from lib.sources import _SKIP_FILES
        expected = {"__init__", "sources", "schema", "env", "http", "dates",
                    "sparkline", "score", "render", "normalize"}
        assert expected.issubset(_SKIP_FILES), f"Missing from _SKIP_FILES: {expected - _SKIP_FILES}"

    def test_required_attrs_defined(self):
        """_REQUIRED_ATTRS must include all 4 source protocol constants."""
        from lib.sources import _REQUIRED_ATTRS
        assert "SOURCE_NAME" in _REQUIRED_ATTRS
        assert "DISPLAY_NAME" in _REQUIRED_ATTRS
        assert "SOURCE_TIER" in _REQUIRED_ATTRS
        assert "SOURCE_DIMENSION" in _REQUIRED_ATTRS

    def test_required_funcs_defined(self):
        """_REQUIRED_FUNCS must include all 3 source protocol functions."""
        from lib.sources import _REQUIRED_FUNCS
        assert "is_available" in _REQUIRED_FUNCS
        assert "should_search" in _REQUIRED_FUNCS
        assert "search" in _REQUIRED_FUNCS

    def test_import_does_not_crash_with_no_sources(self):
        """Importing sources.py must not crash even with 0 source modules."""
        from lib.sources import ALL_SOURCES
        # Just verify it imported without error — registry may be empty
        assert isinstance(ALL_SOURCES, dict)


# ============================================================
# Class 2: TestSourceSelection
# ============================================================

class TestSourceSelection:
    """Test tier-based source selection logic."""

    def test_tier1_always_selected(self):
        """Tier 1 source selected without any keys."""
        from lib.sources import select_sources
        src = _make_source(name="free_src", tier=1, is_available=True, should_search=True)
        with patch("lib.sources.ALL_SOURCES", {"free_src": src}):
            with patch("lib.sources.env") as mock_env:
                mock_env.get_available_tiers.return_value = {
                    "tier1": ["free_src"],
                    "tier2": [],
                    "tier3": [],
                }
                selected, skipped = select_sources("test topic", {})
        assert "free_src" in selected

    def test_tier2_selected_when_key_present(self):
        """Tier 2 source selected when API key is configured."""
        from lib.sources import select_sources
        src = _make_source(name="keyed_src", tier=2, is_available=True, should_search=True)
        with patch("lib.sources.ALL_SOURCES", {"keyed_src": src}):
            with patch("lib.sources.env") as mock_env:
                mock_env.get_available_tiers.return_value = {
                    "tier1": [],
                    "tier2": ["keyed_src"],
                    "tier3": [],
                }
                selected, skipped = select_sources("test topic", {})
        assert "keyed_src" in selected

    def test_tier2_skipped_when_key_absent(self):
        """Tier 2 source skipped when API key is missing."""
        from lib.sources import select_sources
        src = _make_source(name="keyed_src", tier=2, is_available=True, should_search=True)
        with patch("lib.sources.ALL_SOURCES", {"keyed_src": src}):
            with patch("lib.sources.env") as mock_env:
                mock_env.get_available_tiers.return_value = {
                    "tier1": [],
                    "tier2": [],  # key NOT present
                    "tier3": [],
                }
                selected, skipped = select_sources("test topic", {})
        assert "keyed_src" not in selected
        assert "keyed_src" in skipped
        assert "API key" in skipped["keyed_src"]

    def test_tier3_requires_premium_flag(self):
        """Tier 3 source requires both key and premium=True."""
        from lib.sources import select_sources
        src = _make_source(name="paid_src", tier=3, is_available=True, should_search=True)
        with patch("lib.sources.ALL_SOURCES", {"paid_src": src}):
            with patch("lib.sources.env") as mock_env:
                mock_env.get_available_tiers.return_value = {
                    "tier1": [],
                    "tier2": [],
                    "tier3": ["paid_src"],
                }
                # With key but premium=False: skipped
                selected, skipped = select_sources("test topic", {}, premium=False)
        assert "paid_src" not in selected
        assert "paid_src" in skipped

    def test_tier3_selected_with_key_and_premium(self):
        """Tier 3 source selected when key present AND premium=True."""
        from lib.sources import select_sources
        src = _make_source(name="paid_src", tier=3, is_available=True, should_search=True)
        with patch("lib.sources.ALL_SOURCES", {"paid_src": src}):
            with patch("lib.sources.env") as mock_env:
                mock_env.get_available_tiers.return_value = {
                    "tier1": [],
                    "tier2": [],
                    "tier3": ["paid_src"],
                }
                selected, skipped = select_sources("test topic", {}, premium=True)
        assert "paid_src" in selected

    def test_quick_restricts_to_tier1(self):
        """quick=True restricts to Tier 1 only."""
        from lib.sources import select_sources
        src1 = _make_source(name="free_src", tier=1, is_available=True, should_search=True)
        src2 = _make_source(name="keyed_src", tier=2, is_available=True, should_search=True)
        with patch("lib.sources.ALL_SOURCES", {"free_src": src1, "keyed_src": src2}):
            with patch("lib.sources.env") as mock_env:
                mock_env.get_available_tiers.return_value = {
                    "tier1": ["free_src"],
                    "tier2": ["keyed_src"],
                    "tier3": [],
                }
                selected, skipped = select_sources("test topic", {}, quick=True)
        assert "free_src" in selected
        assert "keyed_src" not in selected
        assert "keyed_src" in skipped
        assert "tier" in skipped["keyed_src"].lower()

    def test_is_available_false_skips(self):
        """Source with is_available()=False is skipped."""
        from lib.sources import select_sources
        src = _make_source(name="unavail", tier=1, is_available=False, should_search=True)
        with patch("lib.sources.ALL_SOURCES", {"unavail": src}):
            with patch("lib.sources.env") as mock_env:
                mock_env.get_available_tiers.return_value = {
                    "tier1": ["unavail"],
                    "tier2": [],
                    "tier3": [],
                }
                selected, skipped = select_sources("test topic", {})
        assert "unavail" not in selected
        assert "unavail" in skipped
        assert "not available" in skipped["unavail"]

    def test_should_search_false_skips(self):
        """Source with should_search()=False is skipped."""
        from lib.sources import select_sources
        src = _make_source(name="irrelevant", tier=1, is_available=True, should_search=False)
        with patch("lib.sources.ALL_SOURCES", {"irrelevant": src}):
            with patch("lib.sources.env") as mock_env:
                mock_env.get_available_tiers.return_value = {
                    "tier1": ["irrelevant"],
                    "tier2": [],
                    "tier3": [],
                }
                selected, skipped = select_sources("test topic", {})
        assert "irrelevant" not in selected
        assert "irrelevant" in skipped
        assert "not relevant" in skipped["irrelevant"]

    def test_skipped_dict_contains_reasons(self):
        """Skipped dict has source names mapped to reason strings."""
        from lib.sources import select_sources
        src = _make_source(name="no_key", tier=2, is_available=True, should_search=True)
        with patch("lib.sources.ALL_SOURCES", {"no_key": src}):
            with patch("lib.sources.env") as mock_env:
                mock_env.get_available_tiers.return_value = {
                    "tier1": [],
                    "tier2": [],
                    "tier3": [],
                }
                selected, skipped = select_sources("test topic", {})
        assert isinstance(skipped, dict)
        assert "no_key" in skipped
        assert isinstance(skipped["no_key"], str)
        assert len(skipped["no_key"]) > 0

    def test_empty_registry_returns_empty(self):
        """Empty ALL_SOURCES returns empty selected and skipped."""
        from lib.sources import select_sources
        with patch("lib.sources.ALL_SOURCES", {}):
            with patch("lib.sources.env") as mock_env:
                mock_env.get_available_tiers.return_value = {
                    "tier1": [],
                    "tier2": [],
                    "tier3": [],
                }
                selected, skipped = select_sources("test topic", {})
        assert selected == {}
        assert skipped == {}


# ============================================================
# Class 3: TestParallelExecution
# ============================================================

class TestParallelExecution:
    """Test parallel source execution with ThreadPoolExecutor."""

    def test_two_sources_both_return_signal(self):
        """Two sources both return TrendSignal -> both in results."""
        from lib.sources import run_sources
        sig_a = _make_signal(source="src_a")
        sig_b = _make_signal(source="src_b")
        src_a = _make_source(name="src_a", search_result=sig_a)
        src_b = _make_source(name="src_b", search_result=sig_b)
        selected = {"src_a": src_a, "src_b": src_b}
        results, all_results = run_sources(selected, "topic", 30, {})
        assert "src_a" in results
        assert "src_b" in results
        assert results["src_a"] is sig_a
        assert results["src_b"] is sig_b

    def test_none_return_excluded_from_results(self):
        """Source returning None is in all_results but not in results."""
        from lib.sources import run_sources
        sig = _make_signal(source="good_src")
        src_good = _make_source(name="good_src", search_result=sig)
        src_none = _make_source(name="none_src", search_result=None)
        selected = {"good_src": src_good, "none_src": src_none}
        results, all_results = run_sources(selected, "topic", 30, {})
        assert "good_src" in results
        assert "none_src" not in results
        assert "none_src" in all_results
        assert all_results["none_src"].error is None  # No error, just no data

    def test_source_error_caught_and_classified(self):
        """SourceError is caught and classified as error_type='source'."""
        from lib.sources import run_sources
        err = SourceError("broken_src", "API changed")
        src = _make_source(name="broken_src", search_result=err)
        selected = {"broken_src": src}
        results, all_results = run_sources(selected, "topic", 30, {})
        assert "broken_src" not in results
        assert "broken_src" in all_results
        assert all_results["broken_src"].error is not None
        assert all_results["broken_src"].error_type == "source"

    def test_generic_exception_caught_and_classified(self):
        """Generic exceptions are caught and classified via _classify_error."""
        from lib.sources import run_sources
        err = RuntimeError("something unexpected")
        src = _make_source(name="crash_src", search_result=err)
        selected = {"crash_src": src}
        results, all_results = run_sources(selected, "topic", 30, {})
        assert "crash_src" not in results
        assert "crash_src" in all_results
        assert all_results["crash_src"].error is not None
        assert all_results["crash_src"].error_type == "unknown"

    def test_global_timeout_returns_partial_results(self):
        """Source exceeding global_budget is marked as timed out."""
        from lib.sources import run_sources

        sig_fast = _make_signal(source="fast_src")
        fast_src = _make_source(name="fast_src", search_result=sig_fast)

        # Create a slow source that sleeps longer than the budget
        slow_ns = _make_source(name="slow_src")
        def _slow_search(topic, window_days, config):
            time.sleep(3)
            return _make_signal(source="slow_src")
        slow_ns.search = _slow_search

        selected = {"fast_src": fast_src, "slow_src": slow_ns}
        results, all_results = run_sources(
            selected, "topic", 30, {},
            global_budget=0.5,
        )
        # Fast source should complete
        assert "fast_src" in results
        # Slow source should be timed out
        assert "slow_src" in all_results
        assert all_results["slow_src"].error_type == "timeout"

    def test_empty_selected_returns_empty(self):
        """Empty selected dict returns ({}, {})."""
        from lib.sources import run_sources
        results, all_results = run_sources({}, "topic", 30, {})
        assert results == {}
        assert all_results == {}

    def test_max_workers_capped(self):
        """max_workers is capped at min(active, 10)."""
        from lib.sources import run_sources
        # With 15 sources, workers should be 10
        sigs = {}
        selected = {}
        for i in range(15):
            name = f"src_{i}"
            sig = _make_signal(source=name)
            sigs[name] = sig
            selected[name] = _make_source(name=name, search_result=sig)

        with patch("lib.sources.ThreadPoolExecutor") as mock_pool:
            # Make the mock executor work like normal but capture max_workers
            from concurrent.futures import ThreadPoolExecutor
            real_executor = ThreadPoolExecutor(max_workers=10)
            mock_pool.return_value.__enter__ = lambda s: real_executor
            mock_pool.return_value.__exit__ = lambda s, *a: real_executor.shutdown(wait=True)

            results, all_results = run_sources(selected, "topic", 30, {})
            mock_pool.assert_called_once_with(max_workers=10)


# ============================================================
# Class 4: TestErrorClassification
# ============================================================

class TestErrorClassification:
    """Test _classify_error() for all exception types."""

    def test_http_429_rate_limit(self):
        from lib.sources import _classify_error
        assert _classify_error(HTTPError("rate limited", status_code=429)) == "rate_limit"

    def test_http_401_auth(self):
        from lib.sources import _classify_error
        assert _classify_error(HTTPError("unauthorized", status_code=401)) == "auth"

    def test_http_403_auth(self):
        from lib.sources import _classify_error
        assert _classify_error(HTTPError("forbidden", status_code=403)) == "auth"

    def test_http_500_generic(self):
        from lib.sources import _classify_error
        assert _classify_error(HTTPError("server error", status_code=500)) == "http"

    def test_source_error(self):
        from lib.sources import _classify_error
        assert _classify_error(SourceError("src", "broken")) == "source"

    def test_timeout_error(self):
        from lib.sources import _classify_error
        assert _classify_error(TimeoutError()) == "timeout"

    def test_os_error(self):
        from lib.sources import _classify_error
        assert _classify_error(OSError()) == "timeout"

    def test_json_decode_error(self):
        from lib.sources import _classify_error
        assert _classify_error(json.JSONDecodeError("msg", "doc", 0)) == "parse"

    def test_key_error(self):
        from lib.sources import _classify_error
        assert _classify_error(KeyError()) == "parse"

    def test_value_error(self):
        from lib.sources import _classify_error
        assert _classify_error(ValueError()) == "parse"

    def test_runtime_error_unknown(self):
        from lib.sources import _classify_error
        assert _classify_error(RuntimeError()) == "unknown"


# ============================================================
# Class 5: TestSourceStatus
# ============================================================

class TestSourceStatus:
    """Test get_source_status() report generation."""

    def test_status_with_mixed_results(self):
        """Status report correctly categorizes active, failed, timed_out, skipped."""
        from lib.sources import get_source_status, SourceResult

        selected = {
            "active1": _make_source(name="active1", display_name="Active One"),
            "active2": _make_source(name="active2", display_name="Active Two"),
            "failed1": _make_source(name="failed1", display_name="Failed One"),
            "timed1": _make_source(name="timed1", display_name="Timed One"),
        }
        skipped = {"skip1": "API key not configured"}
        all_results = {
            "active1": SourceResult(name="active1", signal=_make_signal("active1"), elapsed_ms=150),
            "active2": SourceResult(name="active2", signal=_make_signal("active2"), elapsed_ms=200),
            "failed1": SourceResult(name="failed1", error="API error", error_type="http", elapsed_ms=50),
            "timed1": SourceResult(name="timed1", error="global timeout exceeded", error_type="timeout", elapsed_ms=0),
        }

        status = get_source_status(selected, skipped, all_results)

        assert status["active_count"] == 2
        assert len(status["active"]) == 2
        assert len(status["failed"]) == 1
        assert len(status["timed_out"]) == 1
        assert len(status["skipped"]) == 1

    def test_active_entries_have_required_fields(self):
        """Active entries must have name, display_name, elapsed_ms."""
        from lib.sources import get_source_status, SourceResult

        selected = {"src1": _make_source(name="src1", display_name="Source One")}
        all_results = {
            "src1": SourceResult(name="src1", signal=_make_signal("src1"), elapsed_ms=123),
        }

        status = get_source_status(selected, {}, all_results)
        entry = status["active"][0]
        assert "name" in entry
        assert "display_name" in entry
        assert "elapsed_ms" in entry
        assert entry["name"] == "src1"
        assert entry["display_name"] == "Source One"
        assert entry["elapsed_ms"] == 123

    def test_failed_entries_have_error_fields(self):
        """Failed entries must have error and error_type."""
        from lib.sources import get_source_status, SourceResult

        selected = {"fail": _make_source(name="fail", display_name="Fail Src")}
        all_results = {
            "fail": SourceResult(name="fail", error="bad response", error_type="http", elapsed_ms=99),
        }

        status = get_source_status(selected, {}, all_results)
        entry = status["failed"][0]
        assert "error" in entry
        assert "error_type" in entry
        assert entry["error"] == "bad response"
        assert entry["error_type"] == "http"

    def test_timed_out_separated_from_failed(self):
        """Timed out entries (error_type=timeout) separated from failed."""
        from lib.sources import get_source_status, SourceResult

        selected = {
            "http_fail": _make_source(name="http_fail", display_name="HTTP Fail"),
            "timeout_fail": _make_source(name="timeout_fail", display_name="Timeout Fail"),
        }
        all_results = {
            "http_fail": SourceResult(name="http_fail", error="500", error_type="http", elapsed_ms=50),
            "timeout_fail": SourceResult(name="timeout_fail", error="timeout", error_type="timeout", elapsed_ms=0),
        }

        status = get_source_status(selected, {}, all_results)
        failed_names = [e["name"] for e in status["failed"]]
        timed_out_names = [e["name"] for e in status["timed_out"]]
        assert "http_fail" in failed_names
        assert "timeout_fail" not in failed_names
        assert "timeout_fail" in timed_out_names
        assert "http_fail" not in timed_out_names
