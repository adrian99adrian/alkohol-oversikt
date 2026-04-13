"""Exhaustive tests for scripts/validate_data._validate_vinmonopolet_mode.

Covers the strict one-of contract:
  - local: own stores, no nearest, fetched_at set, day_summary populated
  - nearest: no stores, nearest_vinmonopolet set (with mirrored day_summary)
  - fallback: everything empty/null
"""

from __future__ import annotations

from datetime import date

import pytest
from build_calendar import build_calendar
from build_municipality import build_municipality
from validate_data import _validate_vinmonopolet_mode, validate_generated_municipality

WEEKDAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _store(sid="1", muni="sokndal", lat=58.33, lng=6.22) -> dict:
    return {
        "store_id": sid,
        "name": f"Store {sid}",
        "municipality": muni,
        "address": "addr",
        "lat": lat,
        "lng": lng,
        "standard_hours": {k: None for k in WEEKDAY_KEYS},
        "actual_hours": {},
    }


def _muni(kid="sokndal") -> dict:
    return {
        "id": kid,
        "name": kid.title(),
        "county": "Rogaland",
        "sources": [{"title": "T", "url": "https://example.com"}],
        "last_verified": None,
        "verified": False,
        "beer_sales": {
            "weekday_open": "08:00",
            "weekday_close": "20:00",
            "saturday_open": "08:00",
            "saturday_close": "18:00",
            "pre_holiday_close": "18:00",
            "special_day_close": "15:00",
            "special_days": [],
        },
    }


def _cal(n=14):
    return build_calendar(date(2026, 1, 1), num_days=n)


def _build_local() -> dict:
    return build_municipality(
        _muni("oslo"),
        _cal(),
        vinmonopolet_stores=[_store("1", "oslo", 59.91, 10.75)],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
    )


def _build_nearest() -> dict:
    return build_municipality(
        _muni("sokndal"),
        _cal(),
        vinmonopolet_stores=[],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
        all_stores=[_store("1", "flekkefjord", 58.30, 6.66)],
        kommune_registry={
            "sokndal": {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "R",
                "lat": 58.33,
                "lng": 6.22,
            },
            "flekkefjord": {
                "id": "flekkefjord",
                "municipality": "Flekkefjord",
                "county": "R",
                "lat": 58.30,
                "lng": 6.66,
            },
        },
    )


def _build_fallback() -> dict:
    return build_municipality(_muni("sokndal"), _cal(), vinmonopolet_stores=[])


# ---------- valid ----------


def test_valid_local_passes():
    d = _build_local()
    assert _validate_vinmonopolet_mode(d, 14) == []


def test_valid_nearest_passes():
    d = _build_nearest()
    assert _validate_vinmonopolet_mode(d, 14) == []


def test_valid_fallback_passes():
    d = _build_fallback()
    assert _validate_vinmonopolet_mode(d, 14) == []


@pytest.mark.parametrize("days", [1, 3, 7])
def test_valid_local_short_window(days):
    result = build_municipality(
        _muni("oslo"),
        _cal(days),
        vinmonopolet_stores=[_store("1", "oslo", 59.91, 10.75)],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
    )
    assert _validate_vinmonopolet_mode(result, days) == []


def test_valid_nearest_short_window():
    result = build_municipality(
        _muni("sokndal"),
        _cal(7),
        vinmonopolet_stores=[],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
        all_stores=[_store("1", "flekkefjord", 58.30, 6.66)],
        kommune_registry={
            "sokndal": {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "R",
                "lat": 58.33,
                "lng": 6.22,
            },
            "flekkefjord": {
                "id": "flekkefjord",
                "municipality": "Flekkefjord",
                "county": "R",
                "lat": 58.30,
                "lng": 6.66,
            },
        },
    )
    errors = _validate_vinmonopolet_mode(result, 7)
    assert errors == []


# ---------- invalid local ----------


def test_local_with_empty_stores_errors():
    d = _build_local()
    d["vinmonopolet_stores"] = []
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("mode=local" in e and "non-empty" in e for e in errors)


def test_local_with_nearest_set_errors():
    d = _build_local()
    d["nearest_vinmonopolet"] = {
        "store": {},
        "distance_km": 0,
        "source_municipality_id": "x",
        "source_municipality_name": "X",
        "day_summary": [],
    }
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("mode=local" in e and "null" in e for e in errors)


