# Municipality JSON schema

Each file under `data/municipalities/<id>.json` describes one Norwegian kommune's beer-sales rules.

The source of truth for validation is [scripts/validate_data.py](../../scripts/validate_data.py) (`validate_municipality_schema`). This document exists so contributors can see the field list in one place without reading the validator.

## Top-level fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Matches filename. Used in URLs. |
| `name` | string | yes | Display name. |
| `county` | string | yes | Fylke. |
| `beer_sales` | object | yes | See below. |
| `sources` | `[{title, url}]` | yes | At least one entry. Point at the forskrift or kommune page the times come from. |
| `last_verified` | `YYYY-MM-DD` \| null | yes | Must be null when `verified=false`. |
| `verified` | boolean | yes | Flip to `true` once the rules have been checked against a real source. |
| `notes` | string | optional | Free-form display note shown on the kommune page (e.g. bydel-specific rules that don't fit the schema). |

## `beer_sales` fields

### Required

| Field | Type | Example | Notes |
|---|---|---|---|
| `weekday_open` | `HH:MM` | `"08:00"` | Mon-Fri opening. |
| `weekday_close` | `HH:MM` | `"20:00"` | National max 20:00. |
| `saturday_open` | `HH:MM` | `"08:00"` | |
| `saturday_close` | `HH:MM` | `"18:00"` | National max 18:00. |
| `pre_holiday_close` | `HH:MM` | `"18:00"` | Applies to day før søn-/helligdag. National max 18:00 (or 20:00 with a `pre_*` exception). |
| `special_day_close` | `HH:MM` | `"15:00"` | Close time on the special eves listed in `special_days`. |
| `special_days` | array | `["christmas_eve", "new_years_eve"]` | Subset of `easter_eve`, `whit_eve`, `christmas_eve`, `new_years_eve`. Empty array = kommune doesn't treat any eve specially (national-standard kommuner). |

### Optional

| Field | Type | Example | Notes |
|---|---|---|---|
| `special_day_open` | `HH:MM` | `"08:30"` | Opening time on recognized special eves. Falls back to `weekday_open` (or `saturday_open` on Saturday) if absent. Used by kommuner that open later on eves — e.g. Hole 08:30, Orkland 09:00. |
| `exceptions.pre_ascension_day` | `"weekday"` | `"weekday"` | Treat day før Kristi himmelfart as a weekday (close at `weekday_close`). Used by e.g. Larvik. |
| `exceptions.pre_easter_week` | `"pre_holiday"` | `"pre_holiday"` | Force Wed-Sat før påskedag to close at `pre_holiday_close` (18:00). Overrides `special_day_close` on påskeaften. Used by Drammen, Kristiansund, Bærum, Asker, Kongsvinger. |
| `date_overrides` | `[{date: "MM-DD", hours: "saturday"\|"pre_holiday"}]` | `[{"date":"04-30","hours":"saturday"}]` | Force a calendar date into Saturday or pre-holiday hours. Takes precedence over every other rule. Dates are validated as real calendar days (02-30 / 13-01 rejected; leap day accepted). Used by Ørland (April 30, May 16, Dec 27–31). |
| `special_day_close_large_stores` | `HH:MM` | `"16:00"` | Tighter close for stores over `large_store_threshold_sqm`. Only applies on dates listed in `large_store_special_days`. Used by Oslo. |
| `large_store_threshold_sqm` | number | `100` | Square-meter threshold for "large store". |
| `large_store_special_days` | array | `["whit_eve","christmas_eve"]` | Subset of `special_days` that also trigger the large-store rule. |

## Rule precedence

When computing close time for a given date (see [scripts/sales.py](../../scripts/sales.py) `municipal_close`), rules are applied in this order:

1. Sunday / public holiday → sale forbidden (returns `null`).
2. `date_overrides` match → use `saturday_close` or `pre_holiday_close`.
3. `exceptions.pre_easter_week` and day is in påskeuke → `pre_holiday_close`.
4. Day is a recognized special day in `special_days` → `special_day_close`.
5. Pre-holiday with a `pre_*` weekday exception → `weekday_close`.
6. Pre-holiday → `pre_holiday_close`.
7. Saturday → `saturday_close`.
8. Weekday → `weekday_close`.

The final close time is `min(national_max, municipal_close)` — a kommune can only tighten, never loosen, the national maximum.
