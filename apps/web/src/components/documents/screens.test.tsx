import { cleanup, fireEvent, render as renderView, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToolCallCard } from "@/components/chat/tool-call-card";
import { LibraryScreen } from "@/components/documents/screens";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/documents",
  useRouter: () => ({ push: () => undefined }),
}));

function renderExpanded(content: ReactNode) {
  const view = renderView(content);
  for (const card of screen.queryAllByTestId("tool-call")) {
    (card as HTMLDetailsElement).open = true;
    fireEvent(card, new Event("toggle"));
  }
  return view;
}

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("document library", () => {
  afterEach(() => {
    cleanup();
  });

  it("lists each document as a row with its type, pages and status", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["documents:read"],
          user: { displayName: "Ada Lovelace", email: "ada@acme.example" },
        }),
      ),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/library-documents", () =>
        HttpResponse.json({
          items: [
            {
              id: "doc-1",
              title: "Access",
              filename: "access.md",
              mediaType: "text/markdown",
              pageCount: 3,
            },
          ],
        }),
      ),
    );
    renderExpanded(wrap(<LibraryScreen />));
    const title = await screen.findByRole("link", { name: "Access" });
    expect(title.getAttribute("href")).toBe("/documents/doc-1");
    const row = title.closest("tr");
    expect(row?.textContent).toContain("access.md");
    expect(row?.textContent).toContain("Markdown");
    expect(row?.textContent).toContain("3");
    expect(screen.getByText("Ready").className).toContain("tone-success");
    expect(screen.getByRole("link", { name: "Open: Access" })).toBeTruthy();
    expect((screen.getByLabelText("File") as HTMLInputElement).type).toBe("file");
  });

  it("offers Compare once two different documents are chosen", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["documents:read"],
          user: { displayName: "Ada Lovelace", email: "ada@acme.example" },
        }),
      ),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/library-documents", () =>
        HttpResponse.json({
          items: [
            { id: "doc-1", title: "Policy v1", filename: "v1.md", mediaType: "text/markdown" },
            { id: "doc-2", title: "Policy v2", filename: "v2.md", mediaType: "text/markdown" },
          ],
        }),
      ),
    );
    renderView(wrap(<LibraryScreen />));
    const earlier = (await screen.findByLabelText("Earlier document")) as HTMLSelectElement;
    const later = screen.getByLabelText("Later document") as HTMLSelectElement;
    expect((screen.getByRole("button", { name: "Compare" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
    fireEvent.change(earlier, { target: { value: "doc-1" } });
    fireEvent.change(later, { target: { value: "doc-1" } });
    // The same document twice is nothing to compare.
    expect(screen.queryByRole("link", { name: "Compare" })).toBeNull();
    fireEvent.change(later, { target: { value: "doc-2" } });
    expect(screen.getByRole("link", { name: "Compare" }).getAttribute("href")).toBe(
      "/documents/compare?left=doc-1&right=doc-2",
    );
  });

  it("shows an empty library", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["documents:read"],
          user: { displayName: "Ada Lovelace", email: "ada@acme.example" },
        }),
      ),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/library-documents", () => HttpResponse.json({ items: [] })),
    );
    renderExpanded(wrap(<LibraryScreen />));
    expect(
      await screen.findByText(
        "No documents yet. Upload a PDF, document, spreadsheet, presentation, text file or image.",
      ),
    ).toBeTruthy();
  });

  it("shows each agent a reply called, with its task, its answer and a way in", () => {
    renderExpanded(
      wrap(
        <ToolCallCard
          call={{
            qualifiedName: "agents_parallel",
            status: "failed",
            resultPreview: '{"results": []}',
            presentation: {
              kind: "agents",
              agents: [
                {
                  agent: "Policy reader",
                  status: "completed",
                  task: "Read the access policy",
                  summary: "Badges are required.",
                  child_run_id: "run-1",
                },
                { agent: "Log reader", status: "failed", task: "", summary: "Timed out." },
              ],
            },
          }}
          label="Tool"
        />,
      ),
    );
    expect(screen.getByText("Called other agents")).toBeTruthy();
    const rows = screen.getByTestId("called-agents").querySelectorAll("li");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Policy reader · Done");
    expect(rows[0]?.textContent).toContain("Read the access policy");
    expect(rows[0]?.textContent).toContain("Badges are required.");
    expect(rows[1]?.textContent).toContain("Log reader · Didn't finish");
    expect(
      screen.getByRole("link", { name: "See what Policy reader did" }).getAttribute("href"),
    ).toBe("/runs/run-1");
    // An agent with no run to open has no link, and the raw result is not printed.
    expect(screen.queryByRole("link", { name: "See what Log reader did" })).toBeNull();
    expect(screen.queryByText('{"results": []}')).toBeNull();
  });

  it("renders a cited check", () => {
    renderExpanded(
      wrap(
        <ToolCallCard
          call={{
            qualifiedName: "documents.judge",
            status: "succeeded",
            presentation: {
              kind: "check",
              documentId: "doc-1",
              rows: [
                {
                  requirement: "Use badges",
                  verdict: "partial",
                  confidence: 0.7,
                  reason: "The passage mentions badges.",
                  citation: { anchor: "p1-s0", documentId: "doc-1", quote: "Staff use badges." },
                },
                {
                  requirement: "Mars colony",
                  verdict: "not_found",
                  confidence: 0,
                  reason: "The document does not contain a passage that supports this.",
                  citation: null,
                },
              ],
            },
          }}
          label="Tool"
        />,
      ),
    );
    expect(screen.getByText("Use badges")).toBeTruthy();
    expect(screen.getByRole("link", { name: "p1-s0" }).getAttribute("href")).toBe(
      "/documents/doc-1#p1-s0",
    );
    expect(
      screen.getByText("The document does not contain a passage that supports this."),
    ).toBeTruthy();
  });
});