def test_local_without_fetched_at_errors():
    d = _build_local()
    d["vinmonopolet_fetched_at"] = None
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("mode=local" in e and "fetched_at" in e for e in errors)


def test_local_day_summary_wrong_length_errors():
    d = _build_local()
    d["vinmonopolet_day_summary"] = d["vinmonopolet_day_summary"][:5]
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("mode=local" in e and "length" in e for e in errors)


# ---------- invalid nearest ----------


def test_nearest_without_payload_errors():
    d = _build_nearest()
    d["nearest_vinmonopolet"] = None
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("mode=nearest" in e and "required" in e for e in errors)


def test_nearest_with_stores_errors():
    d = _build_nearest()
    d["vinmonopolet_stores"] = [{"store_id": "999"}]
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("mode=nearest" in e and "empty" in e for e in errors)


def test_nearest_without_fetched_at_errors():
    d = _build_nearest()
    d["vinmonopolet_fetched_at"] = None
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("mode=nearest" in e and "fetched_at" in e for e in errors)


def test_nearest_payload_missing_day_summary_errors():
    d = _build_nearest()
    del d["nearest_vinmonopolet"]["day_summary"]
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("nearest_vinmonopolet" in e and "missing fields" in e for e in errors)


def test_nearest_day_summary_wrong_length_errors():
    d = _build_nearest()
    d["nearest_vinmonopolet"]["day_summary"] = d["nearest_vinmonopolet"]["day_summary"][:5]
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("day_summary length" in e for e in errors)


def test_nearest_top_level_day_summary_does_not_mirror_errors():
    d = _build_nearest()
    # Corrupt the top-level summary so it no longer mirrors nearest.day_summary.
    d["vinmonopolet_day_summary"] = list(reversed(d["vinmonopolet_day_summary"]))
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("must mirror" in e for e in errors)


def test_nearest_negative_distance_errors():
    d = _build_nearest()
    d["nearest_vinmonopolet"]["distance_km"] = -1.0
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("non-negative" in e for e in errors)


def test_nearest_non_numeric_distance_errors():
    d = _build_nearest()
    d["nearest_vinmonopolet"]["distance_km"] = "10 km"
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("numeric" in e for e in errors)


def test_nearest_empty_source_municipality_id_errors():
    d = _build_nearest()
    d["nearest_vinmonopolet"]["source_municipality_id"] = ""
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("source_municipality_id" in e for e in errors)


def test_nearest_empty_source_municipality_name_errors():
    d = _build_nearest()
    d["nearest_vinmonopolet"]["source_municipality_name"] = ""
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("source_municipality_name" in e for e in errors)


# ---------- invalid fallback ----------


def test_fallback_with_stores_errors():
    d = _build_fallback()
    d["vinmonopolet_stores"] = [{"store_id": "1"}]
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("mode=fallback" in e and "stores" in e for e in errors)


def test_fallback_with_fetched_at_errors():
    d = _build_fallback()
    d["vinmonopolet_fetched_at"] = "2026-04-13T00:00:00+02:00"
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("mode=fallback" in e and "fetched_at" in e for e in errors)


def test_fallback_with_nearest_errors():
    d = _build_fallback()
    d["nearest_vinmonopolet"] = {
        "store": {},
        "distance_km": 0,
        "source_municipality_id": "x",
        "source_municipality_name": "X",
        "day_summary": [],
    }
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("mode=fallback" in e and "nearest" in e for e in errors)


def test_fallback_with_non_empty_day_summary_errors():
    d = _build_fallback()
    d["vinmonopolet_day_summary"] = [{"type": "closed"}]
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("mode=fallback" in e and "day_summary" in e for e in errors)


# ---------- enum / legacy ----------


def test_unknown_mode_errors():
    d = _build_local()
    d["vinmonopolet_mode"] = "foo"
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("invalid value" in e for e in errors)
    # Error should enumerate allowed values for discoverability.
    assert any("local" in e and "nearest" in e and "fallback" in e for e in errors)


def test_missing_mode_field_errors():
    d = _build_local()
    del d["vinmonopolet_mode"]
    errors = _validate_vinmonopolet_mode(d, 14)
    assert any("missing field" in e for e in errors)


def test_mode_check_integrated_in_full_validator():
    """validate_generated_municipality wires in the mode check."""
    d = _build_local()
    d["vinmonopolet_mode"] = "nonsense"
    cal = _cal()
    errors = validate_generated_municipality(d, d["days"], cal)
    assert any("invalid value" in e for e in errors)
