import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { JobList, ToolCallCard } from "@/components/chat/tool-call-card";
import { ConnectionsScreen } from "@/components/tools/connections-screen";
import { ToolsScreen } from "@/components/tools/tools-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/chat",
  useRouter: () => ({ push: () => undefined }),
}));

function installToolCatalogue() {
  server.use(
    http.get("*/api/v1/tools", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/tenant", () => HttpResponse.json({ settings: {} })),
  );
}

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
    render(
      wrap(
        <ToolCallCard
          call={{
            qualifiedName: "general.code",
            status: "succeeded",
            presentation: {
              kind: "code",
              command: "python",
              exitCode: 0,
              stdout: "42",
              files: [{ fileId: "file-1", name: "summary.txt" }],
            },
          }}
          label="Tool call"
        />,
      ),
    );
    expect(screen.getByText("42")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Download summary.txt" }).getAttribute("href")).toBe(
      "/api/v1/files/file-1/content",
    );
    render(
      wrap(
        <ToolCallCard
          call={{
            qualifiedName: "data.query",
            status: "succeeded",
            presentation: {
              kind: "query",
              sql: "SELECT count(*) FROM public.stores",
              columns: ["count"],
              rows: [[2992]],
              truncated: true,
              files: [{ fileId: "file-2", name: "chart.png" }],
            },
          }}
          label="Tool call"
        />,
      ),
    );
    expect(screen.getByText("SELECT count(*) FROM public.stores")).toBeTruthy();
    expect(screen.getByText("2992")).toBeTruthy();
    expect(screen.getByText("Showing a sample. The full result was truncated.")).toBeTruthy();
    render(
      wrap(
        <ToolCallCard
          call={{
            qualifiedName: "documents.ocr",
            status: "succeeded",
            presentation: {
              kind: "ocr",
              progress: { label: "scan.pdf", completed: 2, total: 4, status: "running" },
            },
          }}
          label="Tool call"
        />,
      ),
    );
    expect(screen.getByText("scan.pdf. 2 of 4")).toBeTruthy();
    expect(screen.getByRole("progressbar")).toBeTruthy();
    render(
      wrap(
        <JobList
          jobs={[
            {
              id: "job-1",
              label: "scan.pdf",
              completed: 2,
              total: 4,
              status: "interrupted",
              detail: "Restored 1 files from the interrupted run.",
            },
          ]}
        />,
      ),
    );
    expect(screen.getByText(/Stopped at 2 of 4/)).toBeTruthy();
  });

  it("lists servers and a recent call", async () => {
    installToolCatalogue();
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
    installToolCatalogue();
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
    installToolCatalogue();
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
      http.get("*/api/v1/service-connections", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<ConnectionsScreen />));
    expect(await screen.findByRole("heading", { name: "Tickets" })).toBeTruthy();
    expect(screen.getByText("Connected")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Warehouse" })).toBeTruthy();
  });
});
