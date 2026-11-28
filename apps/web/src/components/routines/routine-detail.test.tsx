import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RoutineDetail } from "@/components/routines/routine-detail";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/routines/routine",
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

function view(id = "routine") {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <RoutineDetail routineId={id} />
    </NextIntlClientProvider>
  );
}

beforeEach(() => {
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ permissions: ["routines:create"] }),
    ),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/routines/:id", ({ params }) =>
      HttpResponse.json({
        id: params.id,
        name: `Routine ${params.id}`,
        status: "active",
        instructions: "Saved instructions",
        triggerSummary: "Saved schedule",
        nextFires: ["2026-11-23T09:00:00Z"],
      }),
    ),
    http.get("*/api/v1/routines/:id/events", () => HttpResponse.json({ items: [] })),
  );
});

describe("routine detail activity", () => {
  it("bounds 100,000 events and filters the complete loaded list before paging", async () => {
    server.use(
      http.get("*/api/v1/routines/routine/events", () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, index) => ({
            id: `event-${index}`,
            source: `Source ${index}`,
            status: index === 99_999 ? "failed" : "started",
            runId: `run-${index}`,
          })),
        }),
      ),
    );
    render(view());
    const region = within(await screen.findByRole("region", { name: "Events" }));
    expect(region.getAllByRole("listitem")).toHaveLength(25);
    expect(region.getByText("1–25 of 100,000")).toBeTruthy();
    fireEvent.click(region.getByRole("button", { name: "Next" }));
    expect(region.getByText("Source 25", { exact: true })).toBeTruthy();
    const search = region.getByRole("searchbox", { name: messages.schedules.eventSearch });
    fireEvent.change(search, { target: { value: "run-99999" } });
    expect(region.getAllByRole("listitem")).toHaveLength(1);
    expect(region.getByRole("link", { name: "Open run" }).getAttribute("href")).toBe(
      "/runs/run-99999",
    );
    expect(region.getByText("Source 99999")).toBeTruthy();
    fireEvent.change(region.getByRole("combobox", { name: messages.schedules.eventStatus }), {
      target: { value: "started" },
    });
    expect(region.getByText(messages.schedules.noEventMatches)).toBeTruthy();
    expect(region.queryAllByRole("listitem")).toHaveLength(0);
    fireEvent.click(region.getByRole("button", { name: "Clear filters" }));
    expect(region.getByText("Source 0", { exact: true })).toBeTruthy();
    expect(region.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.change(region.getByRole("combobox", { name: messages.schedules.eventStatus }), {
      target: { value: "failed" },
    });
    expect(region.getAllByRole("listitem")).toHaveLength(1);
    expect(region.getByText("Source 99999")).toBeTruthy();
  });

  it("keeps the empty state free of inactive search controls and labels upcoming instants", async () => {
    render(view());
    await screen.findByText(messages.routines.noEvents);
    const events = within(screen.getByRole("region", { name: "Events" }));
    expect(events.queryByRole("searchbox")).toBeNull();
    expect(events.queryByRole("navigation")).toBeNull();
    const upcoming = screen.getByText("Upcoming runs").nextElementSibling;
    const time = upcoming?.querySelector("time");
    expect(time?.getAttribute("datetime")).toBe("2026-11-23T09:00:00Z");
    const zone = new Intl.DateTimeFormat("en", { timeZoneName: "short" })
      .formatToParts(new Date("2026-11-23T09:00:00Z"))
      .find((part) => part.type === "timeZoneName")?.value;
    expect(time?.textContent).toContain(zone);
  });

  it("prevents same-frame duplicate actions and clears secrets and filters on navigation", async () => {
    let writes = 0;
    let finish = () => {};
    const pending = new Promise<void>((resolve) => {
      finish = resolve;
    });
    server.use(
      http.get("*/api/v1/routines/:id/events", ({ params }) =>
        HttpResponse.json({
          items: [{ id: `event-${params.id}`, source: `Source ${params.id}`, status: "started" }],
        }),
      ),
      http.get("*/api/v1/routines/routine", () =>
        HttpResponse.json({
          id: "routine",
          name: "First routine",
          status: "active",
          webhookUrl: "https://example.test/hook",
        }),
      ),
      http.post("*/api/v1/routines/routine:rotate-webhook-secret", async () => {
        writes += 1;
        await pending;
        return HttpResponse.json({ webhookSecret: "test-only-returned-secret" });
      }),
    );
    const rendered = render(view());
    const rotate = await screen.findByRole("button", { name: "Rotate webhook secret" });
    fireEvent.change(screen.getByRole("searchbox", { name: messages.schedules.eventSearch }), {
      target: { value: "Source routine" },
    });
    act(() => {
      fireEvent.click(rotate);
      fireEvent.click(rotate);
    });
    await waitFor(() => expect(writes).toBe(1));
    finish();
    await screen.findByTestId("webhook-secret");
    rendered.rerender(view("other"));
    await screen.findByRole("heading", { name: "Routine other" });
    expect(screen.queryByTestId("webhook-secret")).toBeNull();
    expect(
      screen.getByRole("searchbox", { name: messages.schedules.eventSearch }).getAttribute("value"),
    ).toBe("");
    expect(screen.getByText("Source other", { exact: true })).toBeTruthy();
    expect(writes).toBe(1);
  });

  it("does not let a late action receipt reload another routine", async () => {
    let finish = () => {};
    let started = false;
    let transportSignal: AbortSignal | undefined;
    const pending = new Promise<void>((resolve) => {
      finish = resolve;
    });
    server.use(
      http.post("*/api/v1/routines/routine:run", async ({ request }) => {
        transportSignal = request.signal;
        started = true;
        await pending;
        return HttpResponse.json({ runId: "old-run" });
      }),
    );
    const rendered = render(view());
    fireEvent.click(await screen.findByRole("button", { name: "Run now" }));
    await waitFor(() => expect(started).toBe(true));
    rendered.rerender(view("other"));
    await screen.findByRole("heading", { name: "Routine other" });
    expect(transportSignal?.aborted).toBe(true);
    finish();
    await act(async () => {
      await pending;
    });
    expect(screen.queryByRole("link", { name: "Open run" })).toBeNull();
    expect(screen.queryByText(messages.routines.ran)).toBeNull();
    expect(screen.getByRole("heading", { name: "Routine other" })).toBeTruthy();
  });
});
