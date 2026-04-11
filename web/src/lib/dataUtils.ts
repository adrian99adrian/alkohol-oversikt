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
