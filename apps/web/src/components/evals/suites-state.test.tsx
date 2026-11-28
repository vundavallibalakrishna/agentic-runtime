import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EvalsScreen } from "@/components/evals/evals-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const t = messages.evals;
const session = {
  permissions: ["evals:manage", "evals:run", "agents:read"],
  user: { id: "person", displayName: "Operator" },
  tenant: { id: "workspace" },
};
const base = {
  id: "suite",
  name: "Release checks",
  description: "Saved purpose",
  kind: "functional",
  caseCount: 1,
  agent: null,
  gate: {
    required: true,
    minPassRate: 0.145,
    maxRegressionPct: 2.25,
    mustPassTags: ["priority, urgent", "case\nlabel"],
  },
  lastRun: null,
};
let current = base;
vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/evals",
  useRouter: () => ({ push: () => undefined }),
  useParams: () => ({ id: "agent" }),
}));
function content(agentId?: string) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <EvalsScreen admin agentId={agentId} />
    </NextIntlClientProvider>
  );
}
function show(agentId?: string) {
  return render(content(agentId));
}
function form() {
  return within(within(screen.getByRole("main")).getByRole("complementary"));
}
async function ready() {
  await screen.findByRole("heading", { name: current.name });
}
function field(label: string, value: string) {
  fireEvent.change(form().getByLabelText(label, { exact: true }), { target: { value } });
}
function advanced() {
  const button = form().getByRole("button", { name: "Advanced" });
  if (button.getAttribute("aria-pressed") !== "true") fireEvent.click(button);
}
async function edit() {
  fireEvent.click(
    await screen.findByRole("button", {
      name: t.editSuiteNamed.replace("{name}", current.name),
    }),
  );
  await waitFor(() =>
    expect(document.activeElement).toBe(form().getByLabelText(t.name, { exact: true })),
  );
}
function submit() {
  fireEvent.click(form().getByRole("button", { name: t.saveChanges }));
}
beforeEach(() => {
  localStorage.removeItem("ar-settings-mode");
  current = { ...base, gate: { ...base.gate } };
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json(session)),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/eval-suites", () => HttpResponse.json({ items: [current] })),
    http.get("*/api/v1/eval-suites/suite", () => HttpResponse.json(current)),
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
describe("evaluation suite settings and saved-state lifecycle", () => {
  it("starts with inherited settings and no prepared gate numbers", async () => {
    show();
    await ready();
    expect((form().getByLabelText(t.name) as HTMLInputElement).value).toBe("");
    expect((form().getByLabelText(t.kind) as HTMLSelectElement).value).toBe("");
    expect(form().getByText(t.gateInherited)).toBeTruthy();
    advanced();
    expect((form().getByLabelText(t.threshold) as HTMLInputElement).value).toBe("");
    expect((form().getByLabelText(t.gateRequirement) as HTMLSelectElement).value).toBe("");
    expect((form().getByLabelText(t.gateRegression) as HTMLInputElement).value).toBe("");
    expect((form().getByLabelText(t.gateTags) as HTMLTextAreaElement).value).toBe("");
  });
  it("creates only the requested details, verifies actual defaults and leaves an inspectable receipt", async () => {
    const writes: unknown[] = [];
    const saved = {
      ...base,
      id: "created",
      name: "New checks",
      description: "",
      gate: { ...base.gate, minPassRate: 0.375 },
    };
    server.use(
      http.post("*/api/v1/eval-suites", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json(saved, { status: 201 });
      }),
      http.get("*/api/v1/eval-suites/created", () => HttpResponse.json(saved)),
    );
    show();
    await ready();
    field(t.name, " New checks ");
    fireEvent.click(form().getByRole("button", { name: t.create }));
    await form().findByText(t.suiteSaved);
    expect(writes).toEqual([{ name: "New checks", agentId: null }]);
    expect(form().getByText(t.suiteConfirmed)).toBeTruthy();
    fireEvent.click(form().getByText(t.returnedSuite));
    expect(form().getByRole("region", { name: t.returnedSuite }).textContent).toContain(
      '"minPassRate": 0.375',
    );
    expect((form().getByLabelText(t.name) as HTMLInputElement).value).toBe(" New checks ");
  });
  it("does not force a required gate for an agent-scoped create", async () => {
    const writes: unknown[] = [];
    const scoped = { ...base, agent: { id: "agent", name: "Chosen agent" } };
    const saved = {
      ...scoped,
      id: "created",
      name: "Agent checks",
      gate: { ...scoped.gate, required: false },
    };
    server.use(
      http.get("*/api/v1/eval-suites", () => HttpResponse.json({ items: [scoped] })),
      http.post("*/api/v1/eval-suites", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json(saved, { status: 201 });
      }),
      http.get("*/api/v1/eval-suites/created", () => HttpResponse.json(saved)),
    );
    show("agent");
    await ready();
    field(t.name, "Agent checks");
    fireEvent.click(form().getByRole("button", { name: t.create }));
    await form().findByText(t.suiteSaved);
    expect(writes).toEqual([{ name: "Agent checks", agentId: "agent" }]);
  });
  it("retains hidden overrides through mode changes and resets only create gate overrides", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/v1/eval-suites", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(
          { code: "csrf_failed", detail: "Origin refused" },
          { status: 403 },
        );
      }),
    );
    show();
    await ready();
    field(t.name, "Draft checks");
    field(t.suiteDescription, "A purpose");
    advanced();
    field(t.threshold, "99.995");
    fireEvent.change(form().getByLabelText(t.gateRequirement), { target: { value: "false" } });
    fireEvent.click(form().getByRole("button", { name: "Simple" }));
    expect(form().getByText(t.gateHiddenChanges)).toBeTruthy();
    fireEvent.click(form().getByRole("button", { name: t.create }));
    await form().findByText(messages.apiErrors.csrf);
    expect(body).toEqual({
      name: "Draft checks",
      description: "A purpose",
      agentId: null,
      gate: { required: false, minPassRate: 0.99995 },
    });
    expect((form().getByLabelText(t.name) as HTMLInputElement).disabled).toBe(false);
    fireEvent.click(form().getByRole("button", { name: t.copyRefresh }));
    await form().findByText(t.suiteChecked);
    advanced();
    expect((form().getByLabelText(t.threshold) as HTMLInputElement).value).toBe("99.995");
    fireEvent.click(form().getByRole("button", { name: t.resetGate }));
    expect((form().getByLabelText(t.threshold) as HTMLInputElement).value).toBe("");
    expect((form().getByLabelText(t.name) as HTMLInputElement).value).toBe("Draft checks");
    expect((form().getByLabelText(t.suiteDescription) as HTMLTextAreaElement).value).toBe(
      "A purpose",
    );
  });
  it("patches only a changed name while preserving returned gate settings and description", async () => {
    const writes: unknown[] = [];
    server.use(
      http.patch("*/api/v1/eval-suites/suite", async ({ request }) => {
        const value = (await request.json()) as { name: string };
        writes.push(value);
        current = { ...current, name: value.name };
        return HttpResponse.json(current);
      }),
    );
    show();
    await ready();
    await edit();
    expect(form().getByRole("button", { name: t.saveChanges }).hasAttribute("disabled")).toBe(true);
    field(t.name, " Renamed checks ");
    submit();
    await form().findByText(t.suiteUpdated);
    expect(writes).toEqual([{ name: "Renamed checks" }]);
    expect(current.gate).toEqual(base.gate);
    expect(current.description).toBe(base.description);
    await waitFor(() =>
      expect(form().getByRole("button", { name: t.finishEdit }).matches(":disabled")).toBe(false),
    );
    fireEvent.click(form().getByRole("button", { name: t.finishEdit }));
    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole("button", { name: t.editSuiteNamed.replace("{name}", current.name) }),
      ),
    );
  });
  it("preserves unknown gate metadata on detail edits and withholds unsafe gate replacement", async () => {
    current = {
      ...base,
      gate: { ...base.gate, extensionRule: { enabled: true } },
    } as typeof current;
    const writes: unknown[] = [];
    server.use(
      http.patch("*/api/v1/eval-suites/suite", async ({ request }) => {
        const value = (await request.json()) as { name: string };
        writes.push(value);
        current = { ...current, name: value.name };
        return HttpResponse.json(current);
      }),
    );
    show();
    await ready();
    await edit();
    advanced();
    expect(form().getByText(t.unknownGateEdit)).toBeTruthy();
    expect(form().getByLabelText(t.threshold).matches(":disabled")).toBe(true);
    field(t.name, "New name");
    submit();
    await form().findByText(t.suiteUpdated);
    expect(writes).toEqual([{ name: "New name" }]);
    expect((current.gate as Record<string, unknown>).extensionRule).toEqual({ enabled: true });
  });
  it("uses precise saved percentage text and sends a complete preserved gate only when it changes", async () => {
    const writes: unknown[] = [];
    server.use(
      http.patch("*/api/v1/eval-suites/suite", async ({ request }) => {
        const value = (await request.json()) as { gate: typeof base.gate };
        writes.push(value);
        current = { ...current, gate: value.gate };
        return HttpResponse.json(current);
      }),
    );
    show();
    await ready();
    await edit();
    advanced();
    expect((form().getByLabelText(t.threshold) as HTMLInputElement).value).toBe("14.5");
    field(t.threshold, "33.33333333333333");
    submit();
    await form().findByText(t.suiteUpdated);
    expect(writes).toEqual([{ gate: { ...base.gate, minPassRate: 0.3333333333333333 } }]);
  });
  it("submits explicit regression and arbitrary JSON tag names without delimiter loss", async () => {
    const writes: unknown[] = [];
    server.use(
      http.patch("*/api/v1/eval-suites/suite", async ({ request }) => {
        const value = (await request.json()) as { gate: typeof base.gate };
        writes.push(value);
        current = { ...current, gate: value.gate };
        return HttpResponse.json(current);
      }),
    );
    show();
    await ready();
    await edit();
    advanced();
    field(t.gateRegression, "-1.25");
    field(t.gateTags, JSON.stringify(["comma, tag", "line\nbreak", "日本語"]));
    submit();
    await form().findByText(t.suiteUpdated);
    expect(writes).toEqual([
      {
        gate: {
          ...base.gate,
          maxRegressionPct: -1.25,
          mustPassTags: ["comma, tag", "line\nbreak", "日本語"],
        },
      },
    ]);
  });
  it("does not send invalid precision, non-decimal rates or malformed tag structures", async () => {
    const write = vi.fn(() => HttpResponse.json(current));
    server.use(http.post("*/api/v1/eval-suites", write));
    show();
    await ready();
    field(t.name, "Draft");
    advanced();
    for (const value of ["101", "0x10", "99.999999999999999"]) {
      field(t.threshold, value);
      expect(form().getByText(t.invalidThreshold)).toBeTruthy();
      expect(form().getByRole("button", { name: t.create }).hasAttribute("disabled")).toBe(true);
    }
    field(t.threshold, "50");
    field(t.gateTags, '{"tag":"value"}');
    expect(form().getByText(t.invalidGateTags)).toBeTruthy();
    expect(write).not.toHaveBeenCalled();
  });
  it("preserves a known acknowledgement when entity confirmation fails and recovers through reads", async () => {
    let writes = 0;
    const saved = { ...base, id: "created", name: "Draft" };
    server.use(
      http.post("*/api/v1/eval-suites", () => {
        writes++;
        return HttpResponse.json(saved, { status: 201 });
      }),
      http.get("*/api/v1/eval-suites/created", () =>
        HttpResponse.json({ detail: "Confirmation unavailable" }, { status: 503 }),
      ),
    );
    show();
    await ready();
    field(t.name, "Draft");
    fireEvent.click(form().getByRole("button", { name: t.create }));
    await form().findByText("Confirmation unavailable");
    expect(form().getByText(t.suiteAcknowledged)).toBeTruthy();
    expect(form().queryByText(t.suiteSaved)).toBeNull();
    server.use(http.get("*/api/v1/eval-suites", () => HttpResponse.json({ items: [base, saved] })));
    fireEvent.click(form().getByRole("button", { name: t.copyRefresh }));
    await form().findByText(t.suiteVerified);
    expect(writes).toBe(1);
  });
  it("keeps a directly confirmed suite visible if a later manual catalogue refresh fails", async () => {
    let writes = 0;
    const saved = { ...base, id: "created", name: "Confirmed new" };
    server.use(
      http.post("*/api/v1/eval-suites", () => {
        writes++;
        return HttpResponse.json(saved, { status: 201 });
      }),
      http.get("*/api/v1/eval-suites/created", () => HttpResponse.json(saved)),
      http.get("*/api/v1/eval-suites", () =>
        writes
          ? HttpResponse.json({ detail: "List unavailable" }, { status: 503 })
          : HttpResponse.json({ items: [] }),
      ),
    );
    show();
    await screen.findByText(t.empty);
    field(t.name, "Confirmed new");
    fireEvent.click(form().getByRole("button", { name: t.create }));
    await form().findByText(t.suiteSaved);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: t.refresh }).matches(":disabled")).toBe(false),
    );
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await form().findByText(t.suiteSavedListPending);
    expect(screen.getByRole("heading", { name: "Confirmed new" })).toBeTruthy();
    expect(screen.queryByText(t.empty)).toBeNull();
    expect(form().getByText(t.suiteConfirmed)).toBeTruthy();
    expect(screen.getByText(t.suitesRetained)).toBeTruthy();
  });
  it.each([
    { id: "created" },
    { ...base, id: "created", name: "Different" },
    { ...base, id: "created", name: "Draft", agent: { id: "other" } },
  ])("holds mismatched receipts %j without success", async (value) => {
    server.use(http.post("*/api/v1/eval-suites", () => HttpResponse.json(value, { status: 201 })));
    show();
    await ready();
    field(t.name, "Draft");
    fireEvent.click(form().getByRole("button", { name: t.create }));
    await form().findByText(t.suiteReceipt);
    expect(form().getByText(t.suiteUnconfirmed)).toBeTruthy();
    expect(form().queryByText(t.suiteSaved)).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(form().getByRole("alert")));
  });
  it("holds an ambiguous failure after read-only refresh without replay or draft loss", async () => {
    let writes = 0;
    server.use(
      http.post("*/api/v1/eval-suites", () => {
        writes++;
        return HttpResponse.json({ detail: "Create unavailable" }, { status: 503 });
      }),
    );
    show();
    await ready();
    field(t.name, "Draft");
    fireEvent.click(form().getByRole("button", { name: t.create }));
    await form().findByText("Create unavailable");
    field(t.name, "Edited draft");
    fireEvent.click(form().getByRole("button", { name: t.copyRefresh }));
    await form().findByText(t.suiteUnknownChecked);
    expect((form().getByLabelText(t.name) as HTMLInputElement).value).toBe("Edited draft");
    expect(form().getByRole("button", { name: t.create }).hasAttribute("disabled")).toBe(true);
    expect(writes).toBe(1);
  });
  it("checks the saved definition before editing and never patches an observed conflict", async () => {
    const write = vi.fn(() => HttpResponse.json(current));
    server.use(http.patch("*/api/v1/eval-suites/suite", write));
    show();
    await ready();
    await edit();
    field(t.name, "My draft");
    current = { ...current, description: "Changed elsewhere" };
    submit();
    await form().findByText(t.suiteChanged);
    expect(write).not.toHaveBeenCalled();
    expect((form().getByLabelText(t.name) as HTMLInputElement).value).toBe("My draft");
  });
  it("retains known suites and draft filters after refresh failure", async () => {
    show();
    await ready();
    field(t.name, "Draft");
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Release" } });
    server.use(
      http.get("*/api/v1/eval-suites", () =>
        HttpResponse.json({ detail: "List unavailable" }, { status: 503 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await screen.findByText("List unavailable");
    expect(screen.getByRole("heading", { name: base.name })).toBeTruthy();
    expect((form().getByLabelText(t.name) as HTMLInputElement).value).toBe("Draft");
    expect((screen.getByRole("searchbox") as HTMLInputElement).value).toBe("Release");
  });
  it.each([
    {},
    { items: [{ ...base, gate: undefined }] },
    { items: [{ ...base, caseCount: null }] },
    { items: [base, base] },
  ])(
    "rejects missing/ambiguous metadata %j without fabricated empty/default values",
    async (value) => {
      server.use(http.get("*/api/v1/eval-suites", () => HttpResponse.json(value)));
      show();
      await screen.findByText(t.suiteMetadata);
      expect(screen.queryByText(t.empty)).toBeNull();
      expect(screen.queryByRole("heading", { name: base.name })).toBeNull();
    },
  );
  it("does not read or expose management data for a run-only role", async () => {
    const read = vi.fn(() => HttpResponse.json({ items: [base] }));
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ ...session, permissions: ["evals:run"] }),
      ),
      http.get("*/api/v1/eval-suites", read),
    );
    show();
    await screen.findByText(t.denied);
    expect(read).not.toHaveBeenCalled();
    expect(screen.queryByRole("complementary")).toBeNull();
  });
  it("clears protected rows and drafts on explicit permission loss or a changed current account", async () => {
    show();
    await ready();
    field(t.name, "Private draft");
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ ...session, user: { id: "other" } }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await screen.findByText(t.sessionChanged);
    expect(screen.queryByRole("heading", { name: base.name })).toBeNull();
    expect(screen.queryByDisplayValue("Private draft")).toBeNull();
  });
  it("bounds 100,000 loaded suites, combines kind/run/search filters and resets pages/focus", async () => {
    server.use(
      http.get("*/api/v1/eval-suites", () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, i) => ({
            ...base,
            id: `suite-${i}`,
            name: `Checks ${i}`,
            kind: i === 99999 ? "safety" : "functional",
            lastRun: i === 99999 ? { id: "run", status: "completed", passRate: 0.99995 } : null,
          })),
        }),
      ),
    );
    show();
    await screen.findByRole("heading", { name: "Checks 0" });
    const main = within(screen.getByRole("main"));
    expect(main.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.click(main.getByRole("button", { name: "Next" }));
    expect(main.getByRole("heading", { name: "Checks 25" })).toBeTruthy();
    const filters = within(screen.getByRole("group", { name: t.suiteFilters }));
    fireEvent.change(filters.getByLabelText(t.kind), { target: { value: "safety" } });
    fireEvent.change(filters.getByLabelText(t.status), {
      target: { value: JSON.stringify(["status", "completed"]) },
    });
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "suite-99999" } });
    expect(main.getByRole("heading", { name: "Checks 99999" })).toBeTruthy();
    expect(main.getByText("99.995% passed")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "No matching record" } });
    expect(screen.getByText(t.noSuiteMatches)).toBeTruthy();
    fireEvent.click(main.getByRole("button", { name: t.clearFilters }));
    expect(document.activeElement).toBe(screen.getByRole("searchbox"));
    expect(main.getByRole("heading", { name: "Checks 0" })).toBeTruthy();
    fireEvent.change(main.getByRole("combobox", { name: "Rows per page" }), {
      target: { value: "100" },
    });
    expect(main.getAllByRole("listitem")).toHaveLength(100);
  }, 15000);
  it("labels absent run history and withholds empty-suite execution", async () => {
    current = { ...base, caseCount: 0 };
    show();
    await ready();
    expect(screen.getAllByText(t.noSavedRun).length).toBeGreaterThan(0);
    expect(screen.getByText(t.suiteNeedsCases)).toBeTruthy();
    expect(screen.getByRole("button", { name: t.run }).hasAttribute("disabled")).toBe(true);
    expect(screen.queryByText("0% passed")).toBeNull();
  });
  it("resets editor/dialog state when the agent route scope changes", async () => {
    server.use(
      http.get("*/api/v1/eval-suites", ({ request }) => {
        const id = new URL(request.url).searchParams.get("agent_id");
        return HttpResponse.json({
          items: [{ ...base, agent: { id, name: id }, name: `Checks for ${id}` }],
        });
      }),
    );
    const view = show("first");
    await screen.findByRole("heading", { name: "Checks for first" });
    field(t.name, "Private draft");
    view.rerender(content("second"));
    await screen.findByRole("heading", { name: "Checks for second" });
    expect((form().getByLabelText(t.name) as HTMLInputElement).value).toBe("");
    expect(screen.queryByRole("heading", { name: "Checks for first" })).toBeNull();
  });
  it("offers a direct form shortcut in stacked layouts", async () => {
    show();
    await ready();
    fireEvent.click(screen.getByRole("button", { name: t.openSuiteForm }));
    expect(document.activeElement).toBe(form().getByLabelText(t.name));
  });
  it("guards duplicate saves and ignores aborted late receipts without a verification request", async () => {
    const nativeFetch = globalThis.fetch;
    let resolve!: (value: Response) => void;
    let signal: AbortSignal | null | undefined;
    let writes = 0,
      checks = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input) === "/api/v1/eval-suites" && init?.method === "POST") {
        writes++;
        signal = init.signal;
        return new Promise((done) => {
          resolve = done;
        });
      }
      if (String(input) === "/api/v1/eval-suites/created") checks++;
      return nativeFetch(input, init);
    });
    const view = show();
    await ready();
    field(t.name, "Draft");
    const button = form().getByRole("button", { name: t.create });
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(writes).toBe(1));
    view.unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => {
      resolve(Response.json({ ...base, id: "created", name: "Draft" }));
    });
    expect(checks).toBe(0);
  });
});
