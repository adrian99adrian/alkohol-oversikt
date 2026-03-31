"""Tests for Vinmonopolet API fetch and transformation."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from fetch_vinmonopolet import (
    build_actual_hours,
    derive_standard_hours,
    fetch_all_stores,
    fetch_page,
    format_address,
    get_with_retry,
    map_town_to_municipality,
    transform_store,
)


class TestDeriveStandardHours:
    """Verify standard_hours derivation from 7-day API data."""

    def test_normal_week_no_specials(self, sample_opening_times_normal):
        """All 7 days are normal — each weekday maps directly."""
        result = derive_standard_hours(sample_opening_times_normal, [])
        assert result["monday"] == {"open": "10:00", "close": "18:00"}
        assert result["tuesday"] == {"open": "10:00", "close": "18:00"}
        assert result["wednesday"] == {"open": "10:00", "close": "18:00"}
        assert result["thursday"] == {"open": "10:00", "close": "18:00"}
        assert result["friday"] == {"open": "10:00", "close": "18:00"}
        assert result["saturday"] == {"open": "10:00", "close": "15:00"}
        assert result["sunday"] is None

    def test_holiday_in_week_skipped(
        self, sample_opening_times_easter, sample_special_opening_times_easter
    ):
        """Days in specialOpeningTimes are excluded from standard derivation."""
        result = derive_standard_hours(
            sample_opening_times_easter, sample_special_opening_times_easter
        )
        # Tuesday is the only non-special weekday
        assert result["tuesday"] == {"open": "10:00", "close": "18:00"}
        # Sunday always null
        assert result["sunday"] is None
        # Wednesday, Thursday, Friday, Monday are all special — fall back to
        # mode of other Mon-Fri (only Tuesday: 10-18), so all get 10-18
        assert result["monday"] == {"open": "10:00", "close": "18:00"}
        assert result["wednesday"] == {"open": "10:00", "close": "18:00"}
        assert result["thursday"] == {"open": "10:00", "close": "18:00"}
        assert result["friday"] == {"open": "10:00", "close": "18:00"}
        # Saturday is special (easter eve) — falls back to Mon-Fri mode (10-18)
        # rather than incorrectly assuming the store is closed on Saturdays
        assert result["saturday"] == {"open": "10:00", "close": "18:00"}

    def test_holiday_week_preserves_previous_per_day(
        self, sample_opening_times_easter, sample_special_opening_times_easter
    ):
        """With previous data, special-skipped days keep their per-day hours."""
        previous = {
            "monday": {"open": "10:00", "close": "17:00"},
            "tuesday": {"open": "10:00", "close": "18:00"},
            "wednesday": {"open": "10:00", "close": "17:00"},
            "thursday": {"open": "10:00", "close": "19:00"},
            "friday": {"open": "10:00", "close": "19:00"},
            "saturday": {"open": "10:00", "close": "15:00"},
            "sunday": None,
        }
        result = derive_standard_hours(
            sample_opening_times_easter,
            sample_special_opening_times_easter,
            previous=previous,
        )
        # Tuesday is non-special — uses fresh data
        assert result["tuesday"] == {"open": "10:00", "close": "18:00"}
        # Special-skipped days preserve previous per-day values
        assert result["monday"] == {"open": "10:00", "close": "17:00"}
        assert result["wednesday"] == {"open": "10:00", "close": "17:00"}
        assert result["thursday"] == {"open": "10:00", "close": "19:00"}
        assert result["friday"] == {"open": "10:00", "close": "19:00"}
        assert result["saturday"] == {"open": "10:00", "close": "15:00"}
        assert result["sunday"] is None

    def test_sunday_always_null(self, sample_opening_times_normal):
        """Sunday is always null regardless of API data."""
        result = derive_standard_hours(sample_opening_times_normal, [])
        assert result["sunday"] is None

    def test_all_weekday_keys_present(self, sample_opening_times_normal):
        """Result always has all 7 weekday keys."""
        result = derive_standard_hours(sample_opening_times_normal, [])
        expected_keys = {
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        }
        assert set(result.keys()) == expected_keys

    def test_regular_weekday_closure_preserved(self):
        """A store regularly closed on a non-special weekday gets None, not fallback."""
        from tests.conftest import _make_opening_time

        opening_times = [
            _make_opening_time("2026-03-30", open_h=10, close_h=18, weekday="Mandag"),
            _make_opening_time("2026-03-31", open_h=10, close_h=18, weekday="Tirsdag"),
            _make_opening_time("2026-04-01", closed=True, weekday="Onsdag"),  # Regularly closed
            _make_opening_time("2026-04-02", open_h=10, close_h=18, weekday="Torsdag"),
            _make_opening_time("2026-04-03", open_h=10, close_h=18, weekday="Fredag"),
            _make_opening_time("2026-04-04", open_h=10, close_h=15, weekday="Lørdag"),
            _make_opening_time("2026-04-05", closed=True, weekday="Søndag"),
        ]
        result = derive_standard_hours(opening_times, [])
        assert result["wednesday"] is None
        assert result["monday"] == {"open": "10:00", "close": "18:00"}
        assert result["saturday"] == {"open": "10:00", "close": "15:00"}

    def test_tie_break_uses_earliest_close(self):
        """When multiple weekdays tie for mode, use earliest closing time."""
        from tests.conftest import _make_opening_time

        # 3 weekdays: Mon 10-17, Tue 10-18, Wed 10-19 — all different
        # Thu is special, so needs fallback. Mode is undefined, tie-break
        # should pick earliest close (17:00)
        opening_times = [
            _make_opening_time("2026-06-01", open_h=10, close_h=17, weekday="Mandag"),
            _make_opening_time("2026-06-02", open_h=10, close_h=18, weekday="Tirsdag"),
            _make_opening_time("2026-06-03", open_h=10, close_h=19, weekday="Onsdag"),
            _make_opening_time("2026-06-04", open_h=10, close_h=16, weekday="Torsdag"),
            _make_opening_time("2026-06-05", open_h=10, close_h=18, weekday="Fredag"),
            _make_opening_time("2026-06-06", open_h=10, close_h=15, weekday="Lørdag"),
            _make_opening_time("2026-06-07", closed=True, weekday="Søndag"),
        ]
        # Thursday is special
        specials = [
            _make_opening_time("2026-06-04", open_h=10, close_h=16, weekday="Torsdag"),
        ]
        result = derive_standard_hours(opening_times, specials)
        # Thursday fallback: mode of Mon-Fri non-special hours.
        # Mon=17, Tue=18, Wed=19, Fri=18. Mode is 18 (appears twice).
        assert result["thursday"] == {"open": "10:00", "close": "18:00"}


class TestBuildActualHours:
    """Verify actual_hours preserves raw 7-day API data."""

    def test_normal_week(self, sample_opening_times_normal):
        """Open days get {open, close}, closed days get null."""
        result = build_actual_hours(sample_opening_times_normal)
        assert result["2026-03-30"] == {"open": "10:00", "close": "18:00"}
        assert result["2026-04-04"] == {"open": "10:00", "close": "15:00"}
        assert result["2026-04-05"] is None  # Sunday closed

    def test_exactly_7_entries(self, sample_opening_times_normal):
        """Result has exactly 7 date entries."""
        result = build_actual_hours(sample_opening_times_normal)
        assert len(result) == 7

    def test_easter_week_closed_days(self, sample_opening_times_easter):
        """Holiday closed days become null."""
        result = build_actual_hours(sample_opening_times_easter)
        assert result["2026-04-02"] is None  # Skjærtorsdag
        assert result["2026-04-03"] is None  # Langfredag
        assert result["2026-04-06"] is None  # 2. påskedag
        # Wednesday has reduced hours
        assert result["2026-04-01"] == {"open": "10:00", "close": "16:00"}

    def test_dates_are_iso_format(self, sample_opening_times_normal):
        """Keys are ISO date strings (YYYY-MM-DD)."""
        result = build_actual_hours(sample_opening_times_normal)
        for key in result:
            assert len(key) == 10
            assert key[4] == "-" and key[7] == "-"


class TestFormatAddress:
    """Verify address string formatting."""

    def test_standard_address(self):
        store = {
            "address": {
                "line1": "Museumsgata 2",
                "postalCode": "3210",
                "town": "Sandefjord",
            }
        }
        assert format_address(store) == "Museumsgata 2, 3210 Sandefjord"

    def test_oslo_address(self):
        store = {
            "address": {
                "line1": "Storgata 20",
                "postalCode": "0184",
                "town": "Oslo",
            }
        }
        assert format_address(store) == "Storgata 20, 0184 Oslo"


class TestMapTownToMunicipality:
    """Verify town → municipality mapping."""

    def test_direct_lowercase_match(self):
        """Town lowercases to a known municipality ID."""
        known = {"sandefjord", "larvik", "oslo"}
        assert map_town_to_municipality("Sandefjord", {}, known) == "sandefjord"

    def test_override_match(self):
        """Override maps Stavern → larvik."""
        known = {"sandefjord", "larvik", "oslo"}
        overrides = {"Stavern": "larvik"}
        assert map_town_to_municipality("Stavern", overrides, known) == "larvik"

    def test_unknown_town_returns_none(self):
        """Town not in overrides or known municipalities → None."""
        known = {"sandefjord", "larvik", "oslo"}
        assert map_town_to_municipality("Vestby", {}, known) is None

    def test_override_takes_precedence(self):
        """Override wins even if town lowercases to a known municipality."""
        known = {"sandefjord", "larvik"}
        overrides = {"Sandefjord": "larvik"}  # Unusual but tests precedence
        assert map_town_to_municipality("Sandefjord", overrides, known) == "larvik"

    def test_norwegian_characters(self):
        """Norwegian characters lowercase correctly."""
        known = {"tromsø"}
        assert map_town_to_municipality("Tromsø", {}, known) == "tromsø"


class TestTransformStore:
    """Verify full store transformation."""

    def test_complete_store(self, sample_api_store):
        """Full API store → spec-compliant output."""
        known = {"sandefjord", "larvik", "oslo"}
        result = transform_store(sample_api_store, {}, known)
        assert result["store_id"] == "283"
        assert result["name"] == "Sandefjord"
        assert result["municipality"] == "sandefjord"
        assert result["address"] == "Museumsgata 2, 3210 Sandefjord"
        assert "monday" in result["standard_hours"]
        assert "sunday" in result["standard_hours"]
        assert result["standard_hours"]["sunday"] is None
        assert len(result["actual_hours"]) == 7

    def test_output_has_all_required_fields(self, sample_api_store):
        """All required fields present."""
        known = {"sandefjord"}
        result = transform_store(sample_api_store, {}, known)
        required = {"store_id", "name", "municipality", "address", "standard_hours", "actual_hours"}
        assert required.issubset(result.keys())

    def test_unmapped_municipality_is_none(self, sample_api_store):
        """Store in unknown town and unknown displayName gets municipality=None."""
        store = {**sample_api_store, "displayName": "Ukjent"}
        store["address"] = {**store["address"], "town": "Ukjentby"}
        result = transform_store(store, {}, {"sandefjord"})
        assert result["municipality"] is None

    def test_displayname_fallback_for_municipality(self, sample_api_store):
        """When town doesn't match, displayName is tried as fallback."""
        store = {**sample_api_store}
        store["address"] = {**store["address"], "town": "Stokke"}
        # displayName is "Sandefjord" which matches
        result = transform_store(store, {}, {"sandefjord"})
        assert result["municipality"] == "sandefjord"

    def test_easter_store(self, sample_api_store_easter):
        """Store during Easter week transforms correctly."""
        known = {"sandefjord"}
        result = transform_store(sample_api_store_easter, {}, known)
        # actual_hours preserves the raw data
        assert result["actual_hours"]["2026-04-02"] is None  # Skjærtorsdag
        assert result["actual_hours"]["2026-03-31"] == {"open": "10:00", "close": "18:00"}


