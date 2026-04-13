"""Validate all generated data for consistency and completeness.

Usage:
    python scripts/validate_data.py

Returns exit code 0 on success, 1 on failure.
"""

import json
import math
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from geo_bounds import LAT_MAX as _NORWAY_LAT_MAX
from geo_bounds import LAT_MIN as _NORWAY_LAT_MIN
from geo_bounds import LNG_MAX as _NORWAY_LNG_MAX
from geo_bounds import LNG_MIN as _NORWAY_LNG_MIN

REQUIRED_MUNICIPALITY_FIELDS = [
    "id",
    "name",
    "county",
    "beer_sales",
    "sources",
    "last_verified",
    "verified",
]
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REQUIRED_BEER_SALES_FIELDS = [
    "weekday_open",
    "weekday_close",
    "saturday_open",
    "saturday_close",
    "pre_holiday_close",
    "special_day_close",
    "special_days",
]

_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_MMDD_RE = re.compile(r"^\d{2}-\d{2}$")
_ALLOWED_DATE_OVERRIDE_HOURS = {"saturday", "pre_holiday"}
_ALLOWED_PRE_EASTER_WEEK = {"pre_holiday"}


def _is_real_mmdd(mmdd: str) -> bool:
    """True when MM-DD is a real calendar day (rejects 02-30, 13-01, 00-00 etc.).

    Uses a leap year so Feb 29 remains valid — otherwise a kommune couldn't
    pin a date_override to leap day if they ever needed to.
    """
    try:
        month, day = mmdd.split("-")
        date(2024, int(month), int(day))
    except (ValueError, TypeError):
        return False
    return True


# National max closing times. pre_holiday can be overridden to weekday (20:00)
# by municipal exceptions, so we allow up to 20:00 for pre_holiday.
NATIONAL_MAX = {
    "weekday": "20:00",
    "saturday": "18:00",
    "pre_holiday": "20:00",  # Allows municipal exceptions (e.g., Larvik Ascension)
    "special_day": "18:00",
}

_JSON_GLOB = "*.json"


def _check_required_fields(data: dict) -> list[str]:
    return [f"Missing required field: {f}" for f in REQUIRED_MUNICIPALITY_FIELDS if f not in data]


def _check_beer_sales_fields(data: dict) -> list[str]:
    if "beer_sales" not in data:
        return []
    beer = data["beer_sales"]
    return [f"Missing beer_sales field: {f}" for f in REQUIRED_BEER_SALES_FIELDS if f not in beer]


def _check_verified_invariants(data: dict) -> list[str]:
    """Enforce: verified is boolean, and last_verified is YYYY-MM-DD iff verified is true."""
    if "verified" not in data:
        return []
    verified = data["verified"]
    if not isinstance(verified, bool):
        return [f"verified must be boolean, got {type(verified).__name__}"]
    if "last_verified" not in data:
        return []
    lv = data["last_verified"]
    if verified and not (isinstance(lv, str) and _DATE_RE.match(lv)):
        return ["last_verified must be YYYY-MM-DD string when verified is true"]
    if not verified and lv is not None:
        return ["last_verified must be null when verified is false"]
    return []


def _check_optional_beer_sales_fields(data: dict) -> list[str]:
    """Validate shape of the optional schema-extension fields on beer_sales.

    All fields are optional; if present, they must be well-formed.
    """
    if "beer_sales" not in data:
        return []
    beer = data["beer_sales"]
    errors: list[str] = []

    if "special_day_open" in beer:
        val = beer["special_day_open"]
        if not isinstance(val, str) or not _HHMM_RE.match(val):
            errors.append("special_day_open must be HH:MM string")

    exceptions = beer.get("exceptions")
    if isinstance(exceptions, dict) and "pre_easter_week" in exceptions:
        val = exceptions["pre_easter_week"]
        if val not in _ALLOWED_PRE_EASTER_WEEK:
            errors.append(
                f"exceptions.pre_easter_week must be one of {sorted(_ALLOWED_PRE_EASTER_WEEK)}, "
                f"got {val!r}"
            )

    if "date_overrides" in beer:
        errors.extend(_validate_date_overrides(beer["date_overrides"]))

    return errors


