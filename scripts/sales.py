"""Beer sales time calculation.

Provides functions to compute national maximum closing times, municipal closing
times, and the final min(national, municipal) result for any day/municipality
combination.
"""

from datetime import date

from build_calendar import WEEKDAY_NAMES_NO

# Day types where beer sale is forbidden
_FORBIDDEN_DAY_TYPES = {"sunday", "public_holiday"}


def national_max(day_info: dict) -> str | None:
    """Return the national maximum closing time for a day.

    Returns None if sale is forbidden (Sunday, public holiday).
    """
    day_type = day_info["day_type"]

    if day_type in _FORBIDDEN_DAY_TYPES:
        return None
    if day_type == "weekday":
        return "20:00"
    # Saturday, pre_holiday, and special_day all have 18:00 national max
    return "18:00"


def municipal_close(day_info: dict, municipality: dict) -> str | None:
    """Return the municipal closing time for a day.

    Considers the municipality's specific rules including special days
    and exceptions (e.g., Larvik's pre-Ascension exception).

    Returns None if sale is forbidden.
    """
    day_type = day_info["day_type"]
    beer = municipality["beer_sales"]

    if day_type in _FORBIDDEN_DAY_TYPES:
        return None

    # Check if this is a special day that THIS municipality recognizes
    if day_info["is_special_day"] and day_info["special_day_key"] in beer.get("special_days", []):
        return beer["special_day_close"]

    # Check for exceptions (e.g., Larvik pre-Ascension Day)
    if day_type == "pre_holiday":
        if _has_weekday_exception(day_info, municipality):
            return beer["weekday_close"]
        return beer["pre_holiday_close"]

    if day_type == "saturday":
        return beer["saturday_close"]

    # Unrecognized special day — fall back based on actual weekday
    if day_info["is_special_day"] and day_info.get("is_pre_holiday"):
        if day_info.get("_is_saturday"):
            return beer["saturday_close"]
        return beer["pre_holiday_close"]

    # weekday
    return beer["weekday_close"]


def municipal_open(day_info: dict, municipality: dict) -> str | None:
    """Return the municipal opening time for a day.

    Returns None if sale is forbidden.
    """
    day_type = day_info["day_type"]
    beer = municipality["beer_sales"]

    if day_type in _FORBIDDEN_DAY_TYPES:
        return None

    if day_type == "saturday":
        return beer["saturday_open"]

    # Special days: use saturday_open if on Saturday, else weekday_open
    if day_info["is_special_day"]:
        return beer["saturday_open"] if day_info.get("_is_saturday") else beer["weekday_open"]

    # weekday, pre_holiday
    return beer["weekday_open"]


def closing_time(day_info: dict, municipality: dict) -> str | None:
    """Calculate final closing time: min(national_max, municipal_close).

    When a municipality exception overrides a pre-holiday to weekday rules,
    the national weekday max (20:00) is used instead of the pre-holiday max (18:00).

    Returns None if sale is forbidden.
    """
    mun = municipal_close(day_info, municipality)

    if mun is None:
        return None

    # Check if a municipality exception upgraded this to weekday rules
    nat = national_max(day_info)
    if nat is None:
        return None

    if day_info["day_type"] == "pre_holiday" and _has_weekday_exception(day_info, municipality):
        nat = "20:00"  # Use weekday national max

    return min(nat, mun)


def _has_weekday_exception(day_info: dict, municipality: dict) -> bool:
    """Check if the municipality has a weekday exception for this pre-holiday."""
    beer = municipality["beer_sales"]
    exceptions = beer.get("exceptions", {})
    pre_for = day_info.get("pre_holiday_for")
    if pre_for:
        exception_key = f"pre_{pre_for}"
        return exceptions.get(exception_key) == "weekday"
    return False


def large_store_close(day_info: dict, municipality: dict) -> str | None:
    """Return the large-store closing time, if applicable.

    Only returns a value for municipalities with a large_store_special_days
    rule, and only on the specific special days listed.

    Returns None for all other cases.
    """
    beer = municipality["beer_sales"]

    if "large_store_special_days" not in beer:
        return None

    if not day_info["is_special_day"]:
        return None

    special_key = day_info.get("special_day_key")
    if special_key in beer["large_store_special_days"]:
        return beer["special_day_close_large_stores"]

    return None


def build_day_entry(d: date, day_info: dict, municipality: dict) -> dict:
    """Build a complete day entry for the generated municipality JSON.

    Returns a dict matching the output contract.
    """
    # Enrich day_info with date context for municipal_close fallback logic
    enriched = {**day_info, "date": d.isoformat(), "_is_saturday": d.weekday() == 5}

    sale_allowed = enriched["day_type"] not in _FORBIDDEN_DAY_TYPES
    close = closing_time(enriched, municipality) if sale_allowed else None
    beer_open = municipal_open(enriched, municipality) if sale_allowed else None
    ls_close = large_store_close(enriched, municipality)

    is_deviation = enriched["day_type"] != "weekday"

    # Build comment
    comment = _build_comment(enriched, municipality, close, ls_close)

    return {
        "date": d.isoformat(),
        "weekday": WEEKDAY_NAMES_NO[d.weekday()],
        "day_type": enriched["day_type"],
        "day_type_label": enriched["day_type_label"],
        "beer_sale_allowed": sale_allowed,
        "beer_open": beer_open,
        "beer_close": close,
        "beer_close_large_stores": ls_close,
        "is_deviation": is_deviation,
        "comment": comment,
    }


def _build_comment(
    day_info: dict,
    municipality: dict,
    close: str | None,
    ls_close: str | None,
) -> str | None:
    """Build a Norwegian comment for deviation days."""
    day_type = day_info["day_type"]

    if day_type == "weekday":
        return None

    if day_type in _FORBIDDEN_DAY_TYPES:
        label = day_info["day_type_label"]
        return f"{label} – salg av øl er ikke tillatt"

    parts = []
    label = day_info["day_type_label"]

    if close:
        parts.append(f"{label} – ølsalg stenger kl. {close}")

    if ls_close:
        threshold = municipality["beer_sales"].get("large_store_threshold_sqm", 100)
        parts.append(f"Butikker over {threshold} m² stenger kl. {ls_close}")

    return ". ".join(parts) if parts else label
