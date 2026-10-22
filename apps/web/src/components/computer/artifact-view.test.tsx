import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ArtifactView } from "@/components/computer/artifact-view";

describe("artifact view", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows a chart, a table, and HTML as source", () => {
    const { rerender } = render(
      <ArtifactView file={{ id: "file-1", name: "revenue-by-month.png", mimeType: "image/png" }} />,
    );
    expect(screen.getByRole("img", { name: "revenue-by-month.png" })).toBeTruthy();
    rerender(
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
    );
    expect(screen.getByText("2026-01")).toBeTruthy();
    rerender(
      <ArtifactView
        file={{ name: "page.html", mimeType: "text/html", text: "<script>alert(1)</script>" }}
      />,
    );
    const source = screen.getByTestId("html-source");
    expect(source.textContent).toContain("<script>alert(1)</script>");
    expect(source.querySelector("script")).toBeNull();
  });
});
