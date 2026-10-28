import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkflowScreen } from "@/components/grc/workflow-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const notFound = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/grc/workflows",
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

describe("GRC workflows", () => {
  afterEach(() => {
    cleanup();
    notFound.mockClear();
  });

  it("shows an empty questionnaire library", async () => {
    server.use(
      session(),
      pack(),
      http.get("*/api/v1/ext/grc/answer-library", () => HttpResponse.json({ items: [], jobs: [] })),
    );
    render(wrap(<WorkflowScreen section="questionnaires" />));
    expect(await screen.findByText("Nothing is here yet.")).toBeTruthy();
  });

  it("lists a vendor and keeps the score visible", async () => {
    server.use(
      session(),
      pack(),
      http.get("*/api/v1/ext/grc/vendors", () =>
        HttpResponse.json({ items: [{ id: "v1", name: "Northwind", tier: "high" }] }),
      ),
    );
    render(wrap(<WorkflowScreen section="vendors" />));
    expect((await screen.findAllByText("Northwind")).length).toBeGreaterThan(0);
    expect(await screen.findByText("high")).toBeTruthy();
  });

  it("keeps the empty state until a vendor name is saved", async () => {
    let body: unknown = null;
    server.use(
      session(),
      pack(),
      http.get("*/api/v1/ext/grc/vendors", () => HttpResponse.json({ items: [] })),
      http.post("*/api/v1/ext/grc/vendors", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: "v2", name: "Acme" });
      }),
    );
    render(wrap(<WorkflowScreen section="vendors" />));
    expect(await screen.findByText("Nothing is here yet.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Add vendor" }));
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent",
      "Vendor name is required.",
    );
    fireEvent.change(screen.getByRole("textbox", { name: /Vendor name/ }), {
      target: { value: "Acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add vendor" }));
    await waitFor(() => expect(body).toEqual({ name: "Acme" }));
  });

  it("shows an error when risks cannot be loaded", async () => {
    server.use(
      session(),
      pack(),
      http.get("*/api/v1/ext/grc/risks", () => new HttpResponse(null, { status: 500 })),
    );
    render(wrap(<WorkflowScreen section="risks" />));
    expect(await screen.findByRole("alert")).toBeTruthy();
  });

  it("hides a disabled pack", async () => {
    server.use(
      session(),
      http.get("*/api/v1/tenant/packs", () =>
        HttpResponse.json({ items: [{ packId: "grc", enabled: false }] }),
      ),
    );
    render(wrap(<WorkflowScreen section="overview" />));
    await waitFor(() => expect(notFound).toHaveBeenCalled());
  });
});
