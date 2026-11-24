import { describe, expect, it } from "vitest";

import { wordDiff } from "@/lib/word-diff";

const changed = (parts: { text: string; changed: boolean }[]) =>
  parts.filter((part) => part.changed).map((part) => part.text);
const whole = (parts: { text: string }[]) => parts.map((part) => part.text).join("");

describe("marking the words that differ", () => {
  it("marks one changed figure and nothing else", () => {
    const found = wordDiff("Logs are retained for 90 days.", "Logs are retained for 365 days.");
    expect(changed(found.before)).toEqual(["90"]);
    expect(changed(found.after)).toEqual(["365"]);
  });

  it("keeps every character of both passages, in order", () => {
    const before = "MFA is recommended  for remote access\nand for administrator accounts.";
    const after =
      "MFA is required for all access, for remote access\nand for every administrator account.";
    const found = wordDiff(before, after);
    expect(whole(found.before)).toBe(before);
    expect(whole(found.after)).toBe(after);
  });

  it("joins neighbouring changed words into one run", () => {
    const found = wordDiff("reviewed every twelve months", "reviewed every quarter");
    expect(changed(found.before)).toEqual(["twelve months"]);
    expect(changed(found.after)).toEqual(["quarter"]);
  });

  it("marks words only one side has, at either end", () => {
    const found = wordDiff(
      "It is reviewed yearly",
      "It is reviewed yearly and after any major incident",
    );
    expect(changed(found.before)).toEqual([]);
    expect(changed(found.after)).toEqual(["and after any major incident"]);
  });

  it("marks nothing when the passages are the same or one is empty", () => {
    expect(changed(wordDiff("Same text.", "Same text.").after)).toEqual([]);
    expect(wordDiff("", "New clause.")).toEqual({
      before: [],
      after: [{ text: "New clause.", changed: true }],
    });
  });

  it("shows very long passages whole instead of comparing them", () => {
    const long = Array.from({ length: 1600 }, (_, index) => `w${index}`).join(" ");
    const found = wordDiff(long, `${long} more`);
    expect(found.after).toEqual([{ text: `${long} more`, changed: false }]);
  });
});
