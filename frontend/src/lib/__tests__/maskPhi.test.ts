import { describe, it, expect } from "vitest";
import { maskPhi } from "../maskPhi";

describe("maskPhi", () => {
  it("empty string returns length 0 hint", () => {
    expect(maskPhi("")).toBe("[PHI len=0]");
  });

  it("short string returns correct length hint", () => {
    expect(maskPhi("abc")).toBe("[PHI len=3]");
  });

  it("long string returns correct length hint", () => {
    const long = "MRN-12345678-2024";
    expect(maskPhi(long)).toBe(`[PHI len=${long.length}]`);
  });

  it("number is stringified for length calculation", () => {
    expect(maskPhi(12345)).toBe("[PHI len=5]");
  });

  it("undefined returns length of 'undefined' string", () => {
    expect(maskPhi(undefined)).toBe("[PHI len=9]");
  });

  it("null returns length of 'null' string", () => {
    expect(maskPhi(null)).toBe("[PHI len=4]");
  });

  it("never returns the original value", () => {
    const sensitive = "山田太郎-MRN-0001";
    const result = maskPhi(sensitive);
    expect(result).not.toContain("山田");
    expect(result).not.toContain("MRN-0001");
    expect(result).toMatch(/^\[PHI len=\d+\]$/);
  });
});
