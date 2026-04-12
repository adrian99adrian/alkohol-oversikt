import type { DayData } from "../types";

/** Ensure a base path ends with a trailing slash. */
export function normalizeBasePath(base: string): string {
  return base.endsWith("/") ? base : `${base}/`;
}

/** Check whether the dataset starts from the given build date. */
export function isDataFresh(days: DayData[], buildDate: string): boolean {
  return days.length > 0 && days[0].date === buildDate;
}

/** Find the first day with is_deviation === true in the given array. */
export function findNextDeviation(days: DayData[]): DayData | null {
  return days.find((d) => d.is_deviation) ?? null;
}

/**
 * Find the oldest (minimum) lastVerified date from a list of municipalities.
 * Returns undefined if the array is empty.
 */
export function findOldestLastVerified(
  municipalities: { lastVerified: string }[],
): string | undefined {
  if (municipalities.length === 0) return undefined;
  return municipalities.reduce(
    (oldest, m) => (m.lastVerified < oldest ? m.lastVerified : oldest),
    municipalities[0].lastVerified,
  );
}

/** Capitalize the first letter of a string. */
export function capitalizeFirst(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/** Maximum acceptable age of Vinmonopolet data (in days) before showing a staleness warning. */
export const VINMONOPOLET_STALE_THRESHOLD_DAYS = 2;

/**
 * Check whether a Vinmonopolet fetched_at timestamp is older than maxAgeDays.
 * Returns false for undefined/empty/invalid inputs (graceful — no warning shown).
 * The `now` parameter enables deterministic testing.
 */
export function isVinmonopoletStale(
  fetchedAt: string | undefined,
  maxAgeDays: number,
  now: Date = new Date(),
): boolean {
  if (!fetchedAt) return false;
  const fetchedTime = new Date(fetchedAt).getTime();
  if (Number.isNaN(fetchedTime)) return false;
  const ageMs = now.getTime() - fetchedTime;
  const maxAgeMs = maxAgeDays * 24 * 60 * 60 * 1000;
  return ageMs > maxAgeMs;
}
