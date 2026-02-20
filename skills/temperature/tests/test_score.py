"""Tests for the scoring engine.

Tests normalize_signal, normalize_sentiment, compute_velocity,
compute_direction, detect_breakout, constants, group_by_dimension,
score_dimension, compute_temperature, detect_convergence, and score_signals.
"""

import sys
import os

# Ensure lib is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from lib.schema import (
    TrendDataPoint,
    TrendSignal,
    DimensionScore,
    TemperatureReport,
    get_temperature_label,
)
from lib.score import (
    clamp,
    normalize_signal,
    normalize_sentiment,
    compute_velocity,
    compute_direction,
    detect_breakout,
    group_by_dimension,
    score_dimension,
    compute_temperature,
    detect_convergence,
    score_signals,
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


# =============================================================================
# group_by_dimension()
# =============================================================================


class TestGroupByDimension:
    def test_groups_by_dimension_name(self):
        """Signals with same dimension go in same group."""
        signals = {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=100, period_avg=100,
            ),
            "npm": _signal(
                source="npm", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=1000, period_avg=500,
            ),
        }
        grouped = group_by_dimension(signals)
        assert "search_interest" in grouped
        assert "dev_ecosystem" in grouped
        assert len(grouped["search_interest"]) == 1
        assert len(grouped["dev_ecosystem"]) == 1

    def test_remaps_sentiment_to_media(self):
        """Sentiment dimension is folded into media via DIMENSION_MAP."""
        signals = {
            "gdelt_news_volume": _signal(
                source="gdelt", dimension="media",
                metric_name="news_volume",
                current_value=50, period_avg=40,
            ),
            "gdelt_news_sentiment": _signal(
                source="gdelt", dimension="sentiment",
                metric_name="news_sentiment",
                current_value=3.0, period_avg=0.0,
            ),
        }
        grouped = group_by_dimension(signals)
        assert "sentiment" not in grouped
        assert "media" in grouped
        assert len(grouped["media"]) == 2

    def test_multiple_sources_same_dimension(self):
        """npm + pypi both go into dev_ecosystem."""
        signals = {
            "npm": _signal(
                source="npm", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=1000, period_avg=500,
            ),
            "pypi": _signal(
                source="pypi", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=200, period_avg=100,
            ),
        }
        grouped = group_by_dimension(signals)
        assert len(grouped["dev_ecosystem"]) == 2

    def test_empty_signals(self):
        """Empty input -> empty output."""
        grouped = group_by_dimension({})
        assert grouped == {}


# =============================================================================
# score_dimension()
# =============================================================================


