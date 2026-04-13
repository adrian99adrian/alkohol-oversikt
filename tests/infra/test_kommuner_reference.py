"""Schema sanity checks for data/reference/kommuner.json.

Reference registry of all Norwegian kommuner. Consumed by the nearest-
Vinmonopolet UX via `lat`/`lng`.
"""

import json
import math
from pathlib import Path

import pytest

_REFERENCE_DIR = Path(__file__).parent.parent.parent / "data" / "reference"
_PATH = _REFERENCE_DIR / "kommuner.json"
_OVERRIDES_PATH = _REFERENCE_DIR / "kommune_coords_overrides.json"
_UNRESOLVED_PATH = _REFERENCE_DIR / "kommune_coords_unresolved.json"

# Norway bounding box (match importer constants).
_LAT_MIN, _LAT_MAX = 57.0, 72.0
_LNG_MIN, _LNG_MAX = 4.0, 32.0


@pytest.fixture(scope="module")
def registry() -> dict:
    assert _PATH.exists(), f"{_PATH} is missing"
    with open(_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def kommuner(registry: dict) -> list[dict]:
    return registry["kommuner"]


def test_top_level_shape(registry: dict):
    assert "_schema" in registry
    assert "kommuner" in registry
    assert isinstance(registry["kommuner"], list)


def test_non_empty(kommuner: list[dict]):
    assert len(kommuner) > 0


def test_required_keys_per_entry(kommuner: list[dict]):
    required = {"county", "municipality", "id", "bugs"}
    for entry in kommuner:
        missing = required - entry.keys()
        assert not missing, f"{entry.get('id', '?')}: missing {missing}"


def test_county_and_municipality_are_non_empty_strings(kommuner: list[dict]):
    for entry in kommuner:
        for key in ("county", "municipality"):
            value = entry[key]
            assert isinstance(value, str) and value, (
                f"{entry['id']}: {key} must be a non-empty string, got {value!r}"
            )


def test_ids_are_unique(kommuner: list[dict]):
    ids = [e["id"] for e in kommuner]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate ids: {dupes}"


def test_ids_are_ascii_slugs(kommuner: list[dict]):
    for entry in kommuner:
        id_ = entry["id"]
        assert id_.islower(), f"{id_}: id must be lowercase"
        assert id_.isascii(), f"{id_}: id must be ASCII"
        assert " " not in id_, f"{id_}: id must not contain spaces"


def test_bugs_is_list(kommuner: list[dict]):
    for entry in kommuner:
        assert isinstance(entry["bugs"], list), f"{entry['id']}: bugs must be a list"


def test_lat_lng_present_and_valid(kommuner: list[dict]):
    """Every kommune must have numeric lat/lng inside Norway's bounding box.

    The nearest-Vinmonopolet UX depends on this — missing or bogus coordinates
    would collapse affected municipalities to the fallback Maps link.
    """
    for entry in kommuner:
        kid = entry["id"]
        assert "lat" in entry, f"{kid}: missing lat"
        assert "lng" in entry, f"{kid}: missing lng"
        lat = entry["lat"]
        lng = entry["lng"]
        assert isinstance(lat, (int, float)) and not isinstance(lat, bool), (
            f"{kid}: lat must be numeric, got {type(lat).__name__}"
        )
        assert isinstance(lng, (int, float)) and not isinstance(lng, bool), (
            f"{kid}: lng must be numeric, got {type(lng).__name__}"
        )
        assert not math.isnan(lat) and not math.isinf(lat), f"{kid}: lat is non-finite"
        assert not math.isnan(lng) and not math.isinf(lng), f"{kid}: lng is non-finite"
        assert _LAT_MIN <= lat <= _LAT_MAX, f"{kid}: lat {lat} outside Norway bounds"
        assert _LNG_MIN <= lng <= _LNG_MAX, f"{kid}: lng {lng} outside Norway bounds"


def test_unresolved_is_empty():
    """kommune_coords_unresolved.json on main must be explicitly empty.

    Any non-empty entry means a kommune could not be geocoded and needs a
    manual override in kommune_coords_overrides.json.
    """
    assert _UNRESOLVED_PATH.exists(), f"{_UNRESOLVED_PATH} is missing"
    with open(_UNRESOLVED_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert data == {}, f"unresolved entries: {sorted(data.keys())}"


def test_overrides_file_is_valid_json():
    """Override file must be parseable JSON (fails pre-commit, not runtime)."""
    assert _OVERRIDES_PATH.exists(), f"{_OVERRIDES_PATH} is missing"
    with open(_OVERRIDES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)


def test_overrides_coords_in_bounds():
    """Every override entry must have numeric lat/lng in Norway bounds."""
    with open(_OVERRIDES_PATH, encoding="utf-8") as f:
        overrides = json.load(f)
    for kid, entry in overrides.items():
        assert isinstance(entry, dict), f"override {kid}: must be an object"
        assert "lat" in entry and "lng" in entry, f"override {kid}: missing lat/lng"
        lat, lng = entry["lat"], entry["lng"]
        assert isinstance(lat, (int, float)) and not isinstance(lat, bool), (
            f"override {kid}: lat must be numeric"
        )
        assert isinstance(lng, (int, float)) and not isinstance(lng, bool), (
            f"override {kid}: lng must be numeric"
        )
        assert _LAT_MIN <= lat <= _LAT_MAX, f"override {kid}: lat {lat} out of bounds"
        assert _LNG_MIN <= lng <= _LNG_MAX, f"override {kid}: lng {lng} out of bounds"
