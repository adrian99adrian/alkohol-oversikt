"""TDD tests for Vinmonopolet hour resolution in build_municipality.

Tests the functions that resolve store hours for each day in the 14-day
window, combining actual_hours (days 1-7) with standard_hours fallback
(days 8-14), and generate summary strings for the table column.
"""

import pytest
from vinmonopolet_hours import (
    build_resolved_stores,
    resolve_store_hours,
    summarize_vinmonopolet,
)

# --- Fixtures ---


@pytest.fixture
def sample_store():
    """A Vinmonopolet store with actual_hours for Apr 1-7 and standard_hours."""
    return {
        "store_id": "283",
        "name": "Sandefjord",
        "municipality": "sandefjord",
        "address": "Museumsgata 2, 3210 Sandefjord",
        "standard_hours": {
            "monday": {"open": "10:00", "close": "18:00"},
            "tuesday": {"open": "10:00", "close": "18:00"},
            "wednesday": {"open": "10:00", "close": "18:00"},
            "thursday": {"open": "10:00", "close": "18:00"},
            "friday": {"open": "10:00", "close": "18:00"},
            "saturday": {"open": "10:00", "close": "15:00"},
            "sunday": None,
        },
        "actual_hours": {
            "2026-04-01": {"open": "10:00", "close": "16:00"},  # Wed, pre-holiday reduced
            "2026-04-02": None,  # Thu, Skjærtorsdag closed
            "2026-04-03": None,  # Fri, Langfredag closed
            "2026-04-04": {"open": "10:00", "close": "15:00"},  # Sat, Påskeaften
            "2026-04-05": None,  # Sun, 1. påskedag
            "2026-04-06": None,  # Mon, 2. påskedag
            "2026-04-07": {"open": "10:00", "close": "18:00"},  # Tue, normal
        },
    }


@pytest.fixture
def sample_store_b():
    """A second store with slightly different hours."""
    return {
        "store_id": "404",
        "name": "Stavern",
        "municipality": "larvik",
        "address": "Storgata 1, 3290 Stavern",
        "standard_hours": {
            "monday": {"open": "10:00", "close": "17:00"},
            "tuesday": {"open": "10:00", "close": "17:00"},
            "wednesday": {"open": "10:00", "close": "17:00"},
            "thursday": {"open": "10:00", "close": "17:00"},
            "friday": {"open": "10:00", "close": "17:00"},
            "saturday": {"open": "10:00", "close": "14:00"},
            "sunday": None,
        },
        "actual_hours": {
            "2026-04-01": {"open": "10:00", "close": "16:00"},
            "2026-04-02": None,
            "2026-04-03": None,
            "2026-04-04": {"open": "10:00", "close": "14:00"},
            "2026-04-05": None,
            "2026-04-06": None,
            "2026-04-07": {"open": "10:00", "close": "17:00"},
        },
    }


@pytest.fixture
def sample_calendar_days():
    """Calendar days starting Apr 1 2026, covering Easter and beyond (14 days)."""
    return [
        {"date": "2026-04-01", "weekday": "onsdag", "day_type": "pre_holiday"},
        {"date": "2026-04-02", "weekday": "torsdag", "day_type": "public_holiday"},
        {"date": "2026-04-03", "weekday": "fredag", "day_type": "public_holiday"},
        {"date": "2026-04-04", "weekday": "lørdag", "day_type": "saturday"},
        {"date": "2026-04-05", "weekday": "søndag", "day_type": "sunday"},
        {"date": "2026-04-06", "weekday": "mandag", "day_type": "public_holiday"},
        {"date": "2026-04-07", "weekday": "tirsdag", "day_type": "weekday"},
        # Days 8-14: standard_hours fallback territory
        {"date": "2026-04-08", "weekday": "onsdag", "day_type": "weekday"},
        {"date": "2026-04-09", "weekday": "torsdag", "day_type": "weekday"},
        {"date": "2026-04-10", "weekday": "fredag", "day_type": "weekday"},
        {"date": "2026-04-11", "weekday": "lørdag", "day_type": "saturday"},
        {"date": "2026-04-12", "weekday": "søndag", "day_type": "sunday"},
        {"date": "2026-04-13", "weekday": "mandag", "day_type": "weekday"},
        {"date": "2026-04-14", "weekday": "tirsdag", "day_type": "weekday"},
    ]


# --- resolve_store_hours tests ---


