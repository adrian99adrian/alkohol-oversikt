"""Norway geographic bounding box — single source of truth.

Used by the coordinate importer, the Vinmonopolet fetcher, the nearest-store
lookup, and the validator. Any coordinate outside this box is treated as
corrupt data, not a valid Norwegian location.

Chosen slightly generous so the Svalbard-free mainland plus fringe islands
(Utsira, Vardø) all pass without tweaking.
"""

LAT_MIN = 57.0
LAT_MAX = 72.0
LNG_MIN = 4.0
LNG_MAX = 32.0


def in_norway(lat: float, lng: float) -> bool:
    """True if (lat, lng) is inside the Norway bounding box (inclusive)."""
    return LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX
