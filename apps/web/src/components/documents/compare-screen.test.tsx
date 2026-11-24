import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CompareScreen } from "@/components/documents/compare-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

const sides = {
  left: { id: "a", title: "Policy v1" },
  right: { id: "b", title: "Policy v2" },
};

describe("comparing two documents", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows each section that differs, with both wordings and a way to the passage", async () => {
    let asked = "";
    server.use(
      http.get("*/api/v1/library-documents/a/diff", ({ request }) => {
        asked = new URL(request.url).searchParams.get("otherDocumentId") ?? "";
        return HttpResponse.json({
          ...sides,
          counts: { changed: 1, added: 1, removed: 1, unchanged: 9 },
          total: 3,
          sections: [
            {
              status: "changed",
              heading: "Logs",
              leftAnchor: "p1-s4",
              rightAnchor: "p1-s4",
              leftQuote: "Logs are kept for 90 days.",
              rightQuote: "Logs are kept for 365 days.",
            },
            {
              status: "removed",
              heading: "Media",
              leftAnchor: "p1-s6",
              rightAnchor: "",
              leftQuote: "USB sticks need approval.",
              rightQuote: "",
            },
            {
              status: "added",
              heading: "AI",
              leftAnchor: "",
              rightAnchor: "p1-s8",
              leftQuote: "",
              rightQuote: "AI systems are registered.",
            },
          ],
        });
      }),
    );
    render(wrap(<CompareScreen left="a" right="b" />));
    expect(await screen.findByText("Logs are kept for 365 days.")).toBeTruthy();
    expect(asked).toBe("b");
    expect(screen.getByRole("heading", { name: "Comparison" })).toBeTruthy();
    expect(screen.getByText(/^Policy v1 compared with Policy v2\./)).toBeTruthy();
    expect(screen.getByText("Logs are kept for 90 days.")).toBeTruthy();
    expect(screen.getByText("9 the same")).toBeTruthy();
    expect(screen.getByText("Changed")).toBeTruthy();
    // A section only one document has says so on the other side.
    expect(screen.getByText("Not in Policy v2.")).toBeTruthy();
    expect(screen.getByText("Not in Policy v1.")).toBeTruthy();
    const passage = screen.getByRole("link", { name: "Open passage: Policy v2, p1-s8" });
    expect(passage.getAttribute("href")).toBe("/documents/b#p1-s8");
  });

  it("says so when the two documents do not differ", async () => {
    server.use(
      http.get("*/api/v1/library-documents/a/diff", () =>
        HttpResponse.json({
          ...sides,
          counts: { changed: 0, added: 0, removed: 0, unchanged: 12 },
          total: 0,
          sections: [],
        }),
      ),
    );
    render(wrap(<CompareScreen left="a" right="b" />));
    expect(await screen.findByText(/say the same thing in every section/)).toBeTruthy();
    expect(screen.getByText("12 the same")).toBeTruthy();
  });

  it("says how many are shown when there are more differences than fit", async () => {
    server.use(
      http.get("*/api/v1/library-documents/a/diff", () =>
        HttpResponse.json({
          ...sides,
          counts: { changed: 40, added: 0, removed: 0, unchanged: 0 },
          total: 40,
          sections: [{ status: "changed", heading: "One", leftQuote: "a", rightQuote: "b" }],
        }),
      ),
    );
    render(wrap(<CompareScreen left="a" right="b" />));
    expect(await screen.findByText("Showing the first 1 of 40 sections that differ.")).toBeTruthy();
  });

  it("shows the refusal and tries again when asked", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v1/library-documents/a/diff", () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({ detail: "The document was not found." }, { status: 404 })
          : HttpResponse.json({ ...sides, counts: {}, total: 0, sections: [] });
      }),
    );
    render(wrap(<CompareScreen left="a" right="b" />));
    expect((await screen.findByRole("alert")).textContent).toContain("not found");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(calls).toBe(2);
  });

  it("asks for two documents when it is opened without them", async () => {
    render(wrap(<CompareScreen left="" right="" />));
    expect(await screen.findByText(/Choose two documents/)).toBeTruthy();
  });
});