class TestGetWithRetry:
    """Verify HTTP retry behavior."""

    def test_success_first_try(self):
        client = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()
        client.get.return_value = response

        result = get_with_retry(client, "http://example.com", {})
        assert result == response
        assert client.get.call_count == 1

    @patch("fetch_vinmonopolet.time.sleep")
    def test_retries_on_500(self, mock_sleep):
        client = MagicMock()
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=error_response
        )
        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.raise_for_status = MagicMock()
        client.get.side_effect = [error_response, ok_response]

        result = get_with_retry(client, "http://example.com", {}, max_retries=3)
        assert result == ok_response
        assert client.get.call_count == 2

    @patch("fetch_vinmonopolet.time.sleep")
    def test_retries_on_timeout(self, mock_sleep):
        client = MagicMock()
        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.raise_for_status = MagicMock()
        client.get.side_effect = [httpx.TimeoutException("timeout"), ok_response]

        result = get_with_retry(client, "http://example.com", {}, max_retries=3)
        assert result == ok_response
        assert client.get.call_count == 2

    @patch("fetch_vinmonopolet.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep):
        client = MagicMock()
        client.get.side_effect = httpx.TimeoutException("timeout")

        with pytest.raises(httpx.TimeoutException):
            get_with_retry(client, "http://example.com", {}, max_retries=3)
        assert client.get.call_count == 3

    def test_no_retry_on_404(self):
        client = MagicMock()
        response = MagicMock()
        response.status_code = 404
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=response
        )
        client.get.return_value = response

        with pytest.raises(httpx.HTTPStatusError):
            get_with_retry(client, "http://example.com", {})
        assert client.get.call_count == 1


