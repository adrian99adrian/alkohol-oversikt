"""Nearest-Vinmonopolet computation for municipalities without a local store.

Pure build-time helpers. No I/O, no network. Consumed by
scripts/build_municipality.py when a kommune's `vinmonopolet_mode` is `nearest`.

Distance is straight-line (haversine) from the kommune's rådhus to each store's
`gpsCoord` — good enough for showing "~N km away", not navigation-grade.
"""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two WGS-84 points in kilometers.

    Pure function. Symmetric: haversine(a, b) == haversine(b, a).
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


_TIE_EPSILON_KM = 0.1


def find_nearest_store(
    kommune_entry: dict,
    all_stores: list[dict],
    kommune_registry: dict[str, dict],
) -> dict | None:
    """Return the nearest store to `kommune_entry`, or None if unresolvable.

    Determinism:
    - Stores whose own municipality == kommune_entry["id"] are excluded
      (defense in depth — mode logic should already prevent this path).
    - Stores missing `lat`/`lng` are skipped.
    - Ties within 0.1 km are broken by lowest numeric `store_id`.

    Returns: {store, distance_km (rounded 1 decimal), source_municipality_id,
              source_municipality_name} or None.
    """
    if "lat" not in kommune_entry or "lng" not in kommune_entry:
        return None

    k_lat = kommune_entry["lat"]
    k_lng = kommune_entry["lng"]
    own_id = kommune_entry["id"]

    candidates: list[tuple[float, dict]] = []
    for store in all_stores:
        if store.get("municipality") == own_id:
            continue
        lat = store.get("lat")
        lng = store.get("lng")
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            continue
        if isinstance(lat, bool) or isinstance(lng, bool):
            continue
        distance = haversine_km(k_lat, k_lng, float(lat), float(lng))
        candidates.append((distance, store))

    if not candidates:
        return None

    # Sort by (distance, numeric store_id) so ties within epsilon are
    # broken deterministically by lowest numeric id.
    def _sort_key(item: tuple[float, dict]) -> tuple[float, int]:
        distance, store = item
        try:
            numeric_id = int(store["store_id"])
        except (KeyError, ValueError):
            numeric_id = 2**63 - 1  # push malformed ids to the back
        return (distance, numeric_id)

    candidates.sort(key=_sort_key)
    best_distance, best_store = candidates[0]

    # Within the epsilon band, numeric id alone decides (not distance).
    tied = [(d, s) for d, s in candidates if d - best_distance <= _TIE_EPSILON_KM]
    if len(tied) > 1:

        def _numeric_id(item: tuple[float, dict]) -> int:
            try:
                return int(item[1]["store_id"])
            except (KeyError, ValueError):
                return 2**63 - 1

        tied.sort(key=_numeric_id)
        best_distance, best_store = tied[0]

    source_id = best_store["municipality"]
    source_entry = kommune_registry.get(source_id, {})
    source_name = source_entry.get("municipality", source_id)

    return {
        "store": best_store,
        "distance_km": round(best_distance, 1),
        "source_municipality_id": source_id,
        "source_municipality_name": source_name,
    }
