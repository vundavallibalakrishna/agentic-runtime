import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import messages from "@/messages/en.json";
import { ReviewTable, reviewsOf } from "./citations";

function show(rows: Record<string, unknown>[]) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ReviewTable rows={rows} />
    </NextIntlClientProvider>,
  );
}
function expand(element: Element | null, open = true) {
  const details = element as HTMLDetailsElement;
  details.open = open;
  fireEvent(details, new Event("toggle"));
}
afterEach(cleanup);
describe("saved review rows", () => {
  it("does not render absent review rows or accept arrays and scalars as records", () => {
    const view = show([]);
    expect(view.container.textContent).toBe("");
    expect(
      reviewsOf({
        content: [{ type: "review", rows: [null, 0, "text", [], { result: "present" }] }],
      }),
    ).toEqual([{ result: "present" }]);
  });
  it("lazily bounds 100,000 returned records, keeps duplicate IDs distinct and resets filtered pages", () => {
    const rows = Array.from({ length: 100_000 }, (_, index) => ({
      id: "same",
      result: `Result ${index}`,
      details: { group: index < 2 ? "special" : "ordinary" },
    }));
    const view = show(rows);
    expect(screen.queryByRole("table")).toBeNull();
    expand(view.container.querySelector("details"));
    const table = screen.getByRole("table", { name: messages.chat.reviewRowsTitle });
    expect(within(table).getAllByRole("row")).toHaveLength(26);
    expect(screen.getByText("Result 24")).toBeTruthy();
    expect(screen.queryByText("Result 25")).toBeNull();
    const pagination = screen.getByRole("navigation", { name: "Pagination: Review results" });
    fireEvent.click(within(pagination).getByRole("button", { name: "Next" }));
    expect(screen.getByText("Result 25")).toBeTruthy();
    expect(screen.queryByText("Result 0")).toBeNull();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: " SPECIAL " } });
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(screen.getByText("Result 0")).toBeTruthy();
    expect(screen.getByText("1–2 of 2")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
    expect(
      within(table)
        .getAllByRole("cell")
        .filter((cell) => cell.textContent === JSON.stringify({ group: "special" }, null, 2)),
    ).toHaveLength(2);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "no matching row" } });
    expect(screen.getByText(messages.chat.reviewRowsNoMatches)).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Rows per page"), { target: { value: "100" } });
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(101);
    expand(view.container.querySelector("details"), false);
    expect(screen.queryByRole("table")).toBeNull();
  });
  it("bounds many returned columns with a separate, named column pager", () => {
    const row = Object.fromEntries(
      Array.from({ length: 70 }, (_, index) => [`field${index}`, index]),
    );
    const view = show([row]);
    expand(view.container.querySelector("details"));
    expect(screen.getAllByRole("columnheader")).toHaveLength(25);
    const columns = screen.getByRole("navigation", { name: "Pagination: Review columns" });
    fireEvent.click(within(columns).getByRole("button", { name: "Next" }));
    expect(screen.getByRole("columnheader", { name: "field25" })).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: "field0" })).toBeNull();
    expect(screen.getAllByRole("columnheader")).toHaveLength(25);
    expect(
      screen.getByRole("region", { name: messages.chat.reviewRowsTitle }).getAttribute("tabindex"),
    ).toBe("0");
  });
  it("keeps long structured values readable without mounting full output until expanded", () => {
    const data = { explanation: "Long returned description ".repeat(50), count: 0, enabled: false };
    const view = show([{ result: data }]);
    expand(view.container.querySelector("details"));
    expect(screen.queryByRole("region", { name: messages.chat.reviewCellValue })).toBeNull();
    const cellDetails = screen.getByRole("cell").querySelector("details");
    expand(cellDetails);
    const value = screen.getByRole("region", { name: messages.chat.reviewCellValue });
    expect(value.textContent).toBe(JSON.stringify(data, null, 2));
    expect(value.getAttribute("tabindex")).toBe("0");
    expect(view.container.textContent).not.toContain("[object Object]");
  });
  it("keeps native disclosure and lazy content consistent when saved rows disappear and return", () => {
    const view = show([{ result: "original" }]);
    expand(view.container.querySelector("details"));
    view.rerender(
      <NextIntlClientProvider locale="en" messages={messages}>
        <ReviewTable rows={[]} />
      </NextIntlClientProvider>,
    );
    expect(screen.queryByRole("table")).toBeNull();
    view.rerender(
      <NextIntlClientProvider locale="en" messages={messages}>
        <ReviewTable rows={[{ result: "updated" }]} />
      </NextIntlClientProvider>,
    );
    expect((view.container.querySelector("details") as HTMLDetailsElement).open).toBe(true);
    expect(screen.getByText("updated")).toBeTruthy();
  });
  it("explains fieldless saved rows without an empty table", () => {
    const view = show([{}, {}]);
    expand(view.container.querySelector("details"));
    expect(screen.getByText(messages.chat.reviewRowsNoFields)).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
  });
});
