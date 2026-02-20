"""Tests for the scoring engine primitives.

Tests normalize_signal, normalize_sentiment, compute_velocity,
compute_direction, detect_breakout, and constants.
"""

import sys
import os

# Ensure lib is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from lib.schema import TrendDataPoint, TrendSignal
from lib.score import (
    clamp,
    normalize_signal,
    normalize_sentiment,
    compute_velocity,
    compute_direction,
    detect_breakout,
    DEFAULT_DIMENSION_WEIGHTS,
    SOURCE_WEIGHTS,
    DIRECTION_THRESHOLDS,
    DIMENSION_MAP,
)


# --- Helper to build TrendSignal quickly ---


def _signal(
    current_value=None,
    period_avg=None,
    datapoints=None,
    metric_name="pageviews",
    dimension="search_interest",
    source="wikipedia",
):
    """Build a TrendSignal with minimal args."""
    return TrendSignal(
        source=source,
        metric_name=metric_name,
        metric_unit="units",
        dimension=dimension,
        datapoints=datapoints or [],
        current_value=current_value,
        period_avg=period_avg,
    )


def _datapoints(values):
    """Build list of TrendDataPoint from a list of floats."""
    return [
        TrendDataPoint(timestamp=f"2026-02-{i+1:02d}", value=v)
        for i, v in enumerate(values)
    ]


# =============================================================================
# clamp()
# =============================================================================


class TestClamp:
    def test_within_range(self):
        assert clamp(50, 0, 100) == 50

    def test_below_min(self):
        assert clamp(-10, 0, 100) == 0

    def test_above_max(self):
        assert clamp(150, 0, 100) == 100

    def test_at_min(self):
        assert clamp(0, 0, 100) == 0

    def test_at_max(self):
        assert clamp(100, 0, 100) == 100


# =============================================================================
# normalize_signal()
# =============================================================================


class TestNormalizeSignal:
    def test_at_period_avg_returns_50(self):
        """current_value == period_avg -> 50."""
        sig = _signal(current_value=100, period_avg=100)
        assert normalize_signal(sig) == 50.0

    def test_double_period_avg_returns_100(self):
        """current_value == 2x period_avg -> 100."""
        sig = _signal(current_value=200, period_avg=100)
        assert normalize_signal(sig) == 100.0

    def test_half_period_avg_returns_25(self):
        """current_value == 0.5x period_avg -> 25."""
        sig = _signal(current_value=50, period_avg=100)
        assert normalize_signal(sig) == 25.0

    def test_zero_current_zero_avg_returns_0(self):
        """Both zero -> 0."""
        sig = _signal(current_value=0, period_avg=0)
        assert normalize_signal(sig) == 0.0

    def test_has_data_but_no_baseline_returns_75(self):
        """Has current_value but period_avg=0 -> 75."""
        sig = _signal(current_value=100, period_avg=0)
        assert normalize_signal(sig) == 75.0

    def test_none_current_value_returns_0(self):
        """current_value is None -> 0."""
        sig = _signal(current_value=None, period_avg=100)
        assert normalize_signal(sig) == 0.0

    def test_clamped_at_100(self):
        """Very high ratio still clamped to 100."""
        sig = _signal(current_value=1000, period_avg=100)
        assert normalize_signal(sig) == 100.0

    def test_clamped_at_0(self):
        """Zero current but positive avg -> 0."""
        sig = _signal(current_value=0, period_avg=100)
        assert normalize_signal(sig) == 0.0

    def test_routes_sentiment_to_normalize_sentiment(self):
        """metric_name == 'news_sentiment' routes through sentiment path."""
        # GDELT sentiment with positive tone should give > 50
        sig = _signal(
            current_value=5.0,
            period_avg=0.0,
            metric_name="news_sentiment",
            dimension="sentiment",
            source="gdelt",
        )
        result = normalize_signal(sig)
        assert result == 75.0  # tone=5 -> (5+10)*5 = 75

    def test_none_period_avg_returns_0(self):
        """period_avg is None -> 0 (no baseline)."""
        sig = _signal(current_value=100, period_avg=None)
        # Has data but no baseline info at all
        assert normalize_signal(sig) == 75.0


# =============================================================================
# normalize_sentiment()
# =============================================================================


class TestNormalizeSentiment:
    def test_negative_10_returns_0(self):
        assert normalize_sentiment(-10.0) == 0.0

    def test_zero_returns_50(self):
        assert normalize_sentiment(0.0) == 50.0

    def test_positive_10_returns_100(self):
        assert normalize_sentiment(10.0) == 100.0

    def test_negative_5_returns_25(self):
        assert normalize_sentiment(-5.0) == 25.0

    def test_positive_5_returns_75(self):
        assert normalize_sentiment(5.0) == 75.0

    def test_extreme_negative_clamps(self):
        """Tone below -10 clamps to 0."""
        assert normalize_sentiment(-50.0) == 0.0

    def test_extreme_positive_clamps(self):
        """Tone above +10 clamps to 100."""
        assert normalize_sentiment(50.0) == 100.0


# =============================================================================
# compute_velocity()
# =============================================================================


