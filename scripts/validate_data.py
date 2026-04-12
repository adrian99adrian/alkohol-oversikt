"""Validate all generated data for consistency and completeness.

Usage:
    python scripts/validate_data.py

Returns exit code 0 on success, 1 on failure.
"""

import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

REQUIRED_MUNICIPALITY_FIELDS = [
    "id",
    "name",
    "county",
    "beer_sales",
    "sources",
    "last_verified",
]
REQUIRED_BEER_SALES_FIELDS = [
    "weekday_open",
    "weekday_close",
    "saturday_open",
    "saturday_close",
    "pre_holiday_close",
    "special_day_close",
    "special_days",
]

# National max closing times. pre_holiday can be overridden to weekday (20:00)
# by municipal exceptions, so we allow up to 20:00 for pre_holiday.
NATIONAL_MAX = {
    "weekday": "20:00",
    "saturday": "18:00",
    "pre_holiday": "20:00",  # Allows municipal exceptions (e.g., Larvik Ascension)
    "special_day": "18:00",
}

_JSON_GLOB = "*.json"


def validate_municipality_schema(data: dict) -> list[str]:
    """Validate a municipality JSON file. Returns list of errors."""
    errors = []

    for field in REQUIRED_MUNICIPALITY_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "beer_sales" in data:
        beer = data["beer_sales"]
        for field in REQUIRED_BEER_SALES_FIELDS:
            if field not in beer:
                errors.append(f"Missing beer_sales field: {field}")

    if "sources" in data and len(data.get("sources", [])) == 0:
        errors.append("Must have at least one source")

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
    gen_data: dict, days: list[dict], calendar: list[dict]
) -> list[str]:
    """Validate generated municipality data against calendar."""
    errors: list[str] = []
    errors.extend(_validate_date_coverage(days, calendar))
    errors.extend(_validate_vinmonopolet_summaries(days))
    errors.extend(_validate_day_summary(gen_data, len(days)))
    errors.extend(_validate_store_entries(gen_data, days))
    errors.extend(_validate_vinmonopolet_fetched_at(gen_data))
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
    """Validate required fields, numeric store_id, and duplicates."""
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


def _validate_generated_files(gen_dir: Path, calendar: list[dict]) -> list[str]:
    """Validate all generated municipality files against calendar."""
    errors = []
    for path in sorted(gen_dir.glob(_JSON_GLOB)):
        with open(path, encoding="utf-8") as f:
            gen_data = json.load(f)
        days = gen_data.get("days", [])
        file_errors = validate_generated_municipality(gen_data, days, calendar)
        errors.extend(f"{path.name}: {e}" for e in file_errors)
        file_errors = validate_national_max_compliance(days)
        errors.extend(f"{path.name}: {e}" for e in file_errors)
    return errors


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


def main() -> int:
    """CLI entry point. Returns 0 on success, 1 on failure."""
    data_dir = Path(__file__).parent.parent / "data"
    municipalities_dir = data_dir / "municipalities"

    all_errors = _validate_municipality_files(municipalities_dir)

    calendar_path = data_dir / "generated" / "calendar.json"
    cal_errors, calendar = _validate_calendar_file(calendar_path)
    all_errors.extend(cal_errors)

    if calendar is not None:
        gen_dir = data_dir / "generated" / "municipalities"
        if gen_dir.exists():
            all_errors.extend(_validate_generated_files(gen_dir, calendar))
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
