import { cleanup, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QuotasScreen } from "@/components/usage/quotas-screen";
import { UsageScreen } from "@/components/usage/usage-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/chat",
  useRouter: () => ({ push: () => undefined }),
}));

vi.mock("next/dynamic", () => ({
  default: () => () => null,
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("usage screens", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows a daily total and an export action", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["usage:read"], user: { displayName: "Admin" } }),
      ),
      http.get("*/api/v1/usage/summary", () =>
        HttpResponse.json({
          currency: "INR",
          totals: { quantity: 36000, costMicros: 1200 },
          rows: [{ keys: { day: "2026-10-22" }, quantity: 36000, costMicros: 1200 }],
        }),
      ),
    );
    render(wrap(<UsageScreen />));
    expect(await screen.findByRole("heading", { name: "Usage" })).toBeTruthy();
    expect(await screen.findByText("36,000")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Export CSV" })).toBeTruthy();
  });

  it("lists a token quota with a consumption bar", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["usage:read"], user: { displayName: "Admin" } }),
      ),
      http.get("*/api/v1/quotas", () =>
        HttpResponse.json({
          items: [
            {
              id: "q1",
              metric: "model_tokens",
              period: "day",
              scopeType: "user",
              scope: { id: "u1", name: "Dev Admin" },
              limitValue: 100000,
              used: 36000,
              implicit: false,
            },
          ],
        }),
      ),
    );
    render(wrap(<QuotasScreen />));
    expect(await screen.findByRole("heading", { name: "model_tokens · day" })).toBeTruthy();
    expect(screen.getByText("Dev Admin")).toBeTruthy();
    expect(screen.getByRole("progressbar")).toBeTruthy();
  });

  it("shows the quota error state", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["usage:read"] })),
      http.get("*/api/v1/quotas", () => HttpResponse.json({ detail: "down" }, { status: 500 })),
    );
    render(wrap(<QuotasScreen />));
    expect(await screen.findByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
