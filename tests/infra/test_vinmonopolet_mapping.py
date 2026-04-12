"""Regression tests pinning the Vinmonopolet store → kommune mapping.

The mapping is driven by `data/town_municipality_map.json` + a fallback on
`address.town` lowercasing. Silent drift would happen if:
  - The Vinmonopolet API renames a town field (e.g. "Fosnavåg" → "Herøy")
  - Someone edits the override map and accidentally collapses two kommuner
  - A new store opens in a kommune we don't track

These tests lock in the current state so any of the above trips CI instead
of quietly mis-routing stores.
"""

import json
from pathlib import Path

import pytest

_VMP_PATH = Path(__file__).parent.parent.parent / "data" / "generated" / "vinmonopolet.json"


@pytest.fixture(scope="module")
def vmp() -> dict:
    assert _VMP_PATH.exists(), f"{_VMP_PATH} missing — run scripts/fetch_vinmonopolet.py"
    with open(_VMP_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def stores_by_name(vmp: dict) -> dict:
    return {s["name"]: s for s in vmp["stores"]}


def test_zero_unmapped_stores(vmp: dict):
    """Every Vinmonopolet store must resolve to a kommune.

    If the API renames a town field or opens a store in a kommune we don't
    track, this count becomes non-zero and CI fails.
    """
    unmapped = [s for s in vmp["stores"] if not s.get("municipality")]
    names = [s["name"] for s in unmapped]
    assert len(unmapped) == 0, f"{len(unmapped)} stores unmapped: {names[:10]}"


def test_two_heroy_kommuner_do_not_collapse(stores_by_name: dict):
    """The two 'Herøy' kommuner must map to distinct ids.

    Herøy i Nordland (store 'Herøy', postcode 8850) and Herøy i Møre og
    Romsdal (store 'Fosnavåg', postcode 6090) share a name. If the API
    ever normalizes the M&R store's address.town to just 'Herøy', both
    stores would silently collapse onto heroy-i-nordland.
    """
    heroy_nord = stores_by_name.get("Herøy")
    fosnavag = stores_by_name.get("Fosnavåg")
    assert heroy_nord, "'Herøy' store missing from vinmonopolet.json"
    assert fosnavag, "'Fosnavåg' store missing from vinmonopolet.json"
    assert heroy_nord["municipality"] == "heroy-i-nordland"
    assert fosnavag["municipality"] == "heroy-i-more-og-romsdal"


def test_two_bo_kommuner_do_not_collapse(stores_by_name: dict):
    """Bø i Nordland (still a kommune) vs Bø i Telemark (merged into Midt-Telemark)."""
    bo_telemark = stores_by_name.get("Bø i Telemark")
    bo_vesteralen = stores_by_name.get("Bø i Vesterålen")
    assert bo_telemark, "'Bø i Telemark' store missing"
    assert bo_vesteralen, "'Bø i Vesterålen' store missing"
    assert bo_telemark["municipality"] == "midt-telemark"
    assert bo_vesteralen["municipality"] == "bo-i-nordland"


# Post-2020 merger mappings that are easy to get subtly wrong. If any of
# these regress, users of the merged-into kommune lose a store from their page.
MERGER_PINS = [
    # (store name, expected kommune id, merger note)
    ("Krokstadelva", "drammen", "Nedre Eiker → Drammen (2020)"),
    ("Svelvik", "drammen", "Svelvik → Drammen (2020)"),
    ("Sætre", "asker", "Hurum → Asker (2020)"),
    ("Tofte", "asker", "Hurum → Asker (2020)"),
    ("Slemmestad", "asker", "Røyken → Asker (2020)"),
    ("Ski", "nordre-follo", "Ski → Nordre Follo (2020)"),
    ("Kolbotn", "nordre-follo", "Oppegård → Nordre Follo (2020)"),
    ("Sørumsand", "lillestrom", "Sørum → Lillestrøm (2020)"),
    ("Fetsund", "lillestrom", "Fet → Lillestrøm (2020)"),
    ("Skedsmokorset", "lillestrom", "Skedsmo → Lillestrøm (2020)"),
    ("Bjugn", "orland", "Bjugn → Ørland (2020)"),
    ("Brekstad", "orland", "Ørland seat"),
    ("Mandal", "lindesnes", "Mandal → Lindesnes (2020)"),
    ("Søgne", "kristiansand", "Søgne → Kristiansand (2020)"),
    ("Stokke", "sandefjord", "Stokke → Sandefjord (2017)"),
    ("Andebu", "sandefjord", "Andebu → Sandefjord (2017)"),
    ("Sande", "holmestrand", "Sande (VF) → Holmestrand (2020); town=Sande I Vestfold"),
    ("Nøtterøy", "faerder", "Nøtterøy → Færder (2020)"),
    ("Tjøme", "faerder", "Tjøme → Færder (2020)"),
    ("Eikelandsosen", "bjornafjorden", "Fusa → Bjørnafjorden (2020)"),
    ("Radøy", "alver", "Radøy → Alver (2020); store kept Radøy name, town=Manger"),
    ("Digerneset", "alesund", "Skodje → Ålesund (2020); town=Skodje"),
    ("Førde", "sunnfjord", "Førde → Sunnfjord (2020)"),
    ("Florø", "kinn", "Flora → Kinn (2020)"),
    ("Måløy", "kinn", "Vågsøy → Kinn (2020)"),
    ("Rosendal", "kvinnherad", "Kvinnherad (the motivating example)"),
    ("Husnes", "kvinnherad", "Kvinnherad"),
    ("Trondheim, City Syd", "trondheim", "Trondheim district store; town=Tiller"),
    ("Trondheim, Heimdal", "trondheim", "Trondheim district store; town=Heimdal"),
    ("Sola, Tananger", "sola", "Sola district store; town=Tananger"),
    ("Odda", "ullensvang", "Odda → Ullensvang (2020)"),
    ("Orkanger", "orkland", "Orkland merger (2020)"),
    ("Rissa", "indre-fosen", "Rissa → Indre Fosen (2018)"),
]


@pytest.mark.parametrize("store_name,expected_kommune,_note", MERGER_PINS)
def test_merger_mapping_pinned(
    stores_by_name: dict,
    store_name: str,
    expected_kommune: str,
    _note: str,
):
    """Post-2020 merger mappings — each store must still route to the correct kommune."""
    store = stores_by_name.get(store_name)
    assert store is not None, f"'{store_name}' store missing from vinmonopolet.json"
    assert store["municipality"] == expected_kommune, (
        f"{store_name!r}: expected {expected_kommune!r}, got {store['municipality']!r}"
    )
