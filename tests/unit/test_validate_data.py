"""Tests for data validation."""

from copy import deepcopy
from datetime import date

from build_calendar import build_calendar
from build_municipality import build_municipality
from validate_data import (
    validate_calendar,
    validate_generated_municipality,
    validate_municipality_schema,
    validate_national_max_compliance,
    validate_vinmonopolet,
)

# --- Municipality schema validation ---


class TestValidateMunicipalitySchema:
    """Verify schema validation for municipality JSON files."""

    def test_valid_municipality_passes(self, sample_municipality_sandefjord):
        errors = validate_municipality_schema(sample_municipality_sandefjord)
        assert errors == []

    def test_all_municipalities_pass(self, all_municipalities):
        for m in all_municipalities:
            errors = validate_municipality_schema(m)
            assert errors == [], f"{m['id']}: {errors}"

    def test_missing_id_fails(self, sample_municipality_sandefjord):
        data = deepcopy(sample_municipality_sandefjord)
        del data["id"]
        errors = validate_municipality_schema(data)
        assert any("id" in e for e in errors)

    def test_missing_beer_sales_field_fails(self, sample_municipality_sandefjord):
        data = deepcopy(sample_municipality_sandefjord)
        del data["beer_sales"]["weekday_close"]
        errors = validate_municipality_schema(data)
        assert any("weekday_close" in e for e in errors)

    def test_missing_sources_fails(self, sample_municipality_sandefjord):
        data = deepcopy(sample_municipality_sandefjord)
        data["sources"] = []
        errors = validate_municipality_schema(data)
        assert any("source" in e.lower() for e in errors)


# --- Calendar validation ---


class TestValidateCalendar:
    """Verify calendar data validation."""

    def test_valid_calendar_passes(self):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        errors = validate_calendar(cal)
        assert errors == []

    def test_empty_calendar_fails(self):
        errors = validate_calendar([])
        assert len(errors) > 0

    def test_calendar_with_gap_fails(self):
        cal = build_calendar(date(2026, 1, 1), num_days=10)
        # Remove day 5 to create a gap
        del cal[4]
        errors = validate_calendar(cal)
        assert any("gap" in e.lower() for e in errors)

    def test_calendar_with_duplicate_fails(self):
        cal = build_calendar(date(2026, 1, 1), num_days=10)
        cal.append(cal[0])  # Duplicate first day
        errors = validate_calendar(cal)
        assert any("duplicate" in e.lower() for e in errors)


# --- Generated municipality validation ---