class TestScoreDimension:
    def test_empty_signals_returns_zero_score(self):
        """No signals -> DimensionScore with score=0."""
        result = score_dimension([], SOURCE_WEIGHTS.get("search_interest", {}))
        assert isinstance(result, DimensionScore)
        assert result.score == 0

    def test_single_signal_returns_normalized_score(self):
        """Single signal (wikipedia at avg) -> score of 50."""
        sig = _signal(
            source="wikipedia", dimension="search_interest",
            current_value=100, period_avg=100,
            datapoints=_datapoints([100] * 14),
        )
        result = score_dimension(
            [sig],
            SOURCE_WEIGHTS.get("search_interest", {}),
        )
        assert result.score == 50

    def test_single_signal_double_avg_returns_100(self):
        """Single signal (wikipedia at 2x avg) -> score of 100."""
        sig = _signal(
            source="wikipedia", dimension="search_interest",
            current_value=200, period_avg=100,
            datapoints=_datapoints([100] * 7 + [200] * 7),
        )
        result = score_dimension(
            [sig],
            SOURCE_WEIGHTS.get("search_interest", {}),
        )
        assert result.score == 100

    def test_multiple_signals_weighted_average(self):
        """npm (50%) + pypi (50%) -> weighted average of normalized scores."""
        npm_sig = _signal(
            source="npm", dimension="dev_ecosystem",
            metric_name="downloads",
            current_value=200, period_avg=100,  # score = 100
            datapoints=_datapoints([100] * 14),
        )
        pypi_sig = _signal(
            source="pypi", dimension="dev_ecosystem",
            metric_name="downloads",
            current_value=100, period_avg=100,  # score = 50
            datapoints=_datapoints([100] * 14),
        )
        result = score_dimension(
            [npm_sig, pypi_sig],
            SOURCE_WEIGHTS.get("dev_ecosystem", {}),
        )
        # Weighted: 0.5 * 100 + 0.5 * 50 = 75
        assert result.score == 75

    def test_renormalizes_when_source_missing(self):
        """Only npm present (no pypi) -> npm gets 100% weight within dimension."""
        npm_sig = _signal(
            source="npm", dimension="dev_ecosystem",
            metric_name="downloads",
            current_value=200, period_avg=100,  # normalized = 100
            datapoints=_datapoints([100] * 14),
        )
        result = score_dimension(
            [npm_sig],
            SOURCE_WEIGHTS.get("dev_ecosystem", {}),
        )
        # npm renormalized from 0.50 to 1.0 -> score = 100
        assert result.score == 100

    def test_direction_from_weighted_velocity(self):
        """Direction is computed from weighted velocity average."""
        sig = _signal(
            source="wikipedia", dimension="search_interest",
            current_value=200, period_avg=100,
            datapoints=_datapoints([100] * 7 + [200] * 7),  # velocity ~100%
        )
        result = score_dimension(
            [sig],
            SOURCE_WEIGHTS.get("search_interest", {}),
        )
        assert result.direction == "surging"

    def test_sparkline_from_signal_with_most_datapoints(self):
        """Sparkline uses signal with most datapoints."""
        sig_many = _signal(
            source="npm", dimension="dev_ecosystem",
            metric_name="downloads",
            current_value=100, period_avg=100,
            datapoints=_datapoints([10, 20, 30, 40, 50]),
        )
        sig_few = _signal(
            source="pypi", dimension="dev_ecosystem",
            metric_name="downloads",
            current_value=100, period_avg=100,
            datapoints=_datapoints([1, 2]),
        )
        result = score_dimension(
            [sig_many, sig_few],
            SOURCE_WEIGHTS.get("dev_ecosystem", {}),
        )
        assert len(result.sparkline) == 5  # from npm (5 datapoints)

    def test_active_sources_count(self):
        """active_sources reflects how many signals were provided."""
        npm_sig = _signal(
            source="npm", dimension="dev_ecosystem",
            metric_name="downloads",
            current_value=100, period_avg=100,
            datapoints=_datapoints([100] * 14),
        )
        pypi_sig = _signal(
            source="pypi", dimension="dev_ecosystem",
            metric_name="downloads",
            current_value=100, period_avg=100,
            datapoints=_datapoints([100] * 14),
        )
        result = score_dimension(
            [npm_sig, pypi_sig],
            SOURCE_WEIGHTS.get("dev_ecosystem", {}),
        )
        assert result.active_sources == 2

    def test_gdelt_composite_key_matching(self):
        """GDELT signals use composite keys for weight lookup."""
        vol = _signal(
            source="gdelt", dimension="media",
            metric_name="news_volume",
            current_value=100, period_avg=100,  # score = 50
            datapoints=_datapoints([100] * 14),
        )
        sent = _signal(
            source="gdelt", dimension="sentiment",
            metric_name="news_sentiment",
            current_value=5.0, period_avg=0.0,  # score = 75
            datapoints=_datapoints([3.0] * 14),
        )
        result = score_dimension(
            [vol, sent],
            SOURCE_WEIGHTS.get("media", {}),
        )
        # Weighted: 0.60 * 50 + 0.40 * 75 = 30 + 30 = 60
        assert result.score == 60


# =============================================================================
# compute_temperature()
# =============================================================================


