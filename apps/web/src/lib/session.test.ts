import { HttpResponse, http } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { server } from "@/test/server";

import { clearCachedSession, loadSession, SESSION_CACHE_TTL_MS } from "./session";

afterEach(() => {
  clearCachedSession();
});

describe("loadSession", () => {
  it("shares one request and reuses the result until the TTL", async () => {
    let calls = 0;
    let now = 0;
    server.use(
      http.get("*/api/v1/auth/session", async () => {
        calls += 1;
        await new Promise((resolve) => setTimeout(resolve, 15));
        return HttpResponse.json({ permissions: ["chat:use"] });
      }),
    );
    const [first, second] = await Promise.all([loadSession(() => now), loadSession(() => now)]);
    expect(second).toBe(first);
    expect(calls).toBe(1);
    await loadSession(() => now);
    expect(calls).toBe(1);
    now = SESSION_CACHE_TTL_MS;
    await loadSession(() => now);
    expect(calls).toBe(2);
  });

  it("does not reuse a failed read", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v1/auth/session", () => {
        calls += 1;
        if (calls === 1) {
          return HttpResponse.json(
            { code: "rate_limited", detail: "rate limit exceeded" },
            { status: 429 },
          );
        }
        return HttpResponse.json({ permissions: ["chat:use"] });
      }),
    );
    await expect(loadSession()).rejects.toMatchObject({ status: 429, code: "rate_limited" });
    await expect(loadSession()).resolves.toMatchObject({ permissions: ["chat:use"] });
    expect(calls).toBe(2);
  });
});
