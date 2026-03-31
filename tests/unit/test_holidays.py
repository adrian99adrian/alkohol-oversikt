"""Tests for holiday computation, day type classification, and pre-holiday detection."""

from datetime import date

import pytest
from holidays import (
    HOLIDAY_NAMES,
    classify_day,
    compute_easter,
    get_pre_holiday_for,
    get_public_holidays,
    get_special_days,
    is_pre_holiday,
)

# --- Easter calculation ---


class TestComputeEaster:
    """Verify Easter Sunday computation against known dates."""

    @pytest.mark.parametrize(
        "year, expected",
        [
            (2020, date(2020, 4, 12)),
            (2021, date(2021, 4, 4)),
            (2022, date(2022, 4, 17)),
            (2023, date(2023, 4, 9)),
            (2024, date(2024, 3, 31)),
            (2025, date(2025, 4, 20)),
            (2026, date(2026, 4, 5)),
            (2027, date(2027, 3, 28)),
            (2028, date(2028, 4, 16)),
            (2029, date(2029, 4, 1)),
            (2030, date(2030, 4, 21)),
        ],
    )
    def test_known_easter_dates(self, year: int, expected: date):
        assert compute_easter(year) == expected


# --- Public holidays ---


class TestGetPublicHolidays:
    """Verify public holiday enumeration."""

    def test_fixed_holidays_2026(self):
        holidays = get_public_holidays(2026)
        assert date(2026, 1, 1) in holidays  # 1. nyttårsdag
        assert date(2026, 5, 1) in holidays  # 1. mai
        assert date(2026, 5, 17) in holidays  # 17. mai
        assert date(2026, 12, 25) in holidays  # 1. juledag
        assert date(2026, 12, 26) in holidays  # 2. juledag

    def test_moveable_holidays_2026(self):
        """Easter 2026 = April 5."""
        holidays = get_public_holidays(2026)
        assert date(2026, 3, 29) in holidays  # Palmesøndag (Easter - 7)
        assert date(2026, 4, 2) in holidays  # Skjærtorsdag (Easter - 3)
        assert date(2026, 4, 3) in holidays  # Langfredag (Easter - 2)
        assert date(2026, 4, 5) in holidays  # 1. påskedag
        assert date(2026, 4, 6) in holidays  # 2. påskedag (Easter + 1)
        assert date(2026, 5, 14) in holidays  # Kristi himmelfartsdag (Easter + 39)
        assert date(2026, 5, 24) in holidays  # 1. pinsedag (Easter + 49)
        assert date(2026, 5, 25) in holidays  # 2. pinsedag (Easter + 50)

    def test_palm_sunday_included(self):
        holidays = get_public_holidays(2026)
        assert holidays[date(2026, 3, 29)] == "Palmesøndag"

    def test_all_holidays_have_norwegian_names(self):
        holidays = get_public_holidays(2026)
        for d, name in holidays.items():
            assert isinstance(name, str) and len(name) > 0, f"Missing name for {d}"

    def test_total_count_2026(self):
        """13 public holidays: 5 fixed + 8 moveable."""
        holidays = get_public_holidays(2026)
        assert len(holidays) == 13

    def test_2025_regression(self):
        """Easter 2025 = April 20. Verify all moveable holidays."""
        holidays = get_public_holidays(2025)
        assert date(2025, 4, 13) in holidays  # Palmesøndag
        assert date(2025, 4, 17) in holidays  # Skjærtorsdag
        assert date(2025, 4, 18) in holidays  # Langfredag
        assert date(2025, 4, 20) in holidays  # 1. påskedag
        assert date(2025, 4, 21) in holidays  # 2. påskedag
        assert date(2025, 5, 29) in holidays  # Kristi himmelfartsdag
        assert date(2025, 6, 8) in holidays  # 1. pinsedag
        assert date(2025, 6, 9) in holidays  # 2. pinsedag
        # Fixed
        assert date(2025, 1, 1) in holidays
        assert date(2025, 5, 1) in holidays
        assert date(2025, 5, 17) in holidays
        assert date(2025, 12, 25) in holidays
        assert date(2025, 12, 26) in holidays