def _validate_date_override_date(entry: dict, idx: int, seen: set[str]) -> list[str]:
    """Validate the `date` field of one date_overrides entry.

    Impossible dates (e.g. 02-30, 13-01) match the MM-DD regex but never match
    a real calendar date, which would silently drop the intended override —
    so they're rejected at validation time rather than shipping as a no-op.
    """
    d = entry.get("date")
    if not isinstance(d, str) or not _MMDD_RE.match(d):
        return [f"date_overrides[{idx}].date must be MM-DD string"]
    if not _is_real_mmdd(d):
        return [f"date_overrides[{idx}].date {d!r} is not a real calendar date"]
    if d in seen:
        return [f"date_overrides[{idx}].date duplicate {d!r}"]
    seen.add(d)
    return []


def _validate_date_override_hours(entry: dict, idx: int) -> list[str]:
    """Validate the `hours` field of one date_overrides entry."""
    if "hours" not in entry:
        return [f"date_overrides[{idx}].hours is required"]
    hours = entry["hours"]
    if hours not in _ALLOWED_DATE_OVERRIDE_HOURS:
        return [
            f"date_overrides[{idx}].hours must be one of "
            f"{sorted(_ALLOWED_DATE_OVERRIDE_HOURS)}, got {hours!r}"
        ]
    return []


def _validate_date_overrides(overrides: object) -> list[str]:
    """Each entry must be {date: MM-DD (real calendar day), hours: saturday|pre_holiday}."""
    if not isinstance(overrides, list):
        return ["date_overrides must be a list"]
    errors: list[str] = []
    seen_dates: set[str] = set()
    for i, entry in enumerate(overrides):
        if not isinstance(entry, dict):
            errors.append(f"date_overrides[{i}] must be an object")
            continue
        errors.extend(_validate_date_override_date(entry, i, seen_dates))
        errors.extend(_validate_date_override_hours(entry, i))
    return errors


def _check_notes(data: dict) -> list[str]:
    if "notes" not in data:
        return []
    if not isinstance(data["notes"], str):
        return ["notes must be a string when present"]
    return []


def validate_municipality_schema(data: dict) -> list[str]:
    """Validate a municipality JSON file. Returns list of errors."""
    errors = _check_required_fields(data)
    errors.extend(_check_beer_sales_fields(data))
    errors.extend(_check_optional_beer_sales_fields(data))
    errors.extend(_check_notes(data))
    if "sources" in data and len(data.get("sources", [])) == 0:
        errors.append("Must have at least one source")
    errors.extend(_check_verified_invariants(data))
    return errors


def validate_calendar(calendar: list[dict]) -> list[str]:
    """Validate calendar.json. Returns list of errors."""
    errors = []

    if len(calendar) == 0:
        errors.append("Calendar is empty")
        return errors

    # Check for duplicates
    dates = [entry["date"] for entry in calendar]
    if len(dates) != len(set(dates)):
        seen = set()
        for d in dates:
            if d in seen:
                errors.append(f"Duplicate date: {d}")
            seen.add(d)

    # Check for gaps
    for i in range(1, len(calendar)):
        d1 = date.fromisoformat(calendar[i - 1]["date"])
        d2 = date.fromisoformat(calendar[i]["date"])
        if d2 - d1 != timedelta(days=1):
            errors.append(f"Date gap between {d1} and {d2}")

    return errors


