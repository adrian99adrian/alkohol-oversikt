"""Tests for beer sales time calculation."""

import sys
from datetime import date

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent / "scripts"))

from holidays import classify_day, get_public_holidays, get_special_days
from sales import (
    build_day_entry,
    closing_time,
    large_store_close,
    municipal_close,
    municipal_open,
    national_max,
)


def _classify(d: date) -> dict:
    """Helper: classify a date using both years if needed."""
    holidays = get_public_holidays(d.year)
    special = get_special_days(d.year)
    return classify_day(d, holidays, special)


# --- National maximums ---


class TestNationalMax:
    """Verify national maximum closing times by day type."""

    def test_weekday(self):
        day_info = _classify(date(2026, 3, 10))  # Tuesday
        assert national_max(day_info) == "20:00"

    def test_saturday(self):
        day_info = _classify(date(2026, 3, 7))  # Saturday
        assert national_max(day_info) == "18:00"

    def test_pre_holiday(self):
        day_info = _classify(date(2026, 4, 1))  # Wed before Skjærtorsdag
        assert national_max(day_info) == "18:00"

    def test_sunday(self):
        day_info = _classify(date(2026, 3, 8))  # Sunday
        assert national_max(day_info) is None

    def test_public_holiday(self):
        day_info = _classify(date(2026, 4, 2))  # Skjærtorsdag
        assert national_max(day_info) is None

    def test_special_day(self):
        """Special days have the same max as pre_holiday (18:00)."""
        day_info = _classify(date(2026, 12, 24))  # Julaften
        assert national_max(day_info) == "18:00"


# --- Municipal closing times ---


class TestMunicipalClose:
    """Verify municipal closing time selection."""

    def test_sandefjord_weekday(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 10))
        assert municipal_close(day_info, sample_municipality_sandefjord) == "20:00"

    def test_sandefjord_saturday(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 7))
        assert municipal_close(day_info, sample_municipality_sandefjord) == "20:00"

    def test_sandefjord_pre_holiday(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 4, 1))
        assert municipal_close(day_info, sample_municipality_sandefjord) == "18:00"

    def test_sandefjord_special_day_christmas_eve(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 12, 24))
        assert municipal_close(day_info, sample_municipality_sandefjord) == "15:00"

    def test_larvik_weekday(self, sample_municipality_larvik):
        day_info = _classify(date(2026, 3, 10))
        assert municipal_close(day_info, sample_municipality_larvik) == "20:00"

    def test_larvik_saturday(self, sample_municipality_larvik):
        day_info = _classify(date(2026, 3, 7))
        assert municipal_close(day_info, sample_municipality_larvik) == "18:00"

    def test_larvik_special_day_christmas_eve(self, sample_municipality_larvik):
        day_info = _classify(date(2026, 12, 24))
        assert municipal_close(day_info, sample_municipality_larvik) == "16:00"

    def test_oslo_weekday(self, sample_municipality_oslo):
        day_info = _classify(date(2026, 3, 10))
        assert municipal_close(day_info, sample_municipality_oslo) == "20:00"

    def test_oslo_special_day(self, sample_municipality_oslo):
        day_info = _classify(date(2026, 12, 24))
        assert municipal_close(day_info, sample_municipality_oslo) == "18:00"

    def test_sunday_returns_none(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 8))
        assert municipal_close(day_info, sample_municipality_sandefjord) is None

    def test_public_holiday_returns_none(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 4, 2))  # Skjærtorsdag
        assert municipal_close(day_info, sample_municipality_sandefjord) is None


# --- Municipal opening times ---


class TestMunicipalOpen:
    """Verify municipal opening time selection."""

    def test_sandefjord_weekday(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 10))
        assert municipal_open(day_info, sample_municipality_sandefjord) == "06:00"

    def test_sandefjord_saturday(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 7))
        assert municipal_open(day_info, sample_municipality_sandefjord) == "06:00"

    def test_larvik_weekday(self, sample_municipality_larvik):
        day_info = _classify(date(2026, 3, 10))
        assert municipal_open(day_info, sample_municipality_larvik) == "08:00"

    def test_forbidden_day_returns_none(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 8))  # Sunday
        assert municipal_open(day_info, sample_municipality_sandefjord) is None


# --- Closing time (min formula) ---


class TestClosingTime:
    """Verify min(national, municipal) formula."""

    def test_sandefjord_saturday(self, sample_municipality_sandefjord):
        """min(18:00 national, 20:00 municipal) = 18:00."""
        day_info = _classify(date(2026, 3, 7))
        assert closing_time(day_info, sample_municipality_sandefjord) == "18:00"

    def test_sandefjord_special_day(self, sample_municipality_sandefjord):
        """min(18:00 national, 15:00 municipal) = 15:00."""
        day_info = _classify(date(2026, 12, 24))
        assert closing_time(day_info, sample_municipality_sandefjord) == "15:00"

    def test_oslo_weekday(self, sample_municipality_oslo):
        """min(20:00 national, 20:00 municipal) = 20:00."""
        day_info = _classify(date(2026, 3, 10))
        assert closing_time(day_info, sample_municipality_oslo) == "20:00"

    def test_forbidden_day(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 8))
        assert closing_time(day_info, sample_municipality_sandefjord) is None


