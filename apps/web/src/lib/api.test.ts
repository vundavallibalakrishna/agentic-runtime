import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/server";

import { ApiError, api, apiErrorGuidance, isRateLimited } from "./api";

describe("api", () => {
  it("shares one in-flight GET and sends the next one", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v1/agents", async () => {
        calls += 1;
        await new Promise((resolve) => setTimeout(resolve, 20));
        return HttpResponse.json({ items: [calls] });
      }),
    );
    const [first, second] = await Promise.all([
      api<{ items: number[] }>("/api/v1/agents"),
      api<{ items: number[] }>("/api/v1/agents"),
    ]);
    expect(second).toBe(first);
    expect(calls).toBe(1);
    await api("/api/v1/agents");
    expect(calls).toBe(2);
  });
  it("accepts an empty successful response without treating it as invalid JSON", async () => {
    server.use(http.post("*/api/v1/accepted", () => new HttpResponse(null, { status: 202 })));
    await expect(api("/api/v1/accepted", { method: "POST" })).resolves.toBeUndefined();
  });
  it("tells too many requests apart from a used-up quota", () => {
    expect(isRateLimited(new ApiError("Slow down", 429, "rate_limited"))).toBe(true);
    expect(isRateLimited(new ApiError("Too many requests", 429))).toBe(true);
    const quota = new ApiError("Quota reached: the limit is 0", 429, "quota_exceeded");
    expect(isRateLimited(quota)).toBe(false);
    expect(apiErrorGuidance(quota)).toBeNull();
  });
  it("retains a refused write's code, status and message without retrying it", async () => {
    let writes = 0;
    server.use(
      http.post("*/api/v1/refused-write", () => {
        writes += 1;
        return HttpResponse.json(
          { detail: "Origin rejected", code: "csrf_failed" },
          { status: 403 },
        );
      }),
    );
    const error = await api("/api/v1/refused-write", { method: "POST" }).catch(
      (caught: unknown) => caught,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ message: "Origin rejected", code: "csrf_failed", status: 403 });
    expect(apiErrorGuidance(error as ApiError)).toBe("csrf");
    expect(writes).toBe(1);
  });
});
