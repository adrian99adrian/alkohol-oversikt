"""Tests for beer sales time calculation."""

from datetime import date

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
    """Helper: classify a date and enrich with the same fields build_day_entry adds."""
    holidays = get_public_holidays(d.year)
    special = get_special_days(d.year)
    info = classify_day(d, holidays, special)
    info["date"] = d.isoformat()
    info["_is_saturday"] = d.weekday() == 5
    return info


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

    def test_trondheim_weekday(self, sample_municipality_trondheim):
        day_info = _classify(date(2026, 3, 10))
        assert municipal_close(day_info, sample_municipality_trondheim) == "20:00"

    def test_trondheim_saturday(self, sample_municipality_trondheim):
        day_info = _classify(date(2026, 3, 7))
        assert municipal_close(day_info, sample_municipality_trondheim) == "18:00"

    def test_trondheim_special_day_christmas_eve(self, sample_municipality_trondheim):
        day_info = _classify(date(2026, 12, 24))
        assert municipal_close(day_info, sample_municipality_trondheim) == "15:00"

    def test_trondheim_easter_eve_is_special(self, sample_municipality_trondheim):
        """Trondheim lists easter_eve as special day — close at 15:00."""
        day_info = _classify(date(2026, 4, 4))
        assert municipal_close(day_info, sample_municipality_trondheim) == "15:00"

    def test_trondheim_new_years_eve_not_special(self, sample_municipality_trondheim):
        """Trondheim does NOT list new_years_eve — uses pre_holiday close 18:00."""
        day_info = _classify(date(2026, 12, 31))
        assert municipal_close(day_info, sample_municipality_trondheim) == "18:00"

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

    def test_trondheim_weekday(self, sample_municipality_trondheim):
        day_info = _classify(date(2026, 3, 10))
        assert municipal_open(day_info, sample_municipality_trondheim) == "09:00"

    def test_trondheim_saturday(self, sample_municipality_trondheim):
        day_info = _classify(date(2026, 3, 7))
        assert municipal_open(day_info, sample_municipality_trondheim) == "09:00"

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


# --- Trondheim Ascension Day exception ---


class TestTrondheimAscensionException:
    """Day before Kristi himmelfartsdag uses weekday hours in Trondheim."""

    def test_day_before_ascension_uses_weekday(self, sample_municipality_trondheim):
        """May 13 2026 (Wed) before Ascension (May 14): weekday 20:00."""
        day_info = _classify(date(2026, 5, 13))
        assert day_info["day_type"] == "pre_holiday"
        assert day_info["pre_holiday_for"] == "ascension_day"
        assert closing_time(day_info, sample_municipality_trondheim) == "20:00"

    def test_other_pre_holiday_not_affected(self, sample_municipality_trondheim):
        """April 1, 2026 (Wed before Skjærtorsdag) still uses pre_holiday: 18:00."""
        day_info = _classify(date(2026, 4, 1))
        assert closing_time(day_info, sample_municipality_trondheim) == "18:00"


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

    def test_saturday_is_not_deviation(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 7))
        entry = build_day_entry(date(2026, 3, 7), day_info, sample_municipality_sandefjord)
        assert not entry["is_deviation"]

    def test_sunday_is_not_deviation(self, sample_municipality_sandefjord):
        day_info = _classify(date(2026, 3, 8))
        entry = build_day_entry(date(2026, 3, 8), day_info, sample_municipality_sandefjord)
        assert not entry["is_deviation"]

    def test_pre_holiday_with_weekday_exception_is_not_deviation(self, sample_municipality_larvik):
        """Larvik pre-Ascension keeps weekday hours — not a deviation."""
        day_info = _classify(date(2026, 5, 13))
        entry = build_day_entry(date(2026, 5, 13), day_info, sample_municipality_larvik)
        assert not entry["is_deviation"]

    def test_public_holiday_on_saturday_is_deviation(self, sample_municipality_sandefjord):
        """1. mai 2027 falls on a Saturday — closed instead of open, is a deviation."""
        day_info = _classify(date(2027, 5, 1))
        entry = build_day_entry(date(2027, 5, 1), day_info, sample_municipality_sandefjord)
        assert entry["is_deviation"]

    def test_large_store_close_on_saturday_is_deviation(self, sample_municipality_oslo):
        """Whit eve 2026 is a Saturday — normal beer_close but large stores close early."""
        day_info = _classify(date(2026, 5, 23))
        entry = build_day_entry(date(2026, 5, 23), day_info, sample_municipality_oslo)
        assert entry["is_deviation"]
        assert entry["beer_close_large_stores"] is not None


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


# --- Schema extensions (PR: feat/schema-extensions-for-verification) ---