class TestValidateGeneratedMunicipality:
    """Verify generated municipality data validation."""

    def test_valid_generated_passes(self, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        result = build_municipality(sample_municipality_sandefjord, cal)
        errors = validate_generated_municipality(result["days"], cal)
        assert errors == []

    def test_missing_day_fails(self, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        result = build_municipality(sample_municipality_sandefjord, cal)
        del result["days"][100]  # Remove a day
        errors = validate_generated_municipality(result["days"], cal)
        assert len(errors) > 0


# --- National max compliance ---


class TestValidateNationalMaxCompliance:
    """Verify sales times don't exceed national maximums."""

    def test_valid_data_passes(self, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        result = build_municipality(sample_municipality_sandefjord, cal)
        errors = validate_national_max_compliance(result["days"])
        assert errors == []

    def test_exceeding_weekday_max_fails(self):
        fake_day = {
            "date": "2026-03-10",
            "day_type": "weekday",
            "beer_sale_allowed": True,
            "beer_close": "21:00",  # Exceeds 20:00 national max
        }
        errors = validate_national_max_compliance([fake_day])
        assert len(errors) > 0

    def test_exceeding_saturday_max_fails(self):
        fake_day = {
            "date": "2026-03-07",
            "day_type": "saturday",
            "beer_sale_allowed": True,
            "beer_close": "19:00",  # Exceeds 18:00 national max
        }
        errors = validate_national_max_compliance([fake_day])
        assert len(errors) > 0


# --- Vinmonopolet validation ---


def _valid_store(store_id: str = "283") -> dict:
    """Build a minimal valid store for testing."""
    return {
        "store_id": store_id,
        "name": "Test",
        "municipality": "sandefjord",
        "address": "Test 1, 0000 Test",
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
            "2026-03-30": {"open": "10:00", "close": "18:00"},
            "2026-03-31": {"open": "10:00", "close": "18:00"},
            "2026-04-01": {"open": "10:00", "close": "18:00"},
            "2026-04-02": {"open": "10:00", "close": "18:00"},
            "2026-04-03": {"open": "10:00", "close": "18:00"},
            "2026-04-04": {"open": "10:00", "close": "15:00"},
            "2026-04-05": None,
        },
    }


def _valid_vinmonopolet_data(**overrides) -> dict:
    """Build valid top-level vinmonopolet data."""
    stores = overrides.pop("stores", [_valid_store()])
    return {
        "metadata": {
            "total_stores": len(stores),
            "fetched_at": "2026-03-31T16:00:00+02:00",
            "window_start": "2026-03-30",
            "window_end": "2026-04-05",
            **overrides,
        },
        "stores": stores,
    }


class TestValidateVinmonopolet:
    """Verify vinmonopolet.json validation."""

    def test_valid_data_passes(self):
        errors, _ = validate_vinmonopolet(_valid_vinmonopolet_data())
        assert errors == []

    def test_empty_stores_fails(self):
        data = _valid_vinmonopolet_data(stores=[], total_stores=0)
        errors, _ = validate_vinmonopolet(data)
        assert any("No stores" in e for e in errors)

    def test_missing_metadata_fails(self):
        errors, _ = validate_vinmonopolet({"stores": []})
        assert any("Missing metadata" in e for e in errors)

    def test_missing_store_field_fails(self):
        store = _valid_store()
        del store["name"]
        data = _valid_vinmonopolet_data(stores=[store])
        errors, _ = validate_vinmonopolet(data)
        assert any("missing field 'name'" in e for e in errors)

    def test_duplicate_store_id_fails(self):
        data = _valid_vinmonopolet_data(
            stores=[_valid_store("100"), _valid_store("100")],
            total_stores=2,
        )
        errors, _ = validate_vinmonopolet(data)
        assert any("Duplicate store_id" in e for e in errors)

    def test_non_numeric_store_id_fails(self):
        store = _valid_store()
        store["store_id"] = "abc"
        data = _valid_vinmonopolet_data(stores=[store])
        errors, _ = validate_vinmonopolet(data)
        assert any("numeric" in e for e in errors)

    def test_metadata_count_mismatch_fails(self):
        data = _valid_vinmonopolet_data(total_stores=99)
        errors, _ = validate_vinmonopolet(data)
        assert any("total_stores" in e for e in errors)

    def test_sunday_not_null_fails(self):
        store = _valid_store()
        store["standard_hours"]["sunday"] = {"open": "10:00", "close": "15:00"}
        data = _valid_vinmonopolet_data(stores=[store])
        errors, _ = validate_vinmonopolet(data)
        assert any("sunday must be null" in e for e in errors)

    def test_actual_hours_wrong_count_fails(self):
        store = _valid_store()
        store["actual_hours"] = {"2026-03-30": None}
        data = _valid_vinmonopolet_data(stores=[store])
        errors, _ = validate_vinmonopolet(data)
        assert any("exactly 7" in e for e in errors)

    def test_actual_hours_window_mismatch_fails(self):
        store = _valid_store()
        data = _valid_vinmonopolet_data(
            stores=[store], window_start="2026-01-01", window_end="2026-01-07"
        )
        errors, _ = validate_vinmonopolet(data)
        assert any("window_start" in e for e in errors)

    def test_municipality_coverage_is_info_not_error(self, tmp_path):
        """Municipalities with no stores produce info, not errors."""
        muni_dir = tmp_path / "municipalities"
        muni_dir.mkdir()
        (muni_dir / "sandefjord.json").write_text("{}")
        (muni_dir / "oslo.json").write_text("{}")
        data = _valid_vinmonopolet_data()  # Only has sandefjord
        errors, info = validate_vinmonopolet(data, municipalities_dir=muni_dir)
        assert not any("oslo" in e for e in errors)
        assert any("oslo" in i for i in info)
