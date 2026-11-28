import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import messages from "@/messages/en.json";

import { ToolCallCard } from "./tool-call-card";

function card(call: Record<string, unknown>) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <ToolCallCard call={call} label="Tool call" />
    </NextIntlClientProvider>
  );
}
function open() {
  const element = screen.getByTestId("tool-call") as HTMLDetailsElement;
  element.open = true;
  fireEvent(element, new Event("toggle"));
}
afterEach(cleanup);
describe("shared tool result disclosure", () => {
  it("does not mount collapsed output and bounds a 100,000-row result when opened", () => {
    render(
      card({
        id: "call",
        qualifiedName: "data.query",
        status: "succeeded",
        presentation: {
          kind: "table",
          columns: ["row", "value"],
          rows: Array.from({ length: 100000 }, (_, i) => [`row-${i}`, "same value"]),
        },
      }),
    );
    expect(screen.queryByRole("table")).toBeNull();
    open();
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(26);
    expect(screen.queryByText("row-25")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("row-25")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "row-99999" } });
    expect(screen.getByText("row-99999")).toBeTruthy();
    expect(screen.getByText("1–1 of 1")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "absent result" } });
    expect(screen.getByText(messages.chat.toolNoResultMatches)).toBeTruthy();
  });
  it.each(["check", "compare", "rewrite"])(
    "bounds retained %s result rows and searches their full returned data",
    (kind) => {
      const field = kind === "compare" ? "changes" : kind === "rewrite" ? "hunks" : "rows";
      render(
        card({
          id: "saved",
          qualifiedName: "documents.saved",
          status: "succeeded",
          presentation: {
            kind,
            status: "proposed",
            [field]: Array.from({ length: 100_000 }, (_, i) => ({
              id: "same",
              op: "changed",
              heading: `Section ${i}`,
              requirement: `Requirement ${i}`,
              before: `Before ${i}`,
              after: `After ${i}`,
              verdict: "supported",
              confidence: 0,
              citation: { documentId: "doc", anchor: `p${i}` },
            })),
          },
        }),
      );
      open();
      expect(screen.getAllByRole("listitem")).toHaveLength(25);
      fireEvent.click(screen.getByRole("button", { name: "Next" }));
      expect(
        screen.getByText(kind === "check" ? "Requirement 25" : "changed · Section 25"),
      ).toBeTruthy();
      fireEvent.change(screen.getByRole("searchbox"), {
        target: { value: kind === "check" ? "Requirement 99999" : "Section 99999" },
      });
      expect(screen.getAllByRole("listitem")).toHaveLength(1);
      expect(screen.getByText("1–1 of 1")).toBeTruthy();
      expect(screen.queryByRole("link", { name: "proposed" })).toBeNull();
      expect(screen.queryByRole("button", { name: /Accept|Reject/ })).toBeNull();
    },
  );
  it("shows actual saved rewrite text without obsolete acceptance links or requests", () => {
    render(
      card({
        qualifiedName: "documents.saved",
        status: "succeeded",
        presentation: {
          kind: "rewrite",
          status: "proposed",
          original: "Original passage",
          proposed: "Returned proposal",
          hunks: [],
        },
      }),
    );
    open();
    expect(screen.getByText("Original passage")).toBeTruthy();
    expect(screen.getByText("Returned proposal")).toBeTruthy();
    expect(screen.getByText(messages.chat.savedProposalReadOnly)).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.queryByText(messages.chat.toolNoResultRows)).toBeNull();
  });
  it("shows only returned redacted inputs, result and error without making a call", () => {
    render(
      card({
        qualifiedName: "documents.read",
        status: "failed",
        arguments: { token: "[REDACTED]", path: "source.txt" },
        resultPreview: "Partial result",
        error: { message: "Provider unavailable" },
      }),
    );
    expect(screen.queryByText("Partial result")).toBeNull();
    open();
    expect(screen.getByText("Tool reference: documents.read")).toBeTruthy();
    expect(screen.getByText(/\[REDACTED\]/)).toBeTruthy();
    expect(screen.getByText("Partial result")).toBeTruthy();
    expect(screen.getByText("Provider unavailable")).toBeTruthy();
  });
  it("opens an actionable connection error and keeps a manually opened card open after recovery", () => {
    const view = render(
      card({
        qualifiedName: "workspace.read",
        status: "failed",
        error: { connectUrl: "https://service.example/connect" },
      }),
    );
    expect((screen.getByTestId("tool-call") as HTMLDetailsElement).open).toBe(true);
    expect(screen.getByRole("link", { name: "Connect account" })).toBeTruthy();
    view.rerender(
      card({ qualifiedName: "workspace.read", status: "succeeded", resultPreview: "Recovered" }),
    );
    expect((screen.getByTestId("tool-call") as HTMLDetailsElement).open).toBe(true);
    expect(screen.getByText("Recovered")).toBeTruthy();
  });
});
