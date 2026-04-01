"""Vinmonopolet hour resolution for municipality data generation.

Resolves store hours for each day in a 14-day window by combining
actual_hours (from API, days 1-7) with standard_hours fallback (days 8-14).
"""

from datetime import date

# Day types where Vinmonopolet is always closed
_CLOSED_DAY_TYPES = {"sunday", "public_holiday"}

# Maps Python weekday() (0=Mon) to standard_hours keys
_WEEKDAY_KEYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def resolve_store_hours(store: dict, date_str: str, day_type: str) -> dict | None:
    """Resolve a single store's hours for a given date.

    Strategy:
    - If date is in actual_hours: use that (may be None for closed).
    - Else: look up weekday in standard_hours, but return None if the day
      is a public_holiday or Sunday.

    Returns {"open": "10:00", "close": "18:00"} or None (closed).
    """
    actual = store.get("actual_hours", {})
    if date_str in actual:
        return actual[date_str]

    # Fallback to standard_hours by weekday
    if day_type in _CLOSED_DAY_TYPES:
        return None

    d = date.fromisoformat(date_str)
    weekday_key = _WEEKDAY_KEYS[d.weekday()]
    return store.get("standard_hours", {}).get(weekday_key)


def summarize_vinmonopolet(stores: list[dict], date_str: str, day_type: str) -> str | None:
    """Generate a summary string for the table column.

    Returns:
    - None if no stores
    - "Stengt" if all stores closed
    - "10:00–18:00" if all open stores have the same hours
    - "10:00–17:00 / 10:00–18:00" if stores have different hours
    """
    if not stores:
        return None

    resolved = [resolve_store_hours(s, date_str, day_type) for s in stores]
    open_stores = [h for h in resolved if h is not None]

    if not open_stores:
        return "Stengt"

    unique_hours = sorted(
        {(h["open"], h["close"]) for h in open_stores},
        key=lambda x: x[1],
    )

    if len(unique_hours) == 1:
        o, c = unique_hours[0]
        return f"{o}\u2013{c}"

    return " / ".join(f"{o}\u2013{c}" for o, c in unique_hours)


def build_resolved_stores(stores: list[dict], calendar_days: list[dict]) -> list[dict]:
    """Build resolved store objects with 14-day hours for the municipality output.

    Each store gets a flat hours array with one entry per calendar day.
    """
    result = []
    for store in stores:
        hours = []
        for day in calendar_days:
            resolved = resolve_store_hours(store, day["date"], day["day_type"])
            hours.append(
                {
                    "date": day["date"],
                    "open": resolved["open"] if resolved else None,
                    "close": resolved["close"] if resolved else None,
                }
            )
        result.append(
            {
                "store_id": store["store_id"],
                "name": store["name"],
                "address": store["address"],
                "hours": hours,
            }
        )
    return result
