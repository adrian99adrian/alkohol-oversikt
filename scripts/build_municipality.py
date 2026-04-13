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
    max_vinmonopolet_days = 14
    window_days = calendar[:max_vinmonopolet_days]

    nearest: dict | None = None
    if not local_stores and all_stores is not None and kommune_registry is not None:
        entry_with_coords = kommune_registry.get(municipality["id"])
        if entry_with_coords is not None:
            nearest = find_nearest_store(entry_with_coords, all_stores, kommune_registry)

    if local_stores:
        mode = "local"
        summary_stores = local_stores
    elif nearest is not None:
        mode = "nearest"
        summary_stores = [nearest["store"]]
    else:
        mode = "fallback"
        summary_stores = []

    days = []
    for i, cal_entry in enumerate(calendar):
        d = date.fromisoformat(cal_entry["date"])
        entry = build_day_entry(d, cal_entry, municipality)
        if i < max_vinmonopolet_days and summary_stores:
            entry["vinmonopolet_summary"] = summarize_vinmonopolet(
                summary_stores, cal_entry["date"], cal_entry["day_type"]
            )
        else:
            entry["vinmonopolet_summary"] = None
        days.append(entry)

    # Per-store resolved 14-day hours are only shown for the local store list;
    # in nearest-mode we surface the single source store via nearest_vinmonopolet.
    resolved_stores = build_resolved_stores(local_stores, window_days)
    day_summaries = build_day_summaries(summary_stores, window_days) if summary_stores else []

    nearest_payload: dict | None = None
    if mode == "nearest" and nearest is not None:
        nearest_payload = {
            "store": build_resolved_stores([nearest["store"]], window_days)[0],
            "distance_km": nearest["distance_km"],
            "source_municipality_id": nearest["source_municipality_id"],
            "source_municipality_name": nearest["source_municipality_name"],
            "day_summary": day_summaries,
        }

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
        "vinmonopolet_day_summary": day_summaries,
        "vinmonopolet_fetched_at": vinmonopolet_fetched_at if mode != "fallback" else None,
        "nearest_vinmonopolet": nearest_payload,
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
