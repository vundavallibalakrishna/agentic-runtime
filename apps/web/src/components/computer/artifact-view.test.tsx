import { cleanup, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { ArtifactView } from "@/components/computer/artifact-view";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("artifact view", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows a chart, a table, and HTML as source", () => {
    const { rerender } = render(
      wrap(
        <ArtifactView
          file={{ id: "file-1", name: "revenue-by-month.png", mimeType: "image/png" }}
        />,
      ),
    );
    expect(screen.getByRole("img", { name: "revenue-by-month.png" })).toBeTruthy();
    rerender(
      wrap(
        <ArtifactView
          file={{
            name: "revenue.csv",
            mimeType: "text/csv",
            preview: {
              rows: [
                ["month", "revenue"],
                ["2026-01", "12000"],
              ],
            },
          }}
        />,
      ),
    );
    expect(screen.getByText("2026-01")).toBeTruthy();
    rerender(
      wrap(
        <ArtifactView
          file={{ name: "page.html", mimeType: "text/html", text: "<script>alert(1)</script>" }}
        />,
      ),
    );
    const source = screen.getByTestId("html-source");
    expect(source.textContent).toContain("<script>alert(1)</script>");
    expect(source.querySelector("script")).toBeNull();
  });

  it("reads a text file's content when the list did not send it", async () => {
    server.use(
      http.get("*/api/v1/files/file-2/content", () => HttpResponse.text("line one\nline two")),
      http.get("*/api/v1/files/file-3/content", () => HttpResponse.text("<h1>Report</h1>")),
    );
    render(
      wrap(<ArtifactView file={{ id: "file-2", name: "notes.txt", mimeType: "text/plain" }} />),
    );
    expect((await screen.findByTestId("text-source")).textContent).toContain("line two");
    cleanup();
    render(
      wrap(<ArtifactView file={{ id: "file-3", name: "report.html", mimeType: "text/html" }} />),
    );
    const source = await screen.findByTestId("html-source");
    expect(source.textContent).toContain("<h1>Report</h1>");
    expect(source.querySelector("h1")).toBeNull();
  });

  it("says so when the file is empty or cannot be read", async () => {
    server.use(
      http.get("*/api/v1/files/file-4/content", () => HttpResponse.text("")),
      http.get("*/api/v1/files/file-5/content", () => new HttpResponse(null, { status: 500 })),
    );
    render(
      wrap(<ArtifactView file={{ id: "file-4", name: "empty.txt", mimeType: "text/plain" }} />),
    );
    expect(await screen.findByText("This file is empty.")).toBeTruthy();
    cleanup();
    render(
      wrap(<ArtifactView file={{ id: "file-5", name: "gone.md", mimeType: "text/markdown" }} />),
    );
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});
