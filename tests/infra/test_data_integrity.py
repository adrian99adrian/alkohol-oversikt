"""Infrastructure tests: municipality data file integrity."""

import json
import re
from pathlib import Path

import pytest

MUNICIPALITIES_DIR = Path(__file__).parent.parent.parent / "data" / "municipalities"

KNOWN_SPECIAL_DAYS = {"easter_eve", "whit_eve", "christmas_eve", "new_years_eve"}

TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")


def _load_all_municipalities() -> list[tuple[str, dict]]:
    """Load all municipality JSON files. Returns list of (filename, data)."""
    result = []
    for path in sorted(MUNICIPALITIES_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            result.append((path.name, json.load(f)))
    return result


@pytest.fixture
def municipalities():
    return _load_all_municipalities()


class TestMunicipalityFiles:
    """Validate municipality JSON data files."""

    def test_at_least_one_municipality(self, municipalities):
        assert len(municipalities) > 0

    def test_all_valid_json(self, municipalities):
        """All files loaded without error (implicit from fixture)."""
        for name, data in municipalities:
            assert isinstance(data, dict), f"{name}: not a JSON object"

    def test_required_fields(self, municipalities):
        required = {"id", "name", "county", "beer_sales", "sources", "last_verified"}
        for name, data in municipalities:
            missing = required - data.keys()
            assert not missing, f"{name}: missing fields {missing}"

    def test_beer_sales_fields(self, municipalities):
        required = {
            "weekday_open",
            "weekday_close",
            "saturday_open",
            "saturday_close",
            "pre_holiday_close",
            "special_day_close",
            "special_days",
        }
        for name, data in municipalities:
            beer = data["beer_sales"]
            missing = required - beer.keys()
            assert not missing, f"{name}: missing beer_sales fields {missing}"

    def test_time_format(self, municipalities):
        """All time fields match HH:MM format."""
        time_fields = [
            "weekday_open",
            "weekday_close",
            "saturday_open",
            "saturday_close",
            "pre_holiday_close",
            "special_day_close",
        ]
        for name, data in municipalities:
            beer = data["beer_sales"]
            for field in time_fields:
                val = beer.get(field)
                if val is not None:
                    assert TIME_PATTERN.match(val), f"{name}: {field}={val!r} doesn't match HH:MM"

    def test_special_days_are_known(self, municipalities):
        for name, data in municipalities:
            for sd in data["beer_sales"]["special_days"]:
                assert sd in KNOWN_SPECIAL_DAYS, f"{name}: unknown special_day {sd!r}"

    def test_sources_non_empty(self, municipalities):
        for name, data in municipalities:
            assert len(data["sources"]) > 0, f"{name}: no sources"

    def test_sources_have_url(self, municipalities):
        for name, data in municipalities:
            for source in data["sources"]:
                assert "url" in source, f"{name}: source missing url"
                assert source["url"].startswith("http"), (
                    f"{name}: invalid source url {source['url']!r}"
                )

    def test_last_verified_format(self, municipalities):
        for name, data in municipalities:
            lv = data["last_verified"]
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", lv), (
                f"{name}: last_verified {lv!r} not YYYY-MM-DD"
            )

    def test_id_matches_filename(self, municipalities):
        for name, data in municipalities:
            expected_id = name.replace(".json", "")
            assert data["id"] == expected_id, f"{name}: id={data['id']!r} doesn't match filename"
