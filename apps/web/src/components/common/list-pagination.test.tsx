import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { useMemo, useState } from "react";
import { afterEach, expect, it } from "vitest";

import { ListPagination, usePagedRows } from "@/components/common/list-pagination";
import messages from "@/messages/en.json";

const records = Array.from({ length: 100_000 }, (_, id) => ({ id, name: `Record ${id}` }));
afterEach(cleanup);
function List() {
  const [query, setQuery] = useState("");
  const matching = useMemo(() => records.filter((row) => row.name.includes(query)), [query]);
  const pagination = usePagedRows(matching, query);
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <label>
        Search
        <input value={query} onChange={(event) => setQuery(event.target.value)} />
      </label>
      <ul>
        {pagination.rows.map((row) => (
          <li key={row.id}>{row.name}</li>
        ))}
      </ul>
      <ListPagination {...pagination} />
    </NextIntlClientProvider>
  );
}
it("bounds rendered rows for 100,000 loaded records and resets navigation when filtering", () => {
  render(<List />);
  expect(screen.getAllByRole("listitem")).toHaveLength(25);
  expect(screen.getByText("1–25 of 100,000")).toBeTruthy();
  expect((screen.getByRole("button", { name: "Previous" }) as HTMLButtonElement).disabled).toBe(
    true,
  );
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByText("26–50 of 100,000")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Search"), { target: { value: "Record 99999" } });
  expect(screen.getAllByRole("listitem")).toHaveLength(1);
  expect(screen.getByText("1–1 of 1")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
  expect(screen.queryByLabelText("Rows per page")).toBeNull();
  fireEvent.change(screen.getByLabelText("Search"), { target: { value: "" } });
  expect(screen.getByText("1–25 of 100,000")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Rows per page"), { target: { value: "100" } });
  expect(screen.getAllByRole("listitem")).toHaveLength(100);
  expect(screen.getByText("1–100 of 100,000")).toBeTruthy();
});
it("keeps the actual empty count without unnecessary controls", () => {
  render(<List />);
  fireEvent.change(screen.getByLabelText("Search"), { target: { value: "No matching record" } });
  expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  expect(screen.getByText("0–0 of 0")).toBeTruthy();
  expect(screen.queryByRole("button")).toBeNull();
  expect(screen.queryByLabelText("Rows per page")).toBeNull();
});

function Paged({ count, compact = false }: { count: number; compact?: boolean }) {
  const pagination = usePagedRows(Array.from({ length: count }, (_, id) => id));
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <ListPagination {...pagination} compact={compact} />
    </NextIntlClientProvider>
  );
}
it.each([0, 1, 25])(
  "shows only the count when %i records fit every available page size",
  (count) => {
    render(<Paged count={count} />);
    expect(screen.getByRole("status").textContent).toBe(`${count ? 1 : 0}–${count} of ${count}`);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
  },
);
it("retains size selection for a larger result even when the selected size puts it on one page", () => {
  render(<Paged count={26} />);
  expect(screen.getByRole("button", { name: "Next" }).hasAttribute("disabled")).toBe(false);
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "100" } });
  expect(screen.queryByRole("button")).toBeNull();
  expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe("100");
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "25" } });
  expect(screen.getByRole("button", { name: "Next" }).hasAttribute("disabled")).toBe(false);
});
it("keeps compact navigation only when more than one known page exists", () => {
  const view = render(<Paged count={1} compact />);
  expect(screen.queryByRole("button")).toBeNull();
  view.rerender(<Paged count={26} compact />);
  expect(screen.getByRole("button", { name: "Next" })).toBeTruthy();
  expect(screen.queryByRole("combobox")).toBeNull();
});
it("retains cursor controls without assuming a small event page is the whole stream", () => {
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ListPagination
        cursor
        page={1}
        pageSize={25}
        count={1}
        canNext
        setPage={() => undefined}
        setPageSize={() => undefined}
      />
    </NextIntlClientProvider>,
  );
  expect(screen.getByRole("button", { name: "Next" }).hasAttribute("disabled")).toBe(false);
  expect(screen.getByRole("combobox")).toBeTruthy();
});
