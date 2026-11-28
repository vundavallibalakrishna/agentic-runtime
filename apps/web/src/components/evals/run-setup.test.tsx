import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DisplayError, Session } from "@/lib/api";
import messages from "@/messages/en.json";
import { server } from "@/test/server";
import { RunSetup } from "./run-setup";
import type { Suite } from "./suite-data";

const t = messages.evals;
const session = {
  permissions: ["evals:manage", "evals:run", "agents:read"],
  user: { id: "person" },
  tenant: { id: "workspace" },
} as Session;
const suite: Suite = {
  id: "suite",
  name: "Saved suite",
  description: "",
  kind: "functional",
  caseCount: 3,
  agent: null,
  gate: { required: false, minPassRate: 0.9, maxRegressionPct: 5, mustPassTags: [] },
  lastRun: null,
};
const agent = {
  id: "agent",
  name: "Selected agent",
  published: { id: "published", version: 12, etag: "saved-published" },
  draft: { id: "draft", version: 13, etag: "saved-draft" },
};
const run = {
  id: "run",
  suiteId: "suite",
  agentId: "agent",
  agentVersionId: "draft",
  status: "queued",
};
const onStarted = vi.fn<(id: string) => void>(),
  onClose = vi.fn<() => void>(),
  onHistory = vi.fn<() => void>(),
  onAccessLost = vi.fn<(error: DisplayError) => void>();
