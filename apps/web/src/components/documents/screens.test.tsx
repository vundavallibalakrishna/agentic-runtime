import { cleanup, render, screen } from "@testing-library/react";
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
    render(wrap(<LibraryScreen />));
    expect(
      await screen.findByText(
        "No documents yet. Upload a PDF, document, spreadsheet, presentation, text file or image.",
      ),
    ).toBeTruthy();
  });

  it("renders a cited check", () => {
    render(
      wrap(
        <ToolCallCard
          call={{
            qualifiedName: "documents.check",
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
