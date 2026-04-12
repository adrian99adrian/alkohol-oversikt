"""Integration tests: run the full pipeline and verify output."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from build_calendar import build_calendar
from build_municipality import build_municipality, main
from validate_data import (
    validate_calendar,
    validate_generated_municipality,
    validate_national_max_compliance,
)


def _run_pipeline(
    municipality: dict,
    start: date,
    days: int = 365,
    vinmonopolet_stores: list[dict] | None = None,
    vinmonopolet_fetched_at: str | None = None,
) -> tuple[dict, list[dict]]:
    """Run the full pipeline for a municipality."""
    calendar = build_calendar(start, num_days=days)
    # Default a valid timestamp when stores are provided so validation passes
    if vinmonopolet_stores and vinmonopolet_fetched_at is None:
        vinmonopolet_fetched_at = "2026-04-01T10:00:00+02:00"
    result = build_municipality(
        municipality,
        calendar,
        vinmonopolet_stores=vinmonopolet_stores,
        vinmonopolet_fetched_at=vinmonopolet_fetched_at,
    )
    return result, calendar


class TestFullPipeline:
    """Full pipeline: municipality JSON → calendar → generated output."""

    def test_sandefjord_generates_valid_data(self, sample_municipality_sandefjord):
        result, calendar = _run_pipeline(sample_municipality_sandefjord, date(2026, 1, 1))
        assert validate_calendar(calendar) == []
        assert validate_generated_municipality(result, result["days"], calendar) == []
        assert validate_national_max_compliance(result["days"]) == []

    def test_larvik_generates_valid_data(self, sample_municipality_larvik):
        result, calendar = _run_pipeline(sample_municipality_larvik, date(2026, 1, 1))
        assert validate_calendar(calendar) == []
        assert validate_generated_municipality(result, result["days"], calendar) == []
        assert validate_national_max_compliance(result["days"]) == []

    def test_oslo_generates_valid_data(self, sample_municipality_oslo):
        result, calendar = _run_pipeline(sample_municipality_oslo, date(2026, 1, 1))
        assert validate_calendar(calendar) == []
        assert validate_generated_municipality(result, result["days"], calendar) == []
        assert validate_national_max_compliance(result["days"]) == []

    def test_bergen_generates_valid_data(self, sample_municipality_bergen):
        result, calendar = _run_pipeline(sample_municipality_bergen, date(2026, 1, 1))
        assert validate_calendar(calendar) == []
        assert validate_generated_municipality(result, result["days"], calendar) == []
        assert validate_national_max_compliance(result["days"]) == []

    def test_stavanger_generates_valid_data(self, sample_municipality_stavanger):
        result, calendar = _run_pipeline(sample_municipality_stavanger, date(2026, 1, 1))
        assert validate_calendar(calendar) == []
        assert validate_generated_municipality(result, result["days"], calendar) == []
        assert validate_national_max_compliance(result["days"]) == []


class TestTrondheimPipeline:
    """Full pipeline validation for Trondheim."""

    def test_trondheim_generates_valid_data(self, sample_municipality_trondheim):
        result, calendar = _run_pipeline(sample_municipality_trondheim, date(2026, 1, 1))
        assert validate_calendar(calendar) == []
        assert validate_generated_municipality(result, result["days"], calendar) == []
        assert validate_national_max_compliance(result["days"]) == []


class TestTrondheimEaster:
    """Verify Easter 2026 produces correct results for Trondheim."""

    def test_easter_sequence(self, sample_municipality_trondheim):
        result, _ = _run_pipeline(sample_municipality_trondheim, date(2026, 4, 1), days=7)
        by_date = {d["date"]: d for d in result["days"]}

        # Apr 1 — pre_holiday (day before Skjærtorsdag)
        assert by_date["2026-04-01"]["day_type"] == "pre_holiday"
        assert by_date["2026-04-01"]["beer_close"] == "18:00"

        # Apr 2 — Skjærtorsdag (public holiday)
        assert not by_date["2026-04-02"]["beer_sale_allowed"]

        # Apr 3 — Langfredag (public holiday)
        assert not by_date["2026-04-03"]["beer_sale_allowed"]

        # Apr 4 — Påskeaften (special_day for Trondheim: 15:00)
        assert by_date["2026-04-04"]["day_type"] == "special_day"
        assert by_date["2026-04-04"]["beer_close"] == "15:00"

        # Apr 5 — 1. påskedag (public holiday)
        assert not by_date["2026-04-05"]["beer_sale_allowed"]

        # Apr 6 — 2. påskedag (public holiday)
        assert not by_date["2026-04-06"]["beer_sale_allowed"]

        # Apr 7 — regular Tuesday
        assert by_date["2026-04-07"]["day_type"] == "weekday"
        assert by_date["2026-04-07"]["beer_close"] == "20:00"


class TestTrondheimSpecialDays:
    """Verify Trondheim-specific special day behavior."""

    def test_new_years_eve_not_special(self, sample_municipality_trondheim):
        """Nyttårsaften is NOT a special day in Trondheim — pre_holiday 18:00."""
        result, _ = _run_pipeline(sample_municipality_trondheim, date(2026, 12, 31), days=1)
        day = result["days"][0]
        assert day["beer_close"] == "18:00"

    def test_pre_ascension_uses_weekday(self, sample_municipality_trondheim):
        """Day before Kristi himmelfartsdag keeps weekday hours: 20:00."""
        result, _ = _run_pipeline(sample_municipality_trondheim, date(2026, 5, 13), days=1)
        day = result["days"][0]
        assert day["day_type"] == "pre_holiday"
        assert day["beer_close"] == "20:00"

    def test_whit_eve_is_special(self, sample_municipality_trondheim):
        """Pinseaften is special in Trondheim — close at 15:00."""
        result, _ = _run_pipeline(sample_municipality_trondheim, date(2026, 5, 23), days=1)
        day = result["days"][0]
        assert day["day_type"] == "special_day"
        assert day["beer_close"] == "15:00"


class TestEaster2026:
    """Verify Easter 2026 produces correct results for Sandefjord."""

    def test_easter_sequence(self, sample_municipality_sandefjord):
        result, _ = _run_pipeline(sample_municipality_sandefjord, date(2026, 4, 1), days=7)
        by_date = {d["date"]: d for d in result["days"]}

        # Apr 1 — pre_holiday (day before Skjærtorsdag)
        assert by_date["2026-04-01"]["day_type"] == "pre_holiday"
        assert by_date["2026-04-01"]["beer_sale_allowed"]
        assert by_date["2026-04-01"]["beer_close"] == "18:00"

        # Apr 2 — Skjærtorsdag (public holiday)
        assert by_date["2026-04-02"]["day_type"] == "public_holiday"
        assert not by_date["2026-04-02"]["beer_sale_allowed"]

        # Apr 3 — Langfredag (public holiday)
        assert not by_date["2026-04-03"]["beer_sale_allowed"]

        # Apr 4 — Påskeaften (special_day for Sandefjord: 15:00)
        assert by_date["2026-04-04"]["day_type"] == "special_day"
        assert by_date["2026-04-04"]["beer_sale_allowed"]
        assert by_date["2026-04-04"]["beer_close"] == "15:00"

        # Apr 5 — 1. påskedag (public holiday)
        assert not by_date["2026-04-05"]["beer_sale_allowed"]

        # Apr 6 — 2. påskedag (public holiday)
        assert not by_date["2026-04-06"]["beer_sale_allowed"]

        # Apr 7 — regular Tuesday
        assert by_date["2026-04-07"]["day_type"] == "weekday"
        assert by_date["2026-04-07"]["beer_close"] == "20:00"


class TestChristmas2026:
    """Verify Christmas 2026."""

    def test_christmas_sequence(self, sample_municipality_sandefjord):
        result, _ = _run_pipeline(sample_municipality_sandefjord, date(2026, 12, 24), days=3)
        by_date = {d["date"]: d for d in result["days"]}

        # Dec 24 — Julaften (special_day, 15:00 for Sandefjord)
        assert by_date["2026-12-24"]["day_type"] == "special_day"
        assert by_date["2026-12-24"]["beer_close"] == "15:00"

        # Dec 25 — 1. juledag (public holiday)
        assert not by_date["2026-12-25"]["beer_sale_allowed"]

        # Dec 26 — 2. juledag (public holiday)
        assert not by_date["2026-12-26"]["beer_sale_allowed"]


class TestMay2026:
    """Verify May 1 and May 17, 2026."""

    def test_may_1(self, sample_municipality_sandefjord):
        result, _ = _run_pipeline(sample_municipality_sandefjord, date(2026, 4, 30), days=2)
        by_date = {d["date"]: d for d in result["days"]}

        # Apr 30 — pre_holiday (before May 1)
        assert by_date["2026-04-30"]["day_type"] == "pre_holiday"
        assert by_date["2026-04-30"]["beer_sale_allowed"]

        # May 1 — public holiday (1. mai), forbidden
        assert not by_date["2026-05-01"]["beer_sale_allowed"]

    def test_may_17(self, sample_municipality_sandefjord):
        """May 17, 2026 is a Sunday — both sunday and Constitution Day."""
        result, _ = _run_pipeline(sample_municipality_sandefjord, date(2026, 5, 16), days=2)
        by_date = {d["date"]: d for d in result["days"]}

        # May 16 — Saturday (is_pre_holiday=True, but day_type stays "saturday")
        assert by_date["2026-05-16"]["day_type"] == "saturday"
        assert by_date["2026-05-16"]["beer_sale_allowed"]

        # May 17 — public_holiday (Constitution Day beats Sunday)
        assert by_date["2026-05-17"]["day_type"] == "public_holiday"
        assert not by_date["2026-05-17"]["beer_sale_allowed"]


class TestEasterEvePerMunicipality:
    """easter_eve is special_day for Sandefjord but NOT for Larvik."""

    def test_sandefjord_easter_eve_special(self, sample_municipality_sandefjord):
        result, _ = _run_pipeline(sample_municipality_sandefjord, date(2026, 4, 4), days=1)
        day = result["days"][0]
        assert day["day_type"] == "special_day"
        assert day["beer_close"] == "15:00"

    def test_larvik_easter_eve_not_special(self, sample_municipality_larvik):
        result, _ = _run_pipeline(sample_municipality_larvik, date(2026, 4, 4), days=1)
        day = result["days"][0]
        # Larvik doesn't list easter_eve — uses saturday rules
        assert day["beer_close"] == "18:00"  # min(18:00 national, 18:00 municipal saturday)


class TestOsloLargeStoreIntegration:
    """Verify Oslo large-store rule across special days."""

    def test_christmas_eve_has_large_store(self, sample_municipality_oslo):
        result, _ = _run_pipeline(sample_municipality_oslo, date(2026, 12, 24), days=1)
        day = result["days"][0]
        assert day["beer_close_large_stores"] == "16:00"

    def test_new_years_eve_no_large_store(self, sample_municipality_oslo):
        result, _ = _run_pipeline(sample_municipality_oslo, date(2026, 12, 31), days=1)
        day = result["days"][0]
        assert day["beer_close_large_stores"] is None


class TestVinmonopoletIntegration:
    """Verify Vinmonopolet data flows through build_municipality correctly."""

    SAMPLE_STORE = {
        "store_id": "283",
        "name": "Sandefjord",
        "municipality": "sandefjord",
        "address": "Jernbanealleen 13, 3210 Sandefjord",
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
            "2026-04-01": {"open": "10:00", "close": "16:00"},
            "2026-04-02": None,
            "2026-04-03": None,
            "2026-04-04": {"open": "10:00", "close": "15:00"},
            "2026-04-05": None,
            "2026-04-06": None,
            "2026-04-07": {"open": "10:00", "close": "18:00"},
        },
    }

    def test_vinmonopolet_summary_in_days(self, sample_municipality_sandefjord):
        """Days include vinmonopolet_summary when stores are provided."""
        result, _ = _run_pipeline(
            sample_municipality_sandefjord,
            date(2026, 4, 1),
            days=14,
            vinmonopolet_stores=[self.SAMPLE_STORE],
        )
        day0 = result["days"][0]
        assert day0["vinmonopolet_summary"]["type"] == "uniform"
        assert day0["vinmonopolet_summary"]["open"] == "10:00"
        assert day0["vinmonopolet_summary"]["close"] == "16:00"

        # Holiday should be closed
        day1 = result["days"][1]  # Skjærtorsdag
        assert day1["vinmonopolet_summary"]["type"] == "closed"

    def test_vinmonopolet_summary_null_beyond_14_days(self, sample_municipality_sandefjord):
        """Days beyond 14 have vinmonopolet_summary = null."""
        result, _ = _run_pipeline(
            sample_municipality_sandefjord,
            date(2026, 4, 1),
            days=30,
            vinmonopolet_stores=[self.SAMPLE_STORE],
        )
        assert result["days"][13]["vinmonopolet_summary"] is not None
        assert result["days"][14]["vinmonopolet_summary"] is None

    def test_vinmonopolet_stores_resolved(self, sample_municipality_sandefjord):
        """Output includes resolved vinmonopolet_stores with 14-day hours."""
        result, _ = _run_pipeline(
            sample_municipality_sandefjord,
            date(2026, 4, 1),
            days=14,
            vinmonopolet_stores=[self.SAMPLE_STORE],
        )
        assert len(result["vinmonopolet_stores"]) == 1
        store = result["vinmonopolet_stores"][0]
        assert store["store_id"] == "283"
        assert len(store["hours"]) == 14
        assert store["hours"][0]["close"] == "16:00"

    def test_no_stores_produces_null_summaries(self, sample_municipality_sandefjord):
        """Without stores, all vinmonopolet_summary fields are null."""
        result, _ = _run_pipeline(sample_municipality_sandefjord, date(2026, 4, 1), days=7)
        for day in result["days"]:
            assert day["vinmonopolet_summary"] is None
        assert result["vinmonopolet_stores"] == []

    def test_validation_passes_with_stores(self, sample_municipality_sandefjord):
        """Generated data with stores passes validation."""
        result, calendar = _run_pipeline(
            sample_municipality_sandefjord,
            date(2026, 4, 1),
            days=14,
            vinmonopolet_stores=[self.SAMPLE_STORE],
        )
        assert validate_generated_municipality(result, result["days"], calendar) == []


def _setup_tmp_data_dir(tmp_path: Path) -> None:
    """Mirror the real data/ directory structure inside tmp_path for CLI tests."""
    real_data = Path(__file__).parent.parent.parent / "data"

    # Copy municipality source configs
    muni_dir = tmp_path / "municipalities"
    muni_dir.mkdir()
    for f in (real_data / "municipalities").glob("*.json"):
        (muni_dir / f.name).write_bytes(f.read_bytes())

    # Copy town_municipality_map.json (used by _load_vinmonopolet_stores)
    (tmp_path / "town_municipality_map.json").write_bytes(
        (real_data / "town_municipality_map.json").read_bytes()
    )

    # Minimal stub — stores are optional for municipality generation
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir()
    (gen_dir / "vinmonopolet.json").write_text('{"stores": []}', encoding="utf-8")


class TestMainCLI:
    """Verify CLI entry point and fail-fast behavior."""

    def test_id_not_found_exits_with_error(self):
        """--id with a nonexistent municipality should exit 1."""
        args = ["prog", "--id", "nonexistent", "--start-date", "2026-01-01"]
        with patch("sys.argv", args):
            with pytest.raises(SystemExit, match="1"):
                main()

    def test_id_generates_output(self, tmp_path):
        """--id with a valid municipality should produce a JSON file."""
        _setup_tmp_data_dir(tmp_path)
        args = [
            "prog",
            "--id",
            "sandefjord",
            "--start-date",
            "2026-01-01",
            "--days",
            "3",
            "--data-dir",
            str(tmp_path),
        ]
        with patch("sys.argv", args):
            main()

        output = tmp_path / "generated" / "municipalities" / "sandefjord.json"
        assert output.exists()
        with open(output, encoding="utf-8") as f:
            data = json.load(f)
        assert data["municipality"]["id"] == "sandefjord"
        assert len(data["days"]) == 3

    def test_empty_stores_fixture_no_metadata_propagates_none(self, tmp_path):
        """Fixture with {"stores": []} and no metadata must not break; fetched_at is None."""
        _setup_tmp_data_dir(tmp_path)
        args = [
            "prog",
            "--id",
            "sandefjord",
            "--start-date",
            "2026-01-01",
            "--days",
            "3",
            "--data-dir",
            str(tmp_path),
        ]
        with patch("sys.argv", args):
            main()

        output = tmp_path / "generated" / "municipalities" / "sandefjord.json"
        with open(output, encoding="utf-8") as f:
            data = json.load(f)
        assert "vinmonopolet_fetched_at" in data
        assert data["vinmonopolet_fetched_at"] is None

    def test_fetched_at_propagates_from_metadata(self, tmp_path):
        """fetched_at in vinmonopolet.json metadata must be written to municipality JSON."""
        _setup_tmp_data_dir(tmp_path)
        # Overwrite the stub with one that has metadata
        vinmonopolet_path = tmp_path / "generated" / "vinmonopolet.json"
        vinmonopolet_path.write_text(
            '{"metadata": {"fetched_at": "2026-04-12T10:00:00+02:00"}, "stores": []}',
            encoding="utf-8",
        )
        args = [
            "prog",
            "--id",
            "sandefjord",
            "--start-date",
            "2026-01-01",
            "--days",
            "3",
            "--data-dir",
            str(tmp_path),
        ]
        with patch("sys.argv", args):
            main()

        output = tmp_path / "generated" / "municipalities" / "sandefjord.json"
        with open(output, encoding="utf-8") as f:
            data = json.load(f)
        assert data["vinmonopolet_fetched_at"] == "2026-04-12T10:00:00+02:00"

    def test_all_generates_all_municipalities(self, tmp_path):
        """--all should generate a file for every municipality."""
        _setup_tmp_data_dir(tmp_path)
        args = [
            "prog",
            "--all",
            "--start-date",
            "2026-01-01",
            "--days",
            "3",
            "--data-dir",
            str(tmp_path),
        ]
        with patch("sys.argv", args):
            main()

        gen_dir = tmp_path / "generated" / "municipalities"
        files = sorted(gen_dir.glob("*.json"))
        assert len(files) >= 6  # sandefjord, larvik, oslo, trondheim, bergen, stavanger