# --- Special days ---


class TestGetSpecialDays:
    """Verify special day identification."""

    def test_special_days_2026(self):
        """Easter 2026 = April 5, Whit Sunday = May 24."""
        special = get_special_days(2026)
        assert date(2026, 4, 4) in special  # Påskeaften (Easter - 1)
        assert special[date(2026, 4, 4)] == "easter_eve"
        assert date(2026, 5, 23) in special  # Pinseaften (Whit Sunday - 1)
        assert special[date(2026, 5, 23)] == "whit_eve"
        assert date(2026, 12, 24) in special  # Julaften
        assert special[date(2026, 12, 24)] == "christmas_eve"
        assert date(2026, 12, 31) in special  # Nyttårsaften
        assert special[date(2026, 12, 31)] == "new_years_eve"

    def test_exactly_four_special_days(self):
        special = get_special_days(2026)
        assert len(special) == 4

    def test_special_days_2025(self):
        """Easter 2025 = April 20, Whit Sunday = June 8."""
        special = get_special_days(2025)
        assert special[date(2025, 4, 19)] == "easter_eve"
        assert special[date(2025, 6, 7)] == "whit_eve"
        assert special[date(2025, 12, 24)] == "christmas_eve"
        assert special[date(2025, 12, 31)] == "new_years_eve"


# --- Pre-holiday detection ---


class TestIsPreHoliday:
    """Verify pre-holiday detection."""

    def test_saturday_is_pre_holiday(self):
        """All Saturdays are pre-holiday (day before Sunday)."""
        holidays = get_public_holidays(2026)
        # A regular Saturday: March 7, 2026
        assert date(2026, 3, 7).weekday() == 5  # Saturday
        assert is_pre_holiday(date(2026, 3, 7), holidays)

    def test_wednesday_before_maundy_thursday(self):
        """April 1, 2026 (Wed) is day before Skjærtorsdag (Apr 2)."""
        holidays = get_public_holidays(2026)
        assert is_pre_holiday(date(2026, 4, 1), holidays)

    def test_april_30_before_may_1(self):
        holidays = get_public_holidays(2026)
        assert is_pre_holiday(date(2026, 4, 30), holidays)

    def test_may_16_before_may_17(self):
        holidays = get_public_holidays(2026)
        assert is_pre_holiday(date(2026, 5, 16), holidays)

    def test_christmas_eve_is_pre_holiday(self):
        holidays = get_public_holidays(2026)
        assert is_pre_holiday(date(2026, 12, 24), holidays)

    def test_new_years_eve_is_pre_holiday(self):
        holidays = get_public_holidays(2026)
        assert is_pre_holiday(date(2026, 12, 31), holidays)

    def test_regular_weekday_not_pre_holiday(self):
        """A normal Tuesday is not a pre-holiday."""
        holidays = get_public_holidays(2026)
        # March 10, 2026 is a Tuesday, March 11 is Wednesday (not holiday)
        assert not is_pre_holiday(date(2026, 3, 10), holidays)

    def test_friday_before_regular_saturday_not_pre_holiday(self):
        """Friday is not pre-holiday — Saturday is not a Sunday/holiday."""
        holidays = get_public_holidays(2026)
        # March 6, 2026 is Friday, March 7 is Saturday (not a holiday)
        assert not is_pre_holiday(date(2026, 3, 6), holidays)


# --- pre_holiday_for ---


