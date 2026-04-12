import { describe, it, expect } from "vitest";
import {
  normalizeBasePath,
  isDataFresh,
  findNextDeviation,
  findOldestLastVerified,
  capitalizeFirst,
  isVinmonopoletStale,
  selectFeatured,
  VINMONOPOLET_STALE_THRESHOLD_DAYS,
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

  it("returns undefined for a single null entry", () => {
    expect(findOldestLastVerified([{ lastVerified: null }])).toBeUndefined();
  });

  it("ignores nulls and returns oldest non-null date", () => {
    const items = [
      { lastVerified: "2026-04-15" },
      { lastVerified: null },
      { lastVerified: "2026-03-01" },
      { lastVerified: null },
    ];
    expect(findOldestLastVerified(items)).toBe("2026-03-01");
  });

  it("returns undefined when all entries are null", () => {
    expect(
      findOldestLastVerified([{ lastVerified: null }, { lastVerified: null }]),
    ).toBeUndefined();
  });
});

describe("selectFeatured", () => {
  const items = [
    { id: "oslo", name: "Oslo" },
    { id: "bergen", name: "Bergen" },
    { id: "alta", name: "Alta" },
    { id: "trondheim", name: "Trondheim" },
  ];

  it("returns only items matching the featured ids", () => {
    const got = selectFeatured(items, ["oslo", "bergen"]);
    expect(got.map((i) => i.id).sort()).toEqual(["bergen", "oslo"]);
  });

  it("silently skips unknown ids", () => {
    const got = selectFeatured(items, ["oslo", "nonexistent", "bergen"]);
    expect(got.map((i) => i.id)).toEqual(["oslo", "bergen"]);
  });

  it("preserves the order of featuredIds", () => {
    const got = selectFeatured(items, ["trondheim", "oslo", "bergen"]);
    expect(got.map((i) => i.id)).toEqual(["trondheim", "oslo", "bergen"]);
  });

  it("returns empty when featuredIds is empty", () => {
    expect(selectFeatured(items, [])).toEqual([]);
  });

  it("returns empty when items is empty", () => {
    expect(selectFeatured([], ["oslo"])).toEqual([]);
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

describe("isVinmonopoletStale", () => {
  // Reference: April 12, 2026 12:00 UTC+2 as "now"
  const now = new Date("2026-04-12T12:00:00+02:00");

  it("returns false for undefined input", () => {
    expect(isVinmonopoletStale(undefined, 2, now)).toBe(false);
  });

  it("returns false for empty string", () => {
    expect(isVinmonopoletStale("", 2, now)).toBe(false);
  });

  it("returns false for invalid timestamp", () => {
    expect(isVinmonopoletStale("not-a-timestamp", 2, now)).toBe(false);
  });

  it("returns false for fresh data (same day)", () => {
    expect(isVinmonopoletStale("2026-04-12T06:00:00+02:00", 2, now)).toBe(false);
  });

  it("returns false for data within threshold", () => {
    // 1 day old, threshold 2 days
    expect(isVinmonopoletStale("2026-04-11T12:00:00+02:00", 2, now)).toBe(false);
  });

  it("returns true for stale data (5 days old)", () => {
    expect(isVinmonopoletStale("2026-04-07T12:00:00+02:00", 2, now)).toBe(true);
  });

  it("handles Python ISO format with timezone", () => {
    // 10 days old
    expect(isVinmonopoletStale("2026-04-02T10:00:00+02:00", 2, now)).toBe(true);
  });

  it("returns false exactly at the threshold boundary", () => {
    // Exactly 2 days old (48 hours) — not yet past threshold
    expect(isVinmonopoletStale("2026-04-10T12:00:00+02:00", 2, now)).toBe(false);
  });

  it("returns true just past the threshold", () => {
    // 2 days + 1 second
    expect(isVinmonopoletStale("2026-04-10T11:59:59+02:00", 2, now)).toBe(true);
  });

  it("exports a reasonable threshold constant", () => {
    expect(VINMONOPOLET_STALE_THRESHOLD_DAYS).toBe(2);
  });
});
