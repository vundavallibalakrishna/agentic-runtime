import { describe, expect, it } from "vitest";
import { decimalNumber, fromRate, toRate } from "./suite-data";

describe("stored evaluation gate decimals", () => {
  it.each([
    [0, "0"],
    [1, "100"],
    [0.145, "14.5"],
    [0.3333333333333333, "33.33333333333333"],
    [0.9999999999999999, "99.99999999999999"],
    [0.0000001, "0.00001"],
  ] as const)("round trips %s without percentage multiply/divide drift", (rate, percent) => {
    expect(fromRate(rate)).toBe(percent);
    expect(toRate(percent)).toBe(rate);
  });
  it.each([
    "",
    "-1",
    "101",
    "0x10",
    "1e1",
    "99.999999999999999",
    "0.00000000000000000000000000000000000000000000000000000000000001x",
  ])("rejects invalid or unrepresentable rate %j", (value) => expect(toRate(value)).toBeNull());
  it("accepts normalized decimals and preserves valid negative/small regression numbers", () => {
    expect(toRate(" 0014.5000 ")).toBe(0.145);
    expect(decimalNumber("-2.25")).toBe(-2.25);
    expect(decimalNumber("1e-7")).toBe(1e-7);
    expect(decimalNumber("0e999999999")).toBe(0);
  });
  it.each(["Infinity", "0x10", "1e999", "1e-999", "10.000000000000000001"])(
    "rejects regression conversion loss %j",
    (value) => expect(decimalNumber(value)).toBeNull(),
  );
});
