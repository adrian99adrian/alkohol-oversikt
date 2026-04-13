"""Tests for scripts/nearest_store.py."""

from __future__ import annotations

import time

import pytest
from nearest_store import find_nearest_store, haversine_km

# ---------- haversine ----------


def test_haversine_same_point_is_zero():
    assert haversine_km(59.91, 10.75, 59.91, 10.75) == pytest.approx(0.0)


def test_haversine_oslo_bergen():
    # Oslo: 59.913, 10.739. Bergen: 60.392, 5.324. ~308 km.
    d = haversine_km(59.913, 10.739, 60.392, 5.324)
    assert d == pytest.approx(308.0, abs=5.0)


def test_haversine_lindesnes_nordkapp():
    # Lindesnes: 57.983, 7.047. Nordkapp: 71.170, 25.783. ~1700 km.
    d = haversine_km(57.983, 7.047, 71.170, 25.783)
    assert d == pytest.approx(1700.0, abs=25.0)


def test_haversine_is_symmetric():
    a = (59.913, 10.739)
    b = (60.392, 5.324)
    assert haversine_km(*a, *b) == pytest.approx(haversine_km(*b, *a))


def test_haversine_very_close_points_nonneg():
    d = haversine_km(60.0000, 10.0000, 60.0001, 10.0001)
    assert d >= 0
    assert d < 1.0  # sanity — should be millimeters


def test_haversine_boundary_coords():
    # All four Norway corners — just shouldn't throw.
    haversine_km(57.0, 4.0, 72.0, 32.0)
    haversine_km(57.0, 32.0, 72.0, 4.0)


def test_haversine_negative_coords_work():
    # Defensive — shouldn't occur in dataset, but the formula must handle it.
    d = haversine_km(-30.0, -60.0, -30.0, -60.0)
    assert d == pytest.approx(0.0)


# ---------- find_nearest_store ----------


def _store(store_id: str, muni: str, lat: float, lng: float) -> dict:
    return {
        "store_id": store_id,
        "name": f"Store {store_id}",
        "address": f"{muni} addr",
        "municipality": muni,
        "lat": lat,
        "lng": lng,
    }


def _kommune(kid: str, lat: float, lng: float, muni_name: str | None = None) -> dict:
    return {
        "id": kid,
        "municipality": muni_name or kid.title(),
        "county": "Rogaland",
        "lat": lat,
        "lng": lng,
    }


def _registry(*entries: dict) -> dict[str, dict]:
    return {e["id"]: e for e in entries}


def test_empty_stores_returns_none():
    k = _kommune("sokndal", 58.33, 6.22)
    assert find_nearest_store(k, [], _registry(k)) is None


def test_returns_none_when_kommune_lacks_coords():
    k = {"id": "sokndal", "municipality": "Sokndal", "county": "Rogaland"}
    stores = [_store("1", "flekkefjord", 58.30, 6.66)]
    assert find_nearest_store(k, stores, _registry(k)) is None


def test_picks_geographically_closest():
    k = _kommune("sokndal", 58.33, 6.22, "Sokndal")
    flekkefjord = _store("100", "flekkefjord", 58.30, 6.66)
    oslo = _store("200", "oslo", 59.91, 10.75)
    stavanger = _store("300", "stavanger", 58.97, 5.73)

    result = find_nearest_store(
        k,
        [oslo, stavanger, flekkefjord],
        _registry(
            k,
            _kommune("flekkefjord", 58.30, 6.66, "Flekkefjord"),
            _kommune("oslo", 59.91, 10.75, "Oslo"),
            _kommune("stavanger", 58.97, 5.73, "Stavanger"),
        ),
    )
    assert result is not None
    assert result["store"]["store_id"] == "100"
    assert result is not None
    assert result["source_municipality_id"] == "flekkefjord"
    assert result is not None
    assert result["source_municipality_name"] == "Flekkefjord"


def test_single_candidate_always_wins():
    k = _kommune("sokndal", 58.33, 6.22)
    only = _store("42", "flekkefjord", 58.30, 6.66)
    result = find_nearest_store(k, [only], _registry(k, _kommune("flekkefjord", 58.30, 6.66)))
    assert result is not None
    assert result["store"]["store_id"] == "42"


def test_filters_same_municipality_stores():
    """Defense in depth: never recommend a store in the same municipality."""
    k = _kommune("oslo", 59.91, 10.75)
    own_store = _store("1", "oslo", 59.91, 10.75)  # distance 0
    far_store = _store("2", "bergen", 60.39, 5.32)  # ~308 km
    result = find_nearest_store(
        k, [own_store, far_store], _registry(k, _kommune("bergen", 60.39, 5.32, "Bergen"))
    )
    assert result is not None
    assert result["store"]["store_id"] == "2"
    assert result is not None
    assert result["distance_km"] > 100