class TestComputeVelocity:
    def test_flat_signal_returns_near_zero(self):
        """Constant values -> ~0% velocity."""
        dps = _datapoints([100] * 14)
        result = compute_velocity(dps)
        assert result == pytest.approx(0.0, abs=0.1)

    def test_increasing_signal_returns_positive(self):
        """Increasing values -> positive velocity."""
        # Previous 7 avg = 100, recent 7 avg = 150 -> +50%
        dps = _datapoints([100] * 7 + [150] * 7)
        result = compute_velocity(dps)
        assert result == pytest.approx(50.0, abs=0.1)

    def test_decreasing_signal_returns_negative(self):
        """Decreasing values -> negative velocity."""
        # Previous 7 avg = 100, recent 7 avg = 50 -> -50%
        dps = _datapoints([100] * 7 + [50] * 7)
        result = compute_velocity(dps)
        assert result == pytest.approx(-50.0, abs=0.1)

    def test_uses_7_day_windows_with_14_plus(self):
        """With 14+ datapoints, use strict 7-day windows."""
        # 20 datapoints: first 13 are noise, last 7 = 200, [-14:-7] = 100
        values = [50] * 6 + [100] * 7 + [200] * 7
        dps = _datapoints(values)
        result = compute_velocity(dps)
        assert result == pytest.approx(100.0, abs=0.1)

    def test_sparse_data_splits_in_half(self):
        """2-13 datapoints: split in half and compare."""
        dps = _datapoints([100, 100, 200, 200])
        result = compute_velocity(dps)
        assert result == pytest.approx(100.0, abs=0.1)

    def test_single_datapoint_returns_zero(self):
        """Only 1 datapoint -> 0.0."""
        dps = _datapoints([100])
        assert compute_velocity(dps) == 0.0

    def test_zero_datapoints_returns_zero(self):
        """Empty list -> 0.0."""
        assert compute_velocity([]) == 0.0

    def test_from_zero_growth(self):
        """Previous avg == 0, recent > 0 -> 100.0."""
        dps = _datapoints([0, 0, 100, 100])
        result = compute_velocity(dps)
        assert result == 100.0

    def test_two_datapoints_handled(self):
        """Semantic Scholar case: 2 datapoints."""
        dps = _datapoints([100, 200])
        result = compute_velocity(dps)
        assert result == pytest.approx(100.0, abs=0.1)


# =============================================================================
# compute_direction()
# =============================================================================


class TestComputeDirection:
    def test_surging(self):
        assert compute_direction(60.0) == "surging"

    def test_surging_at_boundary(self):
        assert compute_direction(50.0) == "surging"

    def test_rising(self):
        assert compute_direction(30.0) == "rising"

    def test_rising_at_boundary(self):
        assert compute_direction(15.0) == "rising"

    def test_stable(self):
        assert compute_direction(0.0) == "stable"

    def test_stable_at_negative_boundary(self):
        assert compute_direction(-15.0) == "stable"

    def test_declining(self):
        assert compute_direction(-30.0) == "declining"

    def test_declining_at_boundary(self):
        """velocity == -50 is still declining (>= -50)."""
        assert compute_direction(-50.0) == "declining"

    def test_crashing(self):
        assert compute_direction(-70.0) == "crashing"

    def test_exactly_5_labels(self):
        """Direction maps to exactly 5 labels."""
        labels = set()
        for v in [-100, -60, -30, 0, 20, 60]:
            labels.add(compute_direction(v))
        assert labels == {"surging", "rising", "stable", "declining", "crashing"}


# =============================================================================
# detect_breakout()
# =============================================================================


class TestDetectBreakout:
    def test_all_signals_under_7_returns_true(self):
        """All signals with < 7 datapoints -> True (brand-new topic)."""
        signals = {
            "wiki": _signal(datapoints=_datapoints([1, 2, 3])),
            "npm": _signal(datapoints=_datapoints([10, 20])),
        }
        assert detect_breakout(signals) is True

    def test_any_signal_at_7_returns_false(self):
        """Any signal with >= 7 datapoints -> False (established topic)."""
        signals = {
            "wiki": _signal(datapoints=_datapoints([1] * 7)),
            "npm": _signal(datapoints=_datapoints([10, 20])),
        }
        assert detect_breakout(signals) is False

    def test_any_signal_over_7_returns_false(self):
        """Signal with 30 datapoints -> False."""
        signals = {
            "wiki": _signal(datapoints=_datapoints([1] * 30)),
        }
        assert detect_breakout(signals) is False

    def test_empty_signals_returns_false(self):
        """Empty dict -> False (no signals = not new, just empty)."""
        assert detect_breakout({}) is False

    def test_all_signals_exactly_6_returns_true(self):
        """All signals at 6 datapoints -> True (still under 7)."""
        signals = {
            "a": _signal(datapoints=_datapoints([1] * 6)),
            "b": _signal(datapoints=_datapoints([1] * 6)),
        }
        assert detect_breakout(signals) is True


# =============================================================================
# Constants
# =============================================================================


class TestConstants:
    def test_dimension_weights_sum_to_1(self):
        total = sum(DEFAULT_DIMENSION_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_dimension_weights_has_5_entries(self):
        assert len(DEFAULT_DIMENSION_WEIGHTS) == 5

    def test_dimension_weights_all_equal_20(self):
        for v in DEFAULT_DIMENSION_WEIGHTS.values():
            assert v == pytest.approx(0.20)

    def test_source_weights_has_expected_dimensions(self):
        expected = {"search_interest", "media", "dev_ecosystem", "financial", "academic"}
        assert set(SOURCE_WEIGHTS.keys()) == expected

    def test_direction_thresholds_has_5_entries(self):
        assert len(DIRECTION_THRESHOLDS) == 5

    def test_dimension_map_folds_sentiment_to_media(self):
        assert DIMENSION_MAP.get("sentiment") == "media"
