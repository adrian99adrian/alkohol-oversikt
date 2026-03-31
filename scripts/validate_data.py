"""Validate all generated data for consistency and completeness.

Usage:
    python scripts/validate_data.py

Returns exit code 0 on success, 1 on failure.
"""

import json
import re
import sys
from datetime import date, timedelta
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


def validate_generated_municipality(days: list[dict], calendar: list[dict]) -> list[str]:
    """Validate generated municipality data against calendar."""
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


def validate_vinmonopolet(
    data: dict,
    municipalities_dir: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Validate vinmonopolet.json. Returns (errors, info messages)."""
    errors = []
    info = []

    if "metadata" not in data:
        errors.append("Missing metadata")
        return errors, info
    if "stores" not in data:
        errors.append("Missing stores")
        return errors, info

    metadata = data["metadata"]
    stores = data["stores"]

    # Metadata checks
    if "fetched_at" not in metadata:
        errors.append("Missing metadata.fetched_at")
    if "window_start" not in metadata or "window_end" not in metadata:
        errors.append("Missing metadata.window_start or window_end")
    if metadata.get("total_stores") != len(stores):
        errors.append(
            f"metadata.total_stores ({metadata.get('total_stores')}) != len(stores) ({len(stores)})"
        )

    if len(stores) == 0:
        errors.append("No stores found")
        return errors, info

    # Per-store validation
    seen_ids: set[str] = set()
    window_dates = (
        {metadata["window_start"], metadata["window_end"]}
        if "window_start" in metadata and "window_end" in metadata
        else set()
    )

    for i, store in enumerate(stores):
        sid = store.get("store_id", f"index-{i}")

        for field in REQUIRED_STORE_FIELDS:
            if field not in store:
                errors.append(f"Store {sid}: missing field '{field}'")

        # store_id must be numeric
        if "store_id" in store and not store["store_id"].isdigit():
            errors.append(f"Store {sid}: store_id must be numeric")

        # Duplicate check
        if sid in seen_ids:
            errors.append(f"Duplicate store_id: {sid}")
        seen_ids.add(sid)

        # standard_hours
        sh = store.get("standard_hours", {})
        for day in WEEKDAY_KEYS:
            if day not in sh:
                errors.append(f"Store {sid}: missing standard_hours.{day}")
        if sh.get("sunday") is not None:
            errors.append(f"Store {sid}: sunday must be null")
        for day in WEEKDAY_KEYS:
            val = sh.get(day)
            if val is not None and day != "sunday":
                if not (
                    _TIME_RE.match(val.get("open", "")) and _TIME_RE.match(val.get("close", ""))
                ):
                    errors.append(f"Store {sid}: invalid time in standard_hours.{day}")

        # actual_hours
        ah = store.get("actual_hours", {})
        if len(ah) != 7:
            errors.append(f"Store {sid}: actual_hours must have exactly 7 entries, got {len(ah)}")
        for dk, dv in ah.items():
            if not _DATE_RE.match(dk):
                errors.append(f"Store {sid}: invalid date key in actual_hours: {dk}")
            if dv is not None:
                if not (_TIME_RE.match(dv.get("open", "")) and _TIME_RE.match(dv.get("close", ""))):
                    errors.append(f"Store {sid}: invalid time in actual_hours.{dk}")

        # Check actual_hours window matches metadata
        if len(ah) == 7 and window_dates:
            store_dates = sorted(ah.keys())
            if store_dates[0] != metadata.get("window_start"):
                errors.append(f"Store {sid}: actual_hours start {store_dates[0]} != window_start")
            if store_dates[-1] != metadata.get("window_end"):
                errors.append(f"Store {sid}: actual_hours end {store_dates[-1]} != window_end")

    # Municipality coverage: check which configured municipalities have no stores
    if municipalities_dir and municipalities_dir.exists():
        configured = {p.stem for p in municipalities_dir.glob("*.json")}
        mapped = {s["municipality"] for s in stores if s.get("municipality")}
        missing = configured - mapped
        if missing:
            info.append(f"Municipalities with no Vinmonopolet stores: {sorted(missing)}")

    # Informational: count unmapped stores
    unmapped = sum(1 for s in stores if s.get("municipality") is None)
    if unmapped:
        info.append(f"{unmapped} stores have municipality=null (not mapped)")

    return errors, info


def main() -> int:
    """CLI entry point. Returns 0 on success, 1 on failure."""
    data_dir = Path(__file__).parent.parent / "data"
    all_errors = []

    # Validate municipality source files
    municipalities_dir = data_dir / "municipalities"
    for path in sorted(municipalities_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        errors = validate_municipality_schema(data)
        if errors:
            all_errors.extend(f"{path.name}: {e}" for e in errors)

    # Validate calendar
    calendar_path = data_dir / "generated" / "calendar.json"
    if calendar_path.exists():
        with open(calendar_path, encoding="utf-8") as f:
            calendar = json.load(f)
        errors = validate_calendar(calendar)
        all_errors.extend(f"calendar.json: {e}" for e in errors)

        # Validate generated municipalities
        gen_dir = data_dir / "generated" / "municipalities"
        if gen_dir.exists():
            for path in sorted(gen_dir.glob("*.json")):
                with open(path, encoding="utf-8") as f:
                    gen_data = json.load(f)
                days = gen_data.get("days", [])

                errors = validate_generated_municipality(days, calendar)
                all_errors.extend(f"{path.name}: {e}" for e in errors)

                errors = validate_national_max_compliance(days)
                all_errors.extend(f"{path.name}: {e}" for e in errors)
    else:
        print("Note: calendar.json not found (run build_calendar.py first)")

    # Validate vinmonopolet
    vinmonopolet_path = data_dir / "generated" / "vinmonopolet.json"
    if vinmonopolet_path.exists():
        with open(vinmonopolet_path, encoding="utf-8") as f:
            vinmonopolet_data = json.load(f)
        errors, info = validate_vinmonopolet(vinmonopolet_data, municipalities_dir)
        all_errors.extend(f"vinmonopolet.json: {e}" for e in errors)
        for msg in info:
            print(f"  Info: {msg}")
    else:
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