def test_skips_stores_without_coords():
    k = _kommune("sokndal", 58.33, 6.22)
    no_coords = {"store_id": "1", "name": "X", "municipality": "flekkefjord", "address": "a"}
    good = _store("2", "flekkefjord", 58.30, 6.66)
    result = find_nearest_store(
        k, [no_coords, good], _registry(k, _kommune("flekkefjord", 58.30, 6.66))
    )
    assert result is not None
    assert result["store"]["store_id"] == "2"


def test_rejects_bool_lat_lng_as_non_numeric():
    """Python treats bool as int, so explicit bool rejection matters."""
    k = _kommune("sokndal", 58.33, 6.22)
    bogus = {
        "store_id": "1",
        "name": "X",
        "municipality": "flekkefjord",
        "address": "a",
        "lat": True,
        "lng": False,
    }
    good = _store("2", "flekkefjord", 58.30, 6.66)
    result = find_nearest_store(
        k, [bogus, good], _registry(k, _kommune("flekkefjord", 58.30, 6.66))
    )
    assert result is not None
    assert result["store"]["store_id"] == "2"


def test_tie_break_numeric_not_lexical():
    """Two stores at same location — store_id '100' vs '20' — numeric wins: '20'."""
    k = _kommune("sokndal", 58.33, 6.22)
    # Both at identical coords → tied at 0 distance.
    s20 = _store("20", "muni_a", 58.40, 6.30)
    s100 = _store("100", "muni_b", 58.40, 6.30)
    result = find_nearest_store(
        k,
        [s100, s20],
        _registry(
            k, _kommune("muni_a", 58.40, 6.30, "Muni A"), _kommune("muni_b", 58.40, 6.30, "Muni B")
        ),
    )
    assert result is not None
    assert result["store"]["store_id"] == "20"


def test_tie_break_within_epsilon():
    """Two stores 0.05 km apart (within 0.1 km epsilon) — numeric id wins."""
    k = _kommune("sokndal", 58.33, 6.22)
    s100 = _store("100", "a", 58.40, 6.30)
    # Shift second store ~0.05 km north-ish (0.0005° lat ≈ 55 m).
    s20 = _store("20", "b", 58.4005, 6.30)
    result = find_nearest_store(
        k,
        [s100, s20],
        _registry(k, _kommune("a", 58.40, 6.30, "A"), _kommune("b", 58.4005, 6.30, "B")),
    )
    assert result is not None
    assert result["store"]["store_id"] == "20"


def test_distance_rounded_to_one_decimal():
    k = _kommune("sokndal", 58.33, 6.22)
    result = find_nearest_store(
        k,
        [_store("1", "flekkefjord", 58.30, 6.66)],
        _registry(k, _kommune("flekkefjord", 58.30, 6.66, "Flekkefjord")),
    )
    # Rounded to 1 decimal — compare against a single-decimal value.
    assert result is not None
    assert result["distance_km"] == pytest.approx(round(result["distance_km"], 1))


def test_distance_is_non_negative():
    k = _kommune("sokndal", 58.33, 6.22)
    result = find_nearest_store(
        k,
        [_store("1", "flekkefjord", 58.30, 6.66)],
        _registry(k, _kommune("flekkefjord", 58.30, 6.66)),
    )
    assert result is not None
    assert result["distance_km"] >= 0


def test_returns_all_expected_fields():
    k = _kommune("sokndal", 58.33, 6.22, "Sokndal")
    result = find_nearest_store(
        k,
        [_store("1", "flekkefjord", 58.30, 6.66)],
        _registry(k, _kommune("flekkefjord", 58.30, 6.66, "Flekkefjord")),
    )
    assert result is not None
    assert set(result.keys()) == {
        "store",
        "distance_km",
        "source_municipality_id",
        "source_municipality_name",
    }
    assert result is not None
    assert result["source_municipality_id"] == "flekkefjord"
    assert result is not None
    assert result["source_municipality_name"] == "Flekkefjord"


def test_source_name_falls_back_to_id_if_registry_misses():
    """Defensive: if a store's municipality is not in the registry, use the id."""
    k = _kommune("sokndal", 58.33, 6.22)
    result = find_nearest_store(
        k,
        [_store("1", "unknown_kommune", 58.30, 6.66)],
        _registry(k),  # deliberately missing unknown_kommune
    )
    assert result is not None
    assert result["source_municipality_name"] == "unknown_kommune"


def test_performance_357_x_353():
    """Sanity: 126k haversine computations should complete in <2 seconds."""
    # Synthesize a large dataset.
    kommuner = [
        _kommune(f"k{i}", 58.0 + (i % 100) * 0.1, 5.0 + (i % 100) * 0.1) for i in range(357)
    ]
    stores = [
        _store(str(1000 + i), f"k{i % 200}", 58.0 + (i % 50) * 0.1, 5.0 + (i % 50) * 0.1)
        for i in range(353)
    ]
    registry = {k["id"]: k for k in kommuner}

    start = time.monotonic()
    for k in kommuner:
        find_nearest_store(k, stores, registry)
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"nearest-store loop took {elapsed:.2f}s (>2s threshold)"