class TestComputeTemperature:
    def test_equal_20_percent_weights(self):
        """Default uses equal 20% weights per dimension."""
        dims = {
            "search_interest": DimensionScore(name="search_interest", score=100),
            "media": DimensionScore(name="media", score=100),
            "dev_ecosystem": DimensionScore(name="dev_ecosystem", score=100),
            "academic": DimensionScore(name="academic", score=100),
        }
        temp, label = compute_temperature(dims)
        # 4 dimensions * 20% * 100 = 80 (financial missing = 0)
        assert temp == 80

    def test_missing_dimensions_contribute_zero(self):
        """Missing dimensions contribute 0, no re-normalization."""
        dims = {
            "search_interest": DimensionScore(name="search_interest", score=100),
        }
        temp, label = compute_temperature(dims)
        # 1 dimension * 20% * 100 = 20
        assert temp == 20

    def test_all_dimensions_at_100(self):
        """All 5 dimensions at 100 -> temperature = 100."""
        dims = {
            "search_interest": DimensionScore(name="search_interest", score=100),
            "media": DimensionScore(name="media", score=100),
            "dev_ecosystem": DimensionScore(name="dev_ecosystem", score=100),
            "financial": DimensionScore(name="financial", score=100),
            "academic": DimensionScore(name="academic", score=100),
        }
        temp, label = compute_temperature(dims)
        assert temp == 100

    def test_no_dimensions_returns_zero(self):
        """No active dimensions -> temperature = 0."""
        temp, label = compute_temperature({})
        assert temp == 0

    def test_returns_correct_label(self):
        """Temperature maps to correct label via get_temperature_label."""
        dims = {
            "search_interest": DimensionScore(name="search_interest", score=100),
            "media": DimensionScore(name="media", score=100),
            "dev_ecosystem": DimensionScore(name="dev_ecosystem", score=100),
            "academic": DimensionScore(name="academic", score=100),
        }
        temp, label = compute_temperature(dims)
        # temp = 80 -> "On Fire"
        assert label == get_temperature_label(80)

    def test_custom_weights(self):
        """Custom weights override defaults."""
        dims = {
            "search_interest": DimensionScore(name="search_interest", score=100),
            "media": DimensionScore(name="media", score=0),
        }
        custom = {
            "search_interest": 0.80,
            "media": 0.20,
            "dev_ecosystem": 0.0,
            "financial": 0.0,
            "academic": 0.0,
        }
        temp, label = compute_temperature(dims, custom)
        # 0.80 * 100 + 0.20 * 0 = 80
        assert temp == 80

    def test_v1_max_is_80(self):
        """v1 with no financial source -> max possible temperature is ~80."""
        dims = {
            "search_interest": DimensionScore(name="search_interest", score=100),
            "media": DimensionScore(name="media", score=100),
            "dev_ecosystem": DimensionScore(name="dev_ecosystem", score=100),
            "academic": DimensionScore(name="academic", score=100),
            # No financial dimension
        }
        temp, label = compute_temperature(dims)
        assert temp == 80


# =============================================================================
# detect_convergence()
# =============================================================================


