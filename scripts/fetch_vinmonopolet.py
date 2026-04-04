"""Fetch Vinmonopolet store hours from the public API.

Usage:
    python scripts/fetch_vinmonopolet.py
    python scripts/fetch_vinmonopolet.py --timeout 60

Outputs to data/generated/vinmonopolet.json.
"""

import argparse
import json
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

API_BASE = "https://www.vinmonopolet.no/vmpws/v2/vmp/stores"
DEFAULT_PAGE_SIZE = 400
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3

WEEKDAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def _parse_date(api_date: str) -> str:
    """Extract ISO date (YYYY-MM-DD) from API datetime string."""
    return api_date[:10]


def _time_entry(opening_time: dict) -> dict[str, str]:
    """Extract {open, close} from an API opening time entry.

    Uses formattedHour which is the reliable HH:MM string from the API.
    The integer hour/minute fields are unreliable (e.g. 16:00 → hour=4).
    """
    return {
        "open": opening_time["openingTime"]["formattedHour"],
        "close": opening_time["closingTime"]["formattedHour"],
    }


def build_actual_hours(opening_times: list[dict]) -> dict[str, dict | None]:
    """Build actual_hours from raw 7-day API openingTimes.

    Returns dict keyed by ISO date. Closed days map to None.
    """
    result: dict[str, dict | None] = {}
    for entry in opening_times:
        iso_date = _parse_date(entry["date"])
        if entry.get("closed"):
            result[iso_date] = None
        else:
            result[iso_date] = _time_entry(entry)
    return result


def derive_standard_hours(
    opening_times: list[dict],
    special_opening_times: list[dict],
    previous: dict[str, dict | None] | None = None,
) -> dict[str, dict | None]:
    """Derive standard weekly hours from 7-day API data.

    Excludes days that appear in specialOpeningTimes (holidays, reduced hours).
    Sunday is always None (closed by law).

    For days only seen as special (e.g. Easter Thursday), the previous fetch's
    value for that specific day is preserved. This avoids flattening per-day
    schedules (Mon-Wed 10-17, Thu-Fri 10-18) into a single fallback.
    When no previous data exists, falls back to mode of other Mon-Fri hours
    with tie-break on earliest closing time.
    """
    special_dates = {_parse_date(s["date"]) for s in special_opening_times}

    # Collect non-special hours per weekday index.
    # Explicitly closed (non-special) days are recorded as None.
    weekday_hours: dict[int, dict[str, str] | None] = {}
    special_skipped: set[int] = set()
    for entry in opening_times:
        iso_date = _parse_date(entry["date"])
        d = date.fromisoformat(iso_date)
        wd = d.weekday()  # Monday is 0, Sunday is 6
        if wd == 6:  # Sunday always None
            continue
        if iso_date in special_dates:
            special_skipped.add(wd)
            continue
        if entry.get("closed"):
            weekday_hours[wd] = None
        else:
            weekday_hours[wd] = _time_entry(entry)

    # Build result with fallback for missing weekdays
    result: dict[str, dict | None] = {}

    # Compute Mon-Fri fallback (mode of open hours, tie-break earliest close)
    mon_fri_hours = [h for wd in range(5) if (h := weekday_hours.get(wd)) is not None]
    fallback = _compute_fallback(mon_fri_hours)

    for i, name in enumerate(WEEKDAY_NAMES):
        if name == "sunday":
            result[name] = None
        elif i in weekday_hours:
            result[name] = weekday_hours[i]
        elif i in special_skipped and previous and name in previous:
            # Preserve the previous per-day value rather than flattening
            # different weekday schedules into a single fallback.
            result[name] = previous[name]
        else:
            result[name] = fallback

    return result


def _compute_fallback(hours_list: list[dict]) -> dict | None:
    """Compute the mode of a list of {open, close} dicts.

    Tie-break: earliest closing time (most conservative).
    Returns None if the list is empty.
    """
    if not hours_list:
        return None

    # Count (open, close) pairs
    counter: Counter[tuple[str, str]] = Counter()
    for h in hours_list:
        counter[(h["open"], h["close"])] += 1

    max_count = max(counter.values())
    candidates = [pair for pair, count in counter.items() if count == max_count]

    # Tie-break: earliest closing time
    candidates.sort(key=lambda pair: pair[1])
    best = candidates[0]
    return {"open": best[0], "close": best[1]}


def format_address(store: dict) -> str:
    """Format store address as 'line1, postalCode town'."""
    addr = store["address"]
    return f"{addr['line1']}, {addr['postalCode']} {addr['town']}"


def map_town_to_municipality(
    town: str,
    overrides: dict[str, str],
    known_municipalities: set[str],
) -> str | None:
    """Map a town name to a municipality ID.

    Checks overrides first, then tries lowercasing against the known set.
    Returns None if no match (avoids silent bad data).
    """
    if town in overrides:
        return overrides[town]
    lowered = town.lower()
    if lowered in known_municipalities:
        return lowered
    return None


