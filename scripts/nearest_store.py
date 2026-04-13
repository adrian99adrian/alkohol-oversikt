"""Nearest-Vinmonopolet computation for municipalities without a local store.

Pure build-time helpers. No I/O, no network. Consumed by
scripts/build_municipality.py when a kommune's `vinmonopolet_mode` is `nearest`.

Distance is straight-line (haversine) from the kommune's rådhus to each store's
`gpsCoord` — good enough for showing "~N km away", not navigation-grade.
"""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0


def _numeric_coord(value: object) -> float | None:
    """Return value as float if it is a finite int/float, else None.

    Rejects bool (which is a subtype of int in Python) and non-numeric types
    that would otherwise raise TypeError when passed to math operations.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    val = float(value)
    if math.isnan(val) or math.isinf(val):
        return None
    return val


def _numeric_store_id(store: dict) -> int:
    """Extract the numeric store id for deterministic tie-breaking.

    Non-numeric or missing ids sort after any real store id.
    """
    try:
        return int(store["store_id"])
    except (KeyError, ValueError):
        return 2**63 - 1


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


# Distances within this band of the minimum are treated as ties. 0.1 km
# is roughly the worst-case precision of a rådhus-coordinate → store-coordinate
# haversine, so anything inside it is within measurement noise.
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
    - Stores missing / non-numeric / non-finite `lat`/`lng` are skipped.
    - Kommuner with missing / non-numeric / non-finite coords return None
      (caller falls back to `fallback` mode rather than crashing the build).
    - Ties within 0.1 km are broken by lowest numeric `store_id`.

    Returns: {store, distance_km (rounded 1 decimal), source_municipality_id,
              source_municipality_name} or None.
    """
    k_lat = _numeric_coord(kommune_entry.get("lat"))
    k_lng = _numeric_coord(kommune_entry.get("lng"))
    if k_lat is None or k_lng is None:
        return None

    own_id = kommune_entry["id"]

    candidates: list[tuple[float, dict]] = []
    for store in all_stores:
        if store.get("municipality") == own_id:
            continue
        s_lat = _numeric_coord(store.get("lat"))
        s_lng = _numeric_coord(store.get("lng"))
        if s_lat is None or s_lng is None:
            continue
        candidates.append((haversine_km(k_lat, k_lng, s_lat, s_lng), store))

    if not candidates:
        return None

    # Tie-break rule: any candidate within _TIE_EPSILON_KM of the minimum
    # distance is treated as "tied" with it; among the tied, lowest numeric
    # `store_id` wins. Bucketing would be unreliable at bucket boundaries,
    # so we do it explicitly in two passes.
    min_distance = min(d for d, _ in candidates)
    best_distance, best_store = min(
        ((d, s) for d, s in candidates if d - min_distance <= _TIE_EPSILON_KM),
        key=lambda item: _numeric_store_id(item[1]),
    )

    source_id = best_store["municipality"]
    source_entry = kommune_registry.get(source_id, {})
    source_name = source_entry.get("municipality", source_id)

    return {
        "store": best_store,
        "distance_km": round(best_distance, 1),
        "source_municipality_id": source_id,
        "source_municipality_name": source_name,
    }
