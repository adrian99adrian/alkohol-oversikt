"""Tests for store-coordinate parsing + validation.

Covers:
- fetch_vinmonopolet.parse_gps_coord (parsing + hard-fail modes)
- validate_data._validate_store_fields for the new lat/lng rules
"""

from __future__ import annotations

import math

import pytest
from fetch_vinmonopolet import parse_gps_coord, transform_store
from validate_data import _validate_store_fields

# ---------- parse_gps_coord: geoPoint dict (canonical API shape) ----------


def test_parse_geopoint_dict():
    lat, lng = parse_gps_coord({"latitude": 59.123, "longitude": 10.456}, store_id="1")
    assert lat == pytest.approx(59.123)
    assert lng == pytest.approx(10.456)


def test_parse_geopoint_missing_latitude_hard_fails():
    with pytest.raises(ValueError, match="non-numeric"):
        parse_gps_coord({"longitude": 10.456}, store_id="1")


def test_parse_geopoint_non_numeric_latitude_hard_fails():
    with pytest.raises(ValueError, match="non-numeric"):
        parse_gps_coord({"latitude": "abc", "longitude": 10.456}, store_id="1")


def test_parse_geopoint_out_of_bounds_hard_fails():
    with pytest.raises(ValueError, match="outside Norway"):
        parse_gps_coord({"latitude": 5.0, "longitude": 10.0}, store_id="1")


# ---------- parse_gps_coord: legacy 'lat,lng' string ----------


def test_parse_string_format():
    lat, lng = parse_gps_coord("59.123,10.456", store_id="1")
    assert lat == pytest.approx(59.123)
    assert lng == pytest.approx(10.456)


def test_parse_whitespace_tolerated():
    lat, lng = parse_gps_coord("59.123, 10.456", store_id="1")
    assert lat == pytest.approx(59.123)
    assert lng == pytest.approx(10.456)


def test_parse_missing_field_hard_fails():
    with pytest.raises(ValueError, match="missing"):
        parse_gps_coord(None, store_id="1")


def test_parse_empty_string_hard_fails():
    with pytest.raises(ValueError, match="empty"):
        parse_gps_coord("", store_id="1")


def test_parse_whitespace_only_hard_fails():
    with pytest.raises(ValueError, match="empty"):
        parse_gps_coord("   ", store_id="1")


def test_parse_single_value_hard_fails():
    with pytest.raises(ValueError, match="lat,lng"):
        parse_gps_coord("59.123", store_id="1")


def test_parse_extra_values_hard_fails():
    with pytest.raises(ValueError, match="lat,lng"):
        parse_gps_coord("59.123,10.456,extra", store_id="1")


def test_parse_non_numeric_hard_fails():
    with pytest.raises(ValueError, match="non-numeric"):
        parse_gps_coord("abc,def", store_id="1")


def test_parse_out_of_bounds_south_hard_fails():
    with pytest.raises(ValueError, match="outside Norway"):
        parse_gps_coord("5.0,10.0", store_id="1")


def test_parse_out_of_bounds_east_hard_fails():
    with pytest.raises(ValueError, match="outside Norway"):
        parse_gps_coord("60.0,40.0", store_id="1")


def test_parse_store_id_in_error_message():
    """Error messages must include the store id for debugging."""
    with pytest.raises(ValueError, match="store 283"):
        parse_gps_coord(None, store_id="283")


def test_parse_unsupported_type_hard_fails():
    with pytest.raises(ValueError, match="must be geoPoint dict or"):
        parse_gps_coord(12345, store_id="1")  # type: ignore[arg-type]


# ---------- transform_store integration ----------


def test_transform_store_populates_lat_lng(sample_api_store):
    result = transform_store(sample_api_store, overrides={}, known_municipalities=set())
    assert result["lat"] == pytest.approx(59.1333)
    assert result["lng"] == pytest.approx(10.2167)


def test_transform_store_hard_fails_without_coords(sample_api_store):
    del sample_api_store["geoPoint"]
    with pytest.raises(ValueError, match="missing"):
        transform_store(sample_api_store, overrides={}, known_municipalities=set())


