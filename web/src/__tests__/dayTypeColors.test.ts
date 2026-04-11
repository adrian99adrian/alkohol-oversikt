import { describe, it, expect } from "vitest";
import { dayTypeColorMap } from "../lib/dayTypeColors";

describe("dayTypeColorMap", () => {
  it("maps weekday to green classes", () => {
    expect(dayTypeColorMap["weekday"]).toContain("bg-green");
  });

  it("maps saturday to yellow classes", () => {
    expect(dayTypeColorMap["saturday"]).toContain("bg-yellow");
  });

  it("maps pre_holiday to orange classes", () => {
    expect(dayTypeColorMap["pre_holiday"]).toContain("bg-orange");
  });

  it("maps special_day to orange classes", () => {
    expect(dayTypeColorMap["special_day"]).toContain("bg-orange");
  });

  it("maps sunday to red classes", () => {
    expect(dayTypeColorMap["sunday"]).toContain("bg-red");
  });

  it("maps public_holiday to red classes", () => {
    expect(dayTypeColorMap["public_holiday"]).toContain("bg-red");
  });

  it("returns undefined for unknown day type", () => {
    expect(dayTypeColorMap["unknown"]).toBeUndefined();
  });
});
