import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import messages from "@/messages/en.json";
import { ErrorMessage } from "./detail-state";

const view = (error: string | Error) => (
  <NextIntlClientProvider locale="en" messages={messages}>
    <ErrorMessage error={error} />
  </NextIntlClientProvider>
);

afterEach(cleanup);

describe("shared error guidance", () => {
  it.each([
    [403, "csrf_failed", "csrf"],
    [401, "unauthenticated", "unauthenticated"],
    [429, "rate_limited", "rateLimited"],
    [503, "unavailable", "unavailable"],
    [502, "upstream_error", "unavailable"],
    [504, "upstream_timeout", "unavailable"],
    [500, "internal_error", "internal"],
  ] as const)("explains %s/%s and discloses its unchanged diagnostic", (status, code, key) => {
    const raw = "Original server diagnostic <script>text only</script>";
    render(view(new ApiError(raw, status, code)));
    expect(screen.getByText(messages.apiErrors[key])).toBeTruthy();
    expect(screen.queryByText(raw)).toBeNull();
    const details = screen.getByText(messages.apiErrors.details).closest("details");
    expect(details).toBeTruthy();
    // Native details toggling is exposed through its open property in the browser.
    (details as HTMLDetailsElement).open = true;
    fireEvent(details as HTMLDetailsElement, new Event("toggle"));
    expect(screen.getByText(raw)).toBeTruthy();
    expect(screen.getByText(`HTTP ${status} · ${code}`)).toBeTruthy();
    expect(screen.getByRole("region", { name: messages.apiErrors.details }).tabIndex).toBe(0);
    expect(document.querySelector("script")).toBeNull();
  });

  it.each([
    new ApiError("A second approver is required", 403, "forbidden"),
    new ApiError("Choose an enabled agent", 422, "validation_failed"),
    new Error("csrf_failed is only local text"),
    "Please choose a name",
  ])("keeps business and local errors explicit without guessing from their words", (error) => {
    render(view(error));
    expect(screen.getByText(error instanceof Error ? error.message : error)).toBeTruthy();
    expect(screen.queryByText(messages.apiErrors.details)).toBeNull();
  });

  it("collapses old diagnostics immediately when a different error arrives", () => {
    const first = new ApiError("First diagnostic", 403, "csrf_failed");
    const { rerender } = render(view(first));
    const details = screen
      .getByText(messages.apiErrors.details)
      .closest("details") as HTMLDetailsElement;
    details.open = true;
    fireEvent(details, new Event("toggle"));
    expect(screen.getByText(first.message)).toBeTruthy();
    const second = new ApiError("Second diagnostic", 503, "unavailable");
    rerender(view(second));
    expect(screen.queryByText(first.message)).toBeNull();
    expect(screen.queryByText(second.message)).toBeNull();
    expect(screen.getByText(messages.apiErrors.unavailable)).toBeTruthy();
  });
});