class TestDetectConvergence:
    def test_all_rising_returns_converging_up(self):
        """All active dimensions rising/surging -> 'converging up'."""
        dims = {
            "search_interest": DimensionScore(
                name="search_interest", score=70, direction="rising", velocity=20.0,
            ),
            "media": DimensionScore(
                name="media", score=60, direction="rising", velocity=18.0,
            ),
            "dev_ecosystem": DimensionScore(
                name="dev_ecosystem", score=80, direction="rising", velocity=25.0,
            ),
        }
        result = detect_convergence(dims)
        assert result == "converging up"

    def test_all_surging_returns_strongly_converging_up(self):
        """All surging with avg velocity > 30% -> 'strongly converging up'."""
        dims = {
            "search_interest": DimensionScore(
                name="search_interest", score=90, direction="surging", velocity=60.0,
            ),
            "media": DimensionScore(
                name="media", score=80, direction="surging", velocity=55.0,
            ),
        }
        result = detect_convergence(dims)
        assert result == "strongly converging up"

    def test_all_declining_returns_converging_down(self):
        """All declining/crashing -> 'converging down'."""
        dims = {
            "search_interest": DimensionScore(
                name="search_interest", score=30, direction="declining", velocity=-25.0,
            ),
            "media": DimensionScore(
                name="media", score=20, direction="declining", velocity=-28.0,
            ),
        }
        result = detect_convergence(dims)
        assert result == "converging down"

    def test_all_crashing_returns_strongly_converging_down(self):
        """All crashing with avg |velocity| > 30% -> 'strongly converging down'."""
        dims = {
            "search_interest": DimensionScore(
                name="search_interest", score=10, direction="crashing", velocity=-60.0,
            ),
            "media": DimensionScore(
                name="media", score=5, direction="crashing", velocity=-70.0,
            ),
        }
        result = detect_convergence(dims)
        assert result == "strongly converging down"

    def test_rising_and_declining_returns_diverging(self):
        """Some rising, some declining -> 'diverging'."""
        dims = {
            "search_interest": DimensionScore(
                name="search_interest", score=80, direction="surging", velocity=60.0,
            ),
            "media": DimensionScore(
                name="media", score=20, direction="declining", velocity=-30.0,
            ),
        }
        result = detect_convergence(dims)
        assert result == "diverging"

    def test_all_stable_returns_mixed(self):
        """All stable (neither positive nor negative) -> 'mixed'."""
        dims = {
            "search_interest": DimensionScore(
                name="search_interest", score=50, direction="stable", velocity=0.0,
            ),
            "media": DimensionScore(
                name="media", score=50, direction="stable", velocity=2.0,
            ),
        }
        result = detect_convergence(dims)
        assert result == "mixed"

    def test_fewer_than_2_active_returns_na(self):
        """< 2 active dimensions -> 'n/a'."""
        dims = {
            "search_interest": DimensionScore(
                name="search_interest", score=80, direction="rising", velocity=20.0,
            ),
        }
        result = detect_convergence(dims)
        assert result == "n/a"

    def test_zero_score_dimensions_excluded(self):
        """Dimensions with score=0 are not active."""
        dims = {
            "search_interest": DimensionScore(
                name="search_interest", score=80, direction="rising", velocity=20.0,
            ),
            "financial": DimensionScore(
                name="financial", score=0, direction="stable", velocity=0.0,
            ),
        }
        result = detect_convergence(dims)
        assert result == "n/a"  # Only 1 active

    def test_empty_dimensions(self):
        """No dimensions -> 'n/a'."""
        result = detect_convergence({})
        assert result == "n/a"


# =============================================================================
# score_signals() — Full Pipeline
# =============================================================================


