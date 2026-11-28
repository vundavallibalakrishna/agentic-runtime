import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PoliciesScreen } from "@/components/policies/policies-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/policies",
  useRouter: () => ({ push: () => undefined }),
  useParams: () => ({}),
}));

function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <PoliciesScreen />
    </NextIntlClientProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ permissions: ["policies:read", "policies:manage"] }),
    ),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/tenant", () => HttpResponse.json({ settings: {} })),
    http.get("*/api/v1/tenant/masking", () =>
      HttpResponse.json({ enabled: true, kinds: [], usesDefault: true }),
    ),
    http.get("*/api/v1/policies", () => HttpResponse.json({ items: [] })),
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("policy clarity", () => {
  it("keeps checking active rules separate from the unsaved draft", async () => {
    const checks: unknown[] = [];
    const writes: unknown[] = [];
    server.use(
      http.get("*/api/v1/policies", () =>
        HttpResponse.json({
          items: writes.length
            ? [{ id: "draft", name: "Outbound check", status: "draft", latestVersion: 1 }]
            : [],
        }),
      ),
      http.post("*/api/v1/policies:simulate", async ({ request }) => {
        checks.push(await request.json());
        return HttpResponse.json({ decision: "require_approval" });
      }),
      http.post("*/api/v1/policies", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json({ id: "draft", status: "draft" });
      }),
    );
    show();
    await waitFor(() =>
      expect((screen.getByLabelText("Name") as HTMLInputElement).disabled).toBe(false),
    );
    const draftTool = within(screen.getByRole("complementary")).getByLabelText("Tool", {
      exact: true,
    });
    const checkTool = within(
      screen.getByRole("region", { name: "Check active policies" }),
    ).getByLabelText("Tool", { exact: true });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Outbound check" } });
    fireEvent.change(draftTool, { target: { value: "connector.write" } });
    fireEvent.change(screen.getByLabelText("Message the assistant will see"), {
      target: { value: "Ask before writing" },
    });
    expect((screen.getByRole("combobox", { name: "Effect" }) as HTMLSelectElement).value).toBe(
      "requireApproval",
    );
    expect(screen.getByRole("button", { name: "Check tool" }).hasAttribute("disabled")).toBe(true);
    fireEvent.change(checkTool, { target: { value: "connector.read" } });
    fireEvent.click(screen.getByRole("button", { name: "Check tool" }));
    expect(await screen.findByText("Decision: Require approval")).toBeTruthy();
    expect(checks).toEqual([{ toolQualifiedName: "connector.read", args: {} }]);
    expect(writes).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    expect(await screen.findByText(messages.policies.saved)).toBeTruthy();
    expect(writes).toEqual([
      {
        name: "Outbound check",
        description: "Ask before writing",
        document: {
          rules: [
            {
              id: "rule-1",
              effect: "requireApproval",
              message: "Ask before writing",
              match: { tools: ["connector.write"] },
            },
          ],
        },
      },
    ]);
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("");
  });

  it("bounds policy rows and filters before pagination", async () => {
    server.use(
      http.get("*/api/v1/policies", () =>
        HttpResponse.json({
          items: Array.from({ length: 30 }, (_, i) => ({
            id: `policy-${i}`,
            name: `Rule ${i}`,
            status: i === 29 ? "active" : "draft",
          })),
        }),
      ),
    );
    show();
    await screen.findByRole("heading", { name: "Rule 0" });
    expect(screen.queryByRole("heading", { name: "Rule 29" })).toBeNull();
    fireEvent.change(screen.getByLabelText(messages.policies.search), {
      target: { value: "policy-29" },
    });
    expect(screen.getByRole("heading", { name: "Rule 29" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText(messages.policies.search), {
      target: { value: "missing" },
    });
    expect(screen.getByText(messages.policies.noMatches)).toBeTruthy();
  });

  it("disables authoring for readers while preserving the policy check", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["policies:read"] }),
      ),
    );
    show();
    await screen.findByText(messages.policies.empty);
    expect(screen.getByText(messages.policies.readOnly)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save policy" }).closest("fieldset")?.disabled).toBe(
      true,
    );
    expect(screen.queryByRole("button", { name: "Activate" })).toBeNull();
  });
});

