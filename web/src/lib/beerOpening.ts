import type { DayData } from "../types";

export const NATIONAL_DEFAULT_BEER_OPEN = "08:00";

export function hasLateBeerOpening(days: DayData[]): boolean {
  // Lexicographic compare is safe: times are always zero-padded HH:MM.
  return days.some(
    (day) =>
      day.beer_sale_allowed &&
      day.beer_open !== null &&
      day.beer_open > NATIONAL_DEFAULT_BEER_OPEN,
  );
}
