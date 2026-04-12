import { describe, it, expect } from "vitest";
import { hasLateBeerOpening, NATIONAL_DEFAULT_BEER_OPEN } from "../lib/beerOpening";
import type { DayData } from "../types";

function makeDay(overrides: Partial<DayData> = {}): DayData {
  return {
    date: "2026-04-13",
    weekday: "mandag",
    day_type: "weekday",
    day_type_label: "Hverdag",
    beer_sale_allowed: true,
    beer_open: "08:00",
    beer_close: "20:00",
    beer_close_large_stores: null,
    is_deviation: false,
    comment: null,
    vinmonopolet_summary: null,
    ...overrides,
  };
}

describe("NATIONAL_DEFAULT_BEER_OPEN", () => {
  it("is 08:00", () => {
    expect(NATIONAL_DEFAULT_BEER_OPEN).toBe("08:00");
  });
});

describe("hasLateBeerOpening", () => {
  it("returns false for empty array", () => {
    expect(hasLateBeerOpening([])).toBe(false);
  });

  it("returns false when all days open at the national default", () => {
    const days = [makeDay({ beer_open: "08:00" }), makeDay({ beer_open: "08:00" })];
    expect(hasLateBeerOpening(days)).toBe(false);
  });

  it("returns true when a beer-sales day opens later than 08:00", () => {
    const days = [makeDay({ beer_open: "08:00" }), makeDay({ beer_open: "09:00" })];
    expect(hasLateBeerOpening(days)).toBe(true);
  });

  it("ignores late opening on days where sale is not allowed", () => {
    const days = [
      makeDay({ beer_open: "08:00" }),
      makeDay({
        beer_sale_allowed: false,
        beer_open: "10:00",
        day_type: "sunday",
        day_type_label: "Søndag",
      }),
    ];
    expect(hasLateBeerOpening(days)).toBe(false);
  });

  it("returns false when beer_open is null", () => {
    const days = [makeDay({ beer_open: null })];
    expect(hasLateBeerOpening(days)).toBe(false);
  });
});
