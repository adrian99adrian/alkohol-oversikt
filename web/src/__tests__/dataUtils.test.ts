import { describe, it, expect } from "vitest";
import {
  normalizeBasePath,
  isDataFresh,
  findNextDeviation,
  findOldestLastVerified,
  capitalizeFirst,
} from "../lib/dataUtils";
import type { DayData } from "../types";

// Minimal DayData factory for testing
function makeDay(overrides: Partial<DayData> = {}): DayData {
  return {
    date: "2026-04-11",
    weekday: "lørdag",
    day_type: "saturday",
    day_type_label: "Lørdag",
    beer_sale_allowed: true,
    beer_open: "09:00",
    beer_close: "18:00",
    beer_close_large_stores: null,
    is_deviation: false,
    comment: null,
    vinmonopolet_summary: null,
    ...overrides,
  };
}

describe("normalizeBasePath", () => {
  it("keeps existing trailing slash", () => {
    expect(normalizeBasePath("/foo/")).toBe("/foo/");
  });

  it("adds missing trailing slash", () => {
    expect(normalizeBasePath("/foo")).toBe("/foo/");
  });

  it("keeps root slash unchanged", () => {
    expect(normalizeBasePath("/")).toBe("/");
  });
});

describe("isDataFresh", () => {
  it("returns false for empty array", () => {
    expect(isDataFresh([], "2026-04-11")).toBe(false);
  });

  it("returns true when first day matches build date", () => {
    const days = [makeDay({ date: "2026-04-11" })];
    expect(isDataFresh(days, "2026-04-11")).toBe(true);
  });

  it("returns false when first day does not match", () => {
    const days = [makeDay({ date: "2026-04-10" })];
    expect(isDataFresh(days, "2026-04-11")).toBe(false);
  });
});

describe("findNextDeviation", () => {
  it("returns null for empty array", () => {
    expect(findNextDeviation([])).toBeNull();
  });

  it("returns null when no days are deviations", () => {
    const days = [makeDay(), makeDay({ date: "2026-04-12" })];
    expect(findNextDeviation(days)).toBeNull();
  });

  it("returns the first deviation day", () => {
    const deviation = makeDay({
      date: "2026-04-13",
      is_deviation: true,
      comment: "Dag før 1. mai",
    });
    const days = [makeDay(), makeDay({ date: "2026-04-12" }), deviation];
    expect(findNextDeviation(days)).toBe(deviation);
  });

  it("validates 14-day slice contract: deviation outside slice is not found", () => {
    // 14 normal days followed by a deviation on day 19
    const allDays = Array.from({ length: 20 }, (_, i) =>
      makeDay({
        date: `2026-04-${String(11 + i).padStart(2, "0")}`,
        is_deviation: i === 19,
      }),
    );
    const sliced = allDays.slice(0, 14);
    expect(findNextDeviation(sliced)).toBeNull();
    // But if we pass all days, the deviation is found
    expect(findNextDeviation(allDays)).not.toBeNull();
  });
});

describe("findOldestLastVerified", () => {
  it("returns undefined for empty array", () => {
    expect(findOldestLastVerified([])).toBeUndefined();
  });

  it("returns the only entry for single item", () => {
    expect(
      findOldestLastVerified([{ lastVerified: "2026-03-01" }]),
    ).toBe("2026-03-01");
  });

  it("returns the oldest date from multiple items", () => {
    const items = [
      { lastVerified: "2026-04-15" },
      { lastVerified: "2026-03-01" },
      { lastVerified: "2026-04-20" },
    ];
    expect(findOldestLastVerified(items)).toBe("2026-03-01");
  });
});

describe("capitalizeFirst", () => {
  it("capitalizes a Norwegian weekday", () => {
    expect(capitalizeFirst("mandag")).toBe("Mandag");
  });

  it("handles single character", () => {
    expect(capitalizeFirst("m")).toBe("M");
  });

  it("handles empty string", () => {
    expect(capitalizeFirst("")).toBe("");
  });
});
