import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConnectorsScreen } from "@/components/connectors/connectors-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/connectors",
  useParams: () => ({}),
  useRouter: () => ({ push: () => undefined }),
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("connector catalog", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows a not-live-tested badge and an empty search", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["tools:read", "connections:manage_own"] }),
      ),
      http.get("*/api/v1/connectors", () =>
        HttpResponse.json({
          items: [
            {
              slug: "notion",
              name: "Notion",
              category: "Work",
              summary: "Search pages",
              implementation: "built",
              verification: "not_live",
              proof: "unit",
              verificationNote: "No workspace was connected.",
              installed: false,
            },
          ],
        }),
      ),
    );
    render(wrap(<ConnectorsScreen />));
    expect(await screen.findByText("Unit")).toBeTruthy();
    expect(screen.getByText("Not offered to an agent")).toBeTruthy();
    expect(screen.queryByText("Built")).toBeNull();
    expect(screen.queryByText("Ready")).toBeNull();
    expect(screen.getByText(/does not offer the tool/)).toBeTruthy();
    expect(screen.queryByText("No workspace was connected.")).toBeNull();
    expect(screen.getByRole("region", { name: "Work" })).toBeTruthy();
    expect(screen.getByText("About verification badges")).toBeTruthy();
  });
  it("groups a bounded page by API categories and filters before paging", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["tools:read"] })),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/connectors", () =>
        HttpResponse.json({
          items: Array.from({ length: 30 }, (_, i) => ({
            slug: `connector-${i}`,
            name: `System ${i}`,
            category: i % 2 ? "Work" : "Files",
            summary: "Search records",
            proof: "contract",
          })),
        }),
      ),
    );
    render(wrap(<ConnectorsScreen />));
    await screen.findByRole("region", { name: "Work" });
    expect(within(screen.getByRole("region", { name: "Files" })).getAllByRole("link")).toHaveLength(
      13,
    );
    expect(screen.queryByRole("link", { name: /^System 29.*Set up$/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("link", { name: /^System 29.*Set up$/ })).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search connectors" }), {
      target: { value: "System 0" },
    });
    expect(screen.getByRole("link", { name: /^System 0.*Set up$/ })).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Work" })).toBeNull();
  });

  it("retains verification evidence in setup and labels authentication methods", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["tools:read", "connections:manage_own"] }),
      ),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/connectors", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/connectors/system", () =>
        HttpResponse.json({
          slug: "system",
          name: "Workspace system",
          proof: "contract",
          verificationNote: "No workspace was connected.",
          authKind: "bearer",
          authKinds: ["bearer", "oauth_authorization_code"],
          tools: [],
        }),
      ),
    );
    render(wrap(<ConnectorsScreen slug="system" />));
    expect(await screen.findByText("No workspace was connected.")).toBeTruthy();
    expect(screen.getByRole("option", { name: "Bearer token" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "OAuth — sign in to authorise" })).toBeTruthy();
    expect(await screen.findByLabelText("Bearer token")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Auth type"), {
      target: { value: "oauth_authorization_code" },
    });
    expect(screen.getByLabelText("Client secret")).toBeTruthy();
    expect(screen.getByLabelText("Client id")).toBeTruthy();
  });
});
