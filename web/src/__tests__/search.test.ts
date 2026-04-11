import { describe, it, expect } from "vitest";
import { normalizeSearch, filterMunicipalities } from "../lib/search";

describe("normalizeSearch", () => {
  it("lowercases input", () => {
    expect(normalizeSearch("Oslo")).toBe("oslo");
  });

  it("preserves Norwegian characters after NFC normalization", () => {
    expect(normalizeSearch("BODØ")).toBe("bodø");
  });

  it("handles already lowercase input", () => {
    expect(normalizeSearch("bergen")).toBe("bergen");
  });

  it("normalizes NFD-decomposed characters to NFC form", () => {
    // å as a + combining ring above (NFD) vs precomposed å (NFC)
    const decomposed = "a\u030A"; // a + combining ring above
    expect(normalizeSearch(decomposed)).toBe(normalizeSearch("å"));
  });
});

describe("filterMunicipalities", () => {
  const items = [
    { id: "0301", name: "Oslo" },
    { id: "4601", name: "Bergen" },
    { id: "5001", name: "Trondheim" },
    { id: "1804", name: "Bodø" },
    { id: "3803", name: "Sandefjord" },
  ];

  it("finds exact match", () => {
    const result = filterMunicipalities(items, "Oslo");
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Oslo");
  });

  it("finds substring match", () => {
    const result = filterMunicipalities(items, "berg");
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Bergen");
  });

  it("is case-insensitive", () => {
    const result = filterMunicipalities(items, "BERGEN");
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Bergen");
  });

  it("matches Norwegian characters", () => {
    const result = filterMunicipalities(items, "bodø");
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Bodø");
  });

  it("returns empty array for no match", () => {
    expect(filterMunicipalities(items, "xyz")).toHaveLength(0);
  });

  it("returns all items for empty query", () => {
    expect(filterMunicipalities(items, "")).toHaveLength(5);
  });
});
