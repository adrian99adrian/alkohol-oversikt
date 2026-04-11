import { describe, it, expect } from "vitest";
import { formatDateShort, formatDateLong, weekdayShort } from "../lib/dateFormat";

describe("formatDateShort", () => {
  it("formats a standard date as DD.MM", () => {
    expect(formatDateShort("2026-04-11")).toBe("11.04");
  });

  it("preserves zero-padded day and month", () => {
    expect(formatDateShort("2026-01-05")).toBe("05.01");
  });

  it("handles December edge", () => {
    expect(formatDateShort("2025-12-31")).toBe("31.12");
  });
});

describe("formatDateLong", () => {
  it("formats a standard date as DD.MM.YYYY", () => {
    expect(formatDateLong("2026-04-11")).toBe("11.04.2026");
  });

  it("handles year boundary", () => {
    expect(formatDateLong("2025-01-01")).toBe("01.01.2025");
  });
});

describe("weekdayShort", () => {
  it("maps all 7 Norwegian weekdays to abbreviations", () => {
    expect(weekdayShort["mandag"]).toBe("man");
    expect(weekdayShort["tirsdag"]).toBe("tir");
    expect(weekdayShort["onsdag"]).toBe("ons");
    expect(weekdayShort["torsdag"]).toBe("tor");
    expect(weekdayShort["fredag"]).toBe("fre");
    expect(weekdayShort["lørdag"]).toBe("lør");
    expect(weekdayShort["søndag"]).toBe("søn");
  });

  it("returns undefined for unknown weekday", () => {
    expect(weekdayShort["monday"]).toBeUndefined();
  });
});