function show(fixed = true) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <RunSetup
        suite={suite}
        agentId={fixed ? "agent" : undefined}
        session={session}
        onStarted={onStarted}
        onClose={onClose}
        onHistory={onHistory}
        onAccessLost={onAccessLost}
      />
    </NextIntlClientProvider>,
  );
}
const modal = () => within(screen.getByRole("dialog", { name: t.runSetup }));
const start = () => modal().getByRole("button", { name: t.startRun });
const refresh = () => modal().getByRole("button", { name: t.copyRefresh });
const versions = () => modal().getByRole("combobox", { name: t.version });
async function ready() {
  await waitFor(() => expect(refresh().matches(":disabled")).toBe(false));
}
async function choose(id = "draft") {
  await ready();
  fireEvent.change(versions(), { target: { value: id } });
}
beforeEach(() => {
  vi.clearAllMocks();
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json(session)),
    http.get("*/api/v1/model-aliases", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/eval-suites/suite", () => HttpResponse.json(suite)),
    http.get("*/api/v1/agents/agent", () => HttpResponse.json(agent)),
    http.get("*/api/v1/agents/agent/versions/13", () =>
      HttpResponse.json({ id: "draft", version: 13, agentId: "agent", etag: "saved-draft" }),
    ),
    http.get("*/api/v1/agents/agent/versions/12", () =>
      HttpResponse.json({
        id: "published",
        version: 12,
        agentId: "agent",
        etag: "saved-published",
      }),
    ),
    http.get("*/api/v1/eval-runs/run", () => HttpResponse.json(run)),
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
describe("evaluation run setup", () => {
  it("requires an explicit available saved version and keeps actions in the allocated footer", async () => {
    show();
    await ready();
    expect((versions() as HTMLSelectElement).value).toBe("");
    expect(
      modal()
        .getAllByRole("option")
        .map((item) => item.textContent),
    ).toEqual([t.chooseRunVersion, "Published · Version 12", "Draft · Version 13"]);
    expect(start().matches(":disabled")).toBe(true);
    expect(start().closest('[data-slot="dialog-footer"]')).toBeTruthy();
    fireEvent.click(modal().getByRole("button", { name: t.close }));
    expect(onClose).toHaveBeenCalledOnce();
  });
  it("pins the explicit numeric version and opens only an independently matching saved run", async () => {
    const writes: unknown[] = [];
    let confirm: (() => void) | undefined;
    server.use(
      http.post("*/api/v1/eval-suites/suite:run", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json(run, { status: 202 });
      }),
      http.get("*/api/v1/eval-runs/run", async () => {
        await new Promise<void>((resolve) => {
          confirm = resolve;
        });
        return HttpResponse.json(run);
      }),
    );
    show();
    await choose();
    fireEvent.click(start());
    await modal().findByText(t.runAcknowledged);
    expect(onStarted).not.toHaveBeenCalled();
    expect(writes).toEqual([{ agentId: "agent", agentVersionRef: "13" }]);
    await act(async () => confirm?.());
    await waitFor(() => expect(onStarted).toHaveBeenCalledExactlyOnceWith("run"));
  });
  it("runs on another model only when one is chosen", async () => {
    const writes: unknown[] = [];
    server.use(
      http.get("*/api/v1/model-aliases", () =>
        HttpResponse.json({
          items: [
            { alias: "reasoning", kind: "chat" },
            { alias: "embed", kind: "embedding" },
            { alias: "fast", kind: "chat" },
          ],
        }),
      ),
      http.post("*/api/v1/eval-suites/suite:run", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json(run, { status: 202 });
      }),
      http.get("*/api/v1/eval-runs/run", () => HttpResponse.json(run)),
    );
    show();
    await choose();
    const model = (await modal().findByLabelText(t.model)) as HTMLSelectElement;
    // Only chat models are offered, and the agent's own model is the default.
    expect(
      within(model)
        .getAllByRole("option")
        .map((item) => item.textContent),
    ).toEqual([t.agentModel, "fast", "reasoning"]);
    fireEvent.change(model, { target: { value: "fast" } });
    fireEvent.click(start());
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toEqual({
      agentId: "agent",
      agentVersionRef: "13",
      modelAliasOverride: "fast",
    });
  });
  it("does not substitute a published version for an absent draft", async () => {
    server.use(
      http.get("*/api/v1/agents/agent", () => HttpResponse.json({ ...agent, draft: null })),
    );
    show();
    await ready();
    expect(modal().queryByRole("option", { name: "Draft · Version 13" })).toBeNull();
    expect(start().matches(":disabled")).toBe(true);
  });
  it("explains an agent with no visible versions", async () => {
    server.use(
      http.get("*/api/v1/agents/agent", () =>
        HttpResponse.json({ ...agent, draft: null, published: null }),
      ),
    );
    show();
    await modal().findByText(t.runNoVersions);
    expect(start().matches(":disabled")).toBe(true);
  });
  it("requires an agent choice and clears the prior version when the target changes", async () => {
    server.use(
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({ items: [{ id: "agent", name: agent.name }] }),
      ),
    );
    show(false);
    await ready();
    expect(start().matches(":disabled")).toBe(true);
    fireEvent.click(modal().getByRole("button", { name: /^Agent to evaluate:/ }));
    fireEvent.click(await screen.findByText(agent.name));
    await screen.findByRole("option", { name: "Draft · Version 13" });
    expect((versions() as HTMLSelectElement).value).toBe("");
    await choose();
    expect(start().matches(":disabled")).toBe(false);
  });
  it.each([
    { ...agent, id: "other" },
    { ...agent, draft: { id: "draft", version: 13 } },
    { ...agent, draft: { id: "draft", version: 1.5 } },
    { ...agent, draft: { id: "published", version: 13 } },
  ])("holds malformed or mismatched agent metadata %j", async (value) => {
    server.use(http.get("*/api/v1/agents/agent", () => HttpResponse.json(value)));
    show();
    await modal().findByText(t.runAgentMetadata);
    expect(start().matches(":disabled")).toBe(true);
  });
  it("keeps the selected identity unavailable after it disappears on refresh", async () => {
    show();
    await choose();
    server.use(
      http.get("*/api/v1/agents/agent", () => HttpResponse.json({ ...agent, draft: null })),
    );
    fireEvent.click(refresh());
    await modal().findByRole("option", { name: t.runVersionUnavailable });
    expect((versions() as HTMLSelectElement).value).toBe("draft");
    expect(start().matches(":disabled")).toBe(true);
  });
  it("retains the selection after a failed read but blocks starting until recovery", async () => {
    show();
    await choose();
    server.use(
      http.get("*/api/v1/agents/agent", () =>
        HttpResponse.json({ detail: "Agent unavailable" }, { status: 503 }),
      ),
    );
    fireEvent.click(refresh());
    await modal().findByText("Agent unavailable");
    expect((versions() as HTMLSelectElement).value).toBe("draft");
    expect(start().matches(":disabled")).toBe(true);
    server.use(http.get("*/api/v1/agents/agent", () => HttpResponse.json(agent)));
    fireEvent.click(refresh());
    await ready();
    expect(start().matches(":disabled")).toBe(false);
  });
  it("holds a definite refusal, focuses guidance and recovers by reads without replay", async () => {
    let writes = 0;
    server.use(
      http.post("*/api/v1/eval-suites/suite:run", () => {
        writes++;
        return HttpResponse.json({ code: "csrf_failed", detail: "CSRF rejected" }, { status: 403 });
      }),
    );
    show();
    await choose();
    fireEvent.click(start());
    await modal().findByText(t.runRefused);
    await waitFor(() => expect(document.activeElement).toBe(modal().getByRole("alert")));
    expect(start().matches(":disabled")).toBe(true);
    expect((versions() as HTMLSelectElement).value).toBe("draft");
    fireEvent.click(refresh());
    await modal().findByText(t.runChecked);
    expect(start().matches(":disabled")).toBe(false);
    expect(writes).toBe(1);
    expect(onStarted).not.toHaveBeenCalled();
  });
  it("keeps an ambiguous request held after a read and offers actual run history", async () => {
    let writes = 0;
    server.use(
      http.post("*/api/v1/eval-suites/suite:run", () => {
        writes++;
        return HttpResponse.json({ detail: "Response unavailable" }, { status: 503 });
      }),
    );
    show();
    await choose();
    fireEvent.click(start());
    await modal().findByText(t.runUnconfirmed);
    await ready();
    fireEvent.click(refresh());
    await modal().findByText(t.runUnknownChecked);
    expect(writes).toBe(1);
    expect(start().matches(":disabled")).toBe(true);
    fireEvent.click(modal().getByRole("button", { name: t.runReviewHistory }));
    expect(onHistory).toHaveBeenCalledOnce();
  });
  it.each([
    { ...run, suiteId: "other" },
    { ...run, agentId: "other" },
    { ...run, agentVersionId: "published" },
    { id: "run" },
  ])("withholds results for an incomplete or mismatched acknowledgement %j", async (value) => {
    server.use(
      http.post("*/api/v1/eval-suites/suite:run", () => HttpResponse.json(value, { status: 202 })),
    );
    show();
    await choose();
    fireEvent.click(start());
    await modal().findByText(t.runMetadata);
    expect(onStarted).not.toHaveBeenCalled();
    expect(start().matches(":disabled")).toBe(true);
  });
  it("keeps a known acknowledgement through failed readback and confirms it without POST replay", async () => {
    let writes = 0;
    server.use(
      http.post("*/api/v1/eval-suites/suite:run", () => {
        writes++;
        return HttpResponse.json(run, { status: 202 });
      }),
      http.get("*/api/v1/eval-runs/run", () =>
        HttpResponse.json({ detail: "Read unavailable" }, { status: 503 }),
      ),
    );
    show();
    await choose();
    fireEvent.click(start());
    await modal().findByText("Read unavailable");
    expect(modal().getByText(t.runSavedReference.replace("{id}", "run"))).toBeTruthy();
    expect(onStarted).not.toHaveBeenCalled();
    server.use(http.get("*/api/v1/eval-runs/run", () => HttpResponse.json(run)));
    fireEvent.click(refresh());
    await waitFor(() => expect(onStarted).toHaveBeenCalledExactlyOnceWith("run"));
    expect(writes).toBe(1);
  });
  it("holds a differing saved version after acknowledgement", async () => {
    server.use(
      http.post("*/api/v1/eval-suites/suite:run", () => HttpResponse.json(run)),
      http.get("*/api/v1/eval-runs/run", () =>
        HttpResponse.json({ ...run, agentVersionId: "published" }),
      ),
    );
    show();
    await choose();
    fireEvent.click(start());
    await modal().findByText(t.runMetadata);
    expect(onStarted).not.toHaveBeenCalled();
    expect(modal().getByText(t.runAcknowledged)).toBeTruthy();
  });
  it.each([
    { id: "changed", version: 13, agentId: "agent" },
    { id: "draft", version: 12, agentId: "agent" },
    { id: "draft", version: 13, agentId: "other" },
    { id: "draft", version: 13, agentId: "agent", etag: "changed-draft" },
  ])("checks exact version identity before sending %j", async (value) => {
    let writes = 0;
    server.use(
      http.get("*/api/v1/agents/agent/versions/13", () => HttpResponse.json(value)),
      http.post("*/api/v1/eval-suites/suite:run", () => {
        writes++;
        return HttpResponse.json(run);
      }),
    );
    show();
    await choose();
    fireEvent.click(start());
    await modal().findByText(t.runVersionChanged);
    expect(writes).toBe(0);
  });
  it("checks saved cases before sending", async () => {
    let writes = 0;
    show();
    await choose();
    server.use(
      http.get("*/api/v1/eval-suites/suite", () => HttpResponse.json({ ...suite, caseCount: 0 })),
      http.post("*/api/v1/eval-suites/suite:run", () => {
        writes++;
        return HttpResponse.json(run);
      }),
    );
    fireEvent.click(start());
    await modal().findByText(t.runSuiteUnavailable);
    expect(writes).toBe(0);
  });
  it("explains missing agent read permission without requesting the agent", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ ...session, permissions: ["evals:manage", "evals:run"] }),
      ),
      http.get("*/api/v1/agents/agent", () => {
        reads++;
        return HttpResponse.json(agent);
      }),
    );
    show();
    await modal().findByText(t.agentAccess);
    expect(reads).toBe(0);
    expect(start().matches(":disabled")).toBe(true);
  });
  it.each([
    { ...session, user: { id: "other" } },
    { ...session, permissions: ["evals:manage", "agents:read"] },
  ])("refuses an account or run-authority change before sending %j", async (value) => {
    let writes = 0;
    show();
    await choose();
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json(value)),
      http.post("*/api/v1/eval-suites/suite:run", () => {
        writes++;
        return HttpResponse.json(run);
      }),
    );
    fireEvent.click(start());
    await waitFor(() => expect(onAccessLost).toHaveBeenCalledOnce());
    expect(writes).toBe(0);
  });
  it("aborts its browser wait on unmount and ignores a late acknowledgement", async () => {
    let finish: (() => void) | undefined,
      signal: AbortSignal | undefined,
      writes = 0;
    server.use(
      http.post("*/api/v1/eval-suites/suite:run", async ({ request }) => {
        writes++;
        signal = request.signal;
        await new Promise<void>((resolve) => {
          finish = resolve;
        });
        return HttpResponse.json(run);
      }),
    );
    const view = show();
    await choose();
    fireEvent.click(start());
    fireEvent.submit(document.getElementById("eval-run-setup") as HTMLFormElement);
    await waitFor(() => expect(writes).toBe(1));
    view.unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => finish?.());
    expect(onStarted).not.toHaveBeenCalled();
  });
});
