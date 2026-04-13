"""Import rådhus coordinates for every kommune in data/reference/kommuner.json.

Uses Nominatim (OpenStreetMap) following its ToS: explicit User-Agent,
1.1s sleep between requests, local caching in the committed kommuner.json.

Idempotent: skips entries that already have lat/lng.

Resolution flow for entries without coordinates:
  1. kommune_coords_overrides.json takes precedence (always used if present).
  2. Nominatim query: "<municipality> rådhus, <county>, Norway".
  3. Fallback query: "<municipality> kommune, <county>, Norway".
  4. Each result is accepted only if all four rules pass:
     - country_code == "no"
     - address.county matches kommune.county (fuzzy, diacritic-normalized)
     - address.municipality/city/town matches kommune.municipality
     - lat/lng inside Norway's bounding box
  5. Exactly one passing result → accept. Zero or ≥2 → log to unresolved.json.

Unresolved entries require manual resolution via kommune_coords_overrides.json.

Usage:
    python scripts/import_kommune_coords.py
    python scripts/import_kommune_coords.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from geo_bounds import in_norway

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "alkohol-oversikt/1.0 (https://github.com/adrian99adrian/alkohol-oversikt)"
SLEEP_SECONDS = 1.1
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3


def normalize(text: str) -> str:
    """Lowercase + strip diacritics + collapse whitespace.

    Used for matching kommune names and counties against Nominatim results.
    """
    if not text:
        return ""
    # NFD then drop combining marks → "Ålesund" → "Alesund", "Ørsta" → "Orsta".
    # "ø"/"Ø" have no decomposition in Unicode, so handle them explicitly.
    text = text.replace("ø", "o").replace("Ø", "O")
    text = text.replace("æ", "ae").replace("Æ", "AE")
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


def names_match(expected: str, candidate: str) -> bool:
    """True if `expected` can be matched against `candidate`.

    Substring match in either direction so "Agder" matches "Agder fylke",
    "Sande" matches "Sande i Møre og Romsdal", and "Sande i Møre og Romsdal"
    matches "Sande" (Nominatim often strips disambiguation suffixes).

    Also splits on " i " (Norwegian kommune disambiguation pattern, e.g.
    "Herøy i Nordland") and accepts when the pre-suffix part matches.
    """
    if not expected or not candidate:
        return False
    norm_expected = normalize(expected)
    norm_candidate = normalize(candidate)
    if norm_expected in norm_candidate or norm_candidate in norm_expected:
        return True
    # Strip the Norwegian disambiguation suffix " i <fylke>" and retry.
    expected_base = norm_expected.split(" i ")[0]
    candidate_base = norm_candidate.split(" i ")[0]
    if expected_base and candidate_base:
        if expected_base == candidate_base:
            return True
        if expected_base in candidate_base or candidate_base in expected_base:
            return True
    return False


# Re-export the shared bounding-box check under the local name the rest of
# this module already uses.
coords_in_norway = in_norway


def result_passes(result: dict, kommune: dict) -> bool:
    """Apply the acceptance rules to a single Nominatim result.

    Rules:
    1. address.country_code == "no"
    2. address.municipality|city|town matches kommune["municipality"]
    3. address.county matches kommune["county"] (fuzzy) — OR, if the response
       has no county field (e.g., Oslo, which is its own state), the municipality
       match + country check are sufficient. state/region are also accepted as
       county fallbacks.
    4. lat, lng inside Norway bounding box
    """
    address = result.get("address", {})
    if address.get("country_code") != "no":
        return False

    # Municipality match is load-bearing — do it first.
    muni_candidate = address.get("municipality") or address.get("city") or address.get("town") or ""
    if not names_match(kommune["municipality"], muni_candidate):
        return False

    # County match: try county, state, region, in that order. If none of these
    # are present, the response describes a place where county/state are merged
    # (Oslo) — accept on the strength of the municipality+country match.
    county_candidates = [
        address.get(key, "") for key in ("county", "state", "region") if address.get(key)
    ]
    if county_candidates and not any(names_match(kommune["county"], c) for c in county_candidates):
        return False

    try:
        lat = float(result["lat"])
        lng = float(result["lon"])
    except (KeyError, ValueError, TypeError):
        return False
    if math.isnan(lat) or math.isnan(lng):
        return False
    return coords_in_norway(lat, lng)


def _same_admin_area(a: dict, b: dict) -> bool:
    """True if two results describe the same kommune.

    Since `result_passes` already checked that each candidate's municipality
    matches the queried kommune, any two results that both pass must refer
    to the same administrative area (either the kommune relation or a node
    within it). Ambiguity at this level is not real ambiguity — Nominatim
    just returns multiple representations of the same place.
    """
    addr_a = a.get("address", {})
    addr_b = b.get("address", {})
    muni_a = addr_a.get("municipality") or addr_a.get("city") or addr_a.get("town") or ""
    muni_b = addr_b.get("municipality") or addr_b.get("city") or addr_b.get("town") or ""
    return bool(muni_a) and normalize(muni_a) == normalize(muni_b)


def pick_unique_match(results: list[dict], kommune: dict) -> tuple[dict | None, str]:
    """Return (winner, reason). winner=None if 0 results pass.

    When multiple results pass and they all describe the same kommune (same
    municipality name), they are duplicates — the first is returned.
    Otherwise the result is ambiguous and rejected.

    reason is a short string explaining the outcome (used for unresolved.json).
    """
    passing = [r for r in results if result_passes(r, kommune)]
    if len(passing) == 0:
        return None, f"no match: {len(results)} candidate(s), 0 passed all rules"
    if len(passing) == 1:
        return passing[0], "accepted"

    if all(_same_admin_area(passing[0], p) for p in passing[1:]):
        return passing[0], f"accepted (deduped {len(passing)} co-kommune results)"

    return None, f"ambiguous: {len(passing)} of {len(results)} passed all rules"


def build_queries(kommune: dict) -> list[str]:
    """Build the ordered query strings for a kommune.

    Order: most-specific to least. Rådhus names a building; kommune names
    the administrative unit; bare name is the most forgiving fallback and
    is what Nominatim returns for most small Norwegian kommuner.
    """
    name = kommune["municipality"]
    county = kommune["county"]
    return [
        f"{name} rådhus, {county}, Norway",
        f"{name} kommune, {county}, Norway",
        f"{name}, {county}, Norway",
    ]


def nominatim_search(
    client: httpx.Client,
    query: str,
) -> list[dict]:
    """Call Nominatim search. Returns list of results (may be empty)."""
    params = {
        "q": query,
        "format": "json",
        "addressdetails": "1",
        "limit": "5",
    }
    for attempt in range(MAX_RETRIES):
        try:
            response = client.get(NOMINATIM_URL, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")  # pragma: no cover


def resolve_kommune(
    client: httpx.Client,
    kommune: dict,
    sleep_fn: Any = time.sleep,
) -> tuple[dict | None, list[str], str]:
    """Resolve a single kommune via Nominatim.

    Returns (coords_dict, attempted_queries, reason).
    coords_dict: {"lat": float, "lng": float} on success, None on failure.
    """
    attempted: list[str] = []
    reason = "no queries attempted"
    for query in build_queries(kommune):
        attempted.append(query)
        try:
            results = nominatim_search(client, query)
        except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
            reason = f"http error on {query!r}: {type(e).__name__}"
            sleep_fn(SLEEP_SECONDS)
            continue
        except (ValueError, json.JSONDecodeError) as e:
            reason = f"malformed JSON on {query!r}: {e}"
            sleep_fn(SLEEP_SECONDS)
            continue

        winner, reason = pick_unique_match(results, kommune)
        sleep_fn(SLEEP_SECONDS)
        if winner is not None:
            return (
                {"lat": float(winner["lat"]), "lng": float(winner["lon"])},
                attempted,
                reason,
            )
    return None, attempted, reason


# --- File I/O ---


def load_json(path: Path, default: Any) -> Any:
    """Load JSON from path, returning default if file is absent."""
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """Write JSON to path with stable formatting (2-space indent, utf-8)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def validate_override(kommune_id: str, override: dict) -> None:
    """Raise ValueError if an override entry is malformed or out of bounds."""
    if not isinstance(override, dict):
        raise ValueError(f"override for {kommune_id!r} must be an object")
    try:
        lat = float(override["lat"])
        lng = float(override["lng"])
    except (KeyError, ValueError, TypeError) as e:
        raise ValueError(f"override for {kommune_id!r} missing numeric lat/lng: {e}") from e
    if math.isnan(lat) or math.isnan(lng) or math.isinf(lat) or math.isinf(lng):
        raise ValueError(f"override for {kommune_id!r} has non-finite lat/lng")
    if not coords_in_norway(lat, lng):
        raise ValueError(
            f"override for {kommune_id!r} lat/lng ({lat}, {lng}) outside Norway bounds"
        )


