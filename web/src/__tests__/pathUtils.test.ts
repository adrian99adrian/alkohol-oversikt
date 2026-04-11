import { describe, it, expect } from "vitest";
import { stripBasePrefix, normalizePath, isKommunePath } from "../lib/pathUtils";

describe("stripBasePrefix", () => {
  it("strips base path with trailing slash", () => {
    expect(
      stripBasePrefix("/alkohol-oversikt/kommune/0301", "/alkohol-oversikt/"),
    ).toBe("/kommune/0301");
  });

  it("strips base path without trailing slash", () => {
    expect(
      stripBasePrefix("/alkohol-oversikt/kommune/0301", "/alkohol-oversikt"),
    ).toBe("/kommune/0301");
  });

  it("returns path unchanged when no base prefix", () => {
    expect(stripBasePrefix("/kommune/0301", "/other/")).toBe("/kommune/0301");
  });

  it("handles root base path", () => {
    expect(stripBasePrefix("/kommune/0301", "/")).toBe("/kommune/0301");
  });
});

describe("normalizePath", () => {
  it("returns already normalized path unchanged", () => {
    expect(normalizePath("/kommune/0301")).toBe("/kommune/0301");
  });

  it("adds missing leading slash", () => {
    expect(normalizePath("kommune/0301")).toBe("/kommune/0301");
  });

  it("removes trailing slash", () => {
    expect(normalizePath("/kommune/0301/")).toBe("/kommune/0301");
  });

  it("keeps root slash unchanged", () => {
    expect(normalizePath("/")).toBe("/");
  });

  it("handles both missing leading and trailing slash", () => {
    expect(normalizePath("kommune/0301/")).toBe("/kommune/0301");
  });
});

describe("isKommunePath", () => {
  it("returns true for valid kommune path", () => {
    expect(isKommunePath("/kommune/0301")).toBe(true);
  });

  it("returns true for alphanumeric IDs", () => {
    expect(isKommunePath("/kommune/sandefjord")).toBe(true);
  });

  it("returns false for nested path", () => {
    expect(isKommunePath("/kommune/0301/extra")).toBe(false);
  });

  it("returns false for missing ID", () => {
    expect(isKommunePath("/kommune")).toBe(false);
  });

  it("returns false for unrelated path", () => {
    expect(isKommunePath("/about")).toBe(false);
  });

  it("returns false for root path", () => {
    expect(isKommunePath("/")).toBe(false);
  });
});

describe("full path processing pipeline", () => {
  it("correctly identifies a kommune path after stripping and normalizing", () => {
    const raw = "/alkohol-oversikt/kommune/0301/";
    const stripped = stripBasePrefix(raw, "/alkohol-oversikt/");
    const normalized = normalizePath(stripped);
    expect(isKommunePath(normalized)).toBe(true);
  });

  it("rejects non-kommune path after processing", () => {
    const raw = "/alkohol-oversikt/about/";
    const stripped = stripBasePrefix(raw, "/alkohol-oversikt/");
    const normalized = normalizePath(stripped);
    expect(isKommunePath(normalized)).toBe(false);
  });
});
