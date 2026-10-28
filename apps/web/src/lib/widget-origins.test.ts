import { describe, expect, it } from "vitest";

import { exactOrigins } from "./widget-origins";

describe("widget frame origins", () => {
  it("rejects CSP injection, credentials, paths and deceptive localhost names", () => {
    expect(
      exactOrigins([
        "https://portal.example",
        "http://localhost:3101",
        "http://127.0.0.1:3101",
        "https://evil.test; frame-ancestors *",
        "https://portal.example/path",
        "http://localhost.evil.test",
        "https://user@portal.example",
        "*",
        "https://portal.example\nhttps://evil.test",
        "https://*.example",
        "https://portal.example\\evil",
        null,
      ]),
    ).toEqual(["https://portal.example", "http://localhost:3101", "http://127.0.0.1:3101"]);
    expect(exactOrigins(undefined)).toEqual([]);
  });
});