const draft = {
  id: "policy",
  name: "Workspace rules",
  status: "draft",
  latestVersion: 3,
  activeVersion: null,
};
function catalogue(items: object[] = [draft]) {
  server.use(http.get("*/api/v1/policies", () => HttpResponse.json({ items })));
}
function fillDraft() {
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "My draft" } });
  fireEvent.change(
    within(screen.getByRole("complementary")).getByLabelText("Tool", { exact: true }),
    { target: { value: "workspace.write" } },
  );
  fireEvent.change(screen.getByLabelText("Message the assistant will see"), {
    target: { value: "Ask before writing" },
  });
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
function answer(body: unknown) {
  return new Response(JSON.stringify(body), { headers: { "content-type": "application/json" } });
}

describe("policy action and context states", () => {
  it("preserves drafts when moving among distinct settings tabs", async () => {
    show();
    await screen.findByText(messages.policies.empty);
    fillDraft();
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Website access" }), {
      button: 0,
      ctrlKey: false,
    });
    expect(screen.getByRole("tab", { name: "Website access" }).getAttribute("aria-selected")).toBe(
      "true",
    );
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Data masking" }), {
      button: 0,
      ctrlKey: false,
    });
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Tool rules" }), {
      button: 0,
      ctrlKey: false,
    });
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("My draft");
  });
  it("searches and filters 100,000 loaded policies before paging and clears both filters", async () => {
    catalogue(
      Array.from({ length: 100_000 }, (_, n) => ({
        ...draft,
        id: `policy-${n}`,
        name: `Policy ${n}`,
        status: n % 2 ? "active" : "draft",
      })),
    );
    show();
    await screen.findByRole("heading", { name: "Policy 0" });
    expect(screen.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "policy-99999" } });
    expect(screen.getByRole("heading", { name: "Policy 99999" })).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: "Status" }), {
      target: { value: "draft" },
    });
    expect(screen.getByText(messages.policies.noMatches)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(25);
    expect((screen.getByRole("searchbox") as HTMLInputElement).value).toBe("");
  });
  it("guards same-frame saves and requires read-only recovery after an incomplete receipt", async () => {
    const receipt = deferred<Response>();
    const nativeFetch = globalThis.fetch;
    let writes = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input).endsWith("/policies") && init?.method === "POST") {
          writes++;
          return receipt.promise;
        }
        return nativeFetch(input, init);
      }),
    );
    show();
    await screen.findByText(messages.policies.empty);
    fillDraft();
    const form = screen
      .getByRole("button", { name: "Save policy" })
      .closest("form") as HTMLFormElement;
    act(() => {
      fireEvent.submit(form);
      fireEvent.submit(form);
    });
    expect(writes).toBe(1);
    await act(async () => receipt.resolve(answer({})));
    await screen.findByText(messages.policies.saveUnconfirmed);
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("My draft");
    expect(screen.getByRole("button", { name: "Save policy" }).matches(":disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Refresh policies" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save policy" }).matches(":disabled")).toBe(false),
    );
    expect(writes).toBe(1);
  });
  it("retains an acknowledged draft save through list failure without repeating it", async () => {
    let saved = false;
    let readsFail = true;
    let writes = 0;
    server.use(
      http.get("*/api/v1/policies", () =>
        saved && readsFail
          ? HttpResponse.json({ detail: "catalogue unavailable" }, { status: 503 })
          : HttpResponse.json({ items: saved ? [draft] : [] }),
      ),
      http.post("*/api/v1/policies", () => {
        saved = true;
        writes++;
        return HttpResponse.json({ ...draft });
      }),
    );
    show();
    await screen.findByText(messages.policies.empty);
    fillDraft();
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await screen.findByText("catalogue unavailable");
    expect(screen.getByText(messages.policies.saved)).toBeTruthy();
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("");
    readsFail = false;
    fireEvent.click(screen.getByRole("button", { name: "Refresh policies" }));
    await screen.findByRole("heading", { name: draft.name });
    expect(writes).toBe(1);
  });
  it.each([undefined, 0, -1, 1.5, "3"])(
    "does not guess the missing or invalid activation version %s",
    async (latestVersion) => {
      catalogue([{ ...draft, latestVersion }]);
      show();
      const activate = await screen.findByRole("button", { name: "Activate" });
      expect(activate.matches(":disabled")).toBe(true);
      expect(screen.getByText(messages.policies.versionUnavailable)).toBeTruthy();
    },
  );
  it("does not activate after session confirmation is refused", async () => {
    let activations = 0;
    catalogue();
    server.use(
      http.post("*/api/v1/auth/step-up", () => HttpResponse.json({ steppedUp: "false" })),
      http.post("*/api/v1/policies/policy:activate", () => {
        activations++;
        return HttpResponse.json({});
      }),
    );
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Activate" }));
    await screen.findByText(messages.detail.stepUpUnconfirmed);
    expect(activations).toBe(0);
    expect(screen.getByRole("button", { name: "Activate" }).matches(":disabled")).toBe(false);
  });
  it("confirms the actual activation version and holds further writes until a failed save is read back", async () => {
    let activations = 0;
    catalogue();
    server.use(
      http.post("*/api/v1/auth/step-up", () => HttpResponse.json({ steppedUp: "true" })),
      http.post("*/api/v1/policies/policy:activate", async ({ request }) => {
        activations++;
        expect(await request.json()).toEqual({ version: 3 });
        return HttpResponse.json({ ...draft, status: "active", activeVersion: 2 });
      }),
    );
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Activate" }));
    await screen.findByText(messages.policies.activationUnconfirmed);
    expect(screen.getByRole("button", { name: "Activate" }).matches(":disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Refresh policies" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Activate" }).matches(":disabled")).toBe(false),
    );
    expect(activations).toBe(1);
  });
  it("aborts a pending session confirmation on unmount before activation", async () => {
    catalogue();
    const pending = deferred<Response>();
    const nativeFetch = globalThis.fetch;
    let signal: AbortSignal | null | undefined;
    let activations = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input).endsWith("/step-up")) {
          signal = init?.signal;
          return pending.promise;
        }
        if (String(input).endsWith(":activate")) {
          activations++;
          return Promise.resolve(answer({}));
        }
        return nativeFetch(input, init);
      }),
    );
    const rendered = show();
    fireEvent.click(await screen.findByRole("button", { name: "Activate" }));
    await waitFor(() => expect(signal).toBeTruthy());
    rendered.unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => pending.resolve(answer({ steppedUp: "true" })));
    expect(activations).toBe(0);
  });
  it("disables the simple fields when the advanced document supplies the rules and rejects non-object JSON locally", async () => {
    let writes = 0;
    server.use(
      http.post("*/api/v1/policies", () => {
        writes++;
        return HttpResponse.json({});
      }),
    );
    show();
    await screen.findByText(messages.policies.empty);
    fillDraft();
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    fireEvent.change(screen.getByLabelText("Rule document (JSON)"), { target: { value: "[]" } });
    expect(screen.getByRole("combobox", { name: "Effect" }).matches(":disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await screen.findByText(messages.policies.documentObject);
    expect(writes).toBe(0);
    fireEvent.change(screen.getByLabelText("Rule document (JSON)"), { target: { value: "" } });
    expect(screen.getByRole("combobox", { name: "Effect" }).matches(":disabled")).toBe(false);
  });
  it("keeps a check error local to the active-policy checker without discarding the draft or list", async () => {
    catalogue();
    server.use(
      http.post("*/api/v1/policies:simulate", () =>
        HttpResponse.json({ detail: "simulation unavailable" }, { status: 503 }),
      ),
    );
    show();
    await screen.findByRole("heading", { name: draft.name });
    fillDraft();
    const checker = within(screen.getByRole("region", { name: "Check active policies" }));
    fireEvent.change(checker.getByLabelText("Tool"), { target: { value: "workspace.read" } });
    fireEvent.click(checker.getByRole("button", { name: "Check tool" }));
    expect(await checker.findByText("simulation unavailable")).toBeTruthy();
    expect(screen.getByRole("heading", { name: draft.name })).toBeTruthy();
    expect((screen.getByLabelText("Name") as HTMLInputElement).value).toBe("My draft");
    expect(screen.getByRole("button", { name: "Save policy" }).matches(":disabled")).toBe(false);
  });
});

