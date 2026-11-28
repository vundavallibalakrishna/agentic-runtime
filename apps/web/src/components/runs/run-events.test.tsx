import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/en.json";
import { server } from "@/test/server";
import { RunEvents } from "./run-events";

const row = (seq: number, type = "run.status") => ({
  seq,
  type,
  ts: "2026-11-21T10:00:00Z",
  data: { status: "completed" },
});
const frame = (value: unknown) => `data: ${JSON.stringify(value)}\n\n`;
function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <RunEvents runId="parent" />
    </NextIntlClientProvider>,
  );
}
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
describe("bounded run event reader", () => {
  it("reads real SSE framing with cursor boundaries, ignores duplicates, filters locally and resets page size", async () => {
    const cursors: string[] = [];
    server.use(
      http.get("*/api/v1/runs/parent/events", ({ request }) => {
        const cursor = Number(request.headers.get("Last-Event-ID") ?? 0);
        cursors.push(String(cursor));
        const rows = Array.from({ length: 100 - cursor }, (_, index) =>
          row(cursor + index + 1, (cursor + index) % 2 ? "tool.completed" : "run.status"),
        );
        return new HttpResponse(
          `: ping\n\n${cursor ? frame(row(cursor)) : ""}${rows.map(frame).join("")}`,
          { headers: { "Content-Type": "text/event-stream" } },
        );
      }),
    );
    show();
    await screen.findByText("Sequence 25 · run.status");
    expect(screen.queryByText(/Sequence 26 ·/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("Sequence 26 · tool.completed");
    await screen.findByText("Sequence 50 · tool.completed");
    expect(screen.queryByText(/Sequence 25 ·/)).toBeNull();
    expect(cursors).toEqual(["0", "25"]);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "tool.completed" } });
    expect(screen.queryByText("Sequence 27 · run.status")).toBeNull();
    fireEvent.change(screen.getByLabelText(messages.runs.eventType), {
      target: { value: "run.status" },
    });
    expect(screen.getByText(messages.runs.eventsNoMatches)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Rows per page"), { target: { value: "50" } });
    await screen.findByText("Sequence 1 · run.status");
    await screen.findByText("Sequence 50 · tool.completed");
    expect(screen.getByText("Page 1")).toBeTruthy();
    expect(cursors).toEqual(["0", "25", "0"]);
    const details = screen
      .getByText("Sequence 1 · run.status")
      .closest("details") as HTMLDetailsElement;
    details.open = true;
    fireEvent(details, new Event("toggle"));
    expect(screen.getByRole("region", { name: messages.runs.eventsPayload }).textContent).toContain(
      '"status": "completed"',
    );
  });
  it("shows an actual empty stream and no invented next page", async () => {
    server.use(
      http.get(
        "*/api/v1/runs/parent/events",
        () => new HttpResponse(": ping\n\n", { headers: { "Content-Type": "text/event-stream" } }),
      ),
    );
    show();
    await screen.findByText(messages.runs.noEvents);
    expect(screen.getByRole("button", { name: "Next" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByText(messages.runs.eventsEnd)).toBeTruthy();
  });
  it("retains a partial page on malformed data and retries the same cursor", async () => {
    let attempt = 0;
    server.use(
      http.get(
        "*/api/v1/runs/parent/events",
        () =>
          new HttpResponse(
            ++attempt === 1 ? frame(row(1)) + frame("invalid") : frame(row(1)) + frame(row(2)),
            { headers: { "Content-Type": "text/event-stream" } },
          ),
      ),
    );
    show();
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("Sequence 1 · run.status")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Next" }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: messages.runs.eventsRetry }));
    await screen.findByText("Sequence 2 · run.status");
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(screen.getAllByText("Sequence 1 · run.status")).toHaveLength(1);
  });
  it("reports HTTP failures without retrying or claiming an empty stream", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v1/runs/parent/events", () => {
        calls++;
        return new HttpResponse(null, { status: 403 });
      }),
    );
    show();
    await screen.findByRole("alert");
    expect(calls).toBe(1);
    expect(screen.queryByText(messages.runs.noEvents)).toBeNull();
    expect(screen.queryByText(messages.runs.eventsEnd)).toBeNull();
  });
  it("stops only the reader, keeps received events, and aborts on unmount", async () => {
    const signals: AbortSignal[] = [];
    const fetcher = globalThis.fetch;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (input instanceof Request) signals.push(input.signal);
      return fetcher(input, init);
    });
    server.use(
      http.get("*/api/v1/runs/parent/events", () => {
        return new HttpResponse(
          new ReadableStream({
            start(controller) {
              controller.enqueue(new TextEncoder().encode(frame(row(1))));
            },
          }),
          { headers: { "Content-Type": "text/event-stream" } },
        );
      }),
    );
    const view = show();
    await screen.findByText("Sequence 1 · run.status");
    fireEvent.click(screen.getByRole("button", { name: messages.runs.eventsStop }));
    expect(screen.getByText(messages.runs.eventsStopped)).toBeTruthy();
    expect(screen.getByText("Sequence 1 · run.status")).toBeTruthy();
    await waitFor(() => expect(signals[0]?.aborted).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: messages.runs.eventsRetry }));
    await waitFor(() => expect(signals).toHaveLength(2));
    view.unmount();
    await waitFor(() => expect(signals[1]?.aborted).toBe(true));
  });
});
