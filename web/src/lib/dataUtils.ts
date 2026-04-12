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
 * Ignores entries with null lastVerified (unverified kommuner).
 * Returns undefined if the array is empty or contains only nulls.
 */
export function findOldestLastVerified(
  municipalities: { lastVerified: string | null }[],
): string | undefined {
  const verified = municipalities
    .map((m) => m.lastVerified)
    .filter((d): d is string => d !== null);
  if (verified.length === 0) return undefined;
  return verified.reduce((oldest, d) => (d < oldest ? d : oldest), verified[0]);
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
  fetchedAt: string | null | undefined,
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
