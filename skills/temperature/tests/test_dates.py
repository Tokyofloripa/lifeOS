"""Tests for temperature skill date utilities."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.dates import (
    get_date_range,
    parse_date,
    days_ago,
    recency_score,
    offset_date,
    timestamp_to_date,
    to_wikimedia_format,
    to_gdelt_format,
    to_api_format,
)


class TestGetDateRange:
    """Tests for get_date_range()."""

    def test_30_day_range(self):
        """Test that get_date_range(30) returns two YYYY-MM-DD strings with 30-day gap."""
        from_date, to_date = get_date_range(30)
        # Verify format
        assert len(from_date) == 10  # YYYY-MM-DD
        assert len(to_date) == 10
        assert from_date[4] == '-' and from_date[7] == '-'
        # Verify gap
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end = datetime.strptime(to_date, "%Y-%m-%d").date()
        assert (end - start).days == 30

    def test_60_day_range(self):
        """Test that get_date_range(60) returns 60-day gap."""
        from_date, to_date = get_date_range(60)
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end = datetime.strptime(to_date, "%Y-%m-%d").date()
        assert (end - start).days == 60

    def test_to_date_is_today(self):
        """Test that to_date is today (UTC)."""
        _, to_date = get_date_range(30)
        today = datetime.now(timezone.utc).date().isoformat()
        assert to_date == today

    def test_default_is_30_days(self):
        """Test that default range is 30 days."""
        from_date1, to_date1 = get_date_range()
        from_date2, to_date2 = get_date_range(30)
        assert from_date1 == from_date2
        assert to_date1 == to_date2


class TestFormatters:
    """Tests for API-specific date formatters."""

    def test_to_wikimedia_format(self):
        """Test YYYY-MM-DD -> YYYYMMDD00 conversion."""
        assert to_wikimedia_format("2026-01-15") == "2026011500"

    def test_to_wikimedia_format_another_date(self):
        """Test another date for Wikimedia format."""
        assert to_wikimedia_format("2025-12-31") == "2025123100"

    def test_to_gdelt_format(self):
        """Test YYYY-MM-DD -> YYYYMMDDHHMMSS conversion."""
        assert to_gdelt_format("2026-01-15") == "20260115000000"

    def test_to_gdelt_format_another_date(self):
        """Test another date for GDELT format."""
        assert to_gdelt_format("2025-07-04") == "20250704000000"

    def test_to_api_format_identity(self):
        """Test that to_api_format returns YYYY-MM-DD unchanged."""
        assert to_api_format("2026-01-15") == "2026-01-15"

    def test_to_api_format_preserves_input(self):
        """Test that to_api_format is truly an identity function."""
        date = "2025-12-25"
        assert to_api_format(date) is date  # Same object, not just equal


class TestOffsetDate:
    """Tests for offset_date()."""

    def test_positive_offset(self):
        """Test offsetting forward by 5 days."""
        assert offset_date("2026-01-15", 5) == "2026-01-20"

    def test_month_boundary(self):
        """Test offsetting across month boundary."""
        assert offset_date("2026-01-30", 5) == "2026-02-04"

    def test_negative_offset(self):
        """Test offsetting backward."""
        assert offset_date("2026-01-15", -5) == "2026-01-10"

    def test_year_boundary(self):
        """Test offsetting across year boundary."""
        assert offset_date("2025-12-30", 5) == "2026-01-04"

    def test_zero_offset(self):
        """Test zero offset returns same date."""
        assert offset_date("2026-01-15", 0) == "2026-01-15"


class TestParseDate:
    """Tests for parse_date()."""

    def test_parse_yyyy_mm_dd(self):
        """Test parsing YYYY-MM-DD format."""
        result = parse_date("2026-01-15")
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15

    def test_parse_none_returns_none(self):
        """Test that parse_date(None) returns None."""
        assert parse_date(None) is None

    def test_parse_empty_string_returns_none(self):
        """Test that parse_date('') returns None."""
        assert parse_date("") is None

    def test_parse_unix_timestamp(self):
        """Test parsing Unix timestamp string."""
        # 2026-01-15 00:00:00 UTC = 1768435200
        result = parse_date("1768435200")
        assert isinstance(result, datetime)

    def test_parse_iso_with_timezone(self):
        """Test parsing ISO 8601 with timezone."""
        result = parse_date("2026-01-15T10:30:00Z")
        assert isinstance(result, datetime)
        assert result.hour == 10
        assert result.minute == 30


class TestDaysAgo:
    """Tests for days_ago()."""

    def test_today_is_zero(self):
        """Test that today returns 0 days ago."""
        today = datetime.now(timezone.utc).date().isoformat()
        assert days_ago(today) == 0

    def test_none_returns_none(self):
        """Test that None input returns None."""
        assert days_ago(None) is None

    def test_invalid_date_returns_none(self):
        """Test that invalid date returns None."""
        assert days_ago("not-a-date") is None


class TestTimestampToDate:
    """Tests for timestamp_to_date()."""

    def test_valid_timestamp(self):
        """Test converting a valid Unix timestamp."""
        result = timestamp_to_date(1768435200.0)
        assert isinstance(result, str)
        assert len(result) == 10  # YYYY-MM-DD

    def test_none_returns_none(self):
        """Test that None returns None."""
        assert timestamp_to_date(None) is None


class TestRecencyScore:
    """Tests for recency_score()."""

    def test_today_is_100(self):
        """Test that today's date gets score 100."""
        today = datetime.now(timezone.utc).date().isoformat()
        assert recency_score(today) == 100

    def test_none_is_zero(self):
        """Test that None date gets score 0."""
        assert recency_score(None) == 0

    def test_old_date_is_zero(self):
        """Test that a very old date gets score 0."""
        assert recency_score("2020-01-01") == 0
