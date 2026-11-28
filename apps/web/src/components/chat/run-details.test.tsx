import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { delay, HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { RunDetails } from "@/components/chat/run-details";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("Run details", () => {
  afterEach(() => cleanup());

  it("shows who answered, how long it took and the tools the run called", async () => {
    server.use(
      http.get("*/api/v1/runs/run-1", () =>
        HttpResponse.json({
          id: "run-1",
          status: "completed",
          agentId: "agent-1",
          answeredModel: "reasoning",
          startedAt: "2026-11-16T10:00:00Z",
          endedAt: "2026-11-16T10:00:31Z",
        }),
      ),
      http.get("*/api/v1/runs/run-1/steps", () =>
        HttpResponse.json({ items: [{ id: "s1", kind: "model" }] }),
      ),
      http.get("*/api/v1/runs/run-1/tool-calls", () =>
        HttpResponse.json({
          items: [{ id: "t1", qualifiedName: "documents.judge", status: "failed" }],
        }),
      ),
    );
    render(
      wrap(<RunDetails agents={[{ id: "agent-1", name: "Assistant" }]} runId="run-1" settled />),
    );
    await waitFor(() => expect(screen.getByText("Assistant")).toBeTruthy());
    expect(screen.getByText("reasoning")).toBeTruthy();
    expect(screen.getByText("31s")).toBeTruthy();
    expect(screen.getByText("completed").className).toContain("tone-success");
    expect(screen.getByText("documents.judge")).toBeTruthy();
    expect(within(screen.getByRole("list")).getByText("failed").className).toContain("tone-danger");
    expect(screen.getByRole("link", { name: "View trace" }).getAttribute("href")).toBe(
      "/runs/run-1",
    );
  });

  it("says so when the run called no tools", async () => {
    server.use(
      http.get("*/api/v1/runs/run-2", () => HttpResponse.json({ id: "run-2", status: "running" })),
      http.get("*/api/v1/runs/run-2/steps", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/runs/run-2/tool-calls", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<RunDetails agents={[]} runId="run-2" settled={false} />));
    await waitFor(() => expect(screen.getByText(messages.chat.runNoTools)).toBeTruthy());
    expect(screen.getByText("running").className).toContain("tone-info");
  });

  it("offers another try when the run cannot be read", async () => {
    server.use(
      http.get("*/api/v1/runs/run-3", () => HttpResponse.json({ detail: "gone" }, { status: 500 })),
      http.get("*/api/v1/runs/run-3/steps", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/runs/run-3/tool-calls", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<RunDetails agents={[]} runId="run-3" settled />));
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
  it("keeps run facts when tool reads fail and recovers without reporting a false empty list", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/runs/partial", () =>
        HttpResponse.json({ id: "partial", status: "completed", answeredModel: "Actual model" }),
      ),
      http.get("*/api/v1/runs/partial/steps", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/runs/partial/tool-calls", () =>
        ++reads === 1
          ? HttpResponse.json({ detail: "Activity unavailable" }, { status: 503 })
          : HttpResponse.json({ items: [] }),
      ),
    );
    render(wrap(<RunDetails runId="partial" settled agents={[]} />));
    expect(await screen.findByText("Actual model")).toBeTruthy();
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText(messages.chat.runNoTools)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(messages.chat.runNoTools)).toBeTruthy();
    expect(screen.getByText("Actual model")).toBeTruthy();
  });

  it("bounds the tool list and resets its page when searching or filtering", async () => {
    server.use(
      http.get("*/api/v1/runs/many", () => HttpResponse.json({ id: "many", status: "completed" })),
      http.get("*/api/v1/runs/many/steps", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/runs/many/tool-calls", () =>
        HttpResponse.json({
          items: Array.from({ length: 30 }, (_, i) => ({
            id: `call-${i}`,
            qualifiedName: `tools.operation_${i}`,
            status: i === 29 ? "failed" : "succeeded",
          })),
        }),
      ),
    );
    render(wrap(<RunDetails runId="many" settled agents={[]} />));
    await screen.findByText("tools.operation_0");
    expect(screen.queryByText("tools.operation_29")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("tools.operation_29")).toBeTruthy();
    const filters = screen.getByText(messages.chat.runToolFilters).closest("details");
    if (!filters) throw new Error("Tool filters were not rendered");
    filters.open = true;
    fireEvent(filters, new Event("toggle"));
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "operation_0" } });
    expect(screen.getByText("tools.operation_0")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "failed" } });
    expect(screen.getByText("tools.operation_29")).toBeTruthy();
    expect(screen.queryByText("tools.operation_0")).toBeNull();
  });

  it("ignores delayed activity after switching to another run", async () => {
    server.use(
      http.get("*/api/v1/runs/old", () =>
        HttpResponse.json({ id: "old", answeredModel: "Older model", status: "completed" }),
      ),
      http.get("*/api/v1/runs/old/steps", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/runs/old/tool-calls", async () => {
        await delay(200);
        return HttpResponse.json({
          items: [{ id: "old-call", qualifiedName: "old.operation", status: "succeeded" }],
        });
      }),
      http.get("*/api/v1/runs/new", () =>
        HttpResponse.json({ id: "new", answeredModel: "Current model", status: "completed" }),
      ),
      http.get("*/api/v1/runs/new/steps", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/runs/new/tool-calls", () => HttpResponse.json({ items: [] })),
    );
    const view = render(wrap(<RunDetails runId="old" settled agents={[]} />));
    await screen.findByText("Older model");
    view.rerender(wrap(<RunDetails runId="new" settled agents={[]} />));
    await screen.findByText("Current model");
    await delay(240);
    expect(screen.queryByText("old.operation")).toBeNull();
    expect(screen.queryByText("Older model")).toBeNull();
    expect(screen.getByRole("link", { name: "View trace" }).getAttribute("href")).toBe("/runs/new");
  });
});
