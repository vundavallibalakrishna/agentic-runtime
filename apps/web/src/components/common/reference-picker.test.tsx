import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReferencePicker } from "@/components/common/reference-picker";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

function Picker() {
  const [value, setValue] = useState("");
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <ReferencePicker
        label="Saved connection"
        endpoint="/api/v1/references"
        value={value}
        onChange={setValue}
      />
      <output aria-label="Selected reference">{value}</output>
    </NextIntlClientProvider>
  );
}

describe("saved reference picker", () => {
  afterEach(() => vi.restoreAllMocks());
  it("bounds the list and selects a named record beyond page one through search", async () => {
    server.use(
      http.get("*/api/v1/references", () =>
        HttpResponse.json({
          items: Array.from({ length: 30 }, (_, i) => ({
            id: `ref-${i}`,
            name: `Connection ${i}`,
            kind: "database",
          })),
        }),
      ),
    );
    render(<Picker />);
    fireEvent.click(screen.getByRole("button", { name: /^Saved connection:/ }));
    const dialog = within(screen.getByRole("dialog"));
    await dialog.findByText("Connection 0");
    expect(dialog.queryByText("Connection 29")).toBeNull();
    fireEvent.click(dialog.getByRole("button", { name: "Next" }));
    expect(dialog.getByText("Connection 29")).toBeTruthy();
    fireEvent.change(dialog.getByRole("searchbox"), { target: { value: "Connection 0" } });
    expect(dialog.getByText("Connection 0")).toBeTruthy();
    fireEvent.change(dialog.getByRole("searchbox"), { target: { value: "Connection 29" } });
    fireEvent.click(dialog.getByText("Connection 29"));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByLabelText("Selected reference").textContent).toBe("ref-29");
    fireEvent.click(screen.getByRole("button", { name: "Clear Saved connection" }));
    expect(screen.getByLabelText("Selected reference").textContent).toBe("");
  });

  it("keeps errors actionable and cancellation does not select a record", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v1/references", () =>
        ++calls === 1
          ? HttpResponse.json({ detail: "Metadata unavailable" }, { status: 503 })
          : HttpResponse.json({ items: [{ id: "ref", name: "Saved system" }] }),
      ),
    );
    render(<Picker />);
    fireEvent.click(screen.getByRole("button", { name: /^Saved connection:/ }));
    const dialog = within(screen.getByRole("dialog"));
    await dialog.findByRole("alert");
    fireEvent.click(dialog.getByRole("button", { name: "Try again" }));
    await dialog.findByText("Saved system");
    fireEvent.click(dialog.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByLabelText("Selected reference").textContent).toBe("");
  });
  it("uses already loaded metadata without a request and bounds 100,000 choices", async () => {
    const rows = Array.from({ length: 100_000 }, (_, index) => ({
      id: `local-${index}`,
      name: `Model ${index}`,
      upstream: `upstream-${index}`,
    }));
    const network = vi.spyOn(globalThis, "fetch");
    const changed = vi.fn();
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <ReferencePicker
          label="Loaded model"
          items={rows}
          value="local-99999"
          onChange={changed}
          getDescription={(row) => row.upstream}
          clearable={false}
        />
      </NextIntlClientProvider>,
    );
    expect(screen.queryByRole("list")).toBeNull();
    expect(screen.getByRole("button", { name: "Loaded model: Model 99999" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Clear Loaded model" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Loaded model: Model 99999" }));
    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.click(dialog.getByRole("button", { name: "Next" }));
    expect(dialog.getByText("Model 25")).toBeTruthy();
    fireEvent.change(dialog.getByRole("searchbox"), { target: { value: "upstream-99999" } });
    expect(dialog.getAllByRole("listitem")).toHaveLength(1);
    const current = dialog.getByRole("button", { name: /Model 99999/ });
    expect(current.getAttribute("aria-current")).toBe("true");
    expect(current.getAttribute("aria-description")).toBe(
      messages.referencePicker.currentSelection,
    );
    fireEvent.click(current);
    expect(changed).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Loaded model: Model 99999" }));
    const reopened = within(screen.getByRole("dialog"));
    fireEvent.change(reopened.getByRole("searchbox"), { target: { value: "upstream-99998" } });
    const other = reopened.getByRole("button", { name: /Model 99998/ });
    expect(other.hasAttribute("aria-current")).toBe(false);
    fireEvent.click(other);
    expect(changed).toHaveBeenCalledExactlyOnceWith("local-99998");
    expect(network).not.toHaveBeenCalled();
  });

  it("updates caller-provided rows while open without selecting a record", () => {
    const changed = vi.fn();
    const content = (items: { id: string; name: string }[]) => (
      <NextIntlClientProvider locale="en" messages={messages}>
        <ReferencePicker label="Loaded metadata" items={items} value="" onChange={changed} />
      </NextIntlClientProvider>
    );
    const { rerender } = render(content([]));
    fireEvent.click(screen.getByRole("button", { name: /^Loaded metadata:/ }));
    expect(
      within(screen.getByRole("dialog")).getByText(messages.referencePicker.empty),
    ).toBeTruthy();
    expect(screen.queryByRole("status", { name: messages.referencePicker.loading })).toBeNull();
    rerender(content([{ id: "saved", name: "Newly returned model" }]));
    expect(within(screen.getByRole("dialog")).getByText("Newly returned model")).toBeTruthy();
    expect(changed).not.toHaveBeenCalled();
  });

  it("returns keyboard focus to the trigger after cancelling", async () => {
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <ReferencePicker label="Loaded metadata" items={[]} value="" onChange={vi.fn()} />
      </NextIntlClientProvider>,
    );
    const trigger = screen.getByRole("button", { name: /^Loaded metadata:/ });
    trigger.focus();
    fireEvent.click(trigger);
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(document.activeElement).toBe(trigger));
  });
});

