"""Schema sanity checks for data/reference/kommuner.json.

Reference registry of all Norwegian kommuner. Reference-only today, but
Phase 3 nearest-Vinmonopolet logic will read `borders`, so lock the
shape down now.
"""

import json
from pathlib import Path

import pytest

_PATH = Path(__file__).parent.parent.parent / "data" / "reference" / "kommuner.json"


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
    required = {"county", "municipality", "id", "borders", "bugs"}
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


def test_borders_shape(kommuner: list[dict]):
    for entry in kommuner:
        borders = entry["borders"]
        assert borders is None or isinstance(borders, list), (
            f"{entry['id']}: borders must be null or list, got {type(borders).__name__}"
        )
        if isinstance(borders, list):
            for neighbor in borders:
                assert isinstance(neighbor, str), f"{entry['id']}: borders entries must be strings"


def test_bugs_is_list(kommuner: list[dict]):
    for entry in kommuner:
        assert isinstance(entry["bugs"], list), f"{entry['id']}: bugs must be a list"
