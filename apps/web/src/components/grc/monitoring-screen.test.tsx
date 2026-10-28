import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MonitoringScreen } from "@/components/grc/monitoring-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const notFound = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/grc/findings",
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

describe("GRC monitoring", () => {
  afterEach(() => {
    cleanup();
    notFound.mockClear();
  });

  it("shows an empty findings list", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["grc.controls:read"], user: { displayName: "Admin" } }),
      ),
      pack(),
      http.get("*/api/v1/ext/grc/controls", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/control-tests", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/test-results", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/findings", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/evidence", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<MonitoringScreen section="findings" />));
    expect(await screen.findByText("No findings are open.")).toBeTruthy();
  });

  it("shows a connector and a captured count", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["grc.controls:read"], user: { displayName: "Admin" } }),
      ),
      pack(),
      http.get("*/api/v1/ext/grc/controls", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/control-tests", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/test-results", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/findings", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/evidence", () =>
        HttpResponse.json({ items: [{ id: "e1", sourceSystem: "grc_aws" }] }),
      ),
    );
    render(wrap(<MonitoringScreen section="connectors" />));
    expect(await screen.findByRole("heading", { name: "AWS" })).toBeTruthy();
    expect(await screen.findByText(/1 captured/)).toBeTruthy();
  });

  it("shows an error when findings cannot be loaded", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["grc.controls:read"] }),
      ),
      pack(),
      http.get("*/api/v1/ext/grc/controls", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/control-tests", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/test-results", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/findings", () => new HttpResponse(null, { status: 500 })),
      http.get("*/api/v1/evidence", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<MonitoringScreen section="findings" />));
    expect(await screen.findByRole("alert")).toBeTruthy();
  });

  it("hides a disabled pack", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: [] })),
      http.get("*/api/v1/tenant/packs", () =>
        HttpResponse.json({ items: [{ packId: "grc", enabled: false }] }),
      ),
    );
    render(wrap(<MonitoringScreen section="tests" />));
    await waitFor(() => expect(notFound).toHaveBeenCalled());
  });
});
