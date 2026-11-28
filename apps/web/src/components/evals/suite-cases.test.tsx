import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SuiteCases } from "@/components/evals/suite-cases";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const t = messages.evals;
const session = {
  permissions: ["evals:manage"],
  user: { id: "person" },
  tenant: { id: "workspace" },
};
const saved = {
  id: "case",
  suiteId: "suite",
  name: "Greeting",
  input: { messages: ["Hello"], files: [], variables: {}, asUser: null, grounding: null },
  assertions: [{ type: "contains", value: "hello", caseSensitive: false }],
};
function show(initialTab: "cases" | "add" = "cases", suiteId = "suite") {
  const onSaved = vi.fn(),
    onClose = vi.fn(),
    onAccessLost = vi.fn();
  const view = render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <SuiteCases
        suiteId={suiteId}
        initialTab={initialTab}
        onSaved={onSaved}
        onClose={onClose}
        onAccessLost={onAccessLost}
      />
    </NextIntlClientProvider>,
  );
  return { ...view, onSaved, onClose, onAccessLost };
}
function tab(name: string) {
  fireEvent.mouseDown(screen.getByRole("tab", { name }), { button: 0, ctrlKey: false });
}
async function fill() {
  await screen.findByLabelText(t.caseName);
  fireEvent.change(screen.getByLabelText(t.caseName), { target: { value: " Greeting " } });
  fireEvent.change(screen.getByLabelText(t.message), { target: { value: "Hello" } });
  fireEvent.change(screen.getByLabelText(t.expect), { target: { value: "hello" } });
}
function save() {
  fireEvent.click(screen.getByRole("button", { name: t.saveCase }));
}
beforeEach(() => {
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json(session)),
    http.get("*/api/v1/eval-suites/suite", () =>
      HttpResponse.json({ id: "suite", name: "Release checks" }),
    ),
    http.get("*/api/v1/eval-suites/suite/cases", () => HttpResponse.json({ items: [saved] })),
    http.post("*/api/v1/eval-suites/suite/cases", () => HttpResponse.json(saved, { status: 201 })),
  );
});
afterEach(() => vi.restoreAllMocks());
describe("suite case inspection and authoring", () => {
  it("shows actual case details lazily as escaped inputs and checks without an evaluation verdict", async () => {
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () =>
        HttpResponse.json({
          items: [
            {
              ...saved,
              input: { messages: ["<script>saved input</script>"] },
              assertions: [{ type: "lexical_overlap", rubric: "Review" }],
            },
          ],
        }),
      ),
    );
    show();
    await screen.findByText(saved.name);
    expect(
      within(screen.getByRole("listitem")).getByText(t.assertionTypes.lexical_overlap),
    ).toBeTruthy();
    expect(screen.queryByText(t.copiedCaseHelp)).toBeNull();
    expect(screen.getByTitle(saved.id)).toBeTruthy();
    expect(screen.queryByText(/<script>saved input/)).toBeNull();
    fireEvent.click(screen.getByText(t.copiedCaseDetails));
    await screen.findByText(/<script>saved input/);
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getByRole("region", { name: t.copiedCaseDetails })).toBeTruthy();
    expect(screen.queryByText(/% passed/)).toBeNull();
  });
  it("displays valid file/context-only saved input with no prepared user turn", async () => {
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () =>
        HttpResponse.json({
          items: [
            {
              ...saved,
              input: {
                messages: [],
                files: ["file-id"],
                variables: { context: "actual saved variable" },
              },
            },
          ],
        }),
      ),
    );
    show();
    await screen.findByText(saved.name);
    fireEvent.click(screen.getByText(t.copiedCaseDetails));
    await screen.findByText(/file-id/);
    expect(screen.queryByRole("alert")).toBeNull();
  });
  it("provides an actual empty state with a direct form action and focus", async () => {
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () => HttpResponse.json({ items: [] })),
    );
    show();
    await screen.findByText(t.noSavedCases);
    fireEvent.click(screen.getByRole("button", { name: t.addCase }));
    await screen.findByLabelText(t.caseName);
    expect(document.activeElement).toBe(screen.getByLabelText(t.caseName));
    expect(screen.getByRole("button", { name: t.saveCase }).hasAttribute("disabled")).toBe(true);
  });
  it("does not request private suite/case data without management permission", async () => {
    const read = vi.fn(() => HttpResponse.json({ items: [] }));
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["evals:run"] })),
      http.get("*/api/v1/eval-suites/suite/cases", read),
    );
    const view = show();
    await waitFor(() => expect(view.onAccessLost).toHaveBeenCalledWith(t.denied));
    expect(read).not.toHaveBeenCalled();
    expect(screen.queryByText(t.noSavedCases)).toBeNull();
  });
  it.each([
    {},
    { items: [{ ...saved, suiteId: "other" }] },
    { items: [saved, saved] },
    { items: [{ ...saved, assertions: [] }] },
  ])("rejects incomplete or ambiguous metadata %j without inventing empty cases", async (value) => {
    server.use(http.get("*/api/v1/eval-suites/suite/cases", () => HttpResponse.json(value)));
    show();
    await screen.findByText(t.copyCaseMetadata);
    expect(screen.queryByText(t.noSavedCases)).toBeNull();
    expect(screen.queryByLabelText(t.caseName)).toBeNull();
  });
  it("does not render private case rows beside a mismatching suite identity", async () => {
    server.use(
      http.get("*/api/v1/eval-suites/suite", () =>
        HttpResponse.json({ id: "other", name: "Wrong suite" }),
      ),
    );
    show();
    await screen.findByText(t.caseSuiteMetadata);
    expect(screen.queryByText(saved.name)).toBeNull();
  });
  it("bounds 100,000 loaded cases, searches input/checks and combines type filters with reset/focus/page sizes", async () => {
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, i) => ({
            ...saved,
            id: `case-${i}`,
            name: `Check ${i}`,
            input: { messages: [i === 99999 ? "special source prompt" : "ordinary prompt"] },
            assertions: [
              i === 99999
                ? { type: "lexical_overlap", rubric: "unique rubric" }
                : { type: "contains", value: "hello", caseSensitive: false },
            ],
          })),
        }),
      ),
    );
    show();
    await screen.findByText("Check 0");
    expect(screen.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Check 25")).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: t.assertionType }), {
      target: { value: "lexical_overlap" },
    });
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "SPECIAL SOURCE" } });
    expect(screen.getByText("Check 99999")).toBeTruthy();
    expect(screen.getByRole("option", { name: t.assertionTypes.lexical_overlap })).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "no match" } });
    expect(screen.getByText(t.noCaseMatches)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: t.clearFilters }));
    expect(document.activeElement).toBe(screen.getByRole("searchbox"));
    expect(screen.getByText("Check 0")).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: "Rows per page" }), {
      target: { value: "100" },
    });
    expect(screen.getAllByRole("listitem")).toHaveLength(100);
  }, 15000);
  it("retains saved cases and filters after a failed refresh and recovers with a read", async () => {
    show();
    await screen.findByText(saved.name);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Greeting" } });
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () =>
        HttpResponse.json({ detail: "Cases unavailable" }, { status: 503 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: t.copyRefresh }));
    await screen.findByText("Cases unavailable");
    expect(screen.getByText(saved.name)).toBeTruthy();
    expect(screen.getByText(t.casesRetained)).toBeTruthy();
    expect((screen.getByRole("searchbox") as HTMLInputElement).value).toBe("Greeting");
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () => HttpResponse.json({ items: [saved] })),
    );
    fireEvent.click(screen.getByRole("button", { name: t.copyRefresh }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });
  it("clears protected input and cases after explicit access loss", async () => {
    const view = show();
    await screen.findByText(saved.name);
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () =>
        HttpResponse.json({ detail: "Access removed" }, { status: 403 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: t.copyRefresh }));
    await waitFor(() => expect(view.onAccessLost).toHaveBeenCalled());
    expect(screen.queryByText(saved.name)).toBeNull();
    expect(screen.queryByText(t.noSavedCases)).toBeNull();
  });
  it("preserves a selected check type when it disappears from the next read", async () => {
    show();
    await screen.findByText(saved.name);
    fireEvent.change(screen.getByRole("combobox", { name: t.assertionType }), {
      target: { value: "contains" },
    });
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () => HttpResponse.json({ items: [] })),
    );
    fireEvent.click(screen.getByRole("button", { name: t.copyRefresh }));
    await screen.findByText(t.noSavedCases);
    expect(
      (screen.getByRole("combobox", { name: t.assertionType }) as HTMLSelectElement).value,
    ).toBe("contains");
  });
  it("submits explicit name/message/contains/case sensitivity and confirms the normalized saved case", async () => {
    const writes: unknown[] = [];
    server.use(
      http.post("*/api/v1/eval-suites/suite/cases", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json(saved, { status: 201 });
      }),
    );
    const view = show("add");
    await fill();
    save();
    await screen.findByText(t.saved);
    expect(view.onSaved).toHaveBeenCalledTimes(1);
    expect(writes).toEqual([
      {
        name: "Greeting",
        input: { messages: ["Hello"] },
        assertions: [{ type: "contains", value: "hello", caseSensitive: false }],
      },
    ]);
    expect(screen.getByText(t.caseConfirmed)).toBeTruthy();
    expect(screen.getByRole("button", { name: t.saveCase }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: t.anotherCase }));
    expect((screen.getByLabelText(t.message) as HTMLTextAreaElement).value).toBe("");
    expect(document.activeElement).toBe(screen.getByLabelText(t.caseName));
  });
  it("retains exact prompt/expected whitespace and explicit case-sensitive intent", async () => {
    const writes: unknown[] = [];
    const value = {
      ...saved,
      input: { messages: ["  Hello\nteam  "] },
      assertions: [{ type: "contains", value: " Hello ", caseSensitive: true }],
    };
    server.use(
      http.post("*/api/v1/eval-suites/suite/cases", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json(value, { status: 201 });
      }),
      http.get("*/api/v1/eval-suites/suite/cases", () => HttpResponse.json({ items: [value] })),
    );
    show("add");
    await fill();
    fireEvent.change(screen.getByLabelText(t.message), { target: { value: "  Hello\nteam  " } });
    fireEvent.change(screen.getByLabelText(t.expect), { target: { value: " Hello " } });
    fireEvent.click(screen.getByRole("checkbox", { name: t.matchLetterCase }));
    save();
    await screen.findByText(t.saved);
    expect(writes).toEqual([
      {
        name: "Greeting",
        input: { messages: ["  Hello\nteam  "] },
        assertions: [{ type: "contains", value: " Hello ", caseSensitive: true }],
      },
    ]);
  });
  it("preserves a known acknowledgement on failed readback and verifies it later without replay", async () => {
    let writes = 0,
      reads = 0;
    server.use(
      http.post("*/api/v1/eval-suites/suite/cases", () => {
        writes++;
        return HttpResponse.json(saved, { status: 201 });
      }),
      http.get("*/api/v1/eval-suites/suite/cases", () => {
        reads++;
        return reads === 1
          ? HttpResponse.json({ items: [] })
          : HttpResponse.json({ detail: "Readback unavailable" }, { status: 503 });
      }),
    );
    const view = show("add");
    await fill();
    save();
    await screen.findByText("Readback unavailable");
    expect(screen.getByText(t.copyAcknowledged)).toBeTruthy();
    expect(screen.getByText("Case reference · case")).toBeTruthy();
    expect(view.onSaved).not.toHaveBeenCalled();
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () => HttpResponse.json({ items: [saved] })),
    );
    fireEvent.click(screen.getByRole("button", { name: t.copyRefresh }));
    await screen.findByText(t.saved);
    expect(writes).toBe(1);
    expect(view.onSaved).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: t.copyRefresh }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: t.copyRefresh }).hasAttribute("disabled")).toBe(
        false,
      ),
    );
    expect(view.onSaved).toHaveBeenCalledTimes(1);
  });
  it.each([
    { id: "case" },
    { ...saved, input: { messages: ["Wrong message"] } },
    { ...saved, assertions: [{ type: "contains", value: "hello", caseSensitive: true }] },
  ])("holds a mismatching receipt %j without success", async (value) => {
    server.use(
      http.post("*/api/v1/eval-suites/suite/cases", () =>
        HttpResponse.json(value, { status: 201 }),
      ),
    );
    const view = show("add");
    await fill();
    save();
    await screen.findByText(t.copyCaseMetadata);
    expect(screen.getByText(t.caseUnconfirmed)).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("alert")));
    expect(screen.getByRole("button", { name: t.saveCase }).hasAttribute("disabled")).toBe(true);
    expect(view.onSaved).not.toHaveBeenCalled();
  });
  it("holds an ambiguous create failure after refresh without deleting the editable draft", async () => {
    let writes = 0;
    server.use(
      http.post("*/api/v1/eval-suites/suite/cases", () => {
        writes++;
        return HttpResponse.json({ detail: "Create unavailable" }, { status: 503 });
      }),
    );
    show("add");
    await fill();
    save();
    await screen.findByText("Create unavailable");
    expect((screen.getByLabelText(t.message) as HTMLTextAreaElement).disabled).toBe(false);
    fireEvent.change(screen.getByLabelText(t.message), { target: { value: "New draft" } });
    fireEvent.click(screen.getByRole("button", { name: t.copyRefresh }));
    await screen.findByText(t.caseUnknownChecked);
    expect((screen.getByLabelText(t.message) as HTMLTextAreaElement).value).toBe("New draft");
    expect(screen.getByRole("button", { name: t.saveCase }).hasAttribute("disabled")).toBe(true);
    expect(writes).toBe(1);
  });
  it("releases only a definite refusal after read-only refresh and never replays it", async () => {
    let writes = 0;
    server.use(
      http.post("*/api/v1/eval-suites/suite/cases", () => {
        writes++;
        return HttpResponse.json(
          { code: "csrf_failed", detail: "Origin refused" },
          { status: 403 },
        );
      }),
    );
    show("add");
    await fill();
    save();
    await screen.findByText(messages.apiErrors.csrf);
    expect(screen.getByText(t.caseRefused)).toBeTruthy();
    expect((screen.getByLabelText(t.message) as HTMLTextAreaElement).value).toBe("Hello");
    fireEvent.click(screen.getByRole("button", { name: t.copyRefresh }));
    await screen.findByText(t.caseChecked);
    expect(screen.getByRole("button", { name: t.saveCase }).hasAttribute("disabled")).toBe(false);
    expect(writes).toBe(1);
  });
  it("checks the current session before a write and clears stale draft/content on an account change", async () => {
    const write = vi.fn(() => HttpResponse.json(saved));
    server.use(http.post("*/api/v1/eval-suites/suite/cases", write));
    const view = show("add");
    await fill();
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ ...session, user: { id: "another-person" } }),
      ),
    );
    save();
    await waitFor(() => expect(view.onAccessLost).toHaveBeenCalledWith(t.sessionChanged));
    expect(write).not.toHaveBeenCalled();
    expect(screen.queryByLabelText(t.message)).toBeNull();
  });
  it("does not restart reads on form edits or callback identity changes", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () => {
        reads++;
        return HttpResponse.json({ items: [saved] });
      }),
    );
    const view = show("add");
    await fill();
    view.rerender(
      <NextIntlClientProvider locale="en" messages={messages}>
        <SuiteCases
          suiteId="suite"
          initialTab="add"
          onClose={() => undefined}
          onSaved={() => undefined}
          onAccessLost={() => undefined}
        />
      </NextIntlClientProvider>,
    );
    await act(async () => {
      await new Promise((done) => setTimeout(done, 0));
    });
    expect(reads).toBe(1);
    expect((screen.getByLabelText(t.message) as HTMLTextAreaElement).value).toBe("Hello");
  });
  it("guards duplicate writes, preserves the payload while waiting and aborts late receipts on unmount", async () => {
    const nativeFetch = globalThis.fetch;
    let resolve!: (value: Response) => void;
    let signal: AbortSignal | null | undefined;
    let writes = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input) === "/api/v1/eval-suites/suite/cases" && init?.method === "POST") {
        writes++;
        signal = init.signal;
        return new Promise((done) => {
          resolve = done;
        });
      }
      return nativeFetch(input, init);
    });
    const view = show("add");
    await fill();
    save();
    save();
    await waitFor(() => expect(writes).toBe(1));
    expect(screen.getByText(t.copyCancelHelp)).toBeTruthy();
    expect(screen.getByRole("tab", { name: t.cases }).hasAttribute("disabled")).toBe(true);
    tab(t.cases);
    expect((screen.getByLabelText(t.message) as HTMLTextAreaElement).disabled).toBe(true);
    expect(screen.getByRole("button", { name: t.close }).hasAttribute("disabled")).toBe(false);
    view.unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => {
      resolve(Response.json(saved));
    });
    expect(view.onSaved).not.toHaveBeenCalled();
  });
  it("guards duplicate read refreshes, retains rows during refresh and aborts pending browser waits", async () => {
    const view = show();
    await screen.findByText(saved.name);
    const nativeFetch = globalThis.fetch;
    let resolve!: (value: Response) => void;
    let signal: AbortSignal | null | undefined;
    let reads = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input) === "/api/v1/eval-suites/suite/cases") {
        reads++;
        signal = init?.signal;
        return new Promise((done) => {
          resolve = done;
        });
      }
      return nativeFetch(input, init);
    });
    const refresh = screen.getByRole("button", { name: t.copyRefresh });
    fireEvent.click(refresh);
    fireEvent.click(refresh);
    await waitFor(() => expect(reads).toBe(1));
    expect(screen.getByText(saved.name)).toBeTruthy();
    expect(screen.getByText(t.refreshing)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: t.close }));
    expect(view.onClose).toHaveBeenCalledTimes(1);
    view.unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => {
      resolve(Response.json({ items: [saved] }));
    });
  });
  it("retains a draft and case filters while switching between inspection and authoring", async () => {
    show();
    await screen.findByText(saved.name);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Greeting" } });
    tab(t.addCase);
    await fill();
    tab(t.cases);
    expect((screen.getByRole("searchbox") as HTMLInputElement).value).toBe("Greeting");
    tab(t.addCase);
    expect((screen.getByLabelText(t.message) as HTMLTextAreaElement).value).toBe("Hello");
  });
});