def _validate_date_coverage(days: list[dict], calendar: list[dict]) -> list[str]:
    """Check generated days match calendar dates exactly."""
    errors = []
    cal_dates = {entry["date"] for entry in calendar}
    gen_dates = {entry["date"] for entry in days}

    missing = cal_dates - gen_dates
    if missing:
        errors.append(f"Missing {len(missing)} dates from calendar: {sorted(missing)[:5]}...")

    extra = gen_dates - cal_dates
    if extra:
        errors.append(f"Extra {len(extra)} dates not in calendar: {sorted(extra)[:5]}...")

    return errors


def _validate_vinmonopolet_summaries(days: list[dict]) -> list[str]:
    """Validate vinmonopolet_summary field on each day. Stops at first error."""
    errors = []
    for day in days:
        if "vinmonopolet_summary" not in day:
            errors.append(f"{day['date']}: missing vinmonopolet_summary field")
            return errors
        summary = day["vinmonopolet_summary"]
        if summary is not None and not isinstance(summary, dict):
            errors.append(f"{day['date']}: vinmonopolet_summary must be dict or null")
            return errors
        if isinstance(summary, dict):
            stype = summary.get("type")
            if stype not in {"uniform", "range", "closed"}:
                errors.append(f"{day['date']}: vinmonopolet_summary invalid type '{stype}'")
                return errors
    return errors


def _validate_day_summary(gen_data: dict, num_days: int) -> list[str]:
    """Validate vinmonopolet_day_summary field. Stops at first type error."""
    errors = []
    if "vinmonopolet_day_summary" not in gen_data:
        errors.append("Missing vinmonopolet_day_summary field")
        return errors

    day_summary = gen_data["vinmonopolet_day_summary"]
    has_stores = len(gen_data.get("vinmonopolet_stores", [])) > 0
    if has_stores:
        expected_len = min(14, num_days)
        if len(day_summary) != expected_len:
            errors.append(
                f"vinmonopolet_day_summary: expected {expected_len} entries, got {len(day_summary)}"
            )
    for i, entry in enumerate(day_summary):
        if entry is not None and not isinstance(entry, dict):
            errors.append(f"vinmonopolet_day_summary[{i}]: must be dict or null")
            return errors
        if isinstance(entry, dict):
            etype = entry.get("type")
            if etype not in {"uniform", "range", "closed"}:
                errors.append(f"vinmonopolet_day_summary[{i}]: invalid type '{etype}'")
                return errors
    return errors


def _validate_store_entries(gen_data: dict, days: list[dict]) -> list[str]:
    """Validate vinmonopolet_stores entries. Stops date check at first mismatch."""
    errors = []
    if "vinmonopolet_stores" not in gen_data:
        errors.append("Missing vinmonopolet_stores field")
        return errors

    stores = gen_data["vinmonopolet_stores"]
    for store in stores:
        sid = store.get("store_id", "?")
        for field in ("store_id", "name", "address", "hours"):
            if field not in store:
                errors.append(f"vinmonopolet_stores[{sid}]: missing '{field}'")
        hours = store.get("hours", [])
        if len(hours) != min(14, len(days)):
            errors.append(
                f"vinmonopolet_stores[{sid}]: expected {min(14, len(days))} "
                f"hours entries, got {len(hours)}"
            )
        day_dates = [d["date"] for d in days[:14]]
        for i, h in enumerate(hours):
            if i < len(day_dates) and h.get("date") != day_dates[i]:
                errors.append(
                    f"vinmonopolet_stores[{sid}]: hours[{i}].date {h.get('date')} != {day_dates[i]}"
                )
                break

    return errors


def validate_generated_municipality(
    gen_data: dict,
    days: list[dict],
    calendar: list[dict],
    kommune_registry_ids: set[str] | None = None,
) -> list[str]:
    """Validate generated municipality data against calendar.

    When `kommune_registry_ids` is provided, the validator also checks that
    `nearest_vinmonopolet.source_municipality_id` refers to a known kommune.
    """
    errors: list[str] = []
    errors.extend(_validate_date_coverage(days, calendar))
    errors.extend(_validate_vinmonopolet_summaries(days))
    errors.extend(_validate_day_summary(gen_data, len(days)))
    errors.extend(_validate_store_entries(gen_data, days))
    errors.extend(_validate_vinmonopolet_fetched_at(gen_data))
    errors.extend(_validate_vinmonopolet_mode(gen_data, len(days)))
    errors.extend(_validate_nearest_source_in_registry(gen_data, kommune_registry_ids))
    return errors