# --- CLI ---


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def run(
    registry_path: Path,
    overrides_path: Path,
    unresolved_path: Path,
    *,
    dry_run: bool = False,
    client_factory: Any = None,
    sleep_fn: Any = time.sleep,
) -> tuple[int, int, int]:
    """Run the import. Returns (resolved_count, skipped_count, unresolved_count).

    client_factory is an optional callable returning an httpx.Client context
    manager; tests inject mocks. Defaults to a real client with proper headers.
    """
    registry = load_json(registry_path, default=None)
    if registry is None:
        raise FileNotFoundError(f"registry not found: {registry_path}")

    overrides = load_json(overrides_path, default={})
    # Validate every override up front so bad data fails fast.
    for kid, ov in overrides.items():
        validate_override(kid, ov)

    unresolved: dict[str, dict] = {}

    resolved = skipped = unresolved_count = 0

    def default_factory() -> httpx.Client:
        return httpx.Client(
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )

    factory = client_factory or default_factory

    with factory() as client:
        for entry in registry["kommuner"]:
            kid = entry["id"]
            # Only skip if BOTH coords are already populated AND non-null. A
            # half-written entry (lat set, lng null) would otherwise never be
            # retried, permanently leaving that kommune unresolvable.
            if entry.get("lat") is not None and entry.get("lng") is not None:
                skipped += 1
                continue
            if kid in overrides:
                entry["lat"] = float(overrides[kid]["lat"])
                entry["lng"] = float(overrides[kid]["lng"])
                resolved += 1
                continue

            coords, attempted, reason = resolve_kommune(client, entry, sleep_fn=sleep_fn)
            if coords is None:
                unresolved[kid] = {
                    "attempted_queries": attempted,
                    "reason": reason,
                    "timestamp": _now_iso(),
                }
                unresolved_count += 1
            else:
                entry["lat"] = coords["lat"]
                entry["lng"] = coords["lng"]
                resolved += 1

    if not dry_run:
        write_json(registry_path, registry)
        write_json(unresolved_path, unresolved)

    return resolved, skipped, unresolved_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Import kommune rådhus coordinates via Nominatim")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).parent.parent / "data",
        help="Path to data directory (default: data/)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write output files")
    args = parser.parse_args()

    reference_dir = args.data_dir / "reference"
    registry_path = reference_dir / "kommuner.json"
    overrides_path = reference_dir / "kommune_coords_overrides.json"
    unresolved_path = reference_dir / "kommune_coords_unresolved.json"

    resolved, skipped, unresolved_count = run(
        registry_path,
        overrides_path,
        unresolved_path,
        dry_run=args.dry_run,
    )

    print(
        f"resolved={resolved} skipped={skipped} unresolved={unresolved_count}"
        f" (unresolved logged to {unresolved_path.name})"
    )
    return 0 if unresolved_count == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
