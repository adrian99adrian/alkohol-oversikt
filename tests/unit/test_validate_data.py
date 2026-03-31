"""Tests for data validation."""

import sys
from copy import deepcopy
from datetime import date

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent.parent / "scripts"))

from build_calendar import build_calendar
from build_municipality import build_municipality
from validate_data import (
    validate_calendar,
    validate_generated_municipality,
    validate_municipality_schema,
    validate_national_max_compliance,
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
