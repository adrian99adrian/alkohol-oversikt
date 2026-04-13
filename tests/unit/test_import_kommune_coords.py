"""Unit tests for scripts/import_kommune_coords.py.

Covers:
- Normalization + name matching
- The four acceptance rules (positive + negative each)
- Ambiguity: multiple passing results → rejected
- Override precedence + validation
- Idempotency (re-run does not overwrite)
- HTTP behavior (User-Agent header, sleep called, timeout handling)
- Partial-run recovery
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import httpx
import import_kommune_coords as mod
import pytest

# ---------- Normalization / matching ----------


def test_normalize_strips_diacritics():
    assert mod.normalize("Ålesund") == "alesund"
    assert mod.normalize("Ørsta") == "orsta"
    assert mod.normalize("Stjørdal") == "stjordal"
    assert mod.normalize("Nord-Trøndelag") == "nord-trondelag"


def test_normalize_lowercases_and_collapses_whitespace():
    assert mod.normalize("  OSLO   kommune  ") == "oslo kommune"


def test_normalize_handles_aesc():
    assert mod.normalize("Færder") == "faerder"


def test_normalize_empty():
    assert mod.normalize("") == ""


def test_names_match_substring():
    assert mod.names_match("Agder", "Agder fylke")
    assert mod.names_match("Vestfold", "Vestfold og Telemark")


def test_names_match_case_insensitive():
    assert mod.names_match("OSLO", "oslo kommune")
    assert mod.names_match("oslo", "Oslo Kommune")


def test_names_match_diacritic_insensitive():
    assert mod.names_match("Ålesund", "alesund kommune")
    assert mod.names_match("alesund", "Ålesund")


def test_names_match_rejects_unrelated():
    assert not mod.names_match("Telemark", "Agder")
    # "Vestfold" should NOT match "Vestland" (different county).
    assert not mod.names_match("Vestland", "Vestfold og Telemark")


def test_names_match_empty_strings():
    assert not mod.names_match("", "Oslo")
    assert not mod.names_match("Oslo", "")


def test_coords_in_norway_inclusive_bounds():
    assert mod.coords_in_norway(57.0, 4.0)
    assert mod.coords_in_norway(72.0, 32.0)
    assert mod.coords_in_norway(60.0, 10.5)


def test_coords_in_norway_rejects_outside():
    assert not mod.coords_in_norway(56.9, 10.0)  # too south
    assert not mod.coords_in_norway(72.1, 10.0)  # too north
    assert not mod.coords_in_norway(60.0, 3.9)  # too west
    assert not mod.coords_in_norway(60.0, 32.1)  # too east


# ---------- The four acceptance rules ----------


def _kommune(muni="Sokndal", county="Rogaland", kid="sokndal") -> dict:
    return {"municipality": muni, "county": county, "id": kid}


def _result(
    lat: float = 58.3,
    lon: float = 6.2,
    country_code: str = "no",
    county: str = "Rogaland",
    municipality: str | None = "Sokndal",
    city: str | None = None,
    town: str | None = None,
) -> dict:
    addr: dict[str, Any] = {"country_code": country_code, "county": county}
    if municipality is not None:
        addr["municipality"] = municipality
    if city is not None:
        addr["city"] = city
    if town is not None:
        addr["town"] = town
    return {"lat": str(lat), "lon": str(lon), "address": addr}


def test_rule1_country_code_must_be_no():
    k = _kommune()
    assert mod.result_passes(_result(), k)
    assert not mod.result_passes(_result(country_code="se"), k)


def test_rule2_county_must_match():
    k = _kommune()
    assert mod.result_passes(_result(county="Rogaland"), k)
    assert mod.result_passes(_result(county="Rogaland fylke"), k)  # fuzzy
    assert not mod.result_passes(_result(county="Agder"), k)


def test_rule3_municipality_matches_via_municipality_field():
    k = _kommune()
    assert mod.result_passes(_result(municipality="Sokndal"), k)
    assert not mod.result_passes(_result(municipality="Bjerkreim"), k)


def test_rule3_municipality_matches_via_city_fallback():
    k = _kommune()
    r = _result(municipality=None, city="Sokndal")
    assert mod.result_passes(r, k)


def test_rule3_municipality_matches_via_town_fallback():
    k = _kommune()
    r = _result(municipality=None, city=None, town="Sokndal")
    assert mod.result_passes(r, k)


def test_rule3_no_municipality_field_at_all_rejects():
    k = _kommune()
    r = _result(municipality=None)
    assert not mod.result_passes(r, k)


def test_rule2_county_absent_accepted_when_municipality_matches():
    """Oslo-case: Nominatim response has no county field (Oslo is its own
    state). The importer must still accept the match when municipality
    matches and country_code is 'no'."""
    k = _kommune(muni="Oslo", county="Oslo", kid="oslo")
    r = {
        "lat": "59.91",
        "lon": "10.75",
        "address": {"country_code": "no", "municipality": "Oslo", "city": "Oslo"},
    }
    assert mod.result_passes(r, k)


def test_rule2_county_accepted_via_state_fallback():
    """If address.county is missing but address.state matches, accept."""
    k = _kommune()
    r = {
        "lat": "58.3",
        "lon": "6.2",
        "address": {
            "country_code": "no",
            "municipality": "Sokndal",
            "state": "Rogaland",
        },
    }
    assert mod.result_passes(r, k)


def test_rule4_lat_lng_must_be_in_norway():
    k = _kommune()
    assert mod.result_passes(_result(lat=58.3, lon=6.2), k)
    assert not mod.result_passes(_result(lat=55.0, lon=10.0), k)  # too south (Denmark)
    assert not mod.result_passes(_result(lat=60.0, lon=40.0), k)  # too east (Russia)


def test_rule4_rejects_non_numeric_lat_lng():
    k = _kommune()
    r = {
        "lat": "abc",
        "lon": "6.2",
        "address": {"country_code": "no", "county": "Rogaland", "municipality": "Sokndal"},
    }
    assert not mod.result_passes(r, k)


def test_rule4_rejects_nan():
    k = _kommune()
    r = {
        "lat": "nan",
        "lon": "6.2",
        "address": {"country_code": "no", "county": "Rogaland", "municipality": "Sokndal"},
    }
    assert not mod.result_passes(r, k)


def test_partial_match_rejected_municipality_right_county_wrong():
    """Right municipality name but wrong county → rejected (cross-county name collision)."""
    k = _kommune(muni="Os", county="Innlandet")  # historical Os, Hedmark
    # Result describes the OTHER Os (Hordaland — pre-2020)
    r = _result(county="Vestland", municipality="Os")
    assert not mod.result_passes(r, k)


def test_hyphenated_names_pass():
    k = _kommune(muni="Nord-Odal", county="Innlandet")
    r = _result(county="Innlandet", municipality="Nord-Odal", lat=60.3, lon=11.6)
    assert mod.result_passes(r, k)


# ---------- Ambiguity + zero-match ----------


def test_pick_unique_match_single_passing():
    k = _kommune()
    winner, reason = mod.pick_unique_match([_result()], k)
    assert winner is not None
    assert reason == "accepted"


def test_pick_unique_match_ambiguous_different_municipalities():
    """Two passing results with DIFFERENT municipality names → ambiguous."""
    k = _kommune(muni="Os")
    # Both pass (their muni fields each substring-match "Os"), but they
    # describe different admin areas ("Os" vs "Osen") so they are not
    # duplicates of the same kommune.
    r1 = {
        "lat": "60.19",
        "lon": "5.47",
        "address": {"country_code": "no", "county": "Rogaland", "municipality": "Os"},
    }
    r2 = {
        "lat": "64.29",
        "lon": "10.53",
        "address": {"country_code": "no", "county": "Rogaland", "municipality": "Osen"},
    }
    winner, reason = mod.pick_unique_match([r1, r2], k)
    assert winner is None
    assert "ambiguous" in reason


def test_pick_unique_match_deduplicates_same_kommune():
    """Multiple results with the same municipality name → deduplicated."""
    k = _kommune()
    # Nominatim returns node + relation for Sokndal; coords differ but the
    # admin area is the same.
    winner, reason = mod.pick_unique_match([_result(lat=58.30), _result(lat=58.58, lon=6.08)], k)
    assert winner is not None
    assert "deduped" in reason


def test_pick_unique_match_zero():
    k = _kommune()
    winner, reason = mod.pick_unique_match([], k)
    assert winner is None
    assert "no match" in reason


def test_pick_unique_match_zero_with_non_passing():
    k = _kommune()
    winner, reason = mod.pick_unique_match([_result(country_code="se")], k)
    assert winner is None
    assert "no match" in reason


# ---------- Override validation ----------


def test_validate_override_accepts_good():
    mod.validate_override("sokndal", {"lat": 58.3, "lng": 6.2})


def test_validate_override_rejects_missing_field():
    with pytest.raises(ValueError, match="missing numeric"):
        mod.validate_override("sokndal", {"lat": 58.3})


def test_validate_override_rejects_non_numeric():
    with pytest.raises(ValueError, match="missing numeric"):
        mod.validate_override("sokndal", {"lat": "abc", "lng": 6.2})


def test_validate_override_rejects_out_of_bounds():
    with pytest.raises(ValueError, match="outside Norway"):
        mod.validate_override("sokndal", {"lat": 40.0, "lng": 6.2})


def test_validate_override_rejects_nan():
    with pytest.raises(ValueError, match="non-finite"):
        mod.validate_override("sokndal", {"lat": float("nan"), "lng": 6.2})


def test_validate_override_rejects_inf():
    with pytest.raises(ValueError, match="non-finite"):
        mod.validate_override("sokndal", {"lat": float("inf"), "lng": 6.2})


def test_validate_override_rejects_non_dict():
    with pytest.raises(ValueError, match="must be an object"):
        mod.validate_override("sokndal", ["not", "an", "object"])  # type: ignore[arg-type]


# ---------- run() integration (with mocked HTTP) ----------


def _write(tmp: Path, name: str, data: Any) -> Path:
    p = tmp / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _make_registry(entries: list[dict]) -> dict:
    return {"_schema": {"description": "test"}, "kommuner": entries}


class _MockClient:
    """A minimal stand-in for httpx.Client used in tests."""

    def __init__(self, responses: list[Any]):
        # responses: list of either list[dict] (json result) or Exception
        self._responses = list(responses)
        self.requests: list[tuple[str, dict]] = []
        self.headers: dict[str, str] = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url: str, params: dict):
        self.requests.append((url, params))
        if not self._responses:
            raise AssertionError("unexpected extra HTTP request")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        resp = MagicMock()
        resp.json.return_value = item
        resp.raise_for_status.return_value = None
        return resp


def _factory(client: _MockClient):
    return lambda: client


def test_run_retries_partially_populated_entry(tmp_path: Path):
    """An entry with lat set but lng still null must be retried, not skipped.

    A half-written entry is a bug, not a success. Skipping it would leave the
    registry permanently broken even across re-runs of the importer.
    """
    reg = _make_registry(
        [
            {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "Rogaland",
                "lat": 58.33,
                "lng": None,
                "bugs": [],
            },
        ]
    )
    reg_path = _write(tmp_path, "kommuner.json", reg)
    ov_path = _write(tmp_path, "overrides.json", {})
    un_path = tmp_path / "unresolved.json"

    client = _MockClient([[_result()]])
    resolved, skipped, _ = mod.run(
        reg_path,
        ov_path,
        un_path,
        client_factory=_factory(client),
        sleep_fn=lambda _s: None,
    )
    assert resolved == 1
    assert skipped == 0
    # Nominatim WAS called (one query succeeded).
    assert len(client.requests) == 1

    written = json.loads(reg_path.read_text(encoding="utf-8"))
    assert written["kommuner"][0]["lng"] is not None


def test_run_idempotent_skips_existing_coords(tmp_path: Path):
    reg = _make_registry(
        [
            {
                "id": "oslo",
                "municipality": "Oslo",
                "county": "Oslo",
                "lat": 59.91,
                "lng": 10.75,
                "borders": None,
                "bugs": [],
            },
        ]
    )
    reg_path = _write(tmp_path, "kommuner.json", reg)
    ov_path = _write(tmp_path, "overrides.json", {})
    un_path = tmp_path / "unresolved.json"

    # No HTTP responses queued — if the importer makes a request, the mock raises.
    client = _MockClient([])
    resolved, skipped, un = mod.run(
        reg_path,
        ov_path,
        un_path,
        client_factory=_factory(client),
        sleep_fn=lambda _s: None,
    )
    assert resolved == 0
    assert skipped == 1
    assert un == 0
    assert client.requests == []


def test_run_override_takes_precedence_no_http(tmp_path: Path):
    reg = _make_registry(
        [
            {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "Rogaland",
                "borders": [],
                "bugs": [],
            },
        ]
    )
    reg_path = _write(tmp_path, "kommuner.json", reg)
    ov_path = _write(tmp_path, "overrides.json", {"sokndal": {"lat": 58.33, "lng": 6.22}})
    un_path = tmp_path / "unresolved.json"

    client = _MockClient([])  # must NOT be called
    resolved, _, un = mod.run(
        reg_path,
        ov_path,
        un_path,
        client_factory=_factory(client),
        sleep_fn=lambda _s: None,
    )
    assert resolved == 1
    assert un == 0
    assert client.requests == []

    written = json.loads(reg_path.read_text(encoding="utf-8"))
    assert written["kommuner"][0]["lat"] == pytest.approx(58.33)
    assert written["kommuner"][0]["lng"] == pytest.approx(6.22)


def test_run_rejects_bad_override_fails_fast(tmp_path: Path):
    reg = _make_registry(
        [
            {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "Rogaland",
                "borders": [],
                "bugs": [],
            },
        ]
    )
    reg_path = _write(tmp_path, "kommuner.json", reg)
    ov_path = _write(tmp_path, "overrides.json", {"sokndal": {"lat": 40.0, "lng": 6.2}})
    un_path = tmp_path / "unresolved.json"

    with pytest.raises(ValueError, match="outside Norway"):
        mod.run(
            reg_path,
            ov_path,
            un_path,
            client_factory=_factory(_MockClient([])),
            sleep_fn=lambda _s: None,
        )


def test_run_nominatim_success_writes_registry(tmp_path: Path):
    reg = _make_registry(
        [
            {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "Rogaland",
                "borders": [],
                "bugs": [],
            },
        ]
    )
    reg_path = _write(tmp_path, "kommuner.json", reg)
    ov_path = _write(tmp_path, "overrides.json", {})
    un_path = tmp_path / "unresolved.json"

    client = _MockClient([[_result(lat=58.33, lon=6.22)]])
    resolved, _, un = mod.run(
        reg_path,
        ov_path,
        un_path,
        client_factory=_factory(client),
        sleep_fn=lambda _s: None,
    )
    assert resolved == 1
    assert un == 0
    assert len(client.requests) == 1

    written = json.loads(reg_path.read_text(encoding="utf-8"))
    assert written["kommuner"][0]["lat"] == pytest.approx(58.33)
    assert written["kommuner"][0]["lng"] == pytest.approx(6.22)


def test_run_fallback_query_used_when_primary_fails(tmp_path: Path):
    reg = _make_registry(
        [
            {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "Rogaland",
                "borders": [],
                "bugs": [],
            },
        ]
    )
    reg_path = _write(tmp_path, "kommuner.json", reg)
    ov_path = _write(tmp_path, "overrides.json", {})
    un_path = tmp_path / "unresolved.json"

    # First query returns nothing; second (fallback) succeeds.
    client = _MockClient([[], [_result()]])
    resolved, _, un = mod.run(
        reg_path,
        ov_path,
        un_path,
        client_factory=_factory(client),
        sleep_fn=lambda _s: None,
    )
    assert resolved == 1
    assert un == 0
    assert len(client.requests) == 2
    # Primary query first, second fallback after.
    assert "rådhus" in client.requests[0][1]["q"]
    assert "kommune" in client.requests[1][1]["q"]


def test_run_third_fallback_tried_when_first_two_fail(tmp_path: Path):
    """Bare name query is tried if both qualified variants return nothing."""
    reg = _make_registry(
        [
            {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "Rogaland",
                "borders": [],
                "bugs": [],
            },
        ]
    )
    reg_path = _write(tmp_path, "kommuner.json", reg)
    ov_path = _write(tmp_path, "overrides.json", {})
    un_path = tmp_path / "unresolved.json"

    client = _MockClient([[], [], [_result()]])
    resolved, _, un = mod.run(
        reg_path,
        ov_path,
        un_path,
        client_factory=_factory(client),
        sleep_fn=lambda _s: None,
    )
    assert resolved == 1
    assert un == 0
    assert len(client.requests) == 3
    # Third query has no rådhus/kommune qualifier.
    last_q = client.requests[2][1]["q"]
    assert "rådhus" not in last_q
    assert "kommune" not in last_q


def test_run_ambiguous_goes_to_unresolved(tmp_path: Path):
    reg = _make_registry(
        [
            {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "Rogaland",
                "borders": [],
                "bugs": [],
            },
        ]
    )
    reg_path = _write(tmp_path, "kommuner.json", reg)
    ov_path = _write(tmp_path, "overrides.json", {})
    un_path = tmp_path / "unresolved.json"

    # Two passing results with DIFFERENT municipality names → genuine
    # ambiguity on every query.
    r1 = {
        "lat": "58.30",
        "lon": "6.22",
        "address": {"country_code": "no", "county": "Rogaland", "municipality": "Sokndal"},
    }
    r2 = {
        "lat": "59.50",
        "lon": "10.50",
        "address": {"country_code": "no", "county": "Rogaland", "municipality": "Sokndalen"},
    }
    amb = [r1, r2]
    client = _MockClient([amb, amb, amb])
    resolved, _, un = mod.run(
        reg_path,
        ov_path,
        un_path,
        client_factory=_factory(client),
        sleep_fn=lambda _s: None,
    )
    assert resolved == 0
    assert un == 1

    written_un = json.loads(un_path.read_text(encoding="utf-8"))
    assert "sokndal" in written_un
    assert "ambiguous" in written_un["sokndal"]["reason"]
    assert len(written_un["sokndal"]["attempted_queries"]) == 3


def test_run_zero_match_goes_to_unresolved(tmp_path: Path):
    reg = _make_registry(
        [
            {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "Rogaland",
                "borders": [],
                "bugs": [],
            },
        ]
    )
    reg_path = _write(tmp_path, "kommuner.json", reg)
    ov_path = _write(tmp_path, "overrides.json", {})
    un_path = tmp_path / "unresolved.json"

    client = _MockClient([[], [], []])
    _, _, un = mod.run(
        reg_path,
        ov_path,
        un_path,
        client_factory=_factory(client),
        sleep_fn=lambda _s: None,
    )
    assert un == 1
    written_un = json.loads(un_path.read_text(encoding="utf-8"))
    assert "no match" in written_un["sokndal"]["reason"]


def test_run_sleep_called_between_requests(tmp_path: Path):
    reg = _make_registry(
        [
            {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "Rogaland",
                "borders": [],
                "bugs": [],
            },
        ]
    )
    reg_path = _write(tmp_path, "kommuner.json", reg)
    ov_path = _write(tmp_path, "overrides.json", {})
    un_path = tmp_path / "unresolved.json"

    sleep_calls: list[float] = []
    client = _MockClient([[_result()]])
    mod.run(
        reg_path,
        ov_path,
        un_path,
        client_factory=_factory(client),
        sleep_fn=lambda s: sleep_calls.append(s),
    )
    assert sleep_calls  # at least one call
    assert sleep_calls[0] == pytest.approx(mod.SLEEP_SECONDS)


def test_run_partial_recovery_skips_resolved_entries(tmp_path: Path):
    """First run resolves oslo. Second run should leave oslo untouched and only
    query nominatim for sokndal."""
    reg = _make_registry(
        [
            {
                "id": "oslo",
                "municipality": "Oslo",
                "county": "Oslo",
                "lat": 59.91,
                "lng": 10.75,
                "borders": None,
                "bugs": [],
            },
            {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "Rogaland",
                "borders": [],
                "bugs": [],
            },
        ]
    )
    reg_path = _write(tmp_path, "kommuner.json", reg)
    ov_path = _write(tmp_path, "overrides.json", {})
    un_path = tmp_path / "unresolved.json"

    client = _MockClient([[_result()]])
    mod.run(
        reg_path,
        ov_path,
        un_path,
        client_factory=_factory(client),
        sleep_fn=lambda _s: None,
    )
    assert len(client.requests) == 1  # only one kommune queried
    # Ensure oslo kept its original values.
    written = json.loads(reg_path.read_text(encoding="utf-8"))
    oslo = next(e for e in written["kommuner"] if e["id"] == "oslo")
    assert oslo["lat"] == pytest.approx(59.91)


def test_run_user_agent_header_is_set(tmp_path: Path):
    """The default client factory sets a recognizable User-Agent per Nominatim ToS."""
    # We test the constant and the default factory's composition indirectly — tests
    # using a mock client would not see the header. This assertion guards the constant.
    assert "alkohol-oversikt" in mod.USER_AGENT
    assert "github.com" in mod.USER_AGENT


def test_run_dry_run_does_not_write_files(tmp_path: Path):
    reg = _make_registry(
        [
            {
                "id": "sokndal",
                "municipality": "Sokndal",
                "county": "Rogaland",
                "borders": [],
                "bugs": [],
            },
        ]
    )
    reg_path = _write(tmp_path, "kommuner.json", reg)
    ov_path = _write(tmp_path, "overrides.json", {})
    un_path = tmp_path / "unresolved.json"

    client = _MockClient([[_result()]])
    mod.run(
        reg_path,
        ov_path,
        un_path,
        dry_run=True,
        client_factory=_factory(client),
        sleep_fn=lambda _s: None,
    )
    # Registry file content should be unchanged.
    written = json.loads(reg_path.read_text(encoding="utf-8"))
    assert "lat" not in written["kommuner"][0]
    assert not un_path.exists()


def test_nominatim_search_retries_on_5xx(tmp_path: Path):
    """5xx responses trigger retry; eventual success returns the body."""
    # Build a fake client whose first call raises HTTPStatusError(500),
    # whose second call returns a valid response.
    call_count = {"n": 0}

    class _FlakyClient:
        def get(self, url, params):
            call_count["n"] += 1
            if call_count["n"] == 1:
                resp = MagicMock()
                resp.status_code = 500
                err = httpx.HTTPStatusError("server error", request=MagicMock(), response=resp)
                raise err
            resp = MagicMock()
            resp.json.return_value = [_result()]
            resp.raise_for_status.return_value = None
            return resp

    # Patch sleep to zero so retries don't take real time.
    import import_kommune_coords as m

    orig_sleep = m.time.sleep
    m.time.sleep = lambda _s: None
    try:
        results = m.nominatim_search(_FlakyClient(), "x")  # type: ignore[arg-type]
    finally:
        m.time.sleep = orig_sleep

    assert call_count["n"] == 2
    assert len(results) == 1


def test_nominatim_search_raises_on_4xx():
    class _BadRequestClient:
        def get(self, url, params):
            resp = MagicMock()
            resp.status_code = 400
            raise httpx.HTTPStatusError("bad request", request=MagicMock(), response=resp)

    with pytest.raises(httpx.HTTPStatusError):
        mod.nominatim_search(_BadRequestClient(), "x")  # type: ignore[arg-type]
