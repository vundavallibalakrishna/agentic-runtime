import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SchedulesScreen } from "@/components/schedules/schedules-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/schedules",
  useParams: () => ({}),
  useRouter: () => ({ push: () => undefined }),
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("schedules", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows an empty state", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["routines:create", "chat:use"] }),
      ),
      http.get("*/api/v1/routines", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<SchedulesScreen />));
    expect(await screen.findByRole("heading", { name: "Schedules" })).toBeTruthy();
    expect(
      await screen.findByText(
        "No schedules yet. Create one to run an agent on a clock or from a webhook.",
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("searchbox", { name: messages.schedules.search })).toBeNull();
  });
  function setup(items: object[] = []) {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["routines:create", "chat:use"] }),
      ),
      http.get("*/api/v1/routines", () => HttpResponse.json({ items })),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({
          items: [
            { id: "archived", name: "Archived agent", status: "archived", disabled: false },
            { id: "draft", name: "Draft agent", status: "draft", disabled: false },
            { id: "disabled", name: "Disabled agent", status: "published", disabled: true },
            { id: "agent", name: "Workspace assistant", status: "published", disabled: false },
          ],
        }),
      ),
      http.get("*/api/v1/routines/:id/events", () => HttpResponse.json({ items: [] })),
    );
  }

  it("bounds schedules and activity separately and filters before paging", async () => {
    setup(
      Array.from({ length: 30 }, (_, i) => ({
        id: `schedule-${i}`,
        name: `Task ${i}`,
        status: i % 2 ? "paused" : "active",
        triggerType: i % 3 ? "schedule" : "webhook",
      })),
    );
    server.use(
      http.get("*/api/v1/routines/schedule-0/events", () =>
        HttpResponse.json({
          items: Array.from({ length: 30 }, (_, i) => ({
            id: `event-${i}`,
            runId: `run-${i}`,
            status: i % 2 ? "failed" : "started",
            source: "manual",
            receivedAt: "2026-11-21T10:00:00Z",
          })),
        }),
      ),
    );
    render(wrap(<SchedulesScreen />));
    await screen.findByRole("button", { name: /^Task 0/ });
    expect(screen.queryByRole("button", { name: /^Task 29/ })).toBeNull();
    fireEvent.click(
      within(
        screen.getByRole("navigation", { name: "Pagination: Configured schedules" }),
      ).getByRole("button", {
        name: "Next",
      }),
    );
    expect(screen.getByRole("button", { name: /^Task 29/ })).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.schedules.search }), {
      target: { value: "Task 0" },
    });
    expect(screen.getByRole("button", { name: /^Task 0/ })).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.schedules.search }), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Status" }), {
      target: { value: "paused" },
    });
    expect(screen.queryByRole("button", { name: /^Task 0/ })).toBeNull();
    fireEvent.change(screen.getByRole("combobox", { name: "Trigger type" }), {
      target: { value: "webhook" },
    });
    expect(screen.getAllByRole("button", { name: /^Task / })).toHaveLength(5);
    const activity = within(screen.getByRole("region", { name: "Schedule activity" }));
    await activity.findByRole("link", { name: "Open run · run-0" });
    expect(activity.getAllByRole("link")).toHaveLength(25);
    fireEvent.click(activity.getByRole("button", { name: "Next" }));
    expect(activity.getByRole("link", { name: "Open run · run-29" })).toBeTruthy();
    fireEvent.change(activity.getByRole("searchbox"), { target: { value: "run-0" } });
    expect(activity.getAllByRole("link")).toHaveLength(1);
    fireEvent.change(activity.getByRole("combobox", { name: "Activity status" }), {
      target: { value: "failed" },
    });
    expect(activity.getByText(messages.schedules.noEventMatches)).toBeTruthy();
  });

  it("distinguishes failed activity reads from an empty history and retries", async () => {
    setup([{ id: "one", name: "One", status: "active", triggerType: "schedule" }]);
    let reads = 0;
    server.use(
      http.get("*/api/v1/routines/one/events", () =>
        ++reads === 1
          ? HttpResponse.json({ detail: "Activity unavailable" }, { status: 503 })
          : HttpResponse.json({ items: [] }),
      ),
    );
    render(wrap(<SchedulesScreen />));
    expect(await screen.findByText("Activity unavailable")).toBeTruthy();
    expect(screen.queryByText(messages.schedules.noHistory)).toBeNull();
    fireEvent.click(
      within(screen.getByRole("region", { name: "Schedule activity" })).getByRole("button", {
        name: "Try again",
      }),
    );
    expect(await screen.findByText(messages.schedules.noHistory)).toBeTruthy();
    expect(
      within(screen.getByRole("region", { name: "Schedule activity" })).queryByRole("searchbox"),
    ).toBeNull();
    expect(screen.queryByText("Activity unavailable")).toBeNull();
  });

  it("keeps the selected schedule's activity when an earlier read finishes late", async () => {
    setup([
      { id: "one", name: "One", status: "active" },
      { id: "two", name: "Two", status: "active" },
    ]);
    let release!: () => void;
    let previousSignal: AbortSignal | undefined;
    let started!: () => void;
    const requested = new Promise<void>((resolve) => {
      started = resolve;
    });
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get("*/api/v1/routines/one/events", async ({ request }) => {
        previousSignal = request.signal;
        started();
        await pending;
        return HttpResponse.json({ items: [{ id: "old", runId: "old-run", status: "started" }] });
      }),
      http.get("*/api/v1/routines/two/events", () =>
        HttpResponse.json({ items: [{ id: "new", runId: "new-run", status: "started" }] }),
      ),
    );
    render(wrap(<SchedulesScreen />));
    await requested;
    fireEvent.click(await screen.findByRole("button", { name: /^Two/ }));
    await screen.findByRole("link", { name: "Open run · new-run" });
    expect(previousSignal?.aborted).toBe(true);
    release();
    await waitFor(() =>
      expect(screen.queryByRole("link", { name: "Open run · old-run" })).toBeNull(),
    );
    expect(screen.getByRole("heading", { name: "Activity · Two" })).toBeTruthy();
  });

  it("uses the existing manual-run endpoint and links its saved run", async () => {
    setup([{ id: "one", name: "One", status: "active", triggerType: "schedule" }]);
    const writes: string[] = [];
    server.use(
      http.post("*/api/v1/routines/one:run", async ({ request }) => {
        writes.push(new URL(request.url).pathname);
        return HttpResponse.json({ runId: "saved-run" }, { status: 202 });
      }),
    );
    render(wrap(<SchedulesScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Run now" }));
    expect(screen.getByRole("button", { name: "Create" })).toBeTruthy();
    expect((await screen.findByRole("link", { name: "Open run" })).getAttribute("href")).toBe(
      "/runs/saved-run",
    );
    expect(writes).toEqual(["/api/v1/routines/one:run"]);
    expect(await screen.findByText(messages.schedules.runRequested)).toBeTruthy();
  });

  it("requires an explicit named agent and retains a failed creation for retry", async () => {
    setup();
    let attempts = 0;
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/v1/routines", async ({ request }) => {
        bodies.push(await request.json());
        return ++attempts === 1
          ? HttpResponse.json({ detail: "Save unavailable" }, { status: 503 })
          : HttpResponse.json(
              {
                id: "created",
                webhook: {
                  webhookSecret: "test-signing-secret",
                  webhookUrl: "/api/v1/hooks/routines/created",
                },
              },
              { status: 201 },
            );
      }),
    );
    render(wrap(<SchedulesScreen />));
    await screen.findByText(messages.schedules.empty);
    expect((screen.getByRole("button", { name: "Create" }) as HTMLButtonElement).disabled).toBe(
      true,
    );
    fireEvent.change(screen.getByLabelText("Name", { exact: true }), {
      target: { value: "  Daily task  " },
    });
    fireEvent.change(screen.getByLabelText("Instructions", { exact: true }), {
      target: { value: "Summarise today's activity" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Agent: Choose existing" }));
    await screen.findByText("Workspace assistant");
    expect(within(screen.getByRole("dialog")).getAllByRole("listitem")).toHaveLength(1);
    fireEvent.click(within(screen.getByRole("dialog")).getByText("Workspace assistant"));
    expect(screen.getByRole("button", { name: "Agent: Workspace assistant" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Trigger", { selector: "#schedule-kind" }), {
      target: { value: "webhook" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await screen.findByText("Save unavailable");
    expect((screen.getByLabelText("Name", { exact: true }) as HTMLInputElement).value).toBe(
      "  Daily task  ",
    );
    expect(
      (screen.getByLabelText("Instructions", { exact: true }) as HTMLTextAreaElement).value,
    ).toBe("Summarise today's activity");
    fireEvent.click(screen.getByRole("button", { name: "Refresh schedules" }));
    await screen.findByText(messages.schedules.refreshed);
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await screen.findByText("test-signing-secret");
    expect(bodies).toEqual(
      Array(2).fill({
        name: "Daily task",
        agentId: "agent",
        instructions: "Summarise today's activity",
        concurrencyPolicy: "skip",
        trigger: { type: "webhook", executeModel: true },
        delivery: [{ type: "conversation" }],
      }),
    );
  });

  it("does not request or offer schedule controls without permission", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["chat:use"] })),
      http.get("*/api/v1/routines", () => {
        reads++;
        return HttpResponse.json({ items: [] });
      }),
    );
    render(wrap(<SchedulesScreen />));
    expect(await screen.findByText(messages.schedules.denied)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Create" })).toBeNull();
    expect(reads).toBe(0);
  });

  async function prepareCreate(title = "New schedule", webhook = false) {
    fireEvent.change(await screen.findByLabelText("Name", { exact: true }), {
      target: { value: title },
    });
    fireEvent.change(screen.getByLabelText("Instructions", { exact: true }), {
      target: { value: "Saved work instructions" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Agent: Choose existing" }));
    fireEvent.click(
      await within(screen.getByRole("dialog")).findByText("Workspace assistant", { exact: true }),
    );
    if (webhook)
      fireEvent.change(screen.getByLabelText("Trigger", { selector: "#schedule-kind" }), {
        target: { value: "webhook" },
      });
  }

  it("guards same-frame creation and clears only the acknowledged draft", async () => {
    setup();
    const items: object[] = [];
    let writes = 0;
    let finish = () => {};
    const pending = new Promise<void>((resolve) => {
      finish = resolve;
    });
    server.use(
      http.get("*/api/v1/routines", () => HttpResponse.json({ items })),
      http.post("*/api/v1/routines", async () => {
        writes += 1;
        await pending;
        const created = { id: "created", name: "New schedule", status: "active" };
        items.push(created);
        return HttpResponse.json(created);
      }),
    );
    render(wrap(<SchedulesScreen />));
    await prepareCreate();
    const button = screen.getByRole("button", { name: "Create" });
    act(() => {
      fireEvent.click(button);
      fireEvent.click(button);
    });
    await waitFor(() => expect(writes).toBe(1));
    expect((screen.getByLabelText("Name", { exact: true }) as HTMLInputElement).value).toBe(
      "New schedule",
    );
    expect(screen.getByRole("button", { name: "Creating…" }).matches(":disabled")).toBe(true);
    finish();
    await screen.findByText(messages.schedules.created);
    expect((screen.getByLabelText("Name", { exact: true }) as HTMLInputElement).value).toBe("");
    expect(
      (screen.getByLabelText("Instructions", { exact: true }) as HTMLTextAreaElement).value,
    ).toBe("");
    expect(writes).toBe(1);
  });

  it.each([
    {
      path: "run",
      button: "Run now",
      status: "active",
      next: "active",
      notice: messages.schedules.runRequested,
      pendingLabel: "Requesting a run for One…",
    },
    {
      path: "pause",
      button: "Pause",
      status: "active",
      next: "paused",
      notice: messages.schedules.paused,
      pendingLabel: "Pausing One…",
    },
    {
      path: "resume",
      button: "Enable",
      status: "paused",
      next: "active",
      notice: messages.schedules.enabled,
      pendingLabel: "Enabling One…",
    },
  ])(
    "guards duplicate $path and names its actual target in progress",
    async ({ path, button, status, next, notice, pendingLabel }) => {
      const item = { id: "one", name: "One", status };
      setup([item]);
      let writes = 0;
      let finish = () => {};
      const pending = new Promise<void>((resolve) => {
        finish = resolve;
      });
      server.use(
        http.post(`*/api/v1/routines/one:${path}`, async () => {
          writes += 1;
          await pending;
          item.status = next;
          return HttpResponse.json(path === "run" ? { runId: "saved-run" } : item);
        }),
      );
      render(wrap(<SchedulesScreen />));
      const control = await screen.findByRole("button", { name: button });
      act(() => {
        fireEvent.click(control);
        fireEvent.click(control);
      });
      await screen.findByText(pendingLabel);
      await waitFor(() => expect(writes).toBe(1));
      finish();
      await screen.findByText(notice);
      expect(writes).toBe(1);
      expect(screen.queryByText(messages.schedules.unconfirmedRecovery)).toBeNull();
    },
  );

  it.each(["create", "run", "pause", "resume"])(
    "holds an incomplete %s receipt until read-only recovery without inventing success",
    async (operation) => {
      setup([{ id: "one", name: "One", status: operation === "resume" ? "paused" : "active" }]);
      let writes = 0;
      const endpoint =
        operation === "create" ? "*/api/v1/routines" : `*/api/v1/routines/one:${operation}`;
      server.use(
        http.post(endpoint, () => {
          writes += 1;
          return HttpResponse.json({});
        }),
      );
      render(wrap(<SchedulesScreen />));
      if (operation === "create") await prepareCreate();
      const label =
        operation === "create"
          ? "Create"
          : operation === "run"
            ? "Run now"
            : operation === "pause"
              ? "Pause"
              : "Enable";
      fireEvent.click(await screen.findByRole("button", { name: label }));
      await screen.findByText(messages.schedules.unconfirmedRecovery);
      expect(screen.queryByText(messages.schedules.created)).toBeNull();
      expect(screen.queryByText(messages.schedules.runRequested)).toBeNull();
      expect(screen.queryByText(messages.schedules.paused)).toBeNull();
      expect(screen.queryByText(messages.schedules.enabled)).toBeNull();
      expect(screen.getByRole("button", { name: label }).matches(":disabled")).toBe(true);
      fireEvent.click(screen.getByRole("button", { name: "Refresh schedules" }));
      await screen.findByText(messages.schedules.refreshed);
      expect(writes).toBe(1);
      expect(screen.queryByText(messages.schedules.unconfirmedRecovery)).toBeNull();
    },
  );

  it("preserves a confirmed run link when the following metadata refresh fails", async () => {
    const items = [{ id: "one", name: "One", status: "active" }];
    setup(items);
    let failRead = false;
    let writes = 0;
    server.use(
      http.get("*/api/v1/routines", () =>
        failRead
          ? HttpResponse.json({ detail: "Saved list unavailable" }, { status: 503 })
          : HttpResponse.json({ items }),
      ),
      http.post("*/api/v1/routines/one:run", () => {
        writes += 1;
        failRead = true;
        return HttpResponse.json({ runId: "saved-run" });
      }),
    );
    render(wrap(<SchedulesScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Run now" }));
    await screen.findByText(messages.schedules.acceptedRecovery);
    expect(screen.getByRole("link", { name: "Open run" }).getAttribute("href")).toBe(
      "/runs/saved-run",
    );
    expect(screen.getByText("Saved list unavailable")).toBeTruthy();
    failRead = false;
    fireEvent.click(screen.getByRole("button", { name: "Refresh schedules" }));
    await screen.findByText(messages.schedules.refreshed);
    expect(writes).toBe(1);
    expect(screen.getByRole("link", { name: "Open run" })).toBeTruthy();
  });

  it("keeps recovery held when activity cannot be read even if the schedule list refresh succeeds", async () => {
    setup([{ id: "one", name: "One", status: "active" }]);
    let failed = false;
    let writes = 0;
    server.use(
      http.get("*/api/v1/routines/one/events", () =>
        failed
          ? HttpResponse.json({ detail: "Activity still unavailable" }, { status: 503 })
          : HttpResponse.json({ items: [] }),
      ),
      http.post("*/api/v1/routines/one:run", () => {
        writes += 1;
        failed = true;
        return HttpResponse.json({});
      }),
    );
    render(wrap(<SchedulesScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Run now" }));
    await screen.findByText(messages.schedules.unconfirmedRecovery);
    fireEvent.click(screen.getByRole("button", { name: "Refresh schedules" }));
    await screen.findByText("Activity still unavailable");
    expect(screen.getByText(messages.schedules.unconfirmedRecovery)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Run now" }).matches(":disabled")).toBe(true);
    failed = false;
    fireEvent.click(screen.getByRole("button", { name: "Refresh schedules" }));
    await screen.findByText(messages.schedules.refreshed);
    expect(writes).toBe(1);
  });

  it.each(["selection", "dismiss"])(
    "names a webhook receipt and clears it on %s",
    async (change) => {
      const items = [{ id: "one", name: "Existing schedule", status: "active" }];
      setup(items);
      server.use(
        http.post("*/api/v1/routines", () => {
          const created = { id: "created", name: "Named webhook", status: "active" };
          items.push(created);
          return HttpResponse.json({
            ...created,
            webhook: {
              webhookSecret: "test-only-signing-secret",
              webhookUrl: "/api/v1/hooks/routines/created",
            },
          });
        }),
      );
      render(wrap(<SchedulesScreen />));
      await prepareCreate("Named webhook", true);
      fireEvent.click(screen.getByRole("button", { name: "Create" }));
      const receipt = within(
        await screen.findByRole("region", { name: "Webhook credentials · Named webhook" }),
      );
      await screen.findByText(messages.schedules.created);
      expect(receipt.getByText("test-only-signing-secret")).toBeTruthy();
      if (change === "selection")
        fireEvent.click(screen.getByRole("button", { name: /^Existing schedule/ }));
      else fireEvent.click(receipt.getByRole("button", { name: "Hide secret" }));
      expect(screen.queryByText("test-only-signing-secret")).toBeNull();
    },
  );

  it("discards a late run receipt after leaving the screen without starting a reload", async () => {
    setup([{ id: "one", name: "One", status: "active" }]);
    let release = (_value: Response) => {};
    const pending = new Promise<Response>((resolve) => {
      release = resolve;
    });
    let transportSignal: AbortSignal | null | undefined;
    const originalFetch = globalThis.fetch;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input) === "/api/v1/routines/one:run") {
        transportSignal = init?.signal;
        return pending;
      }
      return originalFetch(input, init);
    });
    const rendered = render(wrap(<SchedulesScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Run now" }));
    await waitFor(() => expect(transportSignal).toBeDefined());
    rendered.unmount();
    expect(transportSignal?.aborted).toBe(true);
    render(wrap(<SchedulesScreen />));
    await screen.findByRole("button", { name: "Run now" });
    await act(async () => {
      release(HttpResponse.json({ runId: "old-run" }));
      await pending;
    });
    expect(screen.queryByRole("link", { name: "Open run" })).toBeNull();
    expect(screen.queryByText(messages.schedules.runRequested)).toBeNull();
  });

  it("bounds 100,000 schedules and events with independent search/filter resets", async () => {
    setup(
      Array.from({ length: 100_000 }, (_, index) => ({
        id: `task-${index}`,
        name: `Work ${index}`,
        status: index === 99_999 ? "paused" : "active",
        triggerType: "schedule",
      })),
    );
    server.use(
      http.get("*/api/v1/routines/task-0/events", () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, index) => ({
            id: `event-${index}`,
            runId: `run-${index}`,
            status: index === 99_999 ? "failed" : "started",
          })),
        }),
      ),
    );
    render(wrap(<SchedulesScreen />));
    await screen.findByRole("button", { name: /^Work 0/ });
    expect(screen.getAllByRole("button", { name: /^Work / })).toHaveLength(25);
    const listSearch = screen.getByRole("searchbox", { name: messages.schedules.search });
    fireEvent.change(listSearch, { target: { value: "task-99999" } });
    expect(screen.getAllByRole("button", { name: /^Work / })).toHaveLength(1);
    fireEvent.change(screen.getByRole("combobox", { name: "Status" }), {
      target: { value: "active" },
    });
    expect(screen.getByText(messages.schedules.noMatches)).toBeTruthy();
    const listFilters = listSearch.parentElement;
    if (!listFilters) throw new Error("List search needs its existing controls");
    fireEvent.click(within(listFilters).getByRole("button", { name: "Clear filters" }));
    expect(screen.getAllByRole("button", { name: /^Work / })).toHaveLength(25);
    const activity = within(screen.getByRole("region", { name: "Schedule activity" }));
    await activity.findByRole("link", { name: "Open run · run-0" });
    expect(activity.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.change(activity.getByRole("searchbox"), { target: { value: "run-99999" } });
    expect(activity.getAllByRole("listitem")).toHaveLength(1);
    fireEvent.change(activity.getByRole("combobox", { name: "Activity status" }), {
      target: { value: "started" },
    });
    expect(activity.getByText(messages.schedules.noEventMatches)).toBeTruthy();
    fireEvent.click(activity.getByRole("button", { name: "Clear filters" }));
    expect(activity.getAllByRole("listitem")).toHaveLength(25);
  });

  it("refreshes the original unconfirmed target after the person inspects another schedule", async () => {
    setup([
      { id: "one", name: "One", status: "active" },
      { id: "two", name: "Two", status: "active" },
    ]);
    let writes = 0;
    const reads: string[] = [];
    server.use(
      http.post("*/api/v1/routines/one:run", () => {
        writes += 1;
        return HttpResponse.json({});
      }),
      http.get("*/api/v1/routines/:id/events", ({ params }) => {
        reads.push(String(params.id));
        return HttpResponse.json({ items: [] });
      }),
    );
    render(wrap(<SchedulesScreen />));
    const one = (await screen.findByRole("button", { name: /^One/ })).closest("li");
    if (!one) throw new Error("Schedule needs its existing row");
    fireEvent.click(within(one).getByRole("button", { name: "Run now" }));
    await screen.findByText(messages.schedules.unconfirmedRecovery);
    fireEvent.click(screen.getByRole("button", { name: /^Two/ }));
    await screen.findByRole("heading", { name: "Activity · Two" });
    fireEvent.click(screen.getByRole("button", { name: "Refresh schedules" }));
    await screen.findByText(messages.schedules.refreshed);
    expect(screen.getByRole("heading", { name: "Activity · One" })).toBeTruthy();
    expect(reads[reads.length - 1]).toBe("one");
    expect(writes).toBe(1);
  });

  it("does not substitute another schedule when the original request target disappears", async () => {
    const items = [{ id: "one", name: "One", status: "active" }];
    setup(items);
    let writes = 0;
    server.use(
      http.post("*/api/v1/routines/one:run", () => {
        writes += 1;
        items.length = 0;
        return HttpResponse.json({ runId: "saved-run" });
      }),
    );
    render(wrap(<SchedulesScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Run now" }));
    await screen.findByText(messages.schedules.targetUnavailable);
    expect(screen.getByText(messages.schedules.acceptedRecovery)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open run" }).getAttribute("href")).toBe(
      "/runs/saved-run",
    );
    fireEvent.click(screen.getByRole("button", { name: "Refresh schedules" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Refresh schedules" }).matches(":disabled")).toBe(
        false,
      ),
    );
    expect(screen.getByText(messages.schedules.targetUnavailable)).toBeTruthy();
    expect(screen.queryByText(messages.schedules.refreshed)).toBeNull();
    expect(writes).toBe(1);
  });

  it("can retry an initial identity read failure without requiring already-loaded permission", async () => {
    setup();
    let identityReads = 0;
    let catalogueReads = 0;
    server.use(
      http.get("*/api/v1/auth/session", () =>
        ++identityReads === 1
          ? HttpResponse.json({ detail: "Identity temporarily unavailable" }, { status: 503 })
          : HttpResponse.json({ permissions: ["routines:create"] }),
      ),
      http.get("*/api/v1/routines", () => {
        catalogueReads += 1;
        return HttpResponse.json({ items: [] });
      }),
    );
    render(wrap(<SchedulesScreen />));
    await screen.findByRole("heading", { name: messages.shell.sessionProblemTitle });
    expect(catalogueReads).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("Identity temporarily unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText(messages.schedules.empty);
    expect(identityReads).toBe(2);
    expect(catalogueReads).toBe(1);
    expect(screen.queryByText("Identity temporarily unavailable")).toBeNull();
  });

  it("holds creation during an initial catalogue read failure and restores it through read-only retry", async () => {
    setup();
    let failed = true;
    let writes = 0;
    server.use(
      http.get("*/api/v1/routines", () =>
        failed
          ? HttpResponse.json({ detail: "Schedule list unavailable" }, { status: 503 })
          : HttpResponse.json({ items: [] }),
      ),
      http.post("*/api/v1/routines", () => {
        writes += 1;
        return HttpResponse.json({ id: "unexpected" });
      }),
    );
    render(wrap(<SchedulesScreen />));
    await screen.findByText("Schedule list unavailable");
    expect(screen.getByLabelText("Name", { exact: true }).matches(":disabled")).toBe(true);
    const form = screen.getByLabelText("Name", { exact: true }).closest("form");
    if (!form) throw new Error("Creation needs its existing form");
    fireEvent.submit(form);
    expect(writes).toBe(0);
    failed = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText(messages.schedules.refreshed);
    expect(screen.getByLabelText("Name", { exact: true }).matches(":disabled")).toBe(false);
    expect(writes).toBe(0);
  });
});
