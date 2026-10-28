import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToolCallCard } from "@/components/chat/tool-call-card";
import { ConnectionsScreen } from "@/components/tools/connections-screen";
import { ToolsScreen } from "@/components/tools/tools-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/chat",
  useRouter: () => ({ push: () => undefined }),
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("tool screens", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows a tool result and a connect link", () => {
    render(
      wrap(
        <ToolCallCard
          call={{
            qualifiedName: "tickets.create_ticket",
            status: "succeeded",
            resultPreview: "TCK-1001",
          }}
          label="Tool call"
        />,
      ),
    );
    expect(screen.getByText("tickets.create_ticket")).toBeTruthy();
    expect(screen.getByText("TCK-1001")).toBeTruthy();
    render(
      wrap(
        <ToolCallCard
          call={{
            qualifiedName: "tickets.create_ticket",
            status: "failed",
            error: { connectUrl: "https://tickets.example/authorize" },
          }}
          label="Tool call"
        />,
      ),
    );
    expect(screen.getByRole("link", { name: "Connect account" }).getAttribute("href")).toBe(
      "https://tickets.example/authorize",
    );
  });

  it("lists servers and a recent call", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["tools:read"] })),
      http.get("*/api/v1/tool-servers", () =>
        HttpResponse.json({
          items: [
            {
              id: "s1",
              name: "Tickets",
              slug: "tickets",
              kind: "remote_mcp",
              status: "approved",
            },
          ],
        }),
      ),
      http.get("*/api/v1/tool-calls", () =>
        HttpResponse.json({
          items: [
            {
              id: "c1",
              qualifiedName: "tickets.create_ticket",
              status: "succeeded",
              resultPreview: "TCK-1001",
            },
          ],
        }),
      ),
    );
    render(wrap(<ToolsScreen />));
    expect(await screen.findByRole("heading", { name: "Tickets" })).toBeTruthy();
    expect(screen.getByText("tickets.create_ticket")).toBeTruthy();
    expect(screen.getByLabelText("Short name")).toBeTruthy();
  });

  it("keeps a submitted tool visible when a different reviewer is required", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({})),
      http.get("*/api/v1/tool-servers", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/tool-calls", () => HttpResponse.json({ items: [] })),
      http.post("*/api/v1/tool-servers", () =>
        HttpResponse.json({ id: "server", versions: [{ id: "version" }] }),
      ),
      http.get("*/api/v1/tool-servers/server/versions/version", () =>
        HttpResponse.json({ tools: [] }),
      ),
      http.post(/\/versions\/version:submit$/, () =>
        HttpResponse.json({ reviewStatus: "pending" }),
      ),
      http.post(/\/versions\/version:approve$/, () =>
        HttpResponse.json({ detail: "four_eyes" }, { status: 403 }),
      ),
    );
    render(wrap(<ToolsScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Register" }));
    expect(await screen.findByText(/Submitted for review/)).toBeTruthy();
    expect(screen.queryByText("four_eyes")).toBeNull();
  });

  it("shows the tools error state", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({})),
      http.get("*/api/v1/tool-servers", () => new HttpResponse(null, { status: 500 })),
      http.get("*/api/v1/tool-calls", () => new HttpResponse(null, { status: 500 })),
    );
    render(wrap(<ToolsScreen />));
    expect(await screen.findByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("shows a connected account and the warehouse", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({})),
      http.get("*/api/v1/connections", () =>
        HttpResponse.json({
          items: [{ id: "g1", providerId: "p1", status: "active" }],
        }),
      ),
      http.get("*/api/v1/credential-providers", () =>
        HttpResponse.json({ items: [{ id: "p1", name: "Tickets", slug: "tickets" }] }),
      ),
      http.get("*/api/v1/data-connections", () =>
        HttpResponse.json({ items: [{ id: "d1", name: "Warehouse", engine: "postgres" }] }),
      ),
    );
    render(wrap(<ConnectionsScreen />));
    expect(await screen.findByRole("heading", { name: "Tickets" })).toBeTruthy();
    expect(screen.getByText("Connected")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Warehouse" })).toBeTruthy();
  });

  it("finishes a workspace connection with a code", async () => {
    let code = "";
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({})),
      http.get("*/api/v1/connections", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/credential-providers", () =>
        HttpResponse.json({
          items: [{ id: "p1", name: "Tickets", slug: "tickets", tokenUrl: "memory://oauth" }],
        }),
      ),
      http.get("*/api/v1/data-connections", () => HttpResponse.json({ items: [] })),
      http.post("*/api/v1/connections/p1:start", () =>
        HttpResponse.json({
          authorizeUrl: "https://tickets.example/authorize?state=abc",
          state: "abc",
        }),
      ),
      http.get("*/api/v1/connections/oauth/callback", ({ request }) => {
        code = new URL(request.url).searchParams.get("code") ?? "";
        return HttpResponse.json({ id: "g1", status: "active" });
      }),
    );
    render(wrap(<ConnectionsScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Connect" }));
    expect(await screen.findByRole("heading", { name: "Finish connecting" })).toBeTruthy();
    expect(screen.getByLabelText("Authorization code")).toHaveProperty("value", "workspace");
    fireEvent.click(screen.getByRole("button", { name: "Connect as me" }));
    await waitFor(() => expect(code).toBe("workspace"));
  });
});