def _make_mun(**beer_sales_overrides) -> dict:
    """Construct a minimal national-standard municipality for field-level tests."""
    beer = {
        "weekday_open": "08:00",
        "weekday_close": "20:00",
        "saturday_open": "08:00",
        "saturday_close": "18:00",
        "pre_holiday_close": "18:00",
        "special_day_close": "18:00",
        "special_days": [],
    }
    beer.update(beer_sales_overrides)
    return {
        "id": "test",
        "name": "Test",
        "county": "Test",
        "beer_sales": beer,
        "sources": [{"title": "t", "url": "u"}],
        "last_verified": None,
        "verified": False,
    }


class TestSpecialDayOpen:
    """Kommuner that open later on special eves (e.g. Hole 08:30, Orkland 09:00)."""

    def test_special_day_open_applied_on_recognized_eve(self):
        mun = _make_mun(
            special_day_open="08:30",
            special_days=["christmas_eve"],
            special_day_close="15:00",
        )
        day_info = _classify(date(2026, 12, 24))
        assert municipal_open(day_info, mun) == "08:30"

    def test_falls_back_to_weekday_open_when_field_absent(self):
        mun = _make_mun(special_days=["christmas_eve"], special_day_close="15:00")
        day_info = _classify(date(2026, 12, 24))
        assert municipal_open(day_info, mun) == "08:00"

    def test_special_day_open_not_used_on_weekday(self):
        mun = _make_mun(special_day_open="09:00")
        day_info = _classify(date(2026, 3, 10))  # Tuesday
        assert municipal_open(day_info, mun) == "08:00"


class TestPreEasterWeekException:
    """Påskeuke rule: Wed/Thu/Fri/Sat før påske close at pre_holiday time."""

    def test_wednesday_before_maundy_thursday_closes_early(self):
        mun = _make_mun(exceptions={"pre_easter_week": "pre_holiday"})
        day_info = _classify(date(2026, 4, 1))  # Wed før skjærtorsdag
        assert day_info["is_pre_easter_week"]
        assert municipal_close(day_info, mun) == "18:00"

    def test_paaskeaften_forced_to_pre_holiday_close_even_if_listed_as_special(self):
        mun = _make_mun(
            exceptions={"pre_easter_week": "pre_holiday"},
            special_days=["easter_eve"],
            special_day_close="15:00",
        )
        day_info = _classify(date(2026, 4, 4))  # Påskeaften
        assert municipal_close(day_info, mun) == "18:00"

    def test_unaffected_without_exception(self):
        mun = _make_mun()  # no exception
        day_info = _classify(date(2026, 4, 1))
        # Falls through to normal pre_holiday logic (18:00 in any case)
        assert municipal_close(day_info, mun) == "18:00"

    def test_ordinary_weekday_outside_paaskeuke_unaffected(self):
        mun = _make_mun(exceptions={"pre_easter_week": "pre_holiday"})
        day_info = _classify(date(2026, 3, 10))  # Tuesday, outside påskeuke
        assert not day_info["is_pre_easter_week"]
        assert municipal_close(day_info, mun) == "20:00"


class TestDateOverrides:
    """date_overrides: arbitrary dates forced to Saturday or pre_holiday hours."""

    def test_saturday_override_on_weekday_closes_early(self):
        mun = _make_mun(
            date_overrides=[{"date": "04-30", "hours": "saturday"}],
            saturday_close="18:00",
        )
        day_info = _classify(date(2026, 4, 30))  # Thursday
        assert municipal_close(day_info, mun) == "18:00"
        assert municipal_open(day_info, mun) == "08:00"  # saturday_open

    def test_pre_holiday_override_on_weekday(self):
        mun = _make_mun(date_overrides=[{"date": "05-16", "hours": "pre_holiday"}])
        day_info = _classify(date(2026, 5, 16))  # Saturday — but year varies
        # override still applies based on MM-DD match
        assert municipal_close(day_info, mun) == "18:00"

    def test_override_wins_over_special_day(self):
        """Dec 31 is new_years_eve; override says saturday → 18:00 overrides special_day_close."""
        mun = _make_mun(
            date_overrides=[{"date": "12-31", "hours": "saturday"}],
            special_days=["new_years_eve"],
            special_day_close="15:00",
        )
        day_info = _classify(date(2026, 12, 31))
        assert municipal_close(day_info, mun) == "18:00"

    def test_deviation_and_comment_on_weekday_override(self):
        mun = _make_mun(date_overrides=[{"date": "04-30", "hours": "saturday"}])
        d = date(2026, 4, 30)
        day_info = _classify(d)
        entry = build_day_entry(d, day_info, mun)
        assert entry["beer_close"] == "18:00"
        assert entry["is_deviation"] is True
        assert entry["comment"] is not None
        assert "18:00" in entry["comment"]

    def test_no_match_is_noop(self):
        mun = _make_mun(date_overrides=[{"date": "04-30", "hours": "saturday"}])
        day_info = _classify(date(2026, 4, 29))  # Wed
        assert municipal_close(day_info, mun) == "20:00"