def _validate_nearest_source_in_registry(
    gen_data: dict, kommune_registry_ids: set[str] | None
) -> list[str]:
    """Self-consistency: nearest.source_municipality_id must be a real kommune."""
    if kommune_registry_ids is None:
        return []
    nearest = gen_data.get("nearest_vinmonopolet")
    if not isinstance(nearest, dict):
        return []
    source_id = nearest.get("source_municipality_id")
    if not isinstance(source_id, str) or not source_id:
        return []
    if source_id not in kommune_registry_ids:
        return [
            f"nearest_vinmonopolet.source_municipality_id {source_id!r} "
            f"is not in the kommune registry"
        ]
    return []


_VALID_MODES = ("local", "nearest", "fallback")


def _validate_vinmonopolet_mode(gen_data: dict, num_days: int) -> list[str]:
    """Enforce the strict one-of contract for vinmonopolet_mode.

    Contract summary:
      - local:    own stores, no nearest, fetched_at set, day_summaries populated
      - nearest:  no stores, nearest_vinmonopolet set with its own day_summary,
                  top-level vinmonopolet_day_summary empty, fetched_at set
      - fallback: everything empty/null
    """
    if "vinmonopolet_mode" not in gen_data:
        return ["vinmonopolet_mode: missing field (legacy data?)"]

    mode = gen_data["vinmonopolet_mode"]
    if mode not in _VALID_MODES:
        return [f"vinmonopolet_mode: invalid value {mode!r} (expected one of {_VALID_MODES})"]

    expected_len = min(14, num_days)
    if mode == "local":
        return _validate_local_mode(gen_data, expected_len)
    if mode == "nearest":
        return _validate_nearest_mode(gen_data, expected_len)
    return _validate_fallback_mode(gen_data)


def _validate_local_mode(gen_data: dict, expected_len: int) -> list[str]:
    errors: list[str] = []
    stores = gen_data.get("vinmonopolet_stores", [])
    day_summary = gen_data.get("vinmonopolet_day_summary", [])
    if len(stores) == 0:
        errors.append("mode=local: vinmonopolet_stores must be non-empty")
    if gen_data.get("nearest_vinmonopolet") is not None:
        errors.append("mode=local: nearest_vinmonopolet must be null")
    if not gen_data.get("vinmonopolet_fetched_at"):
        errors.append("mode=local: vinmonopolet_fetched_at is required")
    if len(day_summary) != expected_len:
        errors.append(
            f"mode=local: vinmonopolet_day_summary length {len(day_summary)} != {expected_len}"
        )
    return errors


def _validate_nearest_mode(gen_data: dict, expected_len: int) -> list[str]:
    errors: list[str] = []
    stores = gen_data.get("vinmonopolet_stores", [])
    nearest = gen_data.get("nearest_vinmonopolet")
    day_summary = gen_data.get("vinmonopolet_day_summary", [])
    if len(stores) != 0:
        errors.append("mode=nearest: vinmonopolet_stores must be empty")
    if nearest is None:
        errors.append("mode=nearest: nearest_vinmonopolet is required")
    else:
        errors.extend(_validate_nearest_payload(nearest, expected_len))
    # Top-level vinmonopolet_day_summary describes this kommune's OWN stores.
    # In nearest mode it must stay empty — the nearest-store 14-day table is
    # served from nearest_vinmonopolet.day_summary.
    if len(day_summary) != 0:
        errors.append(
            "mode=nearest: vinmonopolet_day_summary must be empty "
            "(nearest-store hours live in nearest_vinmonopolet.day_summary)"
        )
    if not gen_data.get("vinmonopolet_fetched_at"):
        errors.append("mode=nearest: vinmonopolet_fetched_at is required")
    return errors


