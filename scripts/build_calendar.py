"""Generate calendar.json with holidays and day types for the next N days.

Usage:
    python scripts/build_calendar.py [--days N] [--start-date YYYY-MM-DD]

Outputs to data/generated/calendar.json.
"""

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from holidays import classify_day, get_public_holidays, get_special_days

WEEKDAY_NAMES_NO: dict[int, str] = {
    0: "mandag",
    1: "tirsdag",
    2: "onsdag",
    3: "torsdag",
    4: "fredag",
    5: "lørdag",
    6: "søndag",
}


def get_today_oslo() -> date:
    """Return today's date in the Europe/Oslo timezone."""
    return datetime.now(tz=ZoneInfo("Europe/Oslo")).date()


def build_calendar(start_date: date, num_days: int = 365) -> list[dict]:
    """Build calendar entries for num_days starting from start_date.

    Returns a list of dicts, one per day, with holiday classification
    and Norwegian weekday names.
    """
    # Collect holidays and special days for all years in the range
    end_date = start_date + timedelta(days=num_days - 1)
    years = set(range(start_date.year, end_date.year + 1))

    all_holidays: dict[date, str] = {}
    all_special_days: dict[date, str] = {}
    for year in years:
        all_holidays.update(get_public_holidays(year))
        all_special_days.update(get_special_days(year))

    entries = []
    for i in range(num_days):
        d = start_date + timedelta(days=i)
        day_info = classify_day(d, all_holidays, all_special_days)
        entry = {
            "date": d.isoformat(),
            "weekday": WEEKDAY_NAMES_NO[d.weekday()],
            **day_info,
        }
        entries.append(entry)

    return entries


def main() -> None:
    """CLI entry point: generate data/generated/calendar.json."""
    parser = argparse.ArgumentParser(description="Generate calendar with holiday data")
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of days to generate (default: 365)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date in YYYY-MM-DD format (default: today in Europe/Oslo)",
    )
    args = parser.parse_args()

    start = date.fromisoformat(args.start_date) if args.start_date else get_today_oslo()
    calendar = build_calendar(start, num_days=args.days)

    output_path = Path(__file__).parent.parent / "data" / "generated" / "calendar.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(calendar, f, ensure_ascii=False, indent=2)

    print(f"Generated {len(calendar)} days to {output_path}")


if __name__ == "__main__":
    main()
