import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { UsageScreen } from "@/components/usage/usage-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/usage",
  useRouter: () => ({ push: () => undefined }),
}));
vi.mock("next/dynamic", () => ({
  default:
    () =>
    ({ points }: { points: unknown[] }) => (
      <output aria-label="Chart points">{points.length}</output>
    ),
}));
const summary = {
  currency: "INR",
  totals: { quantity: 123, costMicros: 1000 },
  rows: [{ keys: { day: "2026-11-22" }, quantity: 123, costMicros: 1000 }],
};
function mount() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <UsageScreen />
    </NextIntlClientProvider>,
  );
}
async function ready() {
  return screen.findByRole("region", { name: "Usage report" });
}
function range(from: string, to: string) {
  fireEvent.change(screen.getByLabelText("From"), { target: { value: from } });
  fireEvent.change(screen.getByLabelText("To"), { target: { value: to } });
}
const createUrl = vi.fn((_blob: Blob) => "blob:usage-report");
const revokeUrl = vi.fn();
let originalCreate: PropertyDescriptor | undefined;
let originalRevoke: PropertyDescriptor | undefined;
beforeEach(() => {
  originalCreate = Object.getOwnPropertyDescriptor(URL, "createObjectURL");
  originalRevoke = Object.getOwnPropertyDescriptor(URL, "revokeObjectURL");
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createUrl });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeUrl });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["usage:read"] })),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/usage/summary", () => HttpResponse.json(summary)),
    http.get("*/api/v1/observability/overview", () =>
      HttpResponse.json({ runs: { total: 7 }, feedback: { up: 2, down: 1 } }),
    ),
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  createUrl.mockClear();
  revokeUrl.mockClear();
  if (originalCreate) Object.defineProperty(URL, "createObjectURL", originalCreate);
  else Reflect.deleteProperty(URL, "createObjectURL");
  if (originalRevoke) Object.defineProperty(URL, "revokeObjectURL", originalRevoke);
  else Reflect.deleteProperty(URL, "revokeObjectURL");
});