class TestResolveStoreHours:
    """Test single-store, single-day hour resolution."""

    def test_actual_hours_hit(self, sample_store):
        """When date is in actual_hours, use those hours."""
        result = resolve_store_hours(sample_store, "2026-04-01", "pre_holiday")
        assert result == {"open": "10:00", "close": "16:00"}

    def test_actual_hours_closed(self, sample_store):
        """When actual_hours entry is None, store is closed."""
        result = resolve_store_hours(sample_store, "2026-04-02", "public_holiday")
        assert result is None

    def test_standard_hours_fallback(self, sample_store):
        """When date not in actual_hours, fall back to standard_hours by weekday."""
        # Apr 8 is a Wednesday, not in actual_hours
        result = resolve_store_hours(sample_store, "2026-04-08", "weekday")
        assert result == {"open": "10:00", "close": "18:00"}

    def test_standard_hours_saturday(self, sample_store):
        """Standard hours Saturday uses saturday pattern."""
        # Apr 11 is a Saturday, not in actual_hours
        result = resolve_store_hours(sample_store, "2026-04-11", "saturday")
        assert result == {"open": "10:00", "close": "15:00"}

    def test_sunday_always_closed(self, sample_store):
        """Sunday is always closed even if standard_hours had a value."""
        result = resolve_store_hours(sample_store, "2026-04-12", "sunday")
        assert result is None

    def test_public_holiday_closed_in_fallback(self, sample_store):
        """Public holidays in standard_hours fallback range return closed."""
        # Hypothetical public holiday on a day not in actual_hours
        result = resolve_store_hours(sample_store, "2026-04-08", "public_holiday")
        assert result is None

    def test_day7_day8_boundary(self, sample_store):
        """Day 7 uses actual_hours, day 8 uses standard_hours correctly."""
        # Day 7: Apr 7 (Tue) — in actual_hours
        day7 = resolve_store_hours(sample_store, "2026-04-07", "weekday")
        assert day7 == {"open": "10:00", "close": "18:00"}

        # Day 8: Apr 8 (Wed) — NOT in actual_hours, standard Wednesday
        day8 = resolve_store_hours(sample_store, "2026-04-08", "weekday")
        assert day8 == {"open": "10:00", "close": "18:00"}

    def test_preserves_weekday_patterns_after_holiday_week(self, sample_store):
        """Standard_hours should have correct per-weekday patterns, not a flat fallback.

        E.g. a store with different Thu vs Fri hours should keep that distinction
        in the days 8-14 range, even after a holiday week where those days were closed.
        """
        # This store has uniform weekday hours, so create one with varied hours
        store = {
            **sample_store,
            "standard_hours": {
                **sample_store["standard_hours"],
                "thursday": {"open": "10:00", "close": "19:00"},
                "friday": {"open": "10:00", "close": "20:00"},
            },
        }
        # Apr 9 is Thursday, Apr 10 is Friday
        thu = resolve_store_hours(store, "2026-04-09", "weekday")
        fri = resolve_store_hours(store, "2026-04-10", "weekday")
        assert thu == {"open": "10:00", "close": "19:00"}
        assert fri == {"open": "10:00", "close": "20:00"}


# --- summarize_vinmonopolet tests ---


class TestSummarizeVinmonopolet:
    """Test summary string generation for the table column."""

    def test_no_stores(self):
        """No stores in municipality returns None."""
        result = summarize_vinmonopolet([], "2026-04-01", "weekday")
        assert result is None

    def test_one_store_open(self, sample_store):
        """Single open store shows hours."""
        result = summarize_vinmonopolet([sample_store], "2026-04-01", "pre_holiday")
        assert result == "10:00–16:00"

    def test_one_store_closed(self, sample_store):
        """Single closed store shows Stengt."""
        result = summarize_vinmonopolet([sample_store], "2026-04-02", "public_holiday")
        assert result == "Stengt"

    def test_multiple_stores_same_hours(self, sample_store):
        """Multiple stores with same hours show those hours."""
        store2 = {**sample_store, "store_id": "999", "name": "Other"}
        result = summarize_vinmonopolet([sample_store, store2], "2026-04-01", "pre_holiday")
        assert result == "10:00–16:00"

    def test_multiple_stores_different_hours(self, sample_store, sample_store_b):
        """Multiple stores with different hours show range."""
        # Apr 7: store_a closes 18:00, store_b closes 17:00
        result = summarize_vinmonopolet([sample_store, sample_store_b], "2026-04-07", "weekday")
        assert result is not None
        assert "17:00" in result
        assert "18:00" in result

    def test_multiple_stores_all_closed(self, sample_store, sample_store_b):
        """All stores closed shows Stengt."""
        result = summarize_vinmonopolet(
            [sample_store, sample_store_b], "2026-04-02", "public_holiday"
        )
        assert result == "Stengt"


# --- build_resolved_stores tests ---


class TestBuildResolvedStores:
    """Test full store resolution for the municipality output."""

    def test_output_shape(self, sample_store, sample_calendar_days):
        """Each resolved store has store_id, name, address, and 14 hours entries."""
        result = build_resolved_stores([sample_store], sample_calendar_days)
        assert len(result) == 1
        store = result[0]
        assert store["store_id"] == "283"
        assert store["name"] == "Sandefjord"
        assert store["address"] == "Museumsgata 2, 3210 Sandefjord"
        assert len(store["hours"]) == 14

    def test_hours_match_calendar_dates(self, sample_store, sample_calendar_days):
        """Each hour entry's date matches the corresponding calendar day."""
        result = build_resolved_stores([sample_store], sample_calendar_days)
        hours = result[0]["hours"]
        for i, h in enumerate(hours):
            assert h["date"] == sample_calendar_days[i]["date"]

    def test_actual_hours_used_for_first_7_days(self, sample_store, sample_calendar_days):
        """First 7 days use actual_hours from the store data."""
        result = build_resolved_stores([sample_store], sample_calendar_days)
        hours = result[0]["hours"]
        # Apr 1: actual_hours says 10:00-16:00
        assert hours[0]["open"] == "10:00"
        assert hours[0]["close"] == "16:00"
        # Apr 2: actual_hours says closed
        assert hours[1]["open"] is None
        assert hours[1]["close"] is None

    def test_standard_hours_used_for_days_8_14(self, sample_store, sample_calendar_days):
        """Days 8-14 use standard_hours based on weekday."""
        result = build_resolved_stores([sample_store], sample_calendar_days)
        hours = result[0]["hours"]
        # Apr 8 (Wed, day 8): standard wednesday 10:00-18:00
        assert hours[7]["open"] == "10:00"
        assert hours[7]["close"] == "18:00"
        # Apr 11 (Sat, day 11): standard saturday 10:00-15:00
        assert hours[10]["open"] == "10:00"
        assert hours[10]["close"] == "15:00"
        # Apr 12 (Sun, day 12): always closed
        assert hours[11]["open"] is None

    def test_empty_stores(self, sample_calendar_days):
        """No stores returns empty list."""
        result = build_resolved_stores([], sample_calendar_days)
        assert result == []