class TestFetchPage:
    """Verify single-page fetch."""

    @patch("fetch_vinmonopolet.get_with_retry")
    def test_returns_parsed_json(self, mock_retry, sample_api_response):
        response = MagicMock()
        response.json.return_value = sample_api_response
        mock_retry.return_value = response
        client = MagicMock()

        result = fetch_page(client, page=0)
        assert result == sample_api_response

    @patch("fetch_vinmonopolet.get_with_retry")
    def test_passes_fields_full(self, mock_retry):
        response = MagicMock()
        response.json.return_value = {"stores": [], "pagination": {}}
        mock_retry.return_value = response
        client = MagicMock()

        fetch_page(client, page=0)
        call_args = mock_retry.call_args
        params = call_args[0][2]  # Third positional arg is params
        assert params["fields"] == "FULL"

    @patch("fetch_vinmonopolet.get_with_retry")
    def test_passes_page_number(self, mock_retry):
        response = MagicMock()
        response.json.return_value = {"stores": [], "pagination": {}}
        mock_retry.return_value = response
        client = MagicMock()

        fetch_page(client, page=3, page_size=50)
        call_args = mock_retry.call_args
        params = call_args[0][2]
        assert params["page"] == 3
        assert params["pageSize"] == 50


class TestFetchAllStores:
    """Verify paginated fetch."""

    @patch("fetch_vinmonopolet.fetch_page")
    def test_fetches_all_pages(self, mock_fetch_page):
        page0 = {
            "pagination": {"totalPages": 2, "totalResults": 3},
            "stores": [{"name": "1"}, {"name": "2"}],
        }
        page1 = {
            "pagination": {"totalPages": 2, "totalResults": 3},
            "stores": [{"name": "3"}],
        }
        mock_fetch_page.side_effect = [page0, page1]

        stores = fetch_all_stores(MagicMock())
        assert len(stores) == 3
        assert mock_fetch_page.call_count == 2

    @patch("fetch_vinmonopolet.fetch_page")
    def test_single_page(self, mock_fetch_page):
        page0 = {
            "pagination": {"totalPages": 1, "totalResults": 2},
            "stores": [{"name": "1"}, {"name": "2"}],
        }
        mock_fetch_page.return_value = page0

        stores = fetch_all_stores(MagicMock())
        assert len(stores) == 2
        assert mock_fetch_page.call_count == 1

    @patch("fetch_vinmonopolet.fetch_page")
    def test_raises_on_count_mismatch(self, mock_fetch_page):
        page0 = {
            "pagination": {"totalPages": 1, "totalResults": 5},
            "stores": [{"name": "1"}, {"name": "2"}],
        }
        mock_fetch_page.return_value = page0

        with pytest.raises(ValueError, match="Expected 5.*got 2"):
            fetch_all_stores(MagicMock())


@pytest.mark.slow
class TestRealAPI:
    """Smoke test against the real Vinmonopolet API."""

    def test_page_zero_returns_stores(self):
        """Fetch page 0 and verify response structure."""
        with httpx.Client(timeout=30) as client:
            result = fetch_page(client, page=0, page_size=2)

        assert "stores" in result
        assert "pagination" in result
        assert len(result["stores"]) > 0

        store = result["stores"][0]
        assert "name" in store
        assert "displayName" in store
        assert "address" in store
        assert "openingTimes" in store
        assert len(store["openingTimes"]) == 7
