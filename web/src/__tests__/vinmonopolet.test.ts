import { describe, it, expect } from "vitest";
import {
  formatVinmonopolet,
  storeLabel,
  formatVinmonopoletRange,
} from "../lib/vinmonopolet";
import type { VinmonopoletSummary } from "../types";

describe("formatVinmonopolet", () => {
  it("returns Stengt for null", () => {
    expect(formatVinmonopolet(null)).toBe("Stengt");
  });

  it("returns Stengt for closed type", () => {
    const summary: VinmonopoletSummary = {
      type: "closed",
      open_count: 0,
      closed_count: 3,
    };
    expect(formatVinmonopolet(summary)).toBe("Stengt");
  });

  it("returns open–close for uniform type", () => {
    const summary: VinmonopoletSummary = {
      type: "uniform",
      open: "10:00",
      close: "18:00",
      open_count: 2,
      closed_count: 0,
    };
    expect(formatVinmonopolet(summary)).toBe("10:00\u201318:00");
  });

  it("returns min_open–max_close for range type", () => {
    const summary: VinmonopoletSummary = {
      type: "range",
      min_open: "09:00",
      max_open: "10:00",
      min_close: "17:00",
      max_close: "20:00",
      open_count: 3,
      closed_count: 1,
    };
    expect(formatVinmonopolet(summary)).toBe("09:00\u201320:00");
  });

  it("handles uniform type with missing open/close as undefined", () => {
    const summary: VinmonopoletSummary = {
      type: "uniform",
      open_count: 1,
      closed_count: 0,
    };
    expect(formatVinmonopolet(summary)).toBe("undefined\u2013undefined");
  });
});

describe("storeLabel", () => {
  it("returns butikk for 1", () => {
    expect(storeLabel(1)).toBe("butikk");
  });

  it("returns butikker for 0", () => {
    expect(storeLabel(0)).toBe("butikker");
  });

  it("returns butikker for 5", () => {
    expect(storeLabel(5)).toBe("butikker");
  });
});

describe("formatVinmonopoletRange", () => {
  it("returns single value when min equals max", () => {
    expect(formatVinmonopoletRange("10:00", "10:00")).toBe("10:00");
  });

  it("returns range when min differs from max", () => {
    expect(formatVinmonopoletRange("09:00", "11:00")).toBe("09:00\u201311:00");
  });
});