# --- Larvik Ascension Day exception ---


class TestLarvikAscensionException:
    """Day before Kristi himmelfartsdag uses weekday hours in Larvik."""

    def test_day_before_ascension_uses_weekday(self, sample_municipality_larvik):
        """May 13 2026 (Wed) before Ascension (May 14): weekday 20:00, not pre_holiday."""
        day_info = _classify(date(2026, 5, 13))
        assert day_info["day_type"] == "pre_holiday"
        assert day_info["pre_holiday_for"] == "ascension_day"
        assert closing_time(day_info, sample_municipality_larvik) == "20:00"

    def test_other_pre_holiday_not_affected(self, sample_municipality_larvik):
        """April 1, 2026 (Wed before Skjærtorsdag) still uses pre_holiday: 18:00."""
        day_info = _classify(date(2026, 4, 1))
        assert closing_time(day_info, sample_municipality_larvik) == "18:00"


# --- Oslo large store rule ---


class TestOsloLargeStoreRule:
    """Verify large store closing time is scoped correctly."""

    def test_christmas_eve_has_large_store_close(self, sample_municipality_oslo):
        day_info = _classify(date(2026, 12, 24))
        assert large_store_close(day_info, sample_municipality_oslo) == "16:00"

    def test_whit_eve_has_large_store_close(self, sample_municipality_oslo):
        """Pinseaften May 23, 2026."""
        day_info = _classify(date(2026, 5, 23))
        assert day_info["special_day_key"] == "whit_eve"
        assert large_store_close(day_info, sample_municipality_oslo) == "16:00"

    def test_new_years_eve_no_large_store_close(self, sample_municipality_oslo):
        """New Year's Eve is special_day but NOT in large_store_special_days."""
        day_info = _classify(date(2026, 12, 31))
        assert large_store_close(day_info, sample_municipality_oslo) is None

    def test_regular_day_no_large_store_close(self, sample_municipality_oslo):
        day_info = _classify(date(2026, 3, 10))
        assert large_store_close(day_info, sample_municipality_oslo) is None

    def test_sandefjord_never_has_large_store_close(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 12, 24))
        assert large_store_close(day_info, sample_municipality_sandefjord) is None


# --- Negative: easter_eve not special for Larvik/Oslo ---


class TestEasterEveNotUniversal:
    """easter_eve is only a special day for municipalities that list it."""

    def test_larvik_easter_eve_not_special(self, sample_municipality_larvik):
        """Larvik doesn't list easter_eve — should use saturday rules."""
        day_info = _classify(date(2026, 4, 4))  # Saturday, easter_eve
        assert day_info["is_special_day"]  # Calendar still marks it
        assert day_info["special_day_key"] == "easter_eve"
        # But Larvik doesn't have easter_eve in special_days, so
        # municipal_close should use saturday_close, not special_day_close
        assert municipal_close(day_info, sample_municipality_larvik) == "18:00"

    def test_sandefjord_easter_eve_is_special(self, sample_municipality_sandefjord):
        """Sandefjord lists easter_eve — should use special_day_close."""
        day_info = _classify(date(2026, 4, 4))
        assert municipal_close(day_info, sample_municipality_sandefjord) == "15:00"


# --- is_deviation ---


class TestIsDeviation:
    """Verify deviation flag."""

    def test_regular_weekday_no_deviation(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 10))
        entry = build_day_entry(date(2026, 3, 10), day_info, sample_municipality_sandefjord)
        assert not entry["is_deviation"]

    def test_pre_holiday_is_deviation(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 4, 1))
        entry = build_day_entry(date(2026, 4, 1), day_info, sample_municipality_sandefjord)
        assert entry["is_deviation"]

    def test_public_holiday_is_deviation(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 4, 2))
        entry = build_day_entry(date(2026, 4, 2), day_info, sample_municipality_sandefjord)
        assert entry["is_deviation"]

    def test_saturday_is_deviation(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 7))
        entry = build_day_entry(date(2026, 3, 7), day_info, sample_municipality_sandefjord)
        assert entry["is_deviation"]


# --- Output schema ---


class TestBuildDayEntry:
    """Verify build_day_entry output matches the JSON contract."""

    def test_schema(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 10))
        entry = build_day_entry(date(2026, 3, 10), day_info, sample_municipality_sandefjord)
        required_fields = {
            "date",
            "weekday",
            "day_type",
            "day_type_label",
            "beer_sale_allowed",
            "beer_open",
            "beer_close",
            "beer_close_large_stores",
            "is_deviation",
            "comment",
        }
        assert required_fields.issubset(entry.keys())

    def test_forbidden_day_nulls(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 8))  # Sunday
        entry = build_day_entry(date(2026, 3, 8), day_info, sample_municipality_sandefjord)
        assert not entry["beer_sale_allowed"]
        assert entry["beer_open"] is None
        assert entry["beer_close"] is None

    def test_weekday_values(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 10))  # Tuesday
        entry = build_day_entry(date(2026, 3, 10), day_info, sample_municipality_sandefjord)
        assert entry["beer_sale_allowed"]
        assert entry["beer_open"] == "06:00"
        assert entry["beer_close"] == "20:00"
        assert entry["beer_close_large_stores"] is None
        assert entry["comment"] is None