describe("policy receipt boundaries", () => {
  it("retains a named activation receipt when metadata refresh fails", async () => {
    let activated = false;
    let writes = 0;
    server.use(
      http.get("*/api/v1/policies", () =>
        activated
          ? HttpResponse.json({ detail: "policy metadata unavailable" }, { status: 503 })
          : HttpResponse.json({ items: [draft] }),
      ),
      http.post("*/api/v1/auth/step-up", () => HttpResponse.json({ steppedUp: true })),
      http.post("*/api/v1/policies/policy:activate", () => {
        writes++;
        activated = true;
        return HttpResponse.json({ ...draft, status: "active", activeVersion: 3 });
      }),
    );
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Activate" }));
    await screen.findByText("policy metadata unavailable");
    expect(screen.getByText("Activation recorded for Workspace rules, version 3.")).toBeTruthy();
    expect(writes).toBe(1);
    expect(screen.getByRole("button", { name: "Activate" }).matches(":disabled")).toBe(true);
  });
  it("does not refresh or update a discarded view after a late create receipt", async () => {
    const pending = deferred<Response>();
    const nativeFetch = globalThis.fetch;
    let signal: AbortSignal | null | undefined;
    let reads = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input).endsWith("/policies") && init?.method === "POST") {
          signal = init.signal;
          return pending.promise;
        }
        if (String(input).endsWith("/policies")) reads++;
        return nativeFetch(input, init);
      }),
    );
    const rendered = show();
    await screen.findByText(messages.policies.empty);
    fillDraft();
    fireEvent.click(screen.getByRole("button", { name: "Save policy" }));
    await waitFor(() => expect(signal).toBeTruthy());
    const initialReads = reads;
    rendered.unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => pending.resolve(answer(draft)));
    expect(reads).toBe(initialReads);
  });
  it("reports an empty successful check response instead of a blank or invented decision", async () => {
    server.use(
      http.post("*/api/v1/policies:simulate", () => new HttpResponse(null, { status: 204 })),
    );
    show();
    await screen.findByText(messages.policies.empty);
    const checker = within(screen.getByRole("region", { name: "Check active policies" }));
    fireEvent.change(checker.getByLabelText("Tool"), { target: { value: "workspace.read" } });
    fireEvent.click(checker.getByRole("button", { name: "Check tool" }));
    expect(await checker.findByText(messages.policies.checkUnconfirmed)).toBeTruthy();
    expect(checker.queryByText(/^Decision:/)).toBeNull();
  });
  it("requires a successful initial list read before allowing creation or simulation", async () => {
    let fail = true;
    server.use(
      http.get("*/api/v1/policies", () =>
        fail
          ? HttpResponse.json({ detail: "policy list unavailable" }, { status: 503 })
          : HttpResponse.json({ items: [] }),
      ),
    );
    show();
    await screen.findByText("policy list unavailable");
    expect(screen.getByRole("button", { name: "Save policy" }).matches(":disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Check tool" }).matches(":disabled")).toBe(true);
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Refresh policies" }));
    await screen.findByText(messages.policies.empty);
    expect(screen.getByLabelText("Name").matches(":disabled")).toBe(false);
  });
});
