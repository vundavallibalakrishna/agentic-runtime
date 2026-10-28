import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GrcScreen } from "@/components/grc/grc-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const notFound = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/grc",
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

describe("GRC screens", () => {
  afterEach(() => {
    cleanup();
    notFound.mockClear();
  });

  it("shows an empty catalogue", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["grc.controls:read"], user: { displayName: "Admin" } }),
      ),
      http.get("*/api/v1/tenant/packs", () =>
        HttpResponse.json({ items: [{ packId: "grc", enabled: true, nav: [] }] }),
      ),
      http.get("*/api/v1/ext/grc/frameworks", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/controls", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/evidence-links", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/evidence", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<GrcScreen section="frameworks" />));
    expect(await screen.findByRole("heading", { name: "GRC" })).toBeTruthy();
    expect(
      await screen.findByText("No frameworks yet. Import an OSCAL catalogue to begin."),
    ).toBeTruthy();
  });

  it("shows an error when the catalogue request fails", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["grc.controls:read"] }),
      ),
      http.get("*/api/v1/tenant/packs", () =>
        HttpResponse.json({ items: [{ packId: "grc", enabled: true }] }),
      ),
      http.get("*/api/v1/ext/grc/frameworks", () => new HttpResponse(null, { status: 500 })),
      http.get("*/api/v1/ext/grc/controls", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/ext/grc/evidence-links", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/evidence", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<GrcScreen section="frameworks" />));
    expect(await screen.findByRole("alert")).toBeTruthy();
  });

  it("hides a disabled pack", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: [] })),
      http.get("*/api/v1/tenant/packs", () =>
        HttpResponse.json({ items: [{ packId: "grc", enabled: false }] }),
      ),
    );
    render(wrap(<GrcScreen section="frameworks" />));
    await waitFor(() => expect(notFound).toHaveBeenCalled());
  });
});