def _validate_fallback_mode(gen_data: dict) -> list[str]:
    errors: list[str] = []
    if len(gen_data.get("vinmonopolet_stores", [])) != 0:
        errors.append("mode=fallback: vinmonopolet_stores must be empty")
    if gen_data.get("nearest_vinmonopolet") is not None:
        errors.append("mode=fallback: nearest_vinmonopolet must be null")
    if gen_data.get("vinmonopolet_fetched_at"):
        errors.append("mode=fallback: vinmonopolet_fetched_at must be null")
    if len(gen_data.get("vinmonopolet_day_summary", [])) != 0:
        errors.append("mode=fallback: vinmonopolet_day_summary must be empty")
    return errors


def _validate_nearest_payload(payload: dict, expected_summary_len: int) -> list[str]:
    """Validate the nearest_vinmonopolet dict's own shape."""
    required = {
        "store",
        "distance_km",
        "source_municipality_id",
        "source_municipality_name",
        "day_summary",
    }
    missing = required - payload.keys()
    if missing:
        return [f"nearest_vinmonopolet: missing fields {sorted(missing)}"]

    errors: list[str] = []
    errors.extend(_check_distance(payload["distance_km"]))
    errors.extend(_check_source_strings(payload))
    errors.extend(_check_nearest_day_summary(payload["day_summary"], expected_summary_len))
    errors.extend(_check_nearest_store(payload["store"]))
    return errors


def _check_distance(distance: object) -> list[str]:
    if not isinstance(distance, (int, float)) or isinstance(distance, bool):
        return [f"nearest_vinmonopolet.distance_km must be numeric, got {type(distance).__name__}"]
    if distance < 0:
        return [f"nearest_vinmonopolet.distance_km must be non-negative, got {distance}"]
    return []


def _check_source_strings(payload: dict) -> list[str]:
    errors: list[str] = []
    for field in ("source_municipality_id", "source_municipality_name"):
        value = payload[field]
        if not isinstance(value, str) or not value:
            errors.append(f"nearest_vinmonopolet.{field} must be a non-empty string")
    return errors


def _check_nearest_day_summary(summary: object, expected_len: int) -> list[str]:
    if not isinstance(summary, list):
        return ["nearest_vinmonopolet.day_summary must be a list"]
    if len(summary) != expected_len:
        return [f"nearest_vinmonopolet.day_summary length {len(summary)} != {expected_len}"]
    return []


def _check_nearest_store(store: object) -> list[str]:
    if not isinstance(store, dict):
        return ["nearest_vinmonopolet.store must be an object"]
    errors: list[str] = []
    sid = store.get("store_id", "?")
    for field in ("store_id", "name", "address"):
        if field not in store:
            errors.append(f"nearest_vinmonopolet.store: missing field '{field}'")
    errors.extend(f"nearest_vinmonopolet.{e}" for e in _validate_store_coords(store, str(sid)))
    return errors


def _validate_vinmonopolet_fetched_at(gen_data: dict) -> list[str]:
    """When stores are present, vinmonopolet_fetched_at must be a valid ISO timestamp."""
    errors: list[str] = []
    stores = gen_data.get("vinmonopolet_stores", [])
    if not stores:
        return errors
    fetched_at = gen_data.get("vinmonopolet_fetched_at")
    if not fetched_at:
        errors.append("vinmonopolet_fetched_at is required when vinmonopolet_stores is non-empty")
        return errors
    try:
        datetime.fromisoformat(fetched_at)
    except (TypeError, ValueError):
        errors.append(f"vinmonopolet_fetched_at is not a valid ISO timestamp: {fetched_at!r}")
    return errors


