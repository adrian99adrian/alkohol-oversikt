"""Tests for municipality data generation."""

from datetime import date, timedelta

from build_calendar import build_calendar
from build_municipality import build_municipality


class TestBuildMunicipality:
    """Verify per-municipality output generation."""

    def _build(self, municipality: dict, start: date = date(2026, 1, 1)) -> dict:
        calendar = build_calendar(start, num_days=365)
        return build_municipality(municipality, calendar)

    def test_has_municipality_metadata(self, sample_municipality_sandefjord):
        result = self._build(sample_municipality_sandefjord)
        assert "municipality" in result
        meta = result["municipality"]
        assert meta["id"] == "sandefjord"
        assert meta["name"] == "Sandefjord"
        assert "sources" in meta
        assert "last_verified" in meta
        assert meta["verified"] is True

    def test_verified_false_propagates_with_null_last_verified(
        self, sample_municipality_sandefjord
    ):
        municipality = dict(sample_municipality_sandefjord)
        municipality["verified"] = False
        municipality["last_verified"] = None
        result = self._build(municipality)
        meta = result["municipality"]
        assert meta["verified"] is False
        assert meta["last_verified"] is None

    def test_has_days_array(self, sample_municipality_sandefjord):
        result = self._build(sample_municipality_sandefjord)
        assert "days" in result
        assert len(result["days"]) == 365

    def test_no_date_gaps(self, sample_municipality_sandefjord):
        result = self._build(sample_municipality_sandefjord)
        dates = [entry["date"] for entry in result["days"]]
        for i in range(1, len(dates)):
            d1 = date.fromisoformat(dates[i - 1])
            d2 = date.fromisoformat(dates[i])
            assert d2 - d1 == timedelta(days=1)

    def test_sandefjord_weekday(self, sample_municipality_sandefjord):
        result = self._build(sample_municipality_sandefjord, start=date(2026, 3, 10))
        day = result["days"][0]  # Tuesday March 10
        assert day["beer_sale_allowed"]
        assert day["beer_close"] == "20:00"
        assert day["beer_open"] == "06:00"

    def test_sandefjord_easter_sequence(self, sample_municipality_sandefjord):
        result = self._build(sample_municipality_sandefjord, start=date(2026, 4, 1))
        by_date = {d["date"]: d for d in result["days"][:7]}

        # Apr 1 — pre_holiday, 18:00
        assert by_date["2026-04-01"]["beer_close"] == "18:00"
        assert by_date["2026-04-01"]["beer_sale_allowed"]

        # Apr 2 — Skjærtorsdag, forbidden
        assert not by_date["2026-04-02"]["beer_sale_allowed"]

        # Apr 4 — Påskeaften, special_day 15:00 for Sandefjord
        assert by_date["2026-04-04"]["beer_close"] == "15:00"
        assert by_date["2026-04-04"]["beer_sale_allowed"]

        # Apr 5 — 1. påskedag, forbidden
        assert not by_date["2026-04-05"]["beer_sale_allowed"]

    def test_larvik_ascension_exception(self, sample_municipality_larvik):
        result = self._build(sample_municipality_larvik, start=date(2026, 5, 13))
        day = result["days"][0]  # May 13 — day before Ascension
        assert day["day_type"] == "pre_holiday"
        assert day["beer_close"] == "20:00"  # Weekday hours due to exception

    def test_oslo_large_store_christmas_eve(self, sample_municipality_oslo):
        result = self._build(sample_municipality_oslo, start=date(2026, 12, 24))
        day = result["days"][0]  # Dec 24
        assert day["beer_close"] == "18:00"
        assert day["beer_close_large_stores"] == "16:00"
        assert "100 m²" in day["comment"]

    def test_oslo_large_store_not_on_new_years_eve(self, sample_municipality_oslo):
        result = self._build(sample_municipality_oslo, start=date(2026, 12, 31))
        day = result["days"][0]
        assert day["beer_close_large_stores"] is None

    def test_all_days_have_schema(self, sample_municipality_sandefjord):
        result = self._build(sample_municipality_sandefjord)
        required = {
            "date",
            "weekday",
            "day_type",
            "day_type_label",
            "beer_sale_allowed",
            "beer_open",
            "beer_close",
            "beer_close_large_stores",
            "is_deviation",
            "comment",
        }
        for day in result["days"]:
            assert required.issubset(day.keys()), f"Missing: {required - day.keys()}"


class TestVinmonopoletFetchedAtPropagation:
    """Verify vinmonopolet_fetched_at is threaded through to output."""

    def _build(
        self,
        municipality: dict,
        fetched_at: str | None,
        start: date = date(2026, 1, 1),
    ) -> dict:
        calendar = build_calendar(start, num_days=14)
        return build_municipality(
            municipality,
            calendar,
            vinmonopolet_stores=[],
            vinmonopolet_fetched_at=fetched_at,
        )

    def test_fetched_at_included_when_provided(self, sample_municipality_sandefjord):
        result = self._build(sample_municipality_sandefjord, "2026-04-12T10:00:00+02:00")
        assert result["vinmonopolet_fetched_at"] == "2026-04-12T10:00:00+02:00"

    def test_fetched_at_is_none_when_missing(self, sample_municipality_sandefjord):
        result = self._build(sample_municipality_sandefjord, None)
        assert result["vinmonopolet_fetched_at"] is None
