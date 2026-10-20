import { describe, expect, it } from "vitest";

import { sanitizeHtml } from "./markdown";

describe("sanitizeHtml", () => {
  it("removes script tags", () => {
    const clean = sanitizeHtml('<p>Hello</p><script>alert("x")</script>');
    expect(clean).toContain("Hello");
    expect(clean.toLowerCase()).not.toContain("<script");
  });
});
