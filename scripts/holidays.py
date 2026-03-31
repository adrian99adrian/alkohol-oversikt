"""Norwegian public holiday computation and day type classification.

Provides functions to compute Easter, enumerate public holidays and special days,
detect pre-holiday status, and classify any date into a day type for beer sales
time calculation.
"""

from datetime import date, timedelta

# Maps internal English keys to Norwegian display names.
# Keys are used in code/JSON; values are shown to users.
HOLIDAY_NAMES: dict[str, str] = {
    # Public holidays (13 total: 5 fixed + 8 moveable)
    "new_years_day": "1. nyttårsdag",
    "palm_sunday": "Palmesøndag",
    "maundy_thursday": "Skjærtorsdag",
    "good_friday": "Langfredag",
    "easter_sunday": "1. påskedag",
    "easter_monday": "2. påskedag",
    "labour_day": "1. mai",
    "constitution_day": "17. mai",
    "ascension_day": "Kristi himmelfartsdag",
    "whit_sunday": "1. pinsedag",
    "whit_monday": "2. pinsedag",
    "first_christmas_day": "1. juledag",
    "second_christmas_day": "2. juledag",
    # Special days (reduced hours, not full holidays)
    "christmas_eve": "Julaften",
    "easter_eve": "Påskeaften",
    "whit_eve": "Pinseaften",
    "new_years_eve": "Nyttårsaften",
}

# Reverse lookup: Norwegian name → English key (for public holidays only)
_NAME_TO_KEY: dict[str, str] = {v: k for k, v in HOLIDAY_NAMES.items()}

# Day type labels in Norwegian
_DAY_TYPE_LABELS: dict[str, str] = {
    "weekday": "Hverdag",
    "saturday": "Lørdag",
    "sunday": "Søndag",
    "public_holiday": "",  # Filled dynamically from holiday name
    "pre_holiday": "",  # Filled dynamically (e.g., "Dag før skjærtorsdag")
    "special_day": "",  # Filled dynamically from special day name
}


def compute_easter(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm (Computus).

    Valid for any year in the Gregorian calendar.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def get_public_holidays(year: int) -> dict[date, str]:
    """Return all Norwegian public holidays for a year.

    Returns a dict mapping each holiday date to its Norwegian name.
    Includes 5 fixed and 8 moveable holidays (13 total).
    """
    easter = compute_easter(year)

    return {
        # Fixed holidays
        date(year, 1, 1): "1. nyttårsdag",
        date(year, 5, 1): "1. mai",
        date(year, 5, 17): "17. mai",
        date(year, 12, 25): "1. juledag",
        date(year, 12, 26): "2. juledag",
        # Moveable holidays (relative to Easter Sunday)
        easter - timedelta(days=7): "Palmesøndag",
        easter - timedelta(days=3): "Skjærtorsdag",
        easter - timedelta(days=2): "Langfredag",
        easter: "1. påskedag",
        easter + timedelta(days=1): "2. påskedag",
        easter + timedelta(days=39): "Kristi himmelfartsdag",
        easter + timedelta(days=49): "1. pinsedag",
        easter + timedelta(days=50): "2. pinsedag",
    }


def get_special_days(year: int) -> dict[date, str]:
    """Return special days for a year (reduced hours, not full holidays).

    Returns a dict mapping each special day date to its key
    (e.g., "christmas_eve"). These keys match the municipality JSON
    special_days arrays.
    """
    easter = compute_easter(year)
    whit_sunday = easter + timedelta(days=49)

    return {
        easter - timedelta(days=1): "easter_eve",
        whit_sunday - timedelta(days=1): "whit_eve",
        date(year, 12, 24): "christmas_eve",
        date(year, 12, 31): "new_years_eve",
    }


def is_pre_holiday(d: date, holidays: dict[date, str]) -> bool:
    """Check if the day before a Sunday or public holiday.

    A day is pre-holiday if the next day is either:
    - A Sunday (all Saturdays qualify)
    - A public holiday

    Handles year boundaries: Dec 31 checks Jan 1 of the next year.
    """
    tomorrow = d + timedelta(days=1)
    if tomorrow.weekday() == 6:
        return True
    if tomorrow in holidays:
        return True
    # Year boundary: if tomorrow is in a different year, check that year's holidays
    if tomorrow.year != d.year:
        next_year_holidays = get_public_holidays(tomorrow.year)
        return tomorrow in next_year_holidays
    return False


def get_pre_holiday_for(d: date, holidays: dict[date, str]) -> str | None:
    """Return the English key of the holiday/Sunday that follows this day.

    Returns "sunday" (a sentinel value, not in HOLIDAY_NAMES) for regular
    Saturdays before a non-holiday Sunday. Returns the holiday key for days
    before a public holiday. Returns None if this day is not a pre-holiday.

    Handles year boundaries: Dec 31 checks Jan 1 of the next year.
    """
    tomorrow = d + timedelta(days=1)

    if tomorrow in holidays:
        norwegian_name = holidays[tomorrow]
        return _NAME_TO_KEY.get(norwegian_name)

    # Year boundary: check next year's holidays
    if tomorrow.year != d.year:
        next_year_holidays = get_public_holidays(tomorrow.year)
        if tomorrow in next_year_holidays:
            norwegian_name = next_year_holidays[tomorrow]
            return _NAME_TO_KEY.get(norwegian_name)

    if tomorrow.weekday() == 6:  # Sunday
        return "sunday"

    return None


def classify_day(
    d: date,
    holidays: dict[date, str],
    special_days: dict[date, str],
) -> dict:
    """Classify a single date into a day type with full metadata.

    Priority (most restrictive first):
        public_holiday > sunday > special_day > pre_holiday > saturday > weekday

    Returns a dict with keys:
        - day_type: str
        - day_type_label: str (Norwegian)
        - is_public_holiday: bool
        - is_pre_holiday: bool
        - pre_holiday_for: str | None
        - is_special_day: bool
        - special_day_key: str | None
        - holiday_name: str | None
    """
    is_holiday = d in holidays
    is_sunday = d.weekday() == 6
    is_saturday = d.weekday() == 5
    is_special = d in special_days
    pre_holiday = is_pre_holiday(d, holidays)
    pre_holiday_for_key = get_pre_holiday_for(d, holidays) if pre_holiday else None

    holiday_name = holidays.get(d)
    special_day_key = special_days.get(d) if is_special else None

    # Determine day_type by priority
    if is_holiday:
        day_type = "public_holiday"
        day_type_label = holiday_name or ""
    elif is_sunday:
        day_type = "sunday"
        day_type_label = "Søndag"
    elif is_special:
        day_type = "special_day"
        day_type_label = HOLIDAY_NAMES.get(special_day_key or "", "")
    elif pre_holiday and not is_saturday:
        day_type = "pre_holiday"
        # Label like "Dag før skjærtorsdag"
        if pre_holiday_for_key and pre_holiday_for_key != "sunday":
            tomorrow_name = HOLIDAY_NAMES.get(pre_holiday_for_key, "")
            day_type_label = f"Dag før {tomorrow_name.lower()}" if tomorrow_name else ""
        else:
            day_type_label = "Dag før helligdag"
    elif is_saturday:
        day_type = "saturday"
        day_type_label = "Lørdag"
    else:
        day_type = "weekday"
        day_type_label = "Hverdag"

    return {
        "day_type": day_type,
        "day_type_label": day_type_label,
        "is_public_holiday": is_holiday,
        "is_pre_holiday": pre_holiday,
        "pre_holiday_for": pre_holiday_for_key,
        "is_special_day": is_special,
        "special_day_key": special_day_key,
        "holiday_name": holiday_name,
    }
