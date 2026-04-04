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
from sales import build_day_entry
from vinmonopolet_hours import build_day_summaries, build_resolved_stores, summarize_vinmonopolet


def build_municipality(
    municipality: dict,
    calendar: list[dict],
    vinmonopolet_stores: list[dict] | None = None,
) -> dict:
    """Build the complete output for a municipality.

    Returns a dict with 'municipality' metadata, 'days' array, and
    'vinmonopolet_stores' with resolved 14-day hours.
    """
    stores = vinmonopolet_stores or []
    max_vinmonopolet_days = 14

    days = []
    for i, cal_entry in enumerate(calendar):
        d = date.fromisoformat(cal_entry["date"])
        entry = build_day_entry(d, cal_entry, municipality)
        # Only resolve Vinmonopolet hours for the first 14 days — beyond that,
        # actual_hours are exhausted and standard_hours fallback is unreliable
        # for holidays further out.
        if i < max_vinmonopolet_days and stores:
            entry["vinmonopolet_summary"] = summarize_vinmonopolet(
                stores, cal_entry["date"], cal_entry["day_type"]
            )
        else:
            entry["vinmonopolet_summary"] = None
        days.append(entry)

    # Resolve per-store 14-day hours (first 14 days only)
    calendar_14 = calendar[:14]
    resolved_stores = build_resolved_stores(stores, calendar_14)
    day_summaries = build_day_summaries(stores, calendar_14) if stores else []

    return {
        "municipality": {
            "id": municipality["id"],
            "name": municipality["name"],
            "county": municipality["county"],
            "sources": municipality["sources"],
            "last_verified": municipality["last_verified"],
        },
        "days": days,
        "vinmonopolet_stores": resolved_stores,
        "vinmonopolet_day_summary": day_summaries,
    }


def _load_municipality(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_vinmonopolet_stores(data_dir: Path) -> dict[str, list[dict]]:
    """Load Vinmonopolet stores grouped by municipality ID.

    Returns a dict mapping municipality_id -> list of store dicts.
    """
    path = data_dir / "generated" / "vinmonopolet.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    stores_by_muni: dict[str, list[dict]] = {}
    for store in data.get("stores", []):
        muni = store.get("municipality")
        if muni:
            stores_by_muni.setdefault(muni, []).append(store)
    return stores_by_muni


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

    vinmonopolet_by_muni = _load_vinmonopolet_stores(data_dir)

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
        result = build_municipality(municipality, calendar, vinmonopolet_stores=stores)

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