def validate_national_max_compliance(days: list[dict]) -> list[str]:
    """Ensure no sales time exceeds national maximum."""
    errors = []

    for day in days:
        if not day.get("beer_sale_allowed"):
            continue

        day_type = day["day_type"]
        close = day.get("beer_close")
        max_close = NATIONAL_MAX.get(day_type)

        if close and max_close and close > max_close:
            errors.append(
                f"{day['date']}: {day_type} closing time {close} exceeds national max {max_close}"
            )

    return errors


REQUIRED_STORE_FIELDS = [
    "store_id",
    "name",
    "municipality",
    "address",
    "lat",
    "lng",
    "standard_hours",
    "actual_hours",
]
WEEKDAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_vm_metadata(metadata: dict, num_stores: int) -> list[str]:
    """Validate vinmonopolet metadata fields."""
    errors = []
    if "fetched_at" not in metadata:
        errors.append("Missing metadata.fetched_at")
    if "window_start" not in metadata or "window_end" not in metadata:
        errors.append("Missing metadata.window_start or window_end")
    if metadata.get("total_stores") != num_stores:
        errors.append(
            f"metadata.total_stores ({metadata.get('total_stores')}) != len(stores) ({num_stores})"
        )
    return errors


def _validate_store_fields(stores: list[dict]) -> list[str]:
    """Validate required fields, numeric store_id, coordinates, and duplicates."""
    errors = []
    seen_ids: set[str] = set()
    for i, store in enumerate(stores):
        sid = store.get("store_id", f"index-{i}")
        for field in REQUIRED_STORE_FIELDS:
            if field not in store:
                errors.append(f"Store {sid}: missing field '{field}'")
        if "store_id" in store and not store["store_id"].isdigit():
            errors.append(f"Store {sid}: store_id must be numeric")
        if sid in seen_ids:
            errors.append(f"Duplicate store_id: {sid}")
        seen_ids.add(sid)
        errors.extend(_validate_store_coords(store, sid))
    return errors


def _validate_store_coords(store: dict, sid: str) -> list[str]:
    """Strict numeric + in-range checks for a single store's lat/lng.

    The nearest-Vinmonopolet UX would silently collapse to fallback if a bad
    coord slipped through, so these rules must be strict.
    """
    errors: list[str] = []
    for key, lo, hi in (
        ("lat", _NORWAY_LAT_MIN, _NORWAY_LAT_MAX),
        ("lng", _NORWAY_LNG_MIN, _NORWAY_LNG_MAX),
    ):
        if key not in store:
            continue  # already reported by the required-fields loop
        val = store[key]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            errors.append(f"Store {sid}: {key} must be numeric, got {type(val).__name__}")
            continue
        if math.isnan(val) or math.isinf(val):
            errors.append(f"Store {sid}: {key} is non-finite")
            continue
        if not (lo <= val <= hi):
            errors.append(f"Store {sid}: {key} {val} outside Norway bounds [{lo}, {hi}]")
    return errors


def _validate_standard_hours(store: dict) -> list[str]:
    """Validate standard_hours for a single store."""
    errors = []
    sid = store.get("store_id", "?")
    sh = store.get("standard_hours", {})
    for day in WEEKDAY_KEYS:
        if day not in sh:
            errors.append(f"Store {sid}: missing standard_hours.{day}")
    if sh.get("sunday") is not None:
        errors.append(f"Store {sid}: sunday must be null")
    for day in WEEKDAY_KEYS:
        val = sh.get(day)
        if (
            val is not None
            and day != "sunday"
            and not (_TIME_RE.match(val.get("open", "")) and _TIME_RE.match(val.get("close", "")))
        ):
            errors.append(f"Store {sid}: invalid time in standard_hours.{day}")
    return errors


