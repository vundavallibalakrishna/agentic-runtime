import { describe, expect, it } from "vitest";

import { fileTypeKey } from "@/lib/file-type";

describe("naming a file type", () => {
  it("knows the office formats by their long media types", () => {
    expect(
      fileTypeKey("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ).toBe("word");
    expect(fileTypeKey("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")).toBe(
      "excel",
    );
    expect(fileTypeKey("application/pdf")).toBe("pdf");
  });

  it("ignores parameters and case", () => {
    expect(fileTypeKey("Text/CSV; charset=utf-8")).toBe("csv");
  });

  it("returns nothing for a type it does not know, so the caller shows it as it is", () => {
    expect(fileTypeKey("application/x-something")).toBe("");
    expect(fileTypeKey(undefined)).toBe("");
  });
});
