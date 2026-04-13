"""Generate per-municipality JSON with daily beer sales times.

Usage:
    python scripts/build_municipality.py --all
    python scripts/build_municipality.py --id sandefjord
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from build_calendar import build_calendar, get_today_oslo
from nearest_store import find_nearest_store
from sales import build_day_entry
from vinmonopolet_hours import build_day_summaries, build_resolved_stores, summarize_vinmonopolet

MAX_VINMONOPOLET_DAYS = 14


def build_municipality(
    municipality: dict,
    calendar: list[dict],
    vinmonopolet_stores: list[dict] | None = None,
    vinmonopolet_fetched_at: str | None = None,
    *,
    all_stores: list[dict] | None = None,
    kommune_registry: dict[str, dict] | None = None,
) -> dict:
    """Build the complete output for a municipality.

    vinmonopolet_mode is one of:
      - "local"    — this kommune has its own stores
      - "nearest"  — no local store, but a nearest store was found
      - "fallback" — no local store and no nearest (missing coords, etc.)

    `all_stores` and `kommune_registry` are required for nearest-mode
    resolution. When omitted, only local/fallback modes are possible.
    """
    local_stores = vinmonopolet_stores or []
    window_days = calendar[:MAX_VINMONOPOLET_DAYS]
    nearest = _resolve_nearest(municipality, local_stores, all_stores, kommune_registry)
    mode = _decide_mode(local_stores, nearest)

    days = _build_days(calendar, municipality, mode, local_stores)
    resolved_stores = build_resolved_stores(local_stores, window_days)
    local_day_summaries = build_day_summaries(local_stores, window_days) if local_stores else []
    nearest_payload = _build_nearest_payload(nearest, window_days) if mode == "nearest" else None

    return {
        "municipality": {
            "id": municipality["id"],
            "name": municipality["name"],
            "county": municipality["county"],
            "sources": municipality["sources"],
            "last_verified": municipality["last_verified"],
            "verified": municipality["verified"],
        },
        "days": days,
        "vinmonopolet_mode": mode,
        "vinmonopolet_stores": resolved_stores,
        "vinmonopolet_day_summary": local_day_summaries,
        "vinmonopolet_fetched_at": vinmonopolet_fetched_at if mode != "fallback" else None,
        "nearest_vinmonopolet": nearest_payload,
    }


def _resolve_nearest(
    municipality: dict,
    local_stores: list[dict],
    all_stores: list[dict] | None,
    kommune_registry: dict[str, dict] | None,
) -> dict | None:
    """Return the nearest-store lookup result, or None if not applicable."""
    if local_stores or all_stores is None or kommune_registry is None:
        return None
    entry_with_coords = kommune_registry.get(municipality["id"])
    if entry_with_coords is None:
        return None
    return find_nearest_store(entry_with_coords, all_stores, kommune_registry)


def _decide_mode(local_stores: list[dict], nearest: dict | None) -> str:
    if local_stores:
        return "local"
    if nearest is not None:
        return "nearest"
    return "fallback"


def _build_days(
    calendar: list[dict],
    municipality: dict,
    mode: str,
    local_stores: list[dict],
) -> list[dict]:
    """Build the per-day output.

    `days[i].vinmonopolet_summary` describes THIS kommune's own stores.
    In nearest mode we must NOT populate it from the nearest (out-of-kommune)
    store — DayCard / BeerSalesTable render it as plain "Vinmonopol-hours"
    with no indication of source, which would misleadingly suggest the
    kommune has a local Vinmonopol. Those consumers instead read from
    `nearest_vinmonopolet.day_summary` via VinmonopoletList.
    """
    show_local_summary = mode == "local" and bool(local_stores)
    days = []
    for i, cal_entry in enumerate(calendar):
        d = date.fromisoformat(cal_entry["date"])
        entry = build_day_entry(d, cal_entry, municipality)
        if show_local_summary and i < MAX_VINMONOPOLET_DAYS:
            entry["vinmonopolet_summary"] = summarize_vinmonopolet(
                local_stores, cal_entry["date"], cal_entry["day_type"]
            )
        else:
            entry["vinmonopolet_summary"] = None
        days.append(entry)
    return days


def _build_nearest_payload(nearest: dict | None, window_days: list[dict]) -> dict | None:
    if nearest is None:
        return None
    return {
        "store": build_resolved_stores([nearest["store"]], window_days)[0],
        "distance_km": nearest["distance_km"],
        "source_municipality_id": nearest["source_municipality_id"],
        "source_municipality_name": nearest["source_municipality_name"],
        "day_summary": build_day_summaries([nearest["store"]], window_days),
    }


def _load_municipality(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_vinmonopolet_stores(
    data_dir: Path,
) -> tuple[dict[str, list[dict]], list[dict], str | None]:
    """Load Vinmonopolet stores.

    Returns (stores_by_municipality_id, all_mapped_stores, fetched_at_timestamp).

    `all_mapped_stores` is the flat list of stores with a known municipality —
    used by the nearest-store lookup. Stores with `municipality is None` are
    excluded because they cannot resolve to a source kommune.
    """
    path = data_dir / "generated" / "vinmonopolet.json"
    if not path.exists():
        return {}, [], None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    stores_by_muni: dict[str, list[dict]] = {}
    all_mapped: list[dict] = []
    for store in data.get("stores", []):
        muni = store.get("municipality")
        if muni:
            stores_by_muni.setdefault(muni, []).append(store)
            all_mapped.append(store)
    fetched_at = data.get("metadata", {}).get("fetched_at")
    return stores_by_muni, all_mapped, fetched_at


def _load_kommune_registry(data_dir: Path) -> dict[str, dict]:
    """Load data/reference/kommuner.json into a dict keyed by `id`.

    Returns empty dict if the file is missing (nearest-mode is then unavailable).
    """
    path = data_dir / "reference" / "kommuner.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {entry["id"]: entry for entry in data.get("kommuner", [])}


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate municipality beer sales data")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Generate for all municipalities")
    group.add_argument("--id", type=str, help="Generate for a specific municipality ID")
    parser.add_argument("--days", type=int, default=365, help="Number of days (default: 365)")
    parser.add_argument("--start-date", type=str, default=None, help="Start date YYYY-MM-DD")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).parent.parent / "data",
        help="Path to data directory (default: data/)",
    )
    args = parser.parse_args()

    start = date.fromisoformat(args.start_date) if args.start_date else get_today_oslo()
    calendar = build_calendar(start, num_days=args.days)

    data_dir = args.data_dir
    municipalities_dir = data_dir / "municipalities"
    output_dir = data_dir / "generated" / "municipalities"
    output_dir.mkdir(parents=True, exist_ok=True)

    vinmonopolet_by_muni, all_stores, vinmonopolet_fetched_at = _load_vinmonopolet_stores(data_dir)
    kommune_registry = _load_kommune_registry(data_dir)

    if args.all:
        paths = sorted(municipalities_dir.glob("*.json"))
        if not paths:
            print(f"Error: no municipality files found in {municipalities_dir}")
            sys.exit(1)
    else:
        target = municipalities_dir / f"{args.id}.json"
        if not target.exists():
            print(f"Error: municipality file not found: {target}")
            sys.exit(1)
        paths = [target]

    for path in paths:
        municipality = _load_municipality(path)
        muni_id = municipality["id"]
        stores = vinmonopolet_by_muni.get(muni_id, [])
        result = build_municipality(
            municipality,
            calendar,
            vinmonopolet_stores=stores,
            vinmonopolet_fetched_at=vinmonopolet_fetched_at,
            all_stores=all_stores,
            kommune_registry=kommune_registry,
        )

        output_path = output_dir / f"{municipality['id']}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        store_count = len(stores)
        print(
            f"Generated {len(result['days'])} days for {municipality['name']}"
            f" ({store_count} Vinmonopolet stores) -> {output_path}"
        )


if __name__ == "__main__":
    main()
