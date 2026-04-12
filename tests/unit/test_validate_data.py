"""Tests for data validation."""

import json
from copy import deepcopy
from datetime import date

from build_calendar import build_calendar
from build_municipality import build_municipality
from validate_data import (
    _validate_actual_hours,
    _validate_calendar_file,
    _validate_date_coverage,
    _validate_day_summary,
    _validate_generated_files,
    _validate_municipality_coverage,
    _validate_municipality_files,
    _validate_standard_hours,
    _validate_store_entries,
    _validate_store_fields,
    _validate_vinmonopolet_file,
    _validate_vinmonopolet_summaries,
    _validate_vm_metadata,
    _validate_window_dates,
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
        errors = validate_generated_municipality(result, result["days"], cal)
        assert errors == []

    def test_missing_day_fails(self, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        result = build_municipality(sample_municipality_sandefjord, cal)
        del result["days"][100]  # Remove a day
        errors = validate_generated_municipality(result, result["days"], cal)
        assert len(errors) > 0

    def test_invalid_vinmonopolet_summary_type_fails(self, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        result = build_municipality(sample_municipality_sandefjord, cal)
        result["days"][0]["vinmonopolet_summary"] = {"type": "invalid"}
        errors = validate_generated_municipality(result, result["days"], cal)
        assert any("invalid type" in e for e in errors)

    def test_string_vinmonopolet_summary_fails(self, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        result = build_municipality(sample_municipality_sandefjord, cal)
        result["days"][0]["vinmonopolet_summary"] = "10:00-18:00"
        errors = validate_generated_municipality(result, result["days"], cal)
        assert any("must be dict or null" in e for e in errors)

    def test_missing_vinmonopolet_day_summary_fails(self, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        result = build_municipality(sample_municipality_sandefjord, cal)
        del result["vinmonopolet_day_summary"]
        errors = validate_generated_municipality(result, result["days"], cal)
        assert any("Missing vinmonopolet_day_summary" in e for e in errors)

    def test_invalid_vinmonopolet_day_summary_type_fails(self, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        result = build_municipality(sample_municipality_sandefjord, cal)
        result["vinmonopolet_day_summary"] = [{"type": "bogus", "date": "2026-01-01"}]
        errors = validate_generated_municipality(result, result["days"], cal)
        assert any("invalid type" in e for e in errors)

    def test_valid_fetched_at_with_stores_passes(self, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=14)
        result = build_municipality(
            sample_municipality_sandefjord,
            cal,
            vinmonopolet_stores=[
                {
                    "store_id": "1",
                    "name": "Test",
                    "municipality": "sandefjord",
                    "address": "Addr",
                    "standard_hours": {},
                    "actual_hours": {},
                }
            ],
            vinmonopolet_fetched_at="2026-04-12T10:00:00+02:00",
        )
        errors = validate_generated_municipality(result, result["days"], cal)
        # May have other errors from minimal store fixture, but not about fetched_at
        assert not any("vinmonopolet_fetched_at" in e for e in errors)

    def test_missing_fetched_at_with_empty_stores_passes(self, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=14)
        result = build_municipality(sample_municipality_sandefjord, cal)
        # No stores, so fetched_at is not required
        errors = validate_generated_municipality(result, result["days"], cal)
        assert not any("vinmonopolet_fetched_at" in e for e in errors)

    def test_missing_fetched_at_with_stores_fails(self, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=14)
        result = build_municipality(
            sample_municipality_sandefjord,
            cal,
            vinmonopolet_stores=[
                {
                    "store_id": "1",
                    "name": "Test",
                    "municipality": "sandefjord",
                    "address": "Addr",
                    "standard_hours": {},
                    "actual_hours": {},
                }
            ],
            vinmonopolet_fetched_at=None,
        )
        errors = validate_generated_municipality(result, result["days"], cal)
        assert any("vinmonopolet_fetched_at" in e for e in errors)

    def test_invalid_fetched_at_format_fails(self, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=14)
        result = build_municipality(
            sample_municipality_sandefjord,
            cal,
            vinmonopolet_stores=[
                {
                    "store_id": "1",
                    "name": "Test",
                    "municipality": "sandefjord",
                    "address": "Addr",
                    "standard_hours": {},
                    "actual_hours": {},
                }
            ],
            vinmonopolet_fetched_at="not-a-timestamp",
        )
        errors = validate_generated_municipality(result, result["days"], cal)
        assert any("vinmonopolet_fetched_at" in e for e in errors)


# --- Generated municipality helper tests ---


class TestValidateDateCoverage:
    """Unit tests for _validate_date_coverage helper."""

    def test_matching_dates_pass(self):
        cal = [{"date": "2026-01-01"}, {"date": "2026-01-02"}]
        days = [{"date": "2026-01-01"}, {"date": "2026-01-02"}]
        assert _validate_date_coverage(days, cal) == []

    def test_missing_date_fails(self):
        cal = [{"date": "2026-01-01"}, {"date": "2026-01-02"}]
        days = [{"date": "2026-01-01"}]
        errors = _validate_date_coverage(days, cal)
        assert any("Missing" in e for e in errors)

    def test_extra_date_fails(self):
        cal = [{"date": "2026-01-01"}]
        days = [{"date": "2026-01-01"}, {"date": "2026-01-02"}]
        errors = _validate_date_coverage(days, cal)
        assert any("Extra" in e for e in errors)


class TestValidateVinmonopoletSummaries:
    """Unit tests for _validate_vinmonopolet_summaries helper."""

    def test_valid_summaries_pass(self):
        days = [{"date": "2026-01-01", "vinmonopolet_summary": {"type": "uniform"}}]
        assert _validate_vinmonopolet_summaries(days) == []

    def test_null_summary_passes(self):
        days = [{"date": "2026-01-01", "vinmonopolet_summary": None}]
        assert _validate_vinmonopolet_summaries(days) == []

    def test_missing_summary_fails(self):
        days = [{"date": "2026-01-01"}]
        errors = _validate_vinmonopolet_summaries(days)
        assert any("missing vinmonopolet_summary" in e for e in errors)

    def test_string_summary_fails(self):
        days = [{"date": "2026-01-01", "vinmonopolet_summary": "bad"}]
        errors = _validate_vinmonopolet_summaries(days)
        assert any("must be dict or null" in e for e in errors)

    def test_breaks_after_first_error(self):
        """Only reports one error even with multiple bad days."""
        days = [
            {"date": "2026-01-01", "vinmonopolet_summary": "bad"},
            {"date": "2026-01-02", "vinmonopolet_summary": "bad"},
        ]
        errors = _validate_vinmonopolet_summaries(days)
        assert len(errors) == 1


class TestValidateDaySummary:
    """Unit tests for _validate_day_summary helper."""

    def test_valid_day_summary_passes(self):
        gen_data = {
            "vinmonopolet_day_summary": [{"type": "uniform"}],
            "vinmonopolet_stores": [{"store_id": "1"}],
        }
        assert _validate_day_summary(gen_data, num_days=1) == []

    def test_missing_day_summary_fails(self):
        errors = _validate_day_summary({}, num_days=14)
        assert any("Missing vinmonopolet_day_summary" in e for e in errors)

    def test_wrong_length_fails(self):
        gen_data = {
            "vinmonopolet_day_summary": [None, None],
            "vinmonopolet_stores": [{"store_id": "1"}],
        }
        errors = _validate_day_summary(gen_data, num_days=14)
        assert any("expected" in e for e in errors)

    def test_breaks_after_first_invalid_type(self):
        gen_data = {
            "vinmonopolet_day_summary": [{"type": "bogus"}, {"type": "bogus"}],
            "vinmonopolet_stores": [],
        }
        errors = _validate_day_summary(gen_data, num_days=14)
        assert sum("invalid type" in e for e in errors) == 1


class TestValidateStoreEntries:
    """Unit tests for _validate_store_entries helper."""

    def test_valid_store_passes(self):
        gen_data = {
            "vinmonopolet_stores": [
                {"store_id": "1", "name": "X", "address": "Y", "hours": [{"date": "2026-01-01"}]}
            ],
        }
        days = [{"date": "2026-01-01"}]
        assert _validate_store_entries(gen_data, days) == []

    def test_missing_stores_key_fails(self):
        errors = _validate_store_entries({}, [{"date": "2026-01-01"}])
        assert any("Missing vinmonopolet_stores" in e for e in errors)

    def test_missing_field_fails(self):
        gen_data = {
            "vinmonopolet_stores": [{"store_id": "1", "name": "X", "address": "Y"}],
        }
        errors = _validate_store_entries(gen_data, [{"date": "2026-01-01"}])
        assert any("missing" in e for e in errors)


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


# --- Vinmonopolet helper tests ---


class TestValidateVmMetadata:
    """Unit tests for _validate_vm_metadata helper."""

    def test_valid_metadata_passes(self):
        meta = {
            "fetched_at": "2026-01-01",
            "window_start": "2026-01-01",
            "window_end": "2026-01-07",
            "total_stores": 1,
        }
        assert _validate_vm_metadata(meta, num_stores=1) == []

    def test_missing_fetched_at_fails(self):
        meta = {"window_start": "x", "window_end": "x", "total_stores": 0}
        errors = _validate_vm_metadata(meta, num_stores=0)
        assert any("fetched_at" in e for e in errors)

    def test_count_mismatch_fails(self):
        meta = {"fetched_at": "x", "window_start": "x", "window_end": "x", "total_stores": 99}
        errors = _validate_vm_metadata(meta, num_stores=1)
        assert any("total_stores" in e for e in errors)


class TestValidateStoreFields:
    """Unit tests for _validate_store_fields helper."""

    def test_valid_store_passes(self):
        assert _validate_store_fields([_valid_store()]) == []

    def test_missing_field_fails(self):
        store = _valid_store()
        del store["name"]
        errors = _validate_store_fields([store])
        assert any("missing field 'name'" in e for e in errors)

    def test_non_numeric_id_fails(self):
        store = _valid_store()
        store["store_id"] = "abc"
        errors = _validate_store_fields([store])
        assert any("numeric" in e for e in errors)

    def test_duplicate_id_fails(self):
        errors = _validate_store_fields([_valid_store("1"), _valid_store("1")])
        assert any("Duplicate" in e for e in errors)


class TestValidateStandardHours:
    """Unit tests for _validate_standard_hours helper."""

    def test_valid_hours_pass(self):
        assert _validate_standard_hours(_valid_store()) == []

    def test_missing_weekday_fails(self):
        store = _valid_store()
        del store["standard_hours"]["monday"]
        errors = _validate_standard_hours(store)
        assert any("missing standard_hours.monday" in e for e in errors)

    def test_sunday_not_null_fails(self):
        store = _valid_store()
        store["standard_hours"]["sunday"] = {"open": "10:00", "close": "15:00"}
        errors = _validate_standard_hours(store)
        assert any("sunday must be null" in e for e in errors)

    def test_invalid_time_format_fails(self):
        store = _valid_store()
        store["standard_hours"]["monday"] = {"open": "bad", "close": "18:00"}
        errors = _validate_standard_hours(store)
        assert any("invalid time" in e for e in errors)


class TestValidateActualHours:
    """Unit tests for _validate_actual_hours helper."""

    def test_valid_hours_pass(self):
        assert _validate_actual_hours(_valid_store()) == []

    def test_wrong_count_fails(self):
        store = _valid_store()
        store["actual_hours"] = {"2026-03-30": None}
        errors = _validate_actual_hours(store)
        assert any("exactly 7" in e for e in errors)

    def test_invalid_date_key_fails(self):
        store = _valid_store()
        store["actual_hours"]["not-a-date"] = None
        errors = _validate_actual_hours(store)
        assert any("invalid date key" in e for e in errors)

    def test_invalid_time_format_fails(self):
        store = _valid_store()
        store["actual_hours"]["2026-03-30"] = {"open": "bad", "close": "18:00"}
        errors = _validate_actual_hours(store)
        assert any("invalid time" in e for e in errors)


class TestValidateWindowDates:
    """Unit tests for _validate_window_dates helper."""

    def test_matching_window_passes(self):
        store = _valid_store()
        meta = {"window_start": "2026-03-30", "window_end": "2026-04-05"}
        assert _validate_window_dates(store, meta) == []

    def test_mismatched_start_fails(self):
        store = _valid_store()
        meta = {"window_start": "2026-01-01", "window_end": "2026-04-05"}
        errors = _validate_window_dates(store, meta)
        assert any("window_start" in e for e in errors)

    def test_skips_when_not_7_entries(self):
        store = _valid_store()
        store["actual_hours"] = {"2026-03-30": None}
        meta = {"window_start": "2026-01-01", "window_end": "2026-01-07"}
        assert _validate_window_dates(store, meta) == []


class TestValidateMunicipalityCoverage:
    """Unit tests for _validate_municipality_coverage helper."""

    def test_all_covered_returns_empty(self, tmp_path):
        muni_dir = tmp_path / "municipalities"
        muni_dir.mkdir()
        (muni_dir / "sandefjord.json").write_text("{}")
        stores = [_valid_store()]
        info, unmapped = _validate_municipality_coverage(stores, muni_dir)
        assert info == []
        assert unmapped == []

    def test_missing_municipality_returns_info(self, tmp_path):
        muni_dir = tmp_path / "municipalities"
        muni_dir.mkdir()
        (muni_dir / "sandefjord.json").write_text("{}")
        (muni_dir / "oslo.json").write_text("{}")
        stores = [_valid_store()]
        info, _ = _validate_municipality_coverage(stores, muni_dir)
        assert any("oslo" in i for i in info)

    def test_unmapped_stores_returns_info(self, tmp_path):
        store = _valid_store()
        store["municipality"] = None
        _, unmapped = _validate_municipality_coverage([store], tmp_path)
        assert any("municipality=null" in u for u in unmapped)


# --- main() helper tests ---


class TestValidateMunicipalityFiles:
    """Unit tests for _validate_municipality_files helper."""

    def test_valid_file_passes(self, tmp_path, sample_municipality_sandefjord):
        (tmp_path / "sandefjord.json").write_text(json.dumps(sample_municipality_sandefjord))
        assert _validate_municipality_files(tmp_path) == []

    def test_invalid_file_returns_errors(self, tmp_path):
        (tmp_path / "bad.json").write_text('{"id": "bad"}')
        errors = _validate_municipality_files(tmp_path)
        assert len(errors) > 0
        assert any("bad.json" in e for e in errors)


class TestValidateCalendarFile:
    """Unit tests for _validate_calendar_file helper."""

    def test_valid_calendar_passes(self, tmp_path):
        cal = build_calendar(date(2026, 1, 1), num_days=10)
        cal_path = tmp_path / "calendar.json"
        cal_path.write_text(json.dumps(cal))
        errors, calendar = _validate_calendar_file(cal_path)
        assert errors == []
        assert calendar is not None

    def test_missing_file_returns_none(self, tmp_path):
        errors, calendar = _validate_calendar_file(tmp_path / "missing.json")
        assert errors == []
        assert calendar is None


class TestValidateGeneratedFiles:
    """Unit tests for _validate_generated_files helper."""

    def test_valid_generated_passes(self, tmp_path, sample_municipality_sandefjord):
        cal = build_calendar(date(2026, 1, 1), num_days=365)
        result = build_municipality(sample_municipality_sandefjord, cal)
        (tmp_path / "sandefjord.json").write_text(json.dumps(result))
        errors = _validate_generated_files(tmp_path, cal)
        assert errors == []


class TestValidateVinmonopoletFile:
    """Unit tests for _validate_vinmonopolet_file helper."""

    def test_valid_file_passes(self, tmp_path):
        data = _valid_vinmonopolet_data()
        vm_path = tmp_path / "vinmonopolet.json"
        vm_path.write_text(json.dumps(data))
        errors, info = _validate_vinmonopolet_file(vm_path, tmp_path)
        assert errors == []

    def test_missing_file_returns_empty(self, tmp_path):
        errors, info = _validate_vinmonopolet_file(tmp_path / "missing.json", tmp_path)
        assert errors == []
        assert info == []
