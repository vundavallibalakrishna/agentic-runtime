import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/server";

import { api } from "./api";

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
});