def test_transform_store_hard_fails_on_bad_coords(sample_api_store):
    sample_api_store["geoPoint"] = {"latitude": "bad", "longitude": "data"}
    with pytest.raises(ValueError, match="non-numeric"):
        transform_store(sample_api_store, overrides={}, known_municipalities=set())


# ---------- validator: store fields ----------


def _make_store(**overrides):
    store = {
        "store_id": "1",
        "name": "Test Store",
        "municipality": "oslo",
        "address": "Kirkegata 1, 0153 Oslo",
        "lat": 59.91,
        "lng": 10.75,
        "standard_hours": {},
        "actual_hours": {},
    }
    store.update(overrides)
    return store


def test_validator_accepts_good_store():
    errors = _validate_store_fields([_make_store()])
    # Filter out coord-specific errors; there should be none.
    coord_errors = [e for e in errors if "lat" in e or "lng" in e]
    assert coord_errors == []


def test_validator_rejects_missing_lat():
    s = _make_store()
    del s["lat"]
    errors = _validate_store_fields([s])
    assert any("missing field 'lat'" in e for e in errors)


def test_validator_rejects_missing_lng():
    s = _make_store()
    del s["lng"]
    errors = _validate_store_fields([s])
    assert any("missing field 'lng'" in e for e in errors)


def test_validator_rejects_lat_none():
    # None passes the isinstance((int, float)) check? No — None is not int/float.
    errors = _validate_store_fields([_make_store(lat=None)])
    assert any("lat must be numeric" in e for e in errors)


def test_validator_rejects_lat_string():
    errors = _validate_store_fields([_make_store(lat="59.91")])
    assert any("lat must be numeric" in e for e in errors)


def test_validator_rejects_lat_bool():
    """Booleans are a subtype of int in Python — must be explicitly rejected."""
    errors = _validate_store_fields([_make_store(lat=True)])
    assert any("lat must be numeric" in e for e in errors)


def test_validator_rejects_lat_zero_out_of_bounds():
    errors = _validate_store_fields([_make_store(lat=0)])
    assert any("lat 0 outside Norway bounds" in e for e in errors)


def test_validator_rejects_lng_zero_out_of_bounds():
    errors = _validate_store_fields([_make_store(lng=0)])
    assert any("lng 0 outside Norway bounds" in e for e in errors)


def test_validator_rejects_lat_nan():
    errors = _validate_store_fields([_make_store(lat=float("nan"))])
    assert any("lat is non-finite" in e for e in errors)


def test_validator_rejects_lat_inf():
    errors = _validate_store_fields([_make_store(lat=float("inf"))])
    assert any("lat is non-finite" in e for e in errors)


def test_validator_rejects_far_outside_norway():
    """lat=90 is valid on Earth but outside Norway."""
    errors = _validate_store_fields([_make_store(lat=90, lng=180)])
    assert any("outside Norway bounds" in e for e in errors)


def test_validator_accepts_lower_boundary():
    errors = _validate_store_fields([_make_store(lat=57.0, lng=4.0)])
    coord_errors = [e for e in errors if "outside" in e or "non-finite" in e]
    assert coord_errors == []


def test_validator_accepts_upper_boundary():
    errors = _validate_store_fields([_make_store(lat=72.0, lng=32.0)])
    coord_errors = [e for e in errors if "outside" in e or "non-finite" in e]
    assert coord_errors == []


def test_validator_lists_lat_lng_in_required():
    from validate_data import REQUIRED_STORE_FIELDS

    assert "lat" in REQUIRED_STORE_FIELDS
    assert "lng" in REQUIRED_STORE_FIELDS


# Sanity: the existing conftest fixture produces a store whose gpsCoord parses
# and passes the validator end-to-end.
def test_end_to_end_fixture_passes(sample_api_store):
    transformed = transform_store(
        sample_api_store, overrides={}, known_municipalities={"sandefjord"}
    )
    errors = _validate_store_fields([transformed])
    coord_errors = [e for e in errors if "lat" in e or "lng" in e]
    assert coord_errors == []
    assert not math.isnan(transformed["lat"])