def _validate_actual_hours(store: dict) -> list[str]:
    """Validate actual_hours for a single store."""
    errors = []
    sid = store.get("store_id", "?")
    ah = store.get("actual_hours", {})
    if len(ah) != 7:
        errors.append(f"Store {sid}: actual_hours must have exactly 7 entries, got {len(ah)}")
    for dk, dv in ah.items():
        if not _DATE_RE.match(dk):
            errors.append(f"Store {sid}: invalid date key in actual_hours: {dk}")
        if dv is not None and not (
            _TIME_RE.match(dv.get("open", "")) and _TIME_RE.match(dv.get("close", ""))
        ):
            errors.append(f"Store {sid}: invalid time in actual_hours.{dk}")
    return errors


def _validate_window_dates(store: dict, metadata: dict) -> list[str]:
    """Validate actual_hours date window matches metadata."""
    errors = []
    ah = store.get("actual_hours", {})
    if len(ah) != 7:
        return errors
    if "window_start" not in metadata or "window_end" not in metadata:
        return errors
    sid = store.get("store_id", "?")
    store_dates = sorted(ah.keys())
    if store_dates[0] != metadata.get("window_start"):
        errors.append(f"Store {sid}: actual_hours start {store_dates[0]} != window_start")
    if store_dates[-1] != metadata.get("window_end"):
        errors.append(f"Store {sid}: actual_hours end {store_dates[-1]} != window_end")
    return errors


def _validate_municipality_coverage(
    stores: list[dict], municipalities_dir: Path | None
) -> tuple[list[str], list[str]]:
    """Check municipality coverage. Returns (coverage_info, unmapped_info)."""
    coverage_info = []
    unmapped_info = []

    if municipalities_dir and municipalities_dir.exists():
        configured = {p.stem for p in municipalities_dir.glob(_JSON_GLOB)}
        mapped = {s["municipality"] for s in stores if s.get("municipality")}
        missing = configured - mapped
        if missing:
            coverage_info.append(f"Municipalities with no Vinmonopolet stores: {sorted(missing)}")

    unmapped = sum(1 for s in stores if s.get("municipality") is None)
    if unmapped:
        unmapped_info.append(f"{unmapped} stores have municipality=null (not mapped)")

    return coverage_info, unmapped_info


