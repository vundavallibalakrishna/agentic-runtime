import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EvalRunHistory } from "@/components/evals/run-history";
import { formatDateTime } from "@/lib/format";
import { clearCachedSession } from "@/lib/session";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const run = {
  id: "run-1",
  suiteId: "suite",
  agentId: "agent",
  status: "completed",
  createdAt: "2026-11-10T12:00:00Z",
  summary: { passRate: 0.99995 },
};
const result = {
  case: { id: "case", name: "Greeting" },
  passed: true,
  outputText: "<script>recorded, not executable</script>",
  runId: "case-run",
};
const suites = new Map([["suite", "Release checks"]]);
function View({ agentId }: { agentId?: string }) {
  const [selected, select] = useState("");
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <EvalRunHistory
        agentId={agentId}
        selectedId={selected}
        onSelect={select}
        suiteNames={suites}
      />
    </NextIntlClientProvider>
  );
}
function show(agentId?: string) {
  return render(<View agentId={agentId} />);
}
async function open() {
  fireEvent.click(await screen.findByRole("button", { name: "View results for run run-1" }));
  const dialog = within(await screen.findByRole("dialog", { name: messages.evals.results }));
  await dialog.findByText("Run reference · run-1");
  return dialog;
}
beforeEach(() => {
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["evals:manage"] })),
    http.get("*/api/v1/eval-runs", () => HttpResponse.json({ items: [run] })),
    http.get("*/api/v1/eval-runs/run-1", () => HttpResponse.json(run)),
    http.get("*/api/v1/eval-runs/run-1/results", () => HttpResponse.json({ items: [result] })),
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});
describe("saved evaluation runs", () => {
  it("renders the actual instant with a zone and full run identity", async () => {
    show();
    const time = await screen.findByText(formatDateTime(run.createdAt, "en"));
    expect(time.getAttribute("datetime")).toBe(run.createdAt);
    expect(screen.getByText("Reference · run-1").getAttribute("title")).toBe(run.id);
  });
  it("does not read runs for a run-only role or infer an empty history", async () => {
    const read = vi.fn(() => HttpResponse.json({ items: [run] }));
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["evals:run"] })),
      http.get("*/api/v1/eval-runs", read),
    );
    show();
    await screen.findByText(messages.evals.denied);
    expect(read).not.toHaveBeenCalled();
    expect(screen.queryByText(messages.evals.noRuns)).toBeNull();
  });
  it.each([
    {},
    { items: [{ ...run, status: undefined }] },
    { items: [run, run] },
    { items: [{ ...run, createdAt: "2026-11-10T12:00:00" }] },
  ])("rejects incomplete or ambiguous history metadata %j", async (value) => {
    server.use(http.get("*/api/v1/eval-runs", () => HttpResponse.json(value)));
    show();
    await screen.findByText(messages.evals.runMetadata);
    expect(screen.queryByText(messages.evals.noRuns)).toBeNull();
    expect(screen.queryByRole("button", { name: /View results for run/ })).toBeNull();
  });
  it("bounds 100,000 loaded runs, combines filters, searches the full set and resets focus/page", async () => {
    server.use(
      http.get("*/api/v1/eval-runs", () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, i) => ({
            ...run,
            id: `run-${i}`,
            status: i === 99999 ? "failed" : "completed",
          })),
        }),
      ),
    );
    show();
    await screen.findByRole("button", { name: "View results for run run-0" });
    expect(screen.getAllByRole("button", { name: /View results for run/ })).toHaveLength(25);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("button", { name: "View results for run run-25" })).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: messages.evals.status }), {
      target: { value: "failed" },
    });
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "99999" } });
    expect(screen.getByRole("button", { name: "View results for run run-99999" })).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "no match" } });
    expect(screen.getByText(messages.evals.noRunMatches)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: messages.evals.clearFilters }));
    expect(document.activeElement).toBe(screen.getByRole("searchbox"));
    expect(screen.getByRole("button", { name: "View results for run run-0" })).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: "Rows per page" }), {
      target: { value: "100" },
    });
    expect(screen.getAllByRole("button", { name: /View results for run/ })).toHaveLength(100);
  });
  it("retains loaded runs and filters after refresh failure and recovers with a read", async () => {
    show();
    await screen.findByText("Release checks");
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "run-1" } });
    server.use(
      http.get("*/api/v1/eval-runs", () =>
        HttpResponse.json({ detail: "History unavailable" }, { status: 503 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: messages.evals.refresh }));
    await screen.findByText("History unavailable");
    expect(screen.getByText(messages.evals.historyRetained)).toBeTruthy();
    expect(screen.getByRole("button", { name: "View results for run run-1" })).toBeTruthy();
    expect((screen.getByRole("searchbox") as HTMLInputElement).value).toBe("run-1");
    server.use(http.get("*/api/v1/eval-runs", () => HttpResponse.json({ items: [run] })));
    fireEvent.click(screen.getByRole("button", { name: messages.evals.refresh }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });
  it("clears protected history on explicit access loss", async () => {
    show();
    await screen.findByText("Release checks");
    server.use(
      http.get("*/api/v1/eval-runs", () =>
        HttpResponse.json({ detail: "Access removed" }, { status: 403 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: messages.evals.refresh }));
    await screen.findByRole("alert");
    expect(screen.queryByText("Release checks")).toBeNull();
    expect(screen.queryByText(messages.evals.noRuns)).toBeNull();
  });
  it("preserves a selected status when the latest list no longer contains it", async () => {
    server.use(
      http.get("*/api/v1/eval-runs", () =>
        HttpResponse.json({ items: [{ ...run, status: "running" }] }),
      ),
    );
    show();
    await screen.findByText("Release checks");
    fireEvent.change(screen.getByRole("combobox", { name: messages.evals.status }), {
      target: { value: "running" },
    });
    server.use(http.get("*/api/v1/eval-runs", () => HttpResponse.json({ items: [run] })));
    fireEvent.click(screen.getByRole("button", { name: messages.evals.refresh }));
    await screen.findByText(messages.evals.noRunMatches);
    expect(
      (screen.getByRole("combobox", { name: messages.evals.status }) as HTMLSelectElement).value,
    ).toBe("running");
  });
  it("resets protected state on agent changes and rejects a mismatching scope", async () => {
    const view = show("agent");
    await screen.findByText("Release checks");
    view.rerender(<View agentId="other-agent" />);
    await screen.findByText(messages.evals.runMetadata);
    expect(screen.queryByRole("button", { name: /View results for run/ })).toBeNull();
  });
  it("shows fractional pass rates without claiming a rounded 100% and lazily escapes output", async () => {
    show();
    const dialog = await open();
    await dialog.findByText("Greeting · Passed");
    expect(dialog.getByText("99.995% passed")).toBeTruthy();
    expect(dialog.queryByText(result.outputText)).toBeNull();
    fireEvent.click(dialog.getByText(messages.evals.output));
    fireEvent(
      dialog.getByText(messages.evals.output).parentElement as HTMLElement,
      new Event("toggle"),
    );
    await dialog.findByText(result.outputText);
    expect(document.querySelector("script")).toBeNull();
    expect(
      dialog.getByRole("link", { name: messages.evals.openCaseRun }).getAttribute("href"),
    ).toBe("/runs/case-run");
  });
  it("lists the facts a judged answer missed and the claims it should not have made", async () => {
    server.use(
      http.get("*/api/v1/eval-runs/run-1/results", () =>
        HttpResponse.json({
          items: [
            {
              ...result,
              passed: false,
              scores: {
                llmJudge0: {
                  items: [
                    { kind: "must", statement: "Names the support hours.", verdict: "stated" },
                    { kind: "must", statement: "Names the premium tier.", verdict: "not_stated" },
                    {
                      kind: "must_not",
                      statement: "Promises round-the-clock support.",
                      verdict: "stated",
                      quote: "we answer at any hour",
                    },
                  ],
                },
              },
            },
          ],
        }),
      ),
    );
    show();
    const dialog = await open();
    await dialog.findByText(/Greeting · Needs work/);
    expect(dialog.getByText(/1 of 2 facts/)).toBeTruthy();
    expect(dialog.getByText(messages.evals.missed)).toBeTruthy();
    expect(dialog.getByText("Names the premium tier.")).toBeTruthy();
    expect(dialog.queryByText("Names the support hours.")).toBeNull();
    expect(dialog.getByText(messages.evals.forbidden)).toBeTruthy();
    expect(dialog.getByText("we answer at any hour")).toBeTruthy();
  });
  it("does not manufacture a pass rate when there is no summary", async () => {
    server.use(
      http.get("*/api/v1/eval-runs/run-1", () => HttpResponse.json({ ...run, summary: {} })),
    );
    show();
    const dialog = await open();
    await dialog.findByText("Greeting · Passed");
    expect(dialog.queryByText(/% passed/)).toBeNull();
  });
  it.each([undefined, null, "false"])(
    "does not turn a missing/malformed verdict %j into failure",
    async (passed) => {
      server.use(
        http.get("*/api/v1/eval-runs/run-1/results", () =>
          HttpResponse.json({ items: [{ ...result, passed }] }),
        ),
      );
      show();
      const dialog = await open();
      await dialog.findByText(messages.evals.resultMetadata);
      expect(dialog.queryByText("Greeting · Needs work")).toBeNull();
      expect(dialog.queryByText(messages.evals.noCaseResults)).toBeNull();
    },
  );
  it("does not display case results beside a mismatched returned run", async () => {
    server.use(
      http.get("*/api/v1/eval-runs/run-1", () => HttpResponse.json({ ...run, id: "other" })),
    );
    show();
    const dialog = await open();
    await dialog.findByText(messages.evals.runMetadata);
    expect(dialog.queryByText("Greeting · Passed")).toBeNull();
  });
  it("retains the previous verified snapshot on a results refresh failure and refreshes both without a write", async () => {
    show();
    const dialog = await open();
    await dialog.findByText("Greeting · Passed");
    server.use(
      http.get("*/api/v1/eval-runs/run-1/results", () =>
        HttpResponse.json({ detail: "Results unavailable" }, { status: 503 }),
      ),
    );
    fireEvent.click(dialog.getByRole("button", { name: messages.evals.refresh }));
    await dialog.findByText("Results unavailable");
    expect(dialog.getByText("Greeting · Passed")).toBeTruthy();
    expect(dialog.getByText(messages.evals.resultsRetained)).toBeTruthy();
    server.use(
      http.get("*/api/v1/eval-runs/run-1/results", () =>
        HttpResponse.json({ items: [{ ...result, passed: false }] }),
      ),
    );
    fireEvent.click(dialog.getByRole("button", { name: messages.evals.refresh }));
    await dialog.findByText("Greeting · Needs work");
    expect(dialog.queryByRole("alert")).toBeNull();
  });
  it("keeps run status visible when the first results read fails", async () => {
    server.use(
      http.get("*/api/v1/eval-runs/run-1/results", () =>
        HttpResponse.json({ detail: "Cases unavailable" }, { status: 503 }),
      ),
    );
    show();
    const dialog = await open();
    await dialog.findByText("Cases unavailable");
    expect(dialog.getByText("Completed")).toBeTruthy();
    expect(dialog.queryByText(messages.evals.noCaseResults)).toBeNull();
  });
  it("clears run and cases if either protected endpoint refuses access", async () => {
    show();
    const dialog = await open();
    await dialog.findByText("Greeting · Passed");
    server.use(
      http.get("*/api/v1/eval-runs/run-1/results", () =>
        HttpResponse.json({ detail: "Access removed" }, { status: 403 }),
      ),
    );
    fireEvent.click(dialog.getByRole("button", { name: messages.evals.refresh }));
    await screen.findByRole("alert");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.queryByText("Greeting · Passed")).toBeNull();
    expect(screen.queryByText("Release checks")).toBeNull();
  });
  it("bounds 100,000 loaded case results and resets combined filters and page", async () => {
    server.use(
      http.get("*/api/v1/eval-runs/run-1/results", () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, i) => ({
            ...result,
            case: { id: `case-${i}`, name: `Case ${i}` },
            passed: i !== 99999,
          })),
        }),
      ),
    );
    show();
    const dialog = await open();
    await dialog.findByText("Case 0 · Passed");
    expect(dialog.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.click(dialog.getByRole("button", { name: "Next" }));
    expect(dialog.getByText("Case 25 · Passed")).toBeTruthy();
    fireEvent.change(dialog.getByRole("combobox", { name: messages.evals.outcome }), {
      target: { value: "failed" },
    });
    fireEvent.change(dialog.getByRole("searchbox"), { target: { value: "99999" } });
    expect(dialog.getByText("Case 99999 · Needs work")).toBeTruthy();
    fireEvent.click(dialog.getByRole("button", { name: messages.evals.clearFilters }));
    expect(document.activeElement).toBe(dialog.getByRole("searchbox"));
    expect(dialog.getByText("Case 0 · Passed")).toBeTruthy();
    fireEvent.change(dialog.getByRole("combobox", { name: "Rows per page" }), {
      target: { value: "50" },
    });
    expect(dialog.getAllByRole("listitem")).toHaveLength(50);
  });
  it("restores exact opener focus on Close without refreshing history or cancelling the run", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/eval-runs", () => {
        reads++;
        return HttpResponse.json({ items: [run] });
      }),
    );
    show();
    const dialog = await open();
    await dialog.findByText("Greeting · Passed");
    fireEvent.click(dialog.getByRole("button", { name: messages.evals.close }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole("button", { name: "View results for run run-1" }),
      ),
    );
    expect(reads).toBe(1);
  });
  it("does not reopen protected details when a refreshed session loses permission", async () => {
    show();
    await screen.findByText("Release checks");
    server.use(http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: [] })));
    clearCachedSession();
    fireEvent.click(screen.getByRole("button", { name: messages.evals.refresh }));
    await screen.findByText(messages.evals.denied);
    expect(screen.queryByText("Release checks")).toBeNull();
  });
  it("guards duplicate history reads and aborts the wait on unmount", async () => {
    const nativeFetch = globalThis.fetch;
    const signals: (AbortSignal | null | undefined)[] = [];
    const resolve: ((response: Response) => void)[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input).startsWith("/api/v1/eval-runs?")) {
        signals.push(init?.signal);
        return new Promise((done) => resolve.push(done));
      }
      return nativeFetch(input, init);
    });
    const view = show();
    await waitFor(() => expect(signals).toHaveLength(1));
    resolve[0]?.(Response.json({ items: [run] }));
    await screen.findByText("Release checks");
    const button = screen.getByRole("button", { name: messages.evals.refresh });
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(signals).toHaveLength(2));
    expect(screen.getByText("Release checks")).toBeTruthy();
    expect(screen.getByText(messages.evals.refreshing)).toBeTruthy();
    view.unmount();
    expect(signals[1]?.aborted).toBe(true);
    await act(async () => {
      resolve[1]?.(Response.json({ items: [] }));
    });
  });
  it("aborts both pending detail reads when the inspector closes without treating a late result as current", async () => {
    const nativeFetch = globalThis.fetch;
    const signals: (AbortSignal | null | undefined)[] = [];
    const resolve: ((response: Response) => void)[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input).startsWith("/api/v1/eval-runs/run-1")) {
        signals.push(init?.signal);
        return new Promise((done) => resolve.push(done));
      }
      return nativeFetch(input, init);
    });
    show();
    const dialog = await open();
    await waitFor(() => expect(signals).toHaveLength(2));
    const refresh = dialog.getByRole("button", { name: messages.evals.refresh });
    fireEvent.click(refresh);
    fireEvent.click(refresh);
    expect(signals).toHaveLength(2);
    fireEvent.click(dialog.getByRole("button", { name: messages.evals.close }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(signals.every((signal) => signal?.aborted)).toBe(true);
    await act(async () => {
      resolve[0]?.(Response.json(run));
      resolve[1]?.(Response.json({ items: [result] }));
    });
    expect(screen.queryByText("Greeting · Passed")).toBeNull();
  });
  it("polls only an ongoing verified run and pauses on a failed refresh until a manual read", async () => {
    let reads = 0,
      caseReads = 0;
    server.use(
      http.get("*/api/v1/eval-runs/run-1", () => {
        reads++;
        return HttpResponse.json({ ...run, status: "running" });
      }),
      http.get("*/api/v1/eval-runs/run-1/results", () => {
        caseReads++;
        return caseReads === 1
          ? HttpResponse.json({ items: [result] })
          : HttpResponse.json({ detail: "Temporarily unavailable" }, { status: 503 });
      }),
    );
    show();
    const dialog = await open();
    await dialog.findByText("Greeting · Passed");
    expect(dialog.getByText(messages.evals.runOngoing)).toBeTruthy();
    await dialog.findByText("Temporarily unavailable", {}, { timeout: 3000 });
    expect(reads).toBe(2);
    expect(caseReads).toBe(2);
    expect(dialog.getByText("Greeting · Passed")).toBeTruthy();
    await act(async () => {
      await new Promise((done) => setTimeout(done, 1200));
    });
    expect(reads).toBe(2);
    expect(caseReads).toBe(2);
    server.use(
      http.get("*/api/v1/eval-runs/run-1", () => {
        reads++;
        return HttpResponse.json(run);
      }),
      http.get("*/api/v1/eval-runs/run-1/results", () => HttpResponse.json({ items: [result] })),
    );
    fireEvent.click(dialog.getByRole("button", { name: messages.evals.refresh }));
    await dialog.findByText("Completed");
    expect(reads).toBe(3);
    expect(dialog.queryByRole("alert")).toBeNull();
  });
  it("clears the previous workspace list before reading a changed session", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["evals:manage"],
          tenant: { id: "workspace-one" },
          user: { id: "person-one" },
        }),
      ),
    );
    show();
    await screen.findByText("Release checks");
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["evals:manage"],
          tenant: { id: "workspace-two" },
          user: { id: "person-one" },
        }),
      ),
      http.get("*/api/v1/eval-runs", () =>
        HttpResponse.json({ detail: "New workspace unavailable" }, { status: 503 }),
      ),
    );
    clearCachedSession();
    fireEvent.click(screen.getByRole("button", { name: messages.evals.refresh }));
    await screen.findByText("New workspace unavailable");
    expect(screen.queryByText("Release checks")).toBeNull();
    expect(screen.queryByText(messages.evals.noRuns)).toBeNull();
  });
  it("closes and clears the whole old view when the inspector detects an account change", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["evals:manage"],
          tenant: { id: "workspace" },
          user: { id: "person-one" },
        }),
      ),
    );
    show();
    const dialog = await open();
    await dialog.findByText("Greeting · Passed");
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["evals:manage"],
          tenant: { id: "workspace" },
          user: { id: "person-two" },
        }),
      ),
    );
    clearCachedSession();
    fireEvent.click(dialog.getByRole("button", { name: messages.evals.refresh }));
    await screen.findByText(messages.evals.sessionChanged);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.queryByText("Release checks")).toBeNull();
    expect(screen.queryByText("Greeting · Passed")).toBeNull();
  });
  it("prevents a pending history refresh from restoring rows after detail access is lost", async () => {
    show();
    await screen.findByText("Release checks");
    const nativeFetch = globalThis.fetch;
    let signal: AbortSignal | null | undefined;
    let resolve!: (value: Response) => void;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input).startsWith("/api/v1/eval-runs?")) {
        signal = init?.signal;
        return new Promise((done) => {
          resolve = done;
        });
      }
      return nativeFetch(input, init);
    });
    server.use(
      http.get("*/api/v1/eval-runs/run-1/results", () =>
        HttpResponse.json({ detail: "Access removed" }, { status: 403 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: messages.evals.refresh }));
    await waitFor(() => expect(signal).toBeTruthy());
    await open();
    await screen.findByRole("alert");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(signal?.aborted).toBe(true);
    await act(async () => {
      resolve(Response.json({ items: [run] }));
    });
    expect(screen.queryByText("Release checks")).toBeNull();
    expect(screen.queryByRole("button", { name: "View results for run run-1" })).toBeNull();
  });
});
