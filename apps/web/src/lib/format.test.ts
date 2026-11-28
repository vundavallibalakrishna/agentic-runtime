import { describe, expect, it } from "vitest";

import { formatCost, formatDateTime, fromMicros, toMicros } from "./format";

describe("formatCost", () => {
  it("keeps missing or invalid currency from crashing a screen or inventing a currency", () => {
    for (const currency of [undefined, "", " ", "invalid"]) {
      expect(formatCost(1_250_000, currency)).toBe("1.25");
    }
  });

  it("formats the configured currency and preserves small costs", () => {
    expect(formatCost(1, " usd ")).toBe("$0.000001");
  });
});

describe("formatDateTime", () => {
  it("converts equivalent offset timestamps to the same labelled instant", () => {
    expect(formatDateTime("2026-11-23T14:30:00+05:30", "en")).toBe(
      formatDateTime("2026-11-23T09:00:00Z", "en"),
    );
  });
  it("preserves an invalid service value without crashing the screen", () => {
    expect(formatDateTime("unavailable", "en")).toBe("unavailable");
  });
});

describe("exact currency form conversion", () => {
  it.each([
    ["0", 0],
    ["1", 1000000],
    ["1.250001", 1250001],
    [".5", 500000],
    ["1.", 1000000],
    ["0.000001", 1],
    ["00001.200000", 1200000],
    ["9007199254.740991", Number.MAX_SAFE_INTEGER],
  ])("serializes %s into exactly %s millionths", (input, expected) => {
    expect(toMicros(input)).toBe(expected);
  });
  it.each([
    "",
    "-1",
    "1e3",
    "Infinity",
    "NaN",
    "1x",
    "0.0000001",
    "9007199254.740992",
    "10000000000",
    "1,25",
  ])("refuses %s rather than rounding or guessing", (value) => {
    expect(toMicros(value)).toBeNull();
  });
  it("round-trips safe integer limits, including zero and the precision boundary", () => {
    for (const value of [0, 1, 1234567, 9007199254740990, Number.MAX_SAFE_INTEGER])
      expect(toMicros(fromMicros(value))).toBe(value);
    expect(fromMicros(undefined)).toBe("");
  });
});
