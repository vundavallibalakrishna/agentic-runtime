import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import messages from "@/messages/en.json";

import { ReadingNote } from "./citations";

function note(reading: Record<string, unknown> | null) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ReadingNote reading={reading} />
    </NextIntlClientProvider>,
  );
}
afterEach(cleanup);
describe("saved reading metadata", () => {
  it("does not display an empty plan or invent missing metadata", () => {
    const view = note({ type: "reading" });
    expect(view.container.textContent).toBe("");
  });
  it("shows the actual used-tool shape without empty strategy or coverage text", () => {
    note({ type: "reading", tools: ["workspace.read", "workspace.read", "documents.search"] });
    expect(screen.getByText("2 tools used")).toBeTruthy();
    expect(screen.getByText("workspace.read")).toBeTruthy();
    expect(screen.queryByText(/Coverage/)).toBeNull();
  });
  it("retains only present fields for legacy reading plans", () => {
    note({ type: "reading", strategy: "mapReduce", coverage: 0 });
    expect(screen.getByText("Reading: mapReduce · Coverage: 0")).toBeTruthy();
    expect(screen.queryByText(/Scope/)).toBeNull();
  });
});