class TestGetPreHolidayFor:
    """Verify the machine-readable pre_holiday_for key."""

    def test_saturday_returns_sunday(self):
        holidays = get_public_holidays(2026)
        assert get_pre_holiday_for(date(2026, 3, 7), holidays) == "sunday"

    def test_before_maundy_thursday(self):
        holidays = get_public_holidays(2026)
        assert get_pre_holiday_for(date(2026, 4, 1), holidays) == "maundy_thursday"

    def test_before_ascension_day(self):
        """May 13, 2026 (Wed) is day before Ascension (May 14)."""
        holidays = get_public_holidays(2026)
        assert get_pre_holiday_for(date(2026, 5, 13), holidays) == "ascension_day"

    def test_before_may_1(self):
        holidays = get_public_holidays(2026)
        assert get_pre_holiday_for(date(2026, 4, 30), holidays) == "labour_day"

    def test_before_may_17(self):
        holidays = get_public_holidays(2026)
        assert get_pre_holiday_for(date(2026, 5, 16), holidays) == "constitution_day"

    def test_christmas_eve_before_first_christmas_day(self):
        holidays = get_public_holidays(2026)
        assert get_pre_holiday_for(date(2026, 12, 24), holidays) == "first_christmas_day"

    def test_new_years_eve_before_new_years_day(self):
        holidays = get_public_holidays(2026)
        assert get_pre_holiday_for(date(2026, 12, 31), holidays) == "new_years_day"

    def test_regular_weekday_returns_none(self):
        holidays = get_public_holidays(2026)
        assert get_pre_holiday_for(date(2026, 3, 10), holidays) is None


# --- Day type classification ---


class TestClassifyDay:
    """Verify day type classification and priority."""

    def _classify(self, d: date) -> dict:
        holidays = get_public_holidays(d.year)
        special = get_special_days(d.year)
        return classify_day(d, holidays, special)

    def test_regular_weekday(self):
        result = self._classify(date(2026, 3, 10))  # Tuesday
        assert result["day_type"] == "weekday"
        assert not result["is_public_holiday"]
        assert not result["is_pre_holiday"]
        assert not result["is_special_day"]

    def test_regular_saturday(self):
        result = self._classify(date(2026, 3, 7))  # Saturday
        assert result["day_type"] == "saturday"
        assert result["is_pre_holiday"]
        assert result["pre_holiday_for"] == "sunday"

    def test_regular_sunday(self):
        result = self._classify(date(2026, 3, 8))  # Sunday
        assert result["day_type"] == "sunday"

    def test_public_holiday(self):
        result = self._classify(date(2026, 12, 25))  # 1. juledag
        assert result["day_type"] == "public_holiday"
        assert result["is_public_holiday"]
        assert result["holiday_name"] == "1. juledag"

    def test_pre_holiday_weekday(self):
        """Wed April 1, 2026 — day before Skjærtorsdag."""
        result = self._classify(date(2026, 4, 1))
        assert result["day_type"] == "pre_holiday"
        assert result["is_pre_holiday"]
        assert result["pre_holiday_for"] == "maundy_thursday"

    def test_special_day_christmas_eve(self):
        """Dec 24, 2026 is both special_day and pre_holiday. Special wins."""
        result = self._classify(date(2026, 12, 24))
        assert result["day_type"] == "special_day"
        assert result["is_special_day"]
        assert result["special_day_key"] == "christmas_eve"
        assert result["is_pre_holiday"]
        assert result["pre_holiday_for"] == "first_christmas_day"

    def test_special_day_new_years_eve(self):
        """Dec 31, 2026 is both special_day and pre_holiday."""
        result = self._classify(date(2026, 12, 31))
        assert result["day_type"] == "special_day"
        assert result["special_day_key"] == "new_years_eve"
        assert result["is_pre_holiday"]

    def test_easter_eve_saturday_special_day(self):
        """April 4, 2026 (Sat) is easter_eve — special_day beats saturday."""
        result = self._classify(date(2026, 4, 4))
        assert result["day_type"] == "special_day"
        assert result["special_day_key"] == "easter_eve"
        assert result["is_pre_holiday"]
        assert result["pre_holiday_for"] == "easter_sunday"

    def test_public_holiday_beats_sunday(self):
        """May 17, 2026 is Sunday AND Constitution Day. public_holiday wins."""
        assert date(2026, 5, 17).weekday() == 6  # Sunday
        result = self._classify(date(2026, 5, 17))
        assert result["day_type"] == "public_holiday"
        assert result["holiday_name"] == "17. mai"

    def test_public_holiday_on_saturday(self):
        """When a holiday falls on Saturday, it's still public_holiday."""
        # Dec 25, 2027 is Saturday
        assert date(2027, 12, 25).weekday() == 5
        holidays_2027 = get_public_holidays(2027)
        special_2027 = get_special_days(2027)
        result = classify_day(date(2027, 12, 25), holidays_2027, special_2027)
        assert result["day_type"] == "public_holiday"

    def test_consecutive_easter_holidays(self):
        """Easter 2026: Thu-Mon should all be classified correctly."""
        results = {
            date(2026, 4, 1): "pre_holiday",  # Wed before Skjærtorsdag
            date(2026, 4, 2): "public_holiday",  # Skjærtorsdag
            date(2026, 4, 3): "public_holiday",  # Langfredag
            date(2026, 4, 4): "special_day",  # Påskeaften (easter_eve)
            date(2026, 4, 5): "public_holiday",  # 1. påskedag (Sunday)
            date(2026, 4, 6): "public_holiday",  # 2. påskedag (Monday)
        }
        for d, expected_type in results.items():
            result = self._classify(d)
            assert result["day_type"] == expected_type, (
                f"{d} should be {expected_type}, got {result['day_type']}"
            )

    def test_year_boundary_dec31_to_jan1(self):
        """Dec 31, 2025 is special_day + pre_holiday. Jan 1, 2026 is public_holiday."""
        holidays_2025 = get_public_holidays(2025)
        special_2025 = get_special_days(2025)
        dec31 = classify_day(date(2025, 12, 31), holidays_2025, special_2025)
        assert dec31["day_type"] == "special_day"
        assert dec31["is_pre_holiday"]

        holidays_2026 = get_public_holidays(2026)
        special_2026 = get_special_days(2026)
        jan1 = classify_day(date(2026, 1, 1), holidays_2026, special_2026)
        assert jan1["day_type"] == "public_holiday"


