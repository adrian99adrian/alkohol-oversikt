"""Tests for calendar generation."""

from datetime import UTC, date, timedelta
from unittest.mock import patch

from build_calendar import WEEKDAY_NAMES_NO, build_calendar, get_today_oslo


class TestBuildCalendar:
    """Verify calendar generation output."""

    def test_generates_365_entries(self):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        assert len(cal) == 365

    def test_starts_from_given_date(self):
        cal = build_calendar(date(2026, 3, 15))
        assert cal[0]["date"] == "2026-03-15"

    def test_no_gaps(self):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        dates = [entry["date"] for entry in cal]
        for i in range(1, len(dates)):
            d1 = date.fromisoformat(dates[i - 1])
            d2 = date.fromisoformat(dates[i])
            assert d2 - d1 == timedelta(days=1), f"Gap between {d1} and {d2}"

    def test_no_duplicates(self):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        dates = [entry["date"] for entry in cal]
        assert len(dates) == len(set(dates))

    def test_dates_in_iso_format(self):
        cal = build_calendar(date(2026, 6, 15), num_days=30)
        for entry in cal:
            # Should parse without error and match YYYY-MM-DD
            parsed = date.fromisoformat(entry["date"])
            assert entry["date"] == parsed.isoformat()

    def test_entry_schema(self):
        """Each entry has all required fields."""
        required_fields = {
            "date",
            "weekday",
            "day_type",
            "day_type_label",
            "is_public_holiday",
            "is_pre_holiday",
            "pre_holiday_for",
            "is_special_day",
            "special_day_key",
            "holiday_name",
        }
        cal = build_calendar(date(2026, 1, 1), num_days=7)
        for entry in cal:
            assert required_fields.issubset(entry.keys()), (
                f"Missing fields: {required_fields - entry.keys()}"
            )

    def test_norwegian_weekday_names(self):
        """Weekday names are in Norwegian."""
        cal = build_calendar(date(2026, 3, 9), num_days=7)  # Mon-Sun
        expected = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"]
        actual = [entry["weekday"] for entry in cal]
        assert actual == expected

    def test_easter_2026_classified(self):
        """Easter 2026 period is correctly classified."""
        cal = build_calendar(date(2026, 4, 1), num_days=7)
        by_date = {e["date"]: e for e in cal}

        assert by_date["2026-04-01"]["day_type"] == "pre_holiday"
        assert by_date["2026-04-02"]["day_type"] == "public_holiday"  # Skjærtorsdag
        assert by_date["2026-04-03"]["day_type"] == "public_holiday"  # Langfredag
        assert by_date["2026-04-04"]["day_type"] == "special_day"  # Påskeaften
        assert by_date["2026-04-05"]["day_type"] == "public_holiday"  # 1. påskedag
        assert by_date["2026-04-06"]["day_type"] == "public_holiday"  # 2. påskedag
        assert by_date["2026-04-07"]["day_type"] == "weekday"  # Tuesday

    def test_christmas_2026_classified(self):
        cal = build_calendar(date(2026, 12, 24), num_days=3)
        by_date = {e["date"]: e for e in cal}

        assert by_date["2026-12-24"]["day_type"] == "special_day"
        assert by_date["2026-12-24"]["special_day_key"] == "christmas_eve"
        assert by_date["2026-12-25"]["day_type"] == "public_holiday"
        assert by_date["2026-12-26"]["day_type"] == "public_holiday"

    def test_2025_full_year(self):
        """Generate 2025 calendar and verify key holidays."""
        cal = build_calendar(date(2025, 1, 1), num_days=365)
        by_date = {e["date"]: e for e in cal}

        # Fixed holidays
        assert by_date["2025-01-01"]["day_type"] == "public_holiday"
        assert by_date["2025-05-01"]["day_type"] == "public_holiday"
        assert by_date["2025-05-17"]["day_type"] == "public_holiday"
        assert by_date["2025-12-25"]["day_type"] == "public_holiday"
        assert by_date["2025-12-26"]["day_type"] == "public_holiday"

        # Easter 2025 = April 20
        assert by_date["2025-04-17"]["day_type"] == "public_holiday"  # Skjærtorsdag
        assert by_date["2025-04-18"]["day_type"] == "public_holiday"  # Langfredag
        assert by_date["2025-04-20"]["day_type"] == "public_holiday"  # 1. påskedag

    def test_year_boundary(self):
        """Calendar starting Dec 1 2025 spans into 2026."""
        cal = build_calendar(date(2025, 12, 1), num_days=60)
        by_date = {e["date"]: e for e in cal}

        # Dec 31 in 2025 holidays, Jan 1 in 2026 holidays
        assert by_date["2025-12-31"]["day_type"] == "special_day"
        assert by_date["2025-12-31"]["is_pre_holiday"]
        assert by_date["2026-01-01"]["day_type"] == "public_holiday"

    def test_leap_year_no_gaps(self):
        """Calendar spanning Feb 2028 (leap year) has no date gaps."""
        cal = build_calendar(date(2028, 2, 1), num_days=60)
        dates = [entry["date"] for entry in cal]
        assert "2028-02-29" in dates
        for i in range(1, len(dates)):
            d1 = date.fromisoformat(dates[i - 1])
            d2 = date.fromisoformat(dates[i])
            assert d2 - d1 == timedelta(days=1)


class TestWeekdayNames:
    """Verify weekday name mapping."""

    def test_all_seven_days(self):
        assert len(WEEKDAY_NAMES_NO) == 7

    def test_monday_is_zero(self):
        assert WEEKDAY_NAMES_NO[0] == "mandag"

    def test_sunday_is_six(self):
        assert WEEKDAY_NAMES_NO[6] == "søndag"


class TestGetTodayOslo:
    """Verify timezone-aware date function."""

    def test_returns_date(self):
        result = get_today_oslo()
        assert isinstance(result, date)

    def test_uses_oslo_timezone(self):
        """Simulating late UTC time that's already next day in Oslo."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        # 23:30 UTC on Dec 31 = 00:30 CET on Jan 1 (Oslo is UTC+1 in winter)
        fake_utc = datetime(2026, 12, 31, 23, 30, tzinfo=UTC)
        with patch("build_calendar.datetime") as mock_dt:
            mock_dt.now.return_value = fake_utc.astimezone(ZoneInfo("Europe/Oslo"))
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = get_today_oslo()
            assert result == date(2027, 1, 1)