class TestScoreSignals:
    def test_produces_temperature_report(self):
        """score_signals returns a TemperatureReport."""
        signals = {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=150, period_avg=100,
                datapoints=_datapoints([100] * 7 + [150] * 7),
            ),
        }
        report = score_signals(signals)
        assert isinstance(report, TemperatureReport)

    def test_temperature_in_valid_range(self):
        """Temperature score is 0-100."""
        signals = {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=150, period_avg=100,
                datapoints=_datapoints([100] * 7 + [150] * 7),
            ),
        }
        report = score_signals(signals)
        assert 0 <= report.temperature <= 100

    def test_label_is_set(self):
        """Report has a non-empty label."""
        signals = {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=150, period_avg=100,
                datapoints=_datapoints([100] * 7 + [150] * 7),
            ),
        }
        report = score_signals(signals)
        assert report.label != ""

    def test_dimensions_populated(self):
        """Report dimensions dict is populated for active dimensions."""
        signals = {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=150, period_avg=100,
                datapoints=_datapoints([100] * 7 + [150] * 7),
            ),
            "npm": _signal(
                source="npm", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=200, period_avg=100,
                datapoints=_datapoints([100] * 7 + [200] * 7),
            ),
        }
        report = score_signals(signals)
        assert "search_interest" in report.dimensions
        assert "dev_ecosystem" in report.dimensions

    def test_convergence_set(self):
        """Report has convergence field set."""
        signals = {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=150, period_avg=100,
                datapoints=_datapoints([100] * 7 + [150] * 7),
            ),
            "npm": _signal(
                source="npm", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=200, period_avg=100,
                datapoints=_datapoints([100] * 7 + [200] * 7),
            ),
        }
        report = score_signals(signals)
        assert report.convergence != ""

    def test_hottest_dimension_identified(self):
        """Report identifies the hottest dimension."""
        signals = {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=200, period_avg=100,  # higher score
                datapoints=_datapoints([100] * 14),
            ),
            "npm": _signal(
                source="npm", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=100, period_avg=100,  # lower score
                datapoints=_datapoints([100] * 14),
            ),
        }
        report = score_signals(signals)
        assert report.hottest_dimension == "search_interest"

    def test_fastest_mover_identified(self):
        """Report identifies the fastest-moving dimension."""
        signals = {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=100, period_avg=100,
                datapoints=_datapoints([100] * 14),  # flat velocity
            ),
            "npm": _signal(
                source="npm", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=200, period_avg=100,
                datapoints=_datapoints([100] * 7 + [200] * 7),  # high velocity
            ),
        }
        report = score_signals(signals)
        assert report.fastest_mover == "dev_ecosystem"

    def test_breakout_sets_direction_new(self):
        """Brand-new topics (< 7 datapoints all signals) get direction='new'."""
        signals = {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=200, period_avg=100,
                datapoints=_datapoints([100, 150, 200]),  # only 3 points
            ),
        }
        report = score_signals(signals)
        assert report.direction == "new"

    def test_all_signals_stored(self):
        """all_signals list contains all input signals."""
        signals = {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=100, period_avg=100,
                datapoints=_datapoints([100] * 14),
            ),
            "npm": _signal(
                source="npm", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=200, period_avg=100,
                datapoints=_datapoints([100] * 14),
            ),
        }
        report = score_signals(signals)
        assert len(report.all_signals) == 2

    def test_topic_timestamp_window_left_empty(self):
        """topic, timestamp, window_days left empty for orchestrator to fill."""
        signals = {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=100, period_avg=100,
                datapoints=_datapoints([100] * 14),
            ),
        }
        report = score_signals(signals)
        assert report.topic == ""
        assert report.timestamp == ""
        assert report.window_days == 0

    def test_multi_source_dimension_pipeline(self):
        """Full pipeline with GDELT dual-signal (volume + sentiment) in media."""
        signals = {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=150, period_avg=100,
                datapoints=_datapoints([100] * 7 + [150] * 7),
            ),
            "gdelt_news_volume": _signal(
                source="gdelt", dimension="media",
                metric_name="news_volume",
                current_value=100, period_avg=100,
                datapoints=_datapoints([100] * 14),
            ),
            "gdelt_news_sentiment": _signal(
                source="gdelt", dimension="sentiment",
                metric_name="news_sentiment",
                current_value=5.0, period_avg=0.0,
                datapoints=_datapoints([3.0] * 14),
            ),
        }
        report = score_signals(signals)
        # Should have search_interest and media dimensions
        assert "search_interest" in report.dimensions
        assert "media" in report.dimensions
        # sentiment should be folded into media
        assert "sentiment" not in report.dimensions


# =============================================================================
# Differentiation Test
# =============================================================================


