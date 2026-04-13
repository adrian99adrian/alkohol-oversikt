"""Tests for build_municipality's vinmonopolet_mode decision + nearest_vinmonopolet payload."""

from __future__ import annotations

from datetime import date

import pytest
from build_calendar import build_calendar
from build_municipality import build_municipality

WEEKDAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _store(sid: str, muni: str, lat: float, lng: float) -> dict:
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


def _muni(kid: str = "sokndal", name: str = "Sokndal") -> dict:
    return {
        "id": kid,
        "name": name,
        "county": "Rogaland",
        "sources": [{"title": "Test", "url": "https://example.com"}],
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


def _cal(days: int = 14) -> list[dict]:
    return build_calendar(date(2026, 1, 1), num_days=days)


def _registry_entry(kid: str, lat: float = 58.33, lng: float = 6.22) -> dict:
    return {"id": kid, "municipality": kid.title(), "county": "Rogaland", "lat": lat, "lng": lng}


# ---------- mode=local ----------


def test_mode_local_when_own_stores_present():
    muni = _muni("oslo")
    result = build_municipality(
        muni, _cal(), vinmonopolet_stores=[_store("1", "oslo", 59.91, 10.75)]
    )
    assert result["vinmonopolet_mode"] == "local"
    assert result["nearest_vinmonopolet"] is None
    assert len(result["vinmonopolet_stores"]) == 1


def test_mode_local_ignores_coords_and_registry():
    """Even when a kommune has coords + registry entry, local stores win."""
    muni = _muni("oslo")
    registry = {"oslo": _registry_entry("oslo"), "bergen": _registry_entry("bergen", 60.39, 5.32)}
    all_stores = [_store("1", "oslo", 59.91, 10.75), _store("2", "bergen", 60.39, 5.32)]
    result = build_municipality(
        muni,
        _cal(),
        vinmonopolet_stores=[_store("1", "oslo", 59.91, 10.75)],
        all_stores=all_stores,
        kommune_registry=registry,
    )
    assert result["vinmonopolet_mode"] == "local"
    assert result["nearest_vinmonopolet"] is None


# ---------- mode=nearest ----------


def test_mode_nearest_when_no_local_store_but_coords_available():
    muni = _muni("sokndal")
    registry = {
        "sokndal": _registry_entry("sokndal", 58.33, 6.22),
        "flekkefjord": _registry_entry("flekkefjord", 58.30, 6.66),
    }
    all_stores = [_store("100", "flekkefjord", 58.30, 6.66)]

    result = build_municipality(
        muni,
        _cal(),
        vinmonopolet_stores=[],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
        all_stores=all_stores,
        kommune_registry=registry,
    )
    assert result["vinmonopolet_mode"] == "nearest"
    assert result["vinmonopolet_stores"] == []
    assert result["nearest_vinmonopolet"] is not None
    near = result["nearest_vinmonopolet"]
    assert near["store"]["store_id"] == "100"
    assert near["source_municipality_id"] == "flekkefjord"
    assert near["source_municipality_name"] == "Flekkefjord"
    assert near["distance_km"] >= 0
    # day_summary has 14 entries.
    assert len(near["day_summary"]) == 14


def test_mode_nearest_does_not_pollute_top_level_or_days():
    """In nearest mode, top-level vinmonopolet_day_summary describes THIS
    kommune's own stores and must stay empty. days[i].vinmonopolet_summary
    must also be None — DayCard / BeerSalesTable render those as this
    kommune's Vinmonopol-hours and would mislead users otherwise."""
    muni = _muni("sokndal")
    registry = {
        "sokndal": _registry_entry("sokndal", 58.33, 6.22),
        "flekkefjord": _registry_entry("flekkefjord", 58.30, 6.66),
    }
    result = build_municipality(
        muni,
        _cal(),
        vinmonopolet_stores=[],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
        all_stores=[_store("1", "flekkefjord", 58.30, 6.66)],
        kommune_registry=registry,
    )
    assert result["vinmonopolet_day_summary"] == []
    for d in result["days"]:
        assert d["vinmonopolet_summary"] is None
    # Nearest-store hours still rendered from nearest_vinmonopolet.day_summary.
    assert len(result["nearest_vinmonopolet"]["day_summary"]) == 14


def test_mode_nearest_days_have_null_vinmonopolet_summary():
    """Keys are present on every day (shape consistency) but values are None
    in nearest mode — see comment on build_municipality."""
    muni = _muni("sokndal")
    registry = {
        "sokndal": _registry_entry("sokndal", 58.33, 6.22),
        "flekkefjord": _registry_entry("flekkefjord", 58.30, 6.66),
    }
    result = build_municipality(
        muni,
        _cal(),
        vinmonopolet_stores=[],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
        all_stores=[_store("1", "flekkefjord", 58.30, 6.66)],
        kommune_registry=registry,
    )
    for d in result["days"]:
        assert "vinmonopolet_summary" in d
        assert d["vinmonopolet_summary"] is None


def test_mode_nearest_fetched_at_preserved():
    muni = _muni("sokndal")
    registry = {
        "sokndal": _registry_entry("sokndal"),
        "flekkefjord": _registry_entry("flekkefjord", 58.30, 6.66),
    }
    result = build_municipality(
        muni,
        _cal(),
        vinmonopolet_stores=[],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
        all_stores=[_store("1", "flekkefjord", 58.30, 6.66)],
        kommune_registry=registry,
    )
    assert result["vinmonopolet_fetched_at"] == "2026-04-13T00:00:00+02:00"


def test_mode_nearest_excludes_self_from_candidates():
    """A store whose municipality is the queried kommune must not be selected
    as 'nearest'. (Invariant that local-mode would already have caught, but
    explicit defense in depth.)"""
    muni = _muni("sokndal")
    # Registry has sokndal; we don't pass any local stores, but simulate a
    # spurious entry in all_stores where a mapped store belongs to sokndal.
    registry = {
        "sokndal": _registry_entry("sokndal"),
        "flekkefjord": _registry_entry("flekkefjord", 58.30, 6.66),
    }
    all_stores = [
        _store("1", "sokndal", 58.33, 6.22),  # same coords — distance 0
        _store("2", "flekkefjord", 58.30, 6.66),  # real nearest
    ]
    result = build_municipality(
        muni,
        _cal(),
        vinmonopolet_stores=[],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
        all_stores=all_stores,
        kommune_registry=registry,
    )
    assert result["vinmonopolet_mode"] == "nearest"
    assert result["nearest_vinmonopolet"]["store"]["store_id"] == "2"


# ---------- mode=fallback ----------


def test_mode_fallback_when_no_coords():
    muni = _muni("sokndal")
    result = build_municipality(
        muni,
        _cal(),
        vinmonopolet_stores=[],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
        all_stores=[_store("1", "flekkefjord", 58.30, 6.66)],
        kommune_registry={},  # empty — kommune not in registry, no coords
    )
    assert result["vinmonopolet_mode"] == "fallback"
    assert result["nearest_vinmonopolet"] is None
    assert result["vinmonopolet_stores"] == []
    assert result["vinmonopolet_day_summary"] == []
    assert result["vinmonopolet_fetched_at"] is None


def test_mode_fallback_all_vinmonopolet_summaries_none():
    muni = _muni("sokndal")
    result = build_municipality(muni, _cal(), vinmonopolet_stores=[])
    for d in result["days"]:
        assert d["vinmonopolet_summary"] is None


def test_mode_fallback_when_no_stores_anywhere():
    """Kommune has coords but there are zero mapped stores — fallback."""
    muni = _muni("sokndal")
    registry = {"sokndal": _registry_entry("sokndal")}
    result = build_municipality(
        muni,
        _cal(),
        vinmonopolet_stores=[],
        all_stores=[],
        kommune_registry=registry,
    )
    assert result["vinmonopolet_mode"] == "fallback"


# ---------- short window ----------


@pytest.mark.parametrize("days", [1, 3, 7, 14])
def test_nearest_day_summary_length_matches_min_14_days(days):
    """In nearest mode, the top-level summary is empty — the nearest
    store's 14-day table lives in nearest_vinmonopolet.day_summary."""
    muni = _muni("sokndal")
    registry = {
        "sokndal": _registry_entry("sokndal"),
        "flekkefjord": _registry_entry("flekkefjord", 58.30, 6.66),
    }
    result = build_municipality(
        muni,
        _cal(days),
        vinmonopolet_stores=[],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
        all_stores=[_store("1", "flekkefjord", 58.30, 6.66)],
        kommune_registry=registry,
    )
    assert result["vinmonopolet_day_summary"] == []
    assert len(result["nearest_vinmonopolet"]["day_summary"]) == min(14, days)


def test_days_30_nearest_summary_capped_at_14():
    muni = _muni("sokndal")
    registry = {
        "sokndal": _registry_entry("sokndal"),
        "flekkefjord": _registry_entry("flekkefjord", 58.30, 6.66),
    }
    result = build_municipality(
        muni,
        _cal(30),
        vinmonopolet_stores=[],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
        all_stores=[_store("1", "flekkefjord", 58.30, 6.66)],
        kommune_registry=registry,
    )
    assert len(result["nearest_vinmonopolet"]["day_summary"]) == 14
    # All days must have vinmonopolet_summary == None in nearest mode.
    for d in result["days"]:
        assert d["vinmonopolet_summary"] is None


# ---------- invariants ----------


def test_local_mode_does_not_invoke_nearest_lookup(monkeypatch):
    """Efficiency invariant: in local mode, find_nearest_store must not be called."""
    import build_municipality as bm

    called = {"n": 0}

    def _spy(*args, **kwargs):
        called["n"] += 1
        return None

    monkeypatch.setattr(bm, "find_nearest_store", _spy)

    muni = _muni("oslo")
    registry = {"oslo": _registry_entry("oslo", 59.91, 10.75)}
    bm.build_municipality(
        muni,
        _cal(),
        vinmonopolet_stores=[_store("1", "oslo", 59.91, 10.75)],
        all_stores=[_store("1", "oslo", 59.91, 10.75)],
        kommune_registry=registry,
    )
    assert called["n"] == 0


def test_deterministic_across_reruns():
    """Same input → same output across multiple invocations."""
    muni = _muni("sokndal")
    registry = {
        "sokndal": _registry_entry("sokndal"),
        "flekkefjord": _registry_entry("flekkefjord", 58.30, 6.66),
    }
    all_stores = [_store("1", "flekkefjord", 58.30, 6.66)]

    r1 = build_municipality(
        muni,
        _cal(),
        vinmonopolet_stores=[],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
        all_stores=all_stores,
        kommune_registry=registry,
    )
    r2 = build_municipality(
        muni,
        _cal(),
        vinmonopolet_stores=[],
        vinmonopolet_fetched_at="2026-04-13T00:00:00+02:00",
        all_stores=all_stores,
        kommune_registry=registry,
    )
    assert r1 == r2