def validate_vinmonopolet(
    data: dict,
    municipalities_dir: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Validate vinmonopolet.json. Returns (errors, info messages)."""
    errors: list[str] = []
    info: list[str] = []

    if "metadata" not in data:
        errors.append("Missing metadata")
        return errors, info
    if "stores" not in data:
        errors.append("Missing stores")
        return errors, info

    metadata = data["metadata"]
    stores = data["stores"]

    errors.extend(_validate_vm_metadata(metadata, len(stores)))

    if len(stores) == 0:
        errors.append("No stores found")
        return errors, info

    errors.extend(_validate_store_fields(stores))
    for store in stores:
        errors.extend(_validate_standard_hours(store))
        errors.extend(_validate_actual_hours(store))
        errors.extend(_validate_window_dates(store, metadata))

    coverage_info, unmapped_info = _validate_municipality_coverage(stores, municipalities_dir)
    info.extend(coverage_info)
    info.extend(unmapped_info)

    return errors, info


def _validate_municipality_files(municipalities_dir: Path) -> list[str]:
    """Validate all municipality source JSON files."""
    errors = []
    for path in sorted(municipalities_dir.glob(_JSON_GLOB)):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        file_errors = validate_municipality_schema(data)
        if file_errors:
            errors.extend(f"{path.name}: {e}" for e in file_errors)
    return errors


def _validate_calendar_file(calendar_path: Path) -> tuple[list[str], list[dict] | None]:
    """Validate calendar.json. Returns (errors, loaded calendar or None)."""
    if not calendar_path.exists():
        return [], None
    with open(calendar_path, encoding="utf-8") as f:
        calendar = json.load(f)
    errors = validate_calendar(calendar)
    return [f"calendar.json: {e}" for e in errors], calendar


def _validate_generated_files(
    gen_dir: Path,
    calendar: list[dict],
    kommune_registry_ids: set[str] | None = None,
) -> list[str]:
    """Validate all generated municipality files against calendar."""
    errors = []
    for path in sorted(gen_dir.glob(_JSON_GLOB)):
        with open(path, encoding="utf-8") as f:
            gen_data = json.load(f)
        days = gen_data.get("days", [])
        file_errors = validate_generated_municipality(
            gen_data, days, calendar, kommune_registry_ids=kommune_registry_ids
        )
        errors.extend(f"{path.name}: {e}" for e in file_errors)
        file_errors = validate_national_max_compliance(days)
        errors.extend(f"{path.name}: {e}" for e in file_errors)
    return errors


def _load_kommune_registry_ids(data_dir: Path) -> set[str] | None:
    """Read kommune ids from data/reference/kommuner.json; None if missing."""
    path = data_dir / "reference" / "kommuner.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {entry["id"] for entry in data.get("kommuner", [])}


def _validate_vinmonopolet_file(
    vinmonopolet_path: Path, municipalities_dir: Path
) -> tuple[list[str], list[str]]:
    """Validate vinmonopolet.json file. Returns (errors, info)."""
    if not vinmonopolet_path.exists():
        return [], []
    with open(vinmonopolet_path, encoding="utf-8") as f:
        vinmonopolet_data = json.load(f)
    errors, info = validate_vinmonopolet(vinmonopolet_data, municipalities_dir)
    return [f"vinmonopolet.json: {e}" for e in errors], info


def _validate_town_municipality_map(data_dir: Path) -> list[str]:
    """Ensure every value in town_municipality_map.json matches a kommune JSON.

    Without this check, a typo or a stale override (e.g. pointing at a kommune
    we never added) silently labels stores with an id that no page consumes,
    and those stores disappear from the rendered site.
    """
    errors = []
    path = data_dir / "town_municipality_map.json"
    if not path.exists():
        return errors
    with open(path, encoding="utf-8") as f:
        overrides = json.load(f)
    known_ids = {p.stem for p in (data_dir / "municipalities").glob(_JSON_GLOB)}
    for town, kommune_id in overrides.items():
        if kommune_id not in known_ids:
            errors.append(
                f"town_municipality_map.json: {town!r} -> {kommune_id!r} "
                f"but no data/municipalities/{kommune_id}.json exists"
            )
    return errors


def main() -> int:
    """CLI entry point. Returns 0 on success, 1 on failure."""
    data_dir = Path(__file__).parent.parent / "data"
    municipalities_dir = data_dir / "municipalities"

    all_errors = _validate_municipality_files(municipalities_dir)
    all_errors.extend(_validate_town_municipality_map(data_dir))

    calendar_path = data_dir / "generated" / "calendar.json"
    cal_errors, calendar = _validate_calendar_file(calendar_path)
    all_errors.extend(cal_errors)

    if calendar is not None:
        gen_dir = data_dir / "generated" / "municipalities"
        if gen_dir.exists():
            registry_ids = _load_kommune_registry_ids(data_dir)
            all_errors.extend(_validate_generated_files(gen_dir, calendar, registry_ids))
    else:
        print("Note: calendar.json not found (run build_calendar.py first)")

    vinmonopolet_path = data_dir / "generated" / "vinmonopolet.json"
    vm_errors, vm_info = _validate_vinmonopolet_file(vinmonopolet_path, municipalities_dir)
    all_errors.extend(vm_errors)
    for msg in vm_info:
        print(f"  Info: {msg}")
    if not vinmonopolet_path.exists():
        print("Note: vinmonopolet.json not found (run fetch_vinmonopolet.py first)")

    if all_errors:
        print(f"Validation failed with {len(all_errors)} error(s):")
        for error in all_errors:
            print(f"  - {error}")
        return 1

    print("All validation checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