def transform_store(
    store: dict,
    overrides: dict[str, str],
    known_municipalities: set[str],
    previous_standard_hours: dict[str, dict | None] | None = None,
) -> dict:
    """Transform a raw API store dict into spec-compliant output."""
    opening_times = store.get("openingTimes", [])
    special_times = store.get("specialOpeningTimes", [])

    # Try town first, then displayName as fallback for municipality mapping
    municipality = map_town_to_municipality(
        store["address"]["town"], overrides, known_municipalities
    )
    if municipality is None:
        municipality = map_town_to_municipality(
            store["displayName"], overrides, known_municipalities
        )

    return {
        "store_id": store["name"],
        "name": store["displayName"],
        "municipality": municipality,
        "address": format_address(store),
        "standard_hours": derive_standard_hours(
            opening_times, special_times, previous=previous_standard_hours
        ),
        "actual_hours": build_actual_hours(opening_times),
    }


def get_with_retry(
    client: httpx.Client,
    url: str,
    params: dict,
    max_retries: int = MAX_RETRIES,
) -> httpx.Response:
    """GET with retry on timeout and 5xx errors.

    Retries with exponential backoff. No retry on 4xx.
    """
    for attempt in range(max_retries):
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response
        except httpx.TimeoutException:
            if attempt == max_retries - 1:
                raise
            time.sleep(2**attempt)
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise
            if attempt == max_retries - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("Unreachable")  # pragma: no cover


def fetch_page(
    client: httpx.Client,
    page: int,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    """Fetch one page of stores from the Vinmonopolet API."""
    params = {"fields": "FULL", "pageSize": page_size, "page": page}
    response = get_with_retry(client, API_BASE, params)
    return response.json()


def fetch_all_stores(
    client: httpx.Client,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[dict]:
    """Fetch all stores, paginating through all pages.

    Verifies the total count matches pagination.totalResults.
    """
    first_page = fetch_page(client, page=0, page_size=page_size)
    total_pages = first_page["pagination"]["totalPages"]

    seen: dict[str, dict] = {}
    for store in first_page["stores"]:
        seen[store["name"]] = store

    for page_num in range(1, total_pages):
        page_data = fetch_page(client, page=page_num, page_size=page_size)
        for store in page_data["stores"]:
            seen[store["name"]] = store

    return list(seen.values())


def load_town_overrides(data_dir: Path) -> dict[str, str]:
    """Load town-to-municipality overrides from data/town_municipality_map.json."""
    path = data_dir / "town_municipality_map.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_known_municipalities(data_dir: Path) -> set[str]:
    """Load known municipality IDs from data/municipalities/*.json."""
    municipalities_dir = data_dir / "municipalities"
    return {p.stem for p in municipalities_dir.glob("*.json")}


def _load_previous_standard_hours(data_dir: Path) -> dict[str, dict]:
    """Load standard_hours per store_id from a previous vinmonopolet.json.

    Returns empty dict if the file doesn't exist yet (first run).
    """
    path = data_dir / "generated" / "vinmonopolet.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {s["store_id"]: s["standard_hours"] for s in data.get("stores", [])}


def _compute_window(stores: list[dict]) -> tuple[str, str]:
    """Compute the shared actual_hours date window from transformed stores."""
    all_dates: set[str] = set()
    for store in stores:
        all_dates.update(store["actual_hours"].keys())
    sorted_dates = sorted(all_dates)
    return sorted_dates[0], sorted_dates[-1]


def main() -> None:
    """CLI entry point: fetch Vinmonopolet stores and write to JSON."""
    parser = argparse.ArgumentParser(description="Fetch Vinmonopolet store hours")
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout (default: 30s)"
    )
    parser.add_argument(
        "--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="API page size (default: 400)"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).parent.parent / "data",
        help="Path to data directory (default: data/)",
    )
    args = parser.parse_args()

    data_dir = args.data_dir
    overrides = load_town_overrides(data_dir)
    known = load_known_municipalities(data_dir)

    # Load previous standard_hours so holiday-week fetches preserve per-day patterns
    previous_hours = _load_previous_standard_hours(data_dir)

    with httpx.Client(timeout=args.timeout) as client:
        raw_stores = fetch_all_stores(client, page_size=args.page_size)

    transformed = [
        transform_store(
            s,
            overrides,
            known,
            previous_standard_hours=previous_hours.get(s["name"]),
        )
        for s in raw_stores
    ]
    transformed.sort(key=lambda s: int(s["store_id"]))

    window_start, window_end = _compute_window(transformed)
    fetched_at = datetime.now(tz=ZoneInfo("Europe/Oslo")).isoformat()

    output = {
        "metadata": {
            "total_stores": len(transformed),
            "fetched_at": fetched_at,
            "window_start": window_start,
            "window_end": window_end,
        },
        "stores": transformed,
    }

    output_path = data_dir / "generated" / "vinmonopolet.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    mapped = sum(1 for s in transformed if s["municipality"] is not None)
    unmapped = len(transformed) - mapped
    print(f"Fetched {len(transformed)} stores ({mapped} mapped, {unmapped} unmapped)")
    print(f"Window: {window_start} to {window_end}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