it.each([false, true])("closes an open picker when disabled (multiple=%s)", async (multiple) => {
  const changed = vi.fn();
  const view = (disabled: boolean) => (
    <NextIntlClientProvider locale="en" messages={messages}>
      {multiple ? (
        <ReferencePicker
          label="Target"
          items={[
            { id: "a", name: "Current" },
            { id: "b", name: "Other" },
          ]}
          multiple
          value={["a"]}
          onChange={changed}
          disabled={disabled}
        />
      ) : (
        <ReferencePicker
          label="Target"
          items={[
            { id: "a", name: "Current" },
            { id: "b", name: "Other" },
          ]}
          value="a"
          onChange={changed}
          disabled={disabled}
        />
      )}
    </NextIntlClientProvider>
  );
  const rendered = render(view(false));
  fireEvent.click(screen.getByRole("button", { name: /^Target/ }));
  const picker = within(screen.getByRole("dialog"));
  if (multiple) fireEvent.click(picker.getByRole("checkbox", { name: "Other" }));
  rendered.rerender(view(true));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.getByRole("button", { name: /^Target/ }).matches(":disabled")).toBe(true);
  expect(changed).not.toHaveBeenCalled();
  rendered.rerender(view(false));
  expect(screen.queryByRole("dialog")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /^Target/ }));
  const reopened = within(screen.getByRole("dialog"));
  if (multiple) {
    expect((reopened.getByRole("checkbox", { name: "Current" }) as HTMLInputElement).checked).toBe(
      true,
    );
    expect((reopened.getByRole("checkbox", { name: "Other" }) as HTMLInputElement).checked).toBe(
      false,
    );
  } else {
    expect(reopened.getByRole("button", { name: /^Current/ }).getAttribute("aria-current")).toBe(
      "true",
    );
  }
  expect(changed).not.toHaveBeenCalled();
});

it("cancels disabled-field metadata reads and does not reopen from a late reply", async () => {
  let finish = () => {};
  let started = false;
  let finished = false;
  let reads = 0;
  const waiting = new Promise<void>((resolve) => {
    finish = resolve;
  });
  server.use(
    http.get(
      "*/api/v1/references",
      async () => {
        reads += 1;
        started = true;
        await waiting;
        finished = true;
        return HttpResponse.json({ items: [{ id: "stale", name: "Old metadata" }] });
      },
      { once: true },
    ),
    http.get("*/api/v1/references", () => {
      reads += 1;
      return HttpResponse.json({ items: [{ id: "fresh", name: "Fresh metadata" }] });
    }),
  );
  const changed = vi.fn();
  const view = (disabled: boolean) => (
    <NextIntlClientProvider locale="en" messages={messages}>
      <ReferencePicker
        label="Target"
        endpoint="/api/v1/references"
        value=""
        onChange={changed}
        disabled={disabled}
      />
    </NextIntlClientProvider>
  );
  const rendered = render(view(false));
  fireEvent.click(screen.getByRole("button", { name: /^Target/ }));
  await waitFor(() => expect(started).toBe(true));
  rendered.rerender(view(true));
  expect(screen.queryByRole("dialog")).toBeNull();
  finish();
  await waitFor(() => expect(finished).toBe(true));
  rendered.rerender(view(false));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(reads).toBe(1);
  fireEvent.click(screen.getByRole("button", { name: /^Target/ }));
  await screen.findByRole("button", { name: /^Fresh metadata/ });
  expect(screen.queryByText("Old metadata")).toBeNull();
  expect(reads).toBe(2);
  expect(changed).not.toHaveBeenCalled();
});
