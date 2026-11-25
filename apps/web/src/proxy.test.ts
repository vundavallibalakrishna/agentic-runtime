import { describe, expect, it } from "vitest";

import { PUBLIC_PATH } from "./proxy";

const gate = new RegExp(`^${PUBLIC_PATH}$`);

describe("the session gate", () => {
  it("leaves a review link open and still gates the review queue", () => {
    expect(gate.test("/review/token")).toBe(false);
    expect(gate.test("/review")).toBe(false);
    expect(gate.test("/reviews")).toBe(true);
    expect(gate.test("/reviews/abc")).toBe(true);
  });
});