# --- Holiday name mapping ---


class TestHolidayNames:
    """Verify HOLIDAY_NAMES covers all holidays and special days."""

    def test_all_public_holidays_have_names(self):
        """Every key used in get_public_holidays maps through HOLIDAY_NAMES."""
        # We check that the Norwegian name returned by get_public_holidays
        # exists as a value in HOLIDAY_NAMES
        holidays = get_public_holidays(2026)
        name_values = set(HOLIDAY_NAMES.values())
        for d, name in holidays.items():
            assert name in name_values, f"Holiday name '{name}' for {d} not in HOLIDAY_NAMES values"

    def test_all_special_days_have_names(self):
        """Every special_day key appears in HOLIDAY_NAMES."""
        special = get_special_days(2026)
        for d, key in special.items():
            assert key in HOLIDAY_NAMES, f"Special day key '{key}' for {d} not in HOLIDAY_NAMES"

    def test_specific_names(self):
        assert HOLIDAY_NAMES["maundy_thursday"] == "Skjærtorsdag"
        assert HOLIDAY_NAMES["good_friday"] == "Langfredag"
        assert HOLIDAY_NAMES["easter_sunday"] == "1. påskedag"
        assert HOLIDAY_NAMES["ascension_day"] == "Kristi himmelfartsdag"
        assert HOLIDAY_NAMES["christmas_eve"] == "Julaften"
        assert HOLIDAY_NAMES["palm_sunday"] == "Palmesøndag"

    def test_classify_day_has_day_type_label(self):
        """Every classified day has a non-empty day_type_label."""
        holidays = get_public_holidays(2026)
        special = get_special_days(2026)
        for d in [
            date(2026, 3, 10),  # weekday
            date(2026, 3, 7),  # saturday
            date(2026, 3, 8),  # sunday
            date(2026, 4, 2),  # public_holiday
            date(2026, 4, 1),  # pre_holiday
            date(2026, 12, 24),  # special_day
        ]:
            result = classify_day(d, holidays, special)
            assert isinstance(result["day_type_label"], str)
            assert len(result["day_type_label"]) > 0
