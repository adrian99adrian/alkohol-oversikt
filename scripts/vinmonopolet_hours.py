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


def summarize_vinmonopolet(stores: list[dict], date_str: str, day_type: str) -> dict | None:
    """Generate a summary dict for the DayCard and table display.

    Returns:
    - None if no stores
    - {"type": "closed", ...} if all stores closed
    - {"type": "uniform", ...} if all open stores have the same hours
    - {"type": "range", ...} if open stores have different hours
    """
    if not stores:
        return None

    resolved = [resolve_store_hours(s, date_str, day_type) for s in stores]
    open_hours = [h for h in resolved if h is not None]
    open_count = len(open_hours)
    closed_count = len(resolved) - open_count

    if not open_hours:
        return {"type": "closed", "open_count": 0, "closed_count": closed_count}

    unique_hours = {(h["open"], h["close"]) for h in open_hours}

    if len(unique_hours) == 1:
        o, c = next(iter(unique_hours))
        return {
            "type": "uniform",
            "open": o,
            "close": c,
            "open_count": open_count,
            "closed_count": closed_count,
        }

    open_times = sorted(h["open"] for h in open_hours)
    close_times = sorted(h["close"] for h in open_hours)
    return {
        "type": "range",
        "min_open": open_times[0],
        "max_open": open_times[-1],
        "min_close": close_times[0],
        "max_close": close_times[-1],
        "open_count": open_count,
        "closed_count": closed_count,
    }


def build_day_summaries(stores: list[dict], calendar_days: list[dict]) -> list[dict | None]:
    """Build aggregated day-level summaries for the 14-day window.

    Returns one summary dict (or None) per calendar day, with the date included.
    """
    result = []
    for day in calendar_days:
        summary = summarize_vinmonopolet(stores, day["date"], day["day_type"])
        if summary is not None:
            summary["date"] = day["date"]
        result.append(summary)
    return result


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
