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


def build_municipality(municipality: dict, calendar: list[dict]) -> dict:
    """Build the complete output for a municipality.

    Returns a dict with 'municipality' metadata and 'days' array,
    matching the generated municipality JSON contract.
    """
    days = []
    for cal_entry in calendar:
        d = date.fromisoformat(cal_entry["date"])
        entry = build_day_entry(d, cal_entry, municipality)
        days.append(entry)

    return {
        "municipality": {
            "id": municipality["id"],
            "name": municipality["name"],
            "county": municipality["county"],
            "sources": municipality["sources"],
            "last_verified": municipality["last_verified"],
        },
        "days": days,
    }


def _load_municipality(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate municipality beer sales data")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Generate for all municipalities")
    group.add_argument("--id", type=str, help="Generate for a specific municipality ID")
    parser.add_argument("--days", type=int, default=365, help="Number of days (default: 365)")
    parser.add_argument("--start-date", type=str, default=None, help="Start date YYYY-MM-DD")
    args = parser.parse_args()

    start = date.fromisoformat(args.start_date) if args.start_date else get_today_oslo()
    calendar = build_calendar(start, num_days=args.days)

    data_dir = Path(__file__).parent.parent / "data"
    municipalities_dir = data_dir / "municipalities"
    output_dir = data_dir / "generated" / "municipalities"
    output_dir.mkdir(parents=True, exist_ok=True)

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
        result = build_municipality(municipality, calendar)

        output_path = output_dir / f"{municipality['id']}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"Generated {len(result['days'])} days for {municipality['name']} -> {output_path}")


if __name__ == "__main__":
    main()
