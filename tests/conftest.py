"""Shared pytest fixtures for all test modules."""

import json
import sys
from pathlib import Path

import pytest

# Add scripts/ to sys.path so test files can import pipeline modules directly
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def _make_opening_time(
    date_str: str,
    *,
    closed: bool = False,
    open_h: int = 10,
    open_m: int = 0,
    close_h: int = 18,
    close_m: int = 0,
    weekday: str = "",
) -> dict:
    """Build a single openingTimes entry matching the Vinmonopolet API shape."""
    entry: dict = {
        "date": f"{date_str}T00:00:00+02:00",
        "closed": closed,
        "weekDay": weekday,
    }
    if not closed:
        entry["openingTime"] = {
            "formattedHour": f"{open_h:02d}:{open_m:02d}",
            "hour": open_h,
            "minute": open_m,
        }
        entry["closingTime"] = {
            "formattedHour": f"{close_h:02d}:{close_m:02d}",
            "hour": close_h,
            "minute": close_m,
        }
    return entry


@pytest.fixture
def project_root() -> Path:
    """Return the repo root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def sample_municipality_sandefjord(project_root: Path) -> dict:
    """Load Sandefjord municipality JSON."""
    path = project_root / "data" / "municipalities" / "sandefjord.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_municipality_larvik(project_root: Path) -> dict:
    """Load Larvik municipality JSON."""
    path = project_root / "data" / "municipalities" / "larvik.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_municipality_oslo(project_root: Path) -> dict:
    """Load Oslo municipality JSON."""
    path = project_root / "data" / "municipalities" / "oslo.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_municipality_trondheim(project_root: Path) -> dict:
    """Load Trondheim municipality JSON."""
    path = project_root / "data" / "municipalities" / "trondheim.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_municipality_bamble(project_root: Path) -> dict:
    """Load Bamble municipality JSON (has pre_labour_day + pre_constitution_day exceptions)."""
    path = project_root / "data" / "municipalities" / "bamble.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_municipality_bergen(project_root: Path) -> dict:
    """Load Bergen municipality JSON."""
    path = project_root / "data" / "municipalities" / "bergen.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_municipality_stavanger(project_root: Path) -> dict:
    """Load Stavanger municipality JSON."""
    path = project_root / "data" / "municipalities" / "stavanger.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def all_municipalities(project_root: Path) -> list[dict]:
    """Load all municipality JSON files from data/municipalities/."""
    municipalities_dir = project_root / "data" / "municipalities"
    result = []
    for path in sorted(municipalities_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            result.append(json.load(f))
    return result


# --- Vinmonopolet API fixtures ---


@pytest.fixture
def sample_opening_times_normal() -> list[dict]:
    """7 normal weekdays (Mon 2026-03-30 to Sun 2026-04-05) with no holidays.

    Uses a hypothetical normal week: Mon-Fri 10-18, Sat 10-15, Sun closed.
    """
    return [
        _make_opening_time("2026-03-30", open_h=10, close_h=18, weekday="Mandag"),
        _make_opening_time("2026-03-31", open_h=10, close_h=18, weekday="Tirsdag"),
        _make_opening_time("2026-04-01", open_h=10, close_h=18, weekday="Onsdag"),
        _make_opening_time("2026-04-02", open_h=10, close_h=18, weekday="Torsdag"),
        _make_opening_time("2026-04-03", open_h=10, close_h=18, weekday="Fredag"),
        _make_opening_time("2026-04-04", open_h=10, close_h=15, weekday="Lørdag"),
        _make_opening_time("2026-04-05", closed=True, weekday="Søndag"),
    ]


@pytest.fixture
def sample_opening_times_easter() -> list[dict]:
    """7 days during Easter 2026 (Tue Mar 31 - Mon Apr 6).

    Tue: normal, Wed: reduced (pre-holiday), Thu-Fri: closed (holidays),
    Sat: reduced (easter eve), Sun: closed, Mon: closed (2. påskedag).
    """
    return [
        _make_opening_time("2026-03-31", open_h=10, close_h=18, weekday="Tirsdag"),
        _make_opening_time("2026-04-01", open_h=10, close_h=16, weekday="Onsdag"),
        _make_opening_time("2026-04-02", closed=True, weekday="Torsdag"),
        _make_opening_time("2026-04-03", closed=True, weekday="Fredag"),
        _make_opening_time("2026-04-04", open_h=10, close_h=15, weekday="Lørdag"),
        _make_opening_time("2026-04-05", closed=True, weekday="Søndag"),
        _make_opening_time("2026-04-06", closed=True, weekday="Mandag"),
    ]


@pytest.fixture
def sample_special_opening_times_easter() -> list[dict]:
    """Special opening times for Easter 2026 (deviations from normal week)."""
    return [
        _make_opening_time("2026-04-01", open_h=10, close_h=16, weekday="Onsdag"),
        _make_opening_time("2026-04-02", closed=True, weekday="Torsdag"),
        _make_opening_time("2026-04-03", closed=True, weekday="Fredag"),
        _make_opening_time("2026-04-04", open_h=10, close_h=15, weekday="Lørdag"),
        _make_opening_time("2026-04-06", closed=True, weekday="Mandag"),
    ]


@pytest.fixture
def sample_api_store(
    sample_opening_times_normal,
) -> dict:
    """A single store dict as returned by the Vinmonopolet API (normal week)."""
    return {
        "name": "283",
        "displayName": "Sandefjord",
        "address": {
            "line1": "Museumsgata 2",
            "postalCode": "3210",
            "town": "Sandefjord",
            "country": {"isocode": "NO", "name": "Norway"},
        },
        "geoPoint": {"latitude": 59.1333, "longitude": 10.2167},
        "openingTimes": sample_opening_times_normal,
        "specialOpeningTimes": [],
    }


@pytest.fixture
def sample_api_store_easter(
    sample_opening_times_easter,
    sample_special_opening_times_easter,
) -> dict:
    """A store during Easter week (with special opening times)."""
    return {
        "name": "283",
        "displayName": "Sandefjord",
        "address": {
            "line1": "Museumsgata 2",
            "postalCode": "3210",
            "town": "Sandefjord",
            "country": {"isocode": "NO", "name": "Norway"},
        },
        "geoPoint": {"latitude": 59.1333, "longitude": 10.2167},
        "openingTimes": sample_opening_times_easter,
        "specialOpeningTimes": sample_special_opening_times_easter,
    }


@pytest.fixture
def sample_api_response(sample_api_store) -> dict:
    """A full single-page API response with one store."""
    return {
        "pagination": {
            "currentPage": 0,
            "pageSize": 100,
            "totalPages": 1,
            "totalResults": 1,
        },
        "stores": [sample_api_store],
    }
