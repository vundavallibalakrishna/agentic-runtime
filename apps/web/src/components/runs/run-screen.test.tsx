import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { delay, HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/en.json";
import { server } from "@/test/server";

import { RunScreen } from "./run-screen";

vi.mock("next/navigation", () => ({
  useParams: () => ({ runId: "parent" }),
  usePathname: () => "/runs/parent",
  useRouter: () => ({ push: () => undefined, replace: () => undefined }),
}));
vi.mock("./run-trace-graph", () => ({
  RunTraceGraph: ({ nodes }: { nodes: { id: string }[] }) => (
    <output aria-label="Graph node count">{nodes.length}</output>
  ),
}));
function renderRun() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <RunScreen />
    </NextIntlClientProvider>,
  );
}
function switchTab(name: string) {
  fireEvent.mouseDown(screen.getByRole("tab", { name }), { button: 0, ctrlKey: false });
}
beforeEach(() => {
  server.use(
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ user: { id: "person" }, permissions: ["chat:use"] }),
    ),
    http.get("*/api/v1/runs/parent", () =>
      HttpResponse.json({ id: "parent", status: "completed", trigger: "chat" }),
    ),
    http.get("*/api/v1/runs/parent/children", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/runs/parent/steps", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/runs/parent/tool-calls", () => HttpResponse.json({ items: [] })),
  );
});
afterEach(cleanup);
describe("run inspector", () => {
  it("shows true empty states and no invented usage or graph", async () => {
    renderRun();
    expect(await screen.findByText(messages.detail.noActivity)).toBeTruthy();
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.queryByLabelText("Graph node count")).toBeNull();
    expect(screen.getByText("parent")).toBeTruthy();
    switchTab("Subagents");
    expect(screen.getByText(messages.runs.noChildren)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Cancel run" })).toBeNull();
  });
  it("bounds activity, children and graph nodes and resets filtered pages", async () => {
    server.use(
      http.get("*/api/v1/runs/parent/steps", () =>
        HttpResponse.json({
          items: Array.from({ length: 30 }, (_, i) => ({
            id: `step-${i}`,
            kind: `Stage ${i}`,
            detail: { agent: `Work ${i}` },
          })),
        }),
      ),
      http.get("*/api/v1/runs/parent/tool-calls", () =>
        HttpResponse.json({
          items: [{ id: "call", qualifiedName: "documents.read", status: "succeeded" }],
        }),
      ),
      http.get("*/api/v1/runs/parent/children", () =>
        HttpResponse.json({
          items: Array.from({ length: 30 }, (_, i) => ({
            id: `child-${i}`,
            agentName: `Worker ${i}`,
            status: i === 29 ? "failed" : "completed",
          })),
        }),
      ),
    );
    renderRun();
    await screen.findByText("Stage 0 · Work 0");
    expect(screen.queryByText("Stage 29 · Work 29")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Stage 29 · Work 29")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Work 0" } });
    expect(screen.getByText("Stage 0 · Work 0")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText(messages.runs.activityKind), {
      target: { value: "tool" },
    });
    expect(screen.getByText("Read")).toBeTruthy();
    expect(screen.queryByText("Stage 0 · Work 0")).toBeNull();
    switchTab("Subagents");
    expect(screen.getAllByRole("link", { name: /^Worker/ })).toHaveLength(25);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("link", { name: "Worker 29" }).getAttribute("href")).toBe(
      "/runs/child-29",
    );
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Worker 0" } });
    expect(screen.getByRole("link", { name: "Worker 0" })).toBeTruthy();
    switchTab("Graph");
    expect(screen.getByLabelText("Graph node count").textContent).toBe("3");
  });
  it("retains the run and successful sections when a detail request fails", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v1/runs/parent/children", () =>
        ++calls === 1
          ? HttpResponse.json({ detail: "Subagents unavailable" }, { status: 503 })
          : HttpResponse.json({
              items: [{ id: "child", agentName: "Research", status: "completed" }],
            }),
      ),
      http.get("*/api/v1/runs/parent/steps", () =>
        HttpResponse.json({ items: [{ id: "step", kind: "Planning" }] }),
      ),
    );
    renderRun();
    expect(await screen.findByText("Planning")).toBeTruthy();
    expect(screen.getByText("parent")).toBeTruthy();
    switchTab("Subagents");
    expect((await screen.findByRole("alert")).textContent).toContain("Subagents unavailable");
    expect(screen.queryByText(messages.runs.noChildren)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("link", { name: "Research" })).toBeTruthy();
  });
  it("shows cancellation failures, retries and uses the saved status", async () => {
    let writes = 0;
    let cancelled = false;
    server.use(
      http.get("*/api/v1/runs/parent", () =>
        HttpResponse.json({
          id: "parent",
          userId: "person",
          status: cancelled ? "cancelled" : "waiting_input",
        }),
      ),
      http.post("*/api/v1/runs/parent:cancel", () => {
        writes++;
        if (writes === 1)
          return HttpResponse.json({ detail: "Workflow unavailable" }, { status: 503 });
        cancelled = true;
        return HttpResponse.json({ id: "parent", userId: "person", status: "cancelled" });
      }),
    );
    renderRun();
    fireEvent.click(await screen.findByRole("button", { name: "Cancel run" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Cancel run" }).hasAttribute("disabled")).toBe(
        false,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancel run" }));
    expect(await screen.findByText(messages.runs.cancelRecorded)).toBeTruthy();
    expect(await screen.findByText("Cancelled")).toBeTruthy();
    expect(writes).toBe(2);
    expect(screen.queryByRole("button", { name: "Cancel run" })).toBeNull();
  });
  it("waits for detail reads before polling and stops on a completed record", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/runs/parent", () =>
        HttpResponse.json({ id: "parent", status: ++reads === 1 ? "running" : "completed" }),
      ),
      http.get("*/api/v1/runs/parent/steps", async () => {
        await delay(2100);
        return HttpResponse.json({ items: [] });
      }),
    );
    renderRun();
    await screen.findByText(messages.detail.noActivity, {}, { timeout: 3500 });
    expect(reads).toBe(1);
    expect(await screen.findByText("Completed", {}, { timeout: 3500 })).toBeTruthy();
    expect(reads).toBe(2);
  });

  it("does not expose cancellation for another person's active run", async () => {
    server.use(
      http.get("*/api/v1/runs/parent", () =>
        HttpResponse.json({ id: "parent", userId: "another", status: "running" }),
      ),
    );
    renderRun();
    await screen.findByText(messages.detail.noActivity);
    expect(screen.queryByRole("button", { name: "Cancel run" })).toBeNull();
  });
});
