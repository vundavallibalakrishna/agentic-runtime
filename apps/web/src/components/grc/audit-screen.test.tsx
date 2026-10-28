import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuditScreen } from "@/components/grc/audit-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const notFound = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/grc/audit/requests",
  useRouter: () => ({ push: () => undefined, replace: () => undefined }),
  notFound: () => notFound(),
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

function pack() {
  return http.get("*/api/v1/tenant/packs", () =>
    HttpResponse.json({ items: [{ packId: "grc", enabled: true, nav: [] }] }),
  );
}

function session() {
  return http.get("*/api/v1/auth/session", () =>
    HttpResponse.json({ permissions: ["grc.controls:read"], user: { displayName: "Admin" } }),
  );
}

describe("GRC audit", () => {
  afterEach(() => {
    cleanup();
    notFound.mockClear();
  });

  it("shows an empty request list", async () => {
    server.use(
      session(),
      pack(),
      http.get("*/api/v1/ext/grc/pbc-requests", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<AuditScreen section="requests" />));
    expect(await screen.findByText("No prepared-by-client requests yet.")).toBeTruthy();
  });

  it("lists a prepared-by-client request", async () => {
    server.use(
      session(),
      pack(),
      http.get("*/api/v1/ext/grc/pbc-requests", () =>
        HttpResponse.json({
          items: [{ id: "p1", title: "SOC 2 population extract", status: "open" }],
        }),
      ),
    );
    render(wrap(<AuditScreen section="requests" />));
    expect(await screen.findByText("SOC 2 population extract")).toBeTruthy();
    expect(await screen.findByText("open")).toBeTruthy();
  });

  it("shows an error when reviews cannot be loaded", async () => {
    server.use(
      session(),
      pack(),
      http.get("*/api/v1/ext/grc/campaigns", () => new HttpResponse(null, { status: 500 })),
      http.get("*/api/v1/ext/grc/sod-rules", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/entitlements", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/campaign-items", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<AuditScreen section="reviews" />));
    expect(await screen.findByRole("alert")).toBeTruthy();
  });

  it("hides a disabled pack", async () => {
    server.use(
      session(),
      http.get("*/api/v1/tenant/packs", () =>
        HttpResponse.json({ items: [{ packId: "grc", enabled: false }] }),
      ),
    );
    render(wrap(<AuditScreen section="requests" />));
    await waitFor(() => expect(notFound).toHaveBeenCalled());
  });
});