describe("usage report context and bounded results", () => {
  it("applies date and group drafts together without relabelling the loaded report", async () => {
    const requests: URL[] = [];
    const overview = vi.fn(() =>
      HttpResponse.json({ runs: { total: 7 }, feedback: { up: 2, down: 1 } }),
    );
    server.use(
      http.get("*/api/v1/usage/summary", ({ request }) => {
        const url = new URL(request.url);
        requests.push(url);
        return HttpResponse.json({
          ...summary,
          rows: [
            {
              ...summary.rows[0],
              keys: { [url.searchParams.get("group_by") ?? "day"]: "Recorded group" },
            },
          ],
        });
      }),
      http.get("*/api/v1/observability/overview", overview),
    );
    mount();
    await ready();
    await screen.findByText("7");
    range("2026-11-01", "2026-11-22");
    fireEvent.change(screen.getByRole("combobox", { name: "Group by" }), {
      target: { value: "agent" },
    });
    expect(requests).toHaveLength(1);
    expect(screen.getByText(/Loaded: default start to default end/)).toBeTruthy();
    expect(screen.getByText("Filter changes have not been applied.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    await screen.findByText("Loaded: 2026-11-01 to 2026-11-22 · grouped by Agent");
    expect(requests[1]?.searchParams.toString()).toBe(
      "group_by=agent&from=2026-11-01&to=2026-11-22",
    );
    expect(overview).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Use default range" }));
    await screen.findByText(/Loaded: default start to default end/);
    expect(requests[2]?.searchParams.toString()).toBe("group_by=day");
  });
  it("blocks a reversed range even on direct form submission", async () => {
    const read = vi.fn(() => HttpResponse.json(summary));
    server.use(http.get("*/api/v1/usage/summary", read));
    mount();
    await ready();
    range("2026-11-22", "2026-11-01");
    const form = screen.getByRole("button", { name: "Apply filters" }).closest("form");
    if (!form) throw new Error("Missing usage filter form");
    fireEvent.submit(form);
    expect(await screen.findByText(messages.usage.invalidRange)).toBeTruthy();
    expect(read).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("To").getAttribute("min")).toBe("2026-11-22");
  });
  it("retains the prior report and its scope when a new range fails", async () => {
    mount();
    await ready();
    server.use(
      http.get("*/api/v1/usage/summary", () =>
        HttpResponse.json({ detail: "Report unavailable" }, { status: 503 }),
      ),
    );
    range("2026-11-01", "2026-11-22");
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    await screen.findByText("Report unavailable");
    expect(screen.getByText(/Loaded: default start to default end/)).toBeTruthy();
    expect(screen.getByText(messages.usage.stale)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Export CSV" }).hasAttribute("disabled")).toBe(true);
  });
  it("bounds both chart and table to the selected page with 100,000 returned groups", async () => {
    server.use(
      http.get("*/api/v1/usage/summary", () =>
        HttpResponse.json({
          ...summary,
          rows: Array.from({ length: 100000 }, (_, index) => ({
            keys: { day: `group-${index}` },
            quantity: index,
            costMicros: 0,
          })),
        }),
      ),
    );
    mount();
    const report = await ready();
    expect(within(report).getAllByRole("row")).toHaveLength(26);
    expect(screen.getByLabelText("Chart points").textContent).toBe("25");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("cell", { name: "group-25" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Rows per page"), { target: { value: "100" } });
    expect(within(report).getAllByRole("row")).toHaveLength(101);
    expect(screen.getByLabelText("Chart points").textContent).toBe("100");
    fireEvent.change(screen.getByLabelText(messages.usage.search), {
      target: { value: "group-99999" },
    });
    expect(within(report).getAllByRole("row")).toHaveLength(2);
    expect(screen.getByRole("cell", { name: "group-99999" })).toBeTruthy();
    expect(screen.getByLabelText("Chart points").textContent).toBe("1");
    fireEvent.change(screen.getByLabelText(messages.usage.search), {
      target: { value: "absent-group" },
    });
    expect(screen.getByText(messages.usage.noMatches)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(screen.getByRole("cell", { name: "group-0" })).toBeTruthy();
  }, 15000);
  it("does not invent missing report totals or a currency", async () => {
    server.use(http.get("*/api/v1/usage/summary", () => HttpResponse.json({ rows: [] })));
    mount();
    await screen.findByText(messages.usage.metadataError);
    expect(screen.queryByRole("region", { name: "Usage report" })).toBeNull();
    server.use(
      http.get("*/api/v1/usage/summary", () => HttpResponse.json({ ...summary, currency: "" })),
    );
    fireEvent.click(screen.getByRole("button", { name: "Refresh usage report" }));
    await ready();
    expect(screen.getByText("Not supplied")).toBeTruthy();
    expect(screen.getByText("Cost (currency not set)")).toBeTruthy();
  });
  it("loads operations independently without turning their failure into zero", async () => {
    server.use(
      http.get("*/api/v1/observability/overview", () =>
        HttpResponse.json({ detail: "Operations unavailable" }, { status: 503 }),
      ),
    );
    mount();
    await ready();
    await screen.findByText("Operations unavailable");
    expect(screen.queryByText(messages.usage.overviewEmpty)).toBeNull();
    server.use(
      http.get("*/api/v1/observability/overview", () =>
        HttpResponse.json({ runs: { total: 8 }, feedback: { up: 3, down: 1 } }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Refresh all-time operations" }));
    await screen.findByText("8");
    expect(screen.getByRole("region", { name: "Usage report" })).toBeTruthy();
  });
  it("keeps operations available when usage fails and rejects incomplete operation totals", async () => {
    server.use(
      http.get("*/api/v1/usage/summary", () =>
        HttpResponse.json({ detail: "Usage unavailable" }, { status: 503 }),
      ),
    );
    mount();
    await screen.findByText("Usage unavailable");
    await screen.findByText("7");
    server.use(
      http.get("*/api/v1/observability/overview", () =>
        HttpResponse.json({ runs: {}, feedback: {} }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Refresh all-time operations" }));
    await screen.findByText(messages.usage.overviewMetadataError);
    expect(screen.getByText("7")).toBeTruthy();
    expect(screen.queryByText(messages.usage.overviewEmpty)).toBeNull();
  });
  it("does not read private reports without usage permission", async () => {
    const read = vi.fn(() => HttpResponse.json(summary));
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: [] })),
      http.get("*/api/v1/usage/summary", read),
    );
    mount();
    await screen.findByText(messages.usage.readDenied);
    expect(read).not.toHaveBeenCalled();
    expect(screen.queryByRole("region", { name: "All-time operations" })).toBeNull();
  });
});

describe("usage CSV download", () => {
  it("downloads CSV bytes using applied filters rather than draft fields or list search", async () => {
    const requests: URL[] = [];
    server.use(
      http.get("*/api/v1/usage/export", ({ request }) => {
        requests.push(new URL(request.url));
        return new HttpResponse("day,quantity\n2026-11-22,123\n", {
          headers: { "Content-Type": "text/csv; charset=utf-8" },
        });
      }),
    );
    const view = mount();
    await ready();
    range("2026-11-01", "2026-11-22");
    fireEvent.change(screen.getByLabelText(messages.usage.search), {
      target: { value: "not-matching" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    await screen.findByText(messages.usage.exportStarted);
    expect(requests[0]?.searchParams.toString()).toBe("group_by=day");
    expect(createUrl).toHaveBeenCalledTimes(1);
    expect(await createUrl.mock.calls[0]?.[0].text()).toBe("day,quantity\n2026-11-22,123\n");
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
    view.unmount();
    expect(revokeUrl).toHaveBeenCalledWith("blob:usage-report");
  });
  it.each([400, 429, 503])("never downloads an HTTP %s error as a CSV", async (status) => {
    server.use(
      http.get("*/api/v1/usage/export", () =>
        HttpResponse.json({ detail: "Export refused" }, { status }),
      ),
    );
    mount();
    await ready();
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    if (status === 429) {
      await screen.findByText(messages.apiErrors.rateLimited);
      const details = screen.getByText(messages.apiErrors.details);
      const disclosure = details.closest("details");
      if (!disclosure) throw new Error("Missing error disclosure");
      disclosure.open = true;
      fireEvent(disclosure, new Event("toggle"));
    }
    await screen.findByText("Export refused");
    expect(createUrl).not.toHaveBeenCalled();
    expect(HTMLAnchorElement.prototype.click).not.toHaveBeenCalled();
    expect(screen.queryByText(messages.usage.exportStarted)).toBeNull();
    expect(screen.getByRole("region", { name: "Usage report" })).toBeTruthy();
  });
  it("rejects an OK response that is not a CSV", async () => {
    server.use(http.get("*/api/v1/usage/export", () => HttpResponse.json({ detail: "Not a CSV" })));
    mount();
    await ready();
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    await screen.findByText(messages.usage.exportFormatError);
    expect(createUrl).not.toHaveBeenCalled();
  });
  it("clears private data when export permission is refused", async () => {
    server.use(
      http.get("*/api/v1/usage/export", () =>
        HttpResponse.json({ detail: "Forbidden" }, { status: 403 }),
      ),
    );
    mount();
    await ready();
    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    await screen.findByText(messages.usage.readDenied);
    expect(screen.queryByRole("region", { name: "Usage report" })).toBeNull();
    expect(screen.queryByRole("region", { name: "All-time operations" })).toBeNull();
    expect(createUrl).not.toHaveBeenCalled();
  });
  it("prevents duplicate exports and aborts a pending download on unmount", async () => {
    const nativeFetch = globalThis.fetch;
    let captured: AbortSignal | null | undefined;
    let resolve!: (response: Response) => void;
    const pending = new Promise<Response>((done) => {
      resolve = done;
    });
    const exports = vi.fn();
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input).startsWith("/api/v1/usage/export")) {
        captured = init?.signal;
        exports();
        return pending;
      }
      return nativeFetch(input, init);
    });
    const view = mount();
    await ready();
    const button = screen.getByRole("button", { name: "Export CSV" });
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(exports).toHaveBeenCalledTimes(1));
    view.unmount();
    expect(captured?.aborted).toBe(true);
    resolve(new Response("day,quantity\n", { headers: { "Content-Type": "text/csv" } }));
    await pending;
    await new Promise((done) => setTimeout(done, 0));
    expect(createUrl).not.toHaveBeenCalled();
  });
});