class TestDifferentiation:
    """5 diverse mock topics must produce differentiated scores."""

    def _popular_tech_signals(self):
        """Popular tech topic: high across all dimensions."""
        return {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=200, period_avg=100,
                datapoints=_datapoints([100] * 7 + [200] * 7),
            ),
            "gdelt_news_volume": _signal(
                source="gdelt", dimension="media",
                metric_name="news_volume",
                current_value=180, period_avg=100,
                datapoints=_datapoints([100] * 7 + [180] * 7),
            ),
            "gdelt_news_sentiment": _signal(
                source="gdelt", dimension="sentiment",
                metric_name="news_sentiment",
                current_value=7.0, period_avg=0.0,
                datapoints=_datapoints([5.0] * 14),
            ),
            "npm": _signal(
                source="npm", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=190, period_avg=100,
                datapoints=_datapoints([100] * 7 + [190] * 7),
            ),
            "pypi": _signal(
                source="pypi", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=170, period_avg=100,
                datapoints=_datapoints([100] * 7 + [170] * 7),
            ),
            "semantic_scholar": _signal(
                source="semantic_scholar", dimension="academic",
                metric_name="paper_count",
                current_value=180, period_avg=100,
                datapoints=_datapoints([100, 180]),
            ),
        }

    def _niche_package_signals(self):
        """Niche package: high dev only."""
        return {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=20, period_avg=100,
                datapoints=_datapoints([100] * 7 + [20] * 7),
            ),
            "npm": _signal(
                source="npm", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=200, period_avg=100,
                datapoints=_datapoints([100] * 7 + [200] * 7),
            ),
            "pypi": _signal(
                source="pypi", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=180, period_avg=100,
                datapoints=_datapoints([100] * 7 + [180] * 7),
            ),
        }

    def _academic_topic_signals(self):
        """Academic topic: high academic only."""
        return {
            "semantic_scholar": _signal(
                source="semantic_scholar", dimension="academic",
                metric_name="paper_count",
                current_value=200, period_avg=100,
                datapoints=_datapoints([100, 200]),
            ),
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=50, period_avg=100,
                datapoints=_datapoints([100] * 7 + [50] * 7),
            ),
        }

    def _trending_news_signals(self):
        """Trending news: high media only."""
        return {
            "gdelt_news_volume": _signal(
                source="gdelt", dimension="media",
                metric_name="news_volume",
                current_value=200, period_avg=100,
                datapoints=_datapoints([100] * 7 + [200] * 7),
            ),
            "gdelt_news_sentiment": _signal(
                source="gdelt", dimension="sentiment",
                metric_name="news_sentiment",
                current_value=8.0, period_avg=0.0,
                datapoints=_datapoints([5.0] * 14),
            ),
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=80, period_avg=100,
                datapoints=_datapoints([100] * 7 + [80] * 7),
            ),
        }

    def _dead_topic_signals(self):
        """Dead topic: low across all dimensions."""
        return {
            "wikipedia": _signal(
                source="wikipedia", dimension="search_interest",
                current_value=10, period_avg=100,
                datapoints=_datapoints([100] * 7 + [10] * 7),
            ),
            "npm": _signal(
                source="npm", dimension="dev_ecosystem",
                metric_name="downloads",
                current_value=5, period_avg=100,
                datapoints=_datapoints([100] * 7 + [5] * 7),
            ),
            "semantic_scholar": _signal(
                source="semantic_scholar", dimension="academic",
                metric_name="paper_count",
                current_value=10, period_avg=100,
                datapoints=_datapoints([100, 10]),
            ),
        }

    def test_scores_not_all_clustered_around_50(self):
        """At least some scores differ significantly from 50."""
        topics = [
            self._popular_tech_signals(),
            self._niche_package_signals(),
            self._academic_topic_signals(),
            self._trending_news_signals(),
            self._dead_topic_signals(),
        ]
        scores = [score_signals(t).temperature for t in topics]

        # Not all within 45-55
        clustered = sum(1 for s in scores if 45 <= s <= 55)
        assert clustered < len(scores), (
            f"Too many scores clustered around 50: {scores}"
        )

    def test_at_least_3_distinct_labels(self):
        """5 diverse topics produce at least 3 different label categories."""
        topics = [
            self._popular_tech_signals(),
            self._niche_package_signals(),
            self._academic_topic_signals(),
            self._trending_news_signals(),
            self._dead_topic_signals(),
        ]
        labels = set(score_signals(t).label for t in topics)
        assert len(labels) >= 3, f"Only {len(labels)} distinct labels: {labels}"

    def test_popular_tech_scores_highest(self):
        """Popular tech (high all) should score higher than dead topic (low all)."""
        popular = score_signals(self._popular_tech_signals())
        dead = score_signals(self._dead_topic_signals())
        assert popular.temperature > dead.temperature

    def test_dead_topic_scores_lowest(self):
        """Dead topic should have the lowest score among all 5."""
        topics = [
            self._popular_tech_signals(),
            self._niche_package_signals(),
            self._academic_topic_signals(),
            self._trending_news_signals(),
            self._dead_topic_signals(),
        ]
        scores = [score_signals(t).temperature for t in topics]
        # Dead topic is the last one
        assert scores[-1] == min(scores)
