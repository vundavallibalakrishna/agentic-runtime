import { describe, expect, it } from "vitest";

import { filterMarkdown, linkRel } from "@/lib/markdown-exfil";

describe("markdown exfiltration filter", () => {
  it("drops remote images and hides long query links", () => {
    const source =
      "See ![secret](https://evil.example/a.png) and [go](https://evil.example/x?q=" +
      "A".repeat(40) +
      ")";
    const safe = filterMarkdown(source);
    expect(safe).toContain("secret");
    expect(safe).not.toContain("evil.example/a.png");
    expect(safe).toContain("link hidden");
    expect(linkRel).toContain("nofollow");
  });
});
