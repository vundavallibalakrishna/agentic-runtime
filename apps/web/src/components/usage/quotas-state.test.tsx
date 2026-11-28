import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QuotasScreen } from "@/components/usage/quotas-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));
const t = messages.quotas;
const rule = {
  id: "quota-1",
  scopeType: "tenant",
  scope: null,
  metric: "runs",
  period: "day",
  limitValue: 10,
  used: 3,
  action: "warn",
  warnAtPct: 70,
  implicit: false,
  resetsAt: "2026-11-23T00:00:00+00:00",
};
function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <QuotasScreen />
    </NextIntlClientProvider>,
  );
}
const form = () => within(screen.getByRole("complementary"));
async function ready() {
  await waitFor(() =>
    expect(screen.getByRole("button", { name: t.refresh }).matches(":disabled")).toBe(false),
  );
}
function refresh() {
  fireEvent.click(screen.getAllByRole("button", { name: t.refresh })[0] as HTMLElement);
}
function setLimit(value: string) {
  fireEvent.change(form().getByLabelText(t.limit), { target: { value } });
}
beforeEach(() => {
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ permissions: ["usage:read", "quotas:manage"] }),
    ),
    http.get("*/api/v1/quotas", () => HttpResponse.json({ items: [] })),
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
});
describe("quota state and precise amounts", () => {
  it("requires an explicit new limit and leaves behavior defaults to the service", async () => {
    let body: Record<string, unknown> = {};
    server.use(
      http.post("*/api/v1/quotas", async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...rule, ...body, id: "saved", scope: null, used: 0 });
      }),
    );
    show();
    await ready();
    expect((form().getByLabelText(t.limit) as HTMLInputElement).value).toBe("");
    expect(form().getByRole("button", { name: t.save }).matches(":disabled")).toBe(true);
    setLimit("15");
    fireEvent.click(form().getByRole("button", { name: t.save }));
    await screen.findByText(t.savedNotListed);
    expect(body).toEqual({
      scopeType: "user",
      scopeId: null,
      metric: "model_tokens",
      period: "day",
      limitValue: 15,
    });
    expect((form().getByLabelText(t.limit) as HTMLInputElement).value).toBe("");
  });
  it("sends exact decimal spend and explicit behavior without exposing storage units", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/v1/quotas", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...rule, ...(body as object), id: "saved", scope: null });
      }),
    );
    show();
    await ready();
    fireEvent.change(form().getByRole("combobox", { name: t.metric }), {
      target: { value: "cost_micros" },
    });
    fireEvent.change(form().getByLabelText(t.spendLimit), {
      target: { value: "9007199254.740991" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    fireEvent.change(form().getByRole("combobox", { name: t.action }), {
      target: { value: "warn" },
    });
    fireEvent.change(form().getByLabelText(t.warn), { target: { value: "65" } });
    fireEvent.click(screen.getByRole("button", { name: "Simple" }));
    expect(form().getByText("When full: Warn only. Warn at 65%.")).toBeTruthy();
    fireEvent.click(form().getByRole("button", { name: t.save }));
    await screen.findByText(t.savedNotListed);
    expect(body).toMatchObject({
      limitValue: Number.MAX_SAFE_INTEGER,
      metric: "cost_micros",
      action: "warn",
      warnAtPct: 65,
    });
  });
  it.each(["0.0000001", "9007199254.740992", "-1", "1e3"])(
    "explains an invalid money amount %s without issuing a write",
    async (value) => {
      const write = vi.fn(() => HttpResponse.json(rule));
      server.use(http.post("*/api/v1/quotas", write));
      show();
      await ready();
      fireEvent.change(form().getByRole("combobox", { name: t.metric }), {
        target: { value: "cost_micros" },
      });
      fireEvent.change(form().getByLabelText(t.spendLimit), { target: { value } });
      expect(form().getByText(t.invalidMoney)).toBeTruthy();
      expect(form().getByRole("button", { name: t.save }).matches(":disabled")).toBe(true);
      expect(write).not.toHaveBeenCalled();
    },
  );
  it("clears an amount when its metric changes and retains inherited behavior through modes", async () => {
    show();
    await ready();
    setLimit("200");
    fireEvent.change(form().getByRole("combobox", { name: t.metric }), {
      target: { value: "cost_micros" },
    });
    expect((form().getByLabelText(t.spendLimit) as HTMLInputElement).value).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    expect((form().getByLabelText(t.warn) as HTMLInputElement).value).toBe("");
    expect((form().getByRole("combobox", { name: t.action }) as HTMLSelectElement).value).toBe("");
  });
  it("keeps a mismatched acknowledgement unconfirmed and recovers without replay", async () => {
    const write = vi.fn(() => HttpResponse.json({ ...rule, id: "other", metric: "tool_calls" }));
    server.use(http.post("*/api/v1/quotas", write));
    show();
    await ready();
    setLimit("20");
    fireEvent.click(form().getByRole("button", { name: t.save }));
    await form().findByText(t.saveUnconfirmed);
    expect(screen.queryByText(t.saved)).toBeNull();
    expect((form().getByLabelText(t.limit) as HTMLInputElement).value).toBe("20");
    expect(form().getByRole("button", { name: t.save }).matches(":disabled")).toBe(true);
    expect(form().getByLabelText(t.limit).matches(":disabled")).toBe(false);
    refresh();
    await screen.findByText(t.checked);
    expect(write).toHaveBeenCalledTimes(1);
    expect(form().getByRole("button", { name: t.save }).matches(":disabled")).toBe(false);
  });
  it("does not invent missing usage, action or warning metadata", async () => {
    server.use(
      http.get("*/api/v1/quotas", () =>
        HttpResponse.json({ items: [{ ...rule, used: undefined }] }),
      ),
    );
    show();
    await screen.findByText(t.metadataError);
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.queryByText(t.empty)).toBeNull();
  });
  it("retains successful data and edit drafts across a failed refresh", async () => {
    server.use(http.get("*/api/v1/quotas", () => HttpResponse.json({ items: [rule] })));
    show();
    await ready();
    fireEvent.click(screen.getByRole("button", { name: `Edit quota ${rule.id}` }));
    setLimit("25");
    server.use(
      http.get("*/api/v1/quotas", () =>
        HttpResponse.json({ detail: "Quota list unavailable" }, { status: 503 }),
      ),
    );
    refresh();
    await screen.findByText("Quota list unavailable");
    expect(screen.getByRole("heading", { name: "Agent runs · Day" })).toBeTruthy();
    expect((form().getByLabelText(t.limit) as HTMLInputElement).value).toBe("25");
    expect(form().getByRole("button", { name: t.saveChanges }).matches(":disabled")).toBe(true);
  });
  it("clears protected views after explicit read access loss", async () => {
    server.use(http.get("*/api/v1/quotas", () => HttpResponse.json({ items: [rule] })));
    show();
    await ready();
    server.use(
      http.get("*/api/v1/quotas", () =>
        HttpResponse.json({ detail: "Forbidden" }, { status: 403 }),
      ),
    );
    refresh();
    await screen.findByText(t.denied);
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.queryByRole("complementary")).toBeNull();
  });
  it("preserves unknown returned behavior in a limit-only edit", async () => {
    const saved = { ...rule, action: "future_policy" };
    let body: unknown;
    server.use(
      http.get("*/api/v1/quotas", () => HttpResponse.json({ items: [saved] })),
      http.patch(`*/api/v1/quotas/${rule.id}`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...saved, limitValue: 25 });
      }),
    );
    show();
    await ready();
    expect(within(screen.getByRole("listitem")).getByText("future_policy")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: `Edit quota ${rule.id}` }));
    expect(form().getByRole("button", { name: t.saveChanges }).matches(":disabled")).toBe(true);
    setLimit("25");
    fireEvent.click(form().getByRole("button", { name: t.saveChanges }));
    await screen.findByText(t.savedNotListed);
    expect(body).toEqual({ limitValue: 25 });
  });
  it("keeps a known save acknowledgement when the following list refresh fails", async () => {
    server.use(http.get("*/api/v1/quotas", () => HttpResponse.json({ items: [rule] })));
    show();
    await ready();
    fireEvent.click(screen.getByRole("button", { name: `Edit quota ${rule.id}` }));
    setLimit("25");
    server.use(
      http.patch(`*/api/v1/quotas/${rule.id}`, () =>
        HttpResponse.json({ ...rule, limitValue: 25 }),
      ),
      http.get("*/api/v1/quotas", () =>
        HttpResponse.json({ detail: "List refresh unavailable" }, { status: 503 }),
      ),
    );
    fireEvent.click(form().getByRole("button", { name: t.saveChanges }));
    await screen.findByText(t.saved);
    await screen.findByText("List refresh unavailable");
    expect(screen.queryByText(t.saveUnconfirmed)).toBeNull();
  });
  it("shows spend rows in currency units and labelled reset times", async () => {
    server.use(
      http.get("*/api/v1/quotas", () =>
        HttpResponse.json({
          items: [{ ...rule, metric: "cost_micros", limitValue: 1250001, used: 250001 }],
        }),
      ),
    );
    show();
    await ready();
    expect(screen.getByText("Used 0.250001 / 1.250001")).toBeTruthy();
    expect(screen.getByText(/^Resets /)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: `Edit quota ${rule.id}` }));
    expect((form().getByLabelText(t.spendLimit) as HTMLInputElement).value).toBe("1.250001");
  });
});
describe("quota removal and request lifetime", () => {
  it("starts confirmation on Cancel and returns focus without deleting", async () => {
    const remove = vi.fn();
    server.use(
      http.get("*/api/v1/quotas", () => HttpResponse.json({ items: [rule] })),
      http.delete(`*/api/v1/quotas/${rule.id}`, remove),
    );
    show();
    await ready();
    const button = screen.getByRole("button", { name: `Remove quota ${rule.id}` });
    fireEvent.click(button);
    const dialog = within(screen.getByRole("dialog", { name: t.removeTitle }));
    await waitFor(() =>
      expect(document.activeElement).toBe(dialog.getByRole("button", { name: t.cancelRemove })),
    );
    expect(dialog.getByText(rule.id)).toBeTruthy();
    fireEvent.click(dialog.getByRole("button", { name: t.cancelRemove }));
    await waitFor(() => expect(document.activeElement).toBe(button));
    expect(remove).not.toHaveBeenCalled();
  });
  it("confirms a successful removal only after the saved row is absent", async () => {
    let items = [rule];
    server.use(
      http.get("*/api/v1/quotas", () => HttpResponse.json({ items })),
      http.delete(`*/api/v1/quotas/${rule.id}`, () => {
        items = [];
        return new HttpResponse(null, { status: 204 });
      }),
    );
    show();
    await ready();
    fireEvent.click(screen.getByRole("button", { name: `Remove quota ${rule.id}` }));
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: t.removeConfirm }),
    );
    await screen.findByText(t.removed);
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  it("does not claim removal when the supposedly removed row is still saved", async () => {
    server.use(
      http.get("*/api/v1/quotas", () => HttpResponse.json({ items: [rule] })),
      http.delete(`*/api/v1/quotas/${rule.id}`, () => new HttpResponse(null, { status: 204 })),
    );
    show();
    await ready();
    fireEvent.click(screen.getByRole("button", { name: `Remove quota ${rule.id}` }));
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: t.removeConfirm }),
    );
    await screen.findByText(t.removeNotReflected);
    expect(screen.queryByText(t.removed)).toBeNull();
    expect(screen.getByRole("progressbar")).toBeTruthy();
    refresh();
    await screen.findByText(t.checked);
  });
  it("bounds 100,000 loaded quotas and clears combined filters back to page one", async () => {
    server.use(
      http.get("*/api/v1/quotas", () =>
        HttpResponse.json({
          items: Array.from({ length: 100000 }, (_, i) => ({
            ...rule,
            id: `rule-${i}`,
            scopeType: "agent",
            scope: { id: `agent-${i}`, name: `Target ${i}` },
          })),
        }),
      ),
    );
    show();
    await ready();
    expect(screen.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Target 25")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Rows per page"), { target: { value: "100" } });
    expect(screen.getAllByRole("listitem")).toHaveLength(100);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "rule-99999" } });
    expect(screen.getByText("Target 99999")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: t.clear }));
    expect(document.activeElement).toBe(screen.getByRole("searchbox"));
    expect(screen.getByText("Target 0")).toBeTruthy();
  }, 15000);
  it("guards duplicate saves and aborts late receipts without a follow-up read", async () => {
    const nativeFetch = globalThis.fetch;
    let signal: AbortSignal | null | undefined;
    let resolve!: (value: Response) => void;
    const pending = new Promise<Response>((done) => {
      resolve = done;
    });
    let writes = 0,
      reads = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input) === "/api/v1/quotas" && init?.method === "POST") {
        writes++;
        signal = init.signal;
        return pending;
      }
      if (String(input) === "/api/v1/quotas") reads++;
      return nativeFetch(input, init);
    });
    const view = show();
    await ready();
    setLimit("20");
    const button = form().getByRole("button", { name: t.save });
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(writes).toBe(1));
    view.unmount();
    expect(signal?.aborted).toBe(true);
    resolve(Response.json({ ...rule, limitValue: 20 }));
    await pending;
    await new Promise((done) => setTimeout(done, 0));
    expect(reads).toBe(1);
  });
});
