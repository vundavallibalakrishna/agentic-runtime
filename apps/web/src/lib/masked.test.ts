import { describe, expect, it } from "vitest";

import { markMasked } from "@/lib/masked";

describe("masked values", () => {
  it("turns a masking token into inline code, wherever it stands", () => {
    expect(markMasked("Write to [EMAIL_ADDRESS] today.")).toBe("Write to `[EMAIL_ADDRESS]` today.");
    expect(markMasked("- [NRP]: 1042.5\n- North: 817.0")).toBe("- `[NRP]`: 1042.5\n- North: 817.0");
    expect(markMasked("[US_SSN]: on file")).toBe("`[US_SSN]`: on file");
  });

  it("leaves Markdown links, references and code alone", () => {
    expect(markMasked("[README](https://example.com/readme)")).toBe(
      "[README](https://example.com/readme)",
    );
    expect(markMasked("[DOCS][1]\n\n[1]: https://example.com")).toBe(
      "[DOCS][1]\n\n[1]: https://example.com",
    );
    expect(markMasked("already `[EMAIL_ADDRESS]` here")).toBe("already `[EMAIL_ADDRESS]` here");
    expect(markMasked("```\n[EMAIL_ADDRESS]\n```")).toBe("```\n[EMAIL_ADDRESS]\n```");
    expect(markMasked("[x] done and [SEE ALSO]")).toBe("[x] done and [SEE ALSO]");
  });
});
