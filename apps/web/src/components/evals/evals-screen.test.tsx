import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EvalsScreen } from "@/components/evals/evals-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/evals",
  useRouter: () => ({ push: () => undefined }),
  useParams: () => ({ id: "agent" }),
}));

function suiteRow(overrides: Record<string, unknown> = {}) {
  return {
    id: "suite",
    name: "Release",
    description: "",
    kind: "functional",
    caseCount: 1,
    agent: null,
    gate: { required: false, minPassRate: 0.9, maxRegressionPct: 5, mustPassTags: ["safety"] },
    lastRun: null,
    ...overrides,
  };
}

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("evaluation screen", () => {
  beforeEach(() => {
    server.use(http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })));
  });

  afterEach(() => {
    cleanup();
  });

  it("shows an empty library and the feedback inbox", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["evals:manage"], user: { displayName: "Admin" } }),
      ),
      http.get("*/api/v1/eval-suites", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/feedback", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<EvalsScreen admin />));
    expect(await screen.findByRole("heading", { name: "Evaluation library" })).toBeTruthy();
    expect(await screen.findByText("No suites yet. Create one to start.")).toBeTruthy();
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Feedback inbox" }), {
      button: 0,
      ctrlKey: false,
    });
    expect(await screen.findByText("No feedback yet.")).toBeTruthy();
  });
  it("creates a named suite with inherited settings and verifies its actual saved receipt", async () => {
    const writes: unknown[] = [];
    let created = false;
    const saved = suiteRow({ name: "Release checks" });
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["evals:manage"] })),
      http.get("*/api/v1/eval-suites", () => HttpResponse.json({ items: created ? [saved] : [] })),
      http.get("*/api/v1/eval-suites/suite", () => HttpResponse.json(saved)),
      http.post("*/api/v1/eval-suites", async ({ request }) => {
        writes.push(await request.json());
        created = true;
        return HttpResponse.json(saved, { status: 201 });
      }),
    );
    render(wrap(<EvalsScreen />));
    const create = await screen.findByRole("button", { name: "New suite" });
    expect(create.hasAttribute("disabled")).toBe(true);
    await screen.findByText("No suites yet. Create one to start.");
    fireEvent.change(screen.getByLabelText(messages.evals.name), {
      target: { value: "  Release checks  " },
    });
    fireEvent.click(create);
    expect(await screen.findByText(messages.evals.suiteSaved)).toBeTruthy();
    expect(writes).toEqual([{ name: "Release checks", agentId: null }]);
  });

  it("keeps separate case inputs after refusal and confirms an explicitly retried save", async () => {
    const writes: unknown[] = [];
    const saved = {
      id: "case",
      suiteId: "suite",
      name: "Greeting",
      input: { messages: ["Say hello to the team"] },
      assertions: [{ type: "contains", value: "hello", caseSensitive: false }],
    };
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["evals:manage"] })),
      http.get("*/api/v1/eval-suites", () =>
        HttpResponse.json({ items: [suiteRow({ name: "Release checks" })] }),
      ),
      http.get("*/api/v1/eval-suites/suite", () =>
        HttpResponse.json({ id: "suite", name: "Release checks" }),
      ),
      http.get("*/api/v1/eval-suites/suite/cases", () =>
        HttpResponse.json({ items: writes.length > 1 ? [saved] : [] }),
      ),
      http.post("*/api/v1/eval-suites/suite/cases", async ({ request }) => {
        writes.push(await request.json());
        return writes.length === 1
          ? HttpResponse.json({ code: "csrf_failed", detail: "Origin refused" }, { status: 403 })
          : HttpResponse.json(saved, { status: 201 });
      }),
    );
    render(wrap(<EvalsScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Add case to Release checks" }));
    const dialog = within(screen.getByRole("dialog"));
    await dialog.findByLabelText("Case name");
    expect(dialog.getByRole("button", { name: "Save case" }).hasAttribute("disabled")).toBe(true);
    fireEvent.change(dialog.getByLabelText("Case name"), { target: { value: "Greeting" } });
    fireEvent.change(dialog.getByLabelText("User message"), {
      target: { value: "Say hello to the team" },
    });
    fireEvent.change(dialog.getByLabelText("Reply must contain"), { target: { value: "hello" } });
    fireEvent.click(dialog.getByRole("button", { name: "Save case" }));
    await dialog.findByRole("alert");
    expect((dialog.getByLabelText("User message") as HTMLTextAreaElement).value).toBe(
      "Say hello to the team",
    );
    expect(dialog.getByRole("button", { name: "Save case" }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(dialog.getByRole("button", { name: messages.evals.copyRefresh }));
    await dialog.findByText(messages.evals.caseChecked);
    fireEvent.click(dialog.getByRole("button", { name: "Save case" }));
    await dialog.findByText("Case saved.");
    expect(writes).toEqual(
      Array(2).fill({
        name: "Greeting",
        input: { messages: ["Say hello to the team"] },
        assertions: [{ type: "contains", value: "hello", caseSensitive: false }],
      }),
    );
    fireEvent.click(dialog.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("imports a case file as text into a suite and reads the list again", async () => {
    let imported = "";
    let reads = 0;
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["evals:manage"] })),
      http.get("*/api/v1/eval-suites", () => {
        reads++;
        return HttpResponse.json({
          items: [suiteRow({ name: "Website questions", caseCount: reads > 1 ? 2 : 1 })],
        });
      }),
      http.post("*/api/v1/eval-suites/suite/cases:import", async ({ request }) => {
        const body = (await request.json()) as { content?: string };
        imported = body.content ?? "";
        return HttpResponse.json({ imported: 1, errors: [] });
      }),
    );
    render(wrap(<EvalsScreen />));
    expect(await screen.findByRole("heading", { name: "Website questions" })).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Import cases into Website questions" }),
    ).toBeTruthy();
    const input = screen.getByLabelText("Import cases", { selector: "input" });
    const file = new File(['{"name":"a","input":{"messages":["hi"]}}'], "cases.jsonl");
    Object.defineProperty(file, "text", { value: () => Promise.resolve('{"name":"a"}') });
    fireEvent.change(input, { target: { files: [file] } });
    expect(await screen.findByText("1 case imported.")).toBeTruthy();
    expect(imported).toBe('{"name":"a"}');
    await waitFor(() => expect(reads).toBe(2));
  });

  it("says why an import was refused", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["evals:manage"] })),
      http.get("*/api/v1/eval-suites", () => HttpResponse.json({ items: [suiteRow()] })),
      http.post("*/api/v1/eval-suites/suite/cases:import", () =>
        HttpResponse.json({ detail: "The file is not valid JSONL." }, { status: 422 }),
      ),
    );
    render(wrap(<EvalsScreen />));
    await screen.findByRole("heading", { name: "Release" });
    const file = new File(["not json"], "cases.jsonl");
    Object.defineProperty(file, "text", { value: () => Promise.resolve("not json") });
    fireEvent.change(screen.getByLabelText("Import cases", { selector: "input" }), {
      target: { files: [file] },
    });
    expect(await screen.findByText("The file is not valid JSONL.")).toBeTruthy();
  });

  it("does not request management-only reads for a run-only role", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["evals:run"] })),
      http.get("*/api/v1/eval-suites", () => {
        reads++;
        return HttpResponse.json({ items: [] });
      }),
    );
    render(wrap(<EvalsScreen />));
    expect(await screen.findByText(messages.evals.denied)).toBeTruthy();
    expect(reads).toBe(0);
    expect(screen.queryByRole("button", { name: "Run suite" })).toBeNull();
  });
  it("paginates every suite kind and resets the page when searching", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["evals:manage"] })),
      http.get("*/api/v1/eval-suites", () =>
        HttpResponse.json({
          items: Array.from({ length: 30 }, (_, i) =>
            suiteRow({
              id: `suite-${i}`,
              name: `Checks ${i}`,
              kind: i === 29 ? "safety" : "retrieval",
            }),
          ),
        }),
      ),
    );
    render(wrap(<EvalsScreen />));
    await screen.findByRole("heading", { name: "Checks 0" });
    expect(screen.queryByRole("heading", { name: "Checks 29" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "Checks 29" })).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Checks 0" } });
    expect(screen.getByRole("heading", { name: "Checks 0" })).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "" } });
    fireEvent.change(
      within(screen.getByRole("group", { name: messages.evals.suiteFilters })).getByLabelText(
        "Kind",
      ),
      { target: { value: "safety" } },
    );
    expect(screen.getByRole("heading", { name: "Checks 29" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Checks 0" })).toBeNull();
  });

  it("requests the chosen agent/version reference and opens its saved run", async () => {
    const writes: unknown[] = [];
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["evals:manage", "evals:run", "agents:read"] }),
      ),
      http.get("*/api/v1/eval-suites", () => HttpResponse.json({ items: [suiteRow()] })),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({ items: [{ id: "chosen", name: "Support" }] }),
      ),
      http.get("*/api/v1/eval-suites/suite", () => HttpResponse.json(suiteRow())),
      http.get("*/api/v1/agents/chosen", () =>
        HttpResponse.json({
          id: "chosen",
          name: "Support",
          published: { id: "published", version: 1, etag: "saved-published" },
          draft: { id: "version", version: 2, etag: "saved-draft" },
        }),
      ),
      http.get("*/api/v1/agents/chosen/versions/2", () =>
        HttpResponse.json({ id: "version", version: 2, agentId: "chosen", etag: "saved-draft" }),
      ),
      http.post("*/api/v1/eval-suites/suite:run", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json(
          {
            id: "saved-run",
            suiteId: "suite",
            agentId: "chosen",
            agentVersionId: "version",
            status: "queued",
          },
          { status: 202 },
        );
      }),
      http.get("*/api/v1/eval-runs", () =>
        HttpResponse.json({ items: [{ id: "saved-run", suiteId: "suite", status: "completed" }] }),
      ),
      http.get("*/api/v1/eval-runs/saved-run", () =>
        HttpResponse.json({
          id: "saved-run",
          suiteId: "suite",
          agentId: "chosen",
          agentVersionId: "version",
          status: "completed",
          summary: { passRate: 1 },
        }),
      ),
      http.get("*/api/v1/eval-runs/saved-run/results", () =>
        HttpResponse.json({
          items: [
            {
              case: { id: "case", name: "Greeting" },
              passed: true,
              outputText: "Hello team",
              runId: "case-run",
            },
          ],
        }),
      ),
    );
    render(wrap(<EvalsScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Run suite" }));
    expect(
      screen.getByRole("button", { name: messages.evals.startRun }).hasAttribute("disabled"),
    ).toBe(true);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^Agent to evaluate:/ }).matches(":disabled")).toBe(
        false,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: /^Agent to evaluate:/ }));
    fireEvent.click(await screen.findByText("Support"));
    await screen.findByRole("option", { name: "Draft · Version 2" });
    fireEvent.change(screen.getByLabelText(messages.evals.version), {
      target: { value: "version" },
    });
    fireEvent.click(screen.getByRole("button", { name: messages.evals.startRun }));
    const results = within(await screen.findByRole("dialog", { name: messages.evals.results }));
    expect(await results.findByText("Greeting · Passed")).toBeTruthy();
    expect(writes).toEqual([{ agentId: "chosen", agentVersionRef: "2" }]);
    expect(
      results.getByRole("link", { name: messages.evals.openCaseRun }).getAttribute("href"),
    ).toBe("/runs/case-run");
    fireEvent.change(results.getByLabelText(messages.evals.outcome), {
      target: { value: "failed" },
    });
    expect(results.getByText(messages.evals.noResultMatches)).toBeTruthy();
    fireEvent.click(results.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    fireEvent.click(await screen.findByRole("button", { name: "View results for run saved-run" }));
    expect(await screen.findByText("Greeting · Passed")).toBeTruthy();
  });

  it("requires an explicit feedback destination and retains it after failure", async () => {
    const writes: unknown[] = [];
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["evals:manage", "chat:use"], user: { id: "person" } }),
      ),
      http.get("*/api/v1/eval-suites", () => HttpResponse.json({ items: [suiteRow()] })),
      http.get("*/api/v1/conversations/conversation", () =>
        HttpResponse.json({ id: "conversation", userId: "person", messages: [{ id: "message" }] }),
      ),
      http.get("*/api/v1/eval-suites/suite/cases", () =>
        HttpResponse.json({
          items:
            writes.length > 1
              ? [
                  {
                    id: "case",
                    suiteId: "suite",
                    name: "Copied case",
                    input: { messages: ["Hello"] },
                    assertions: [{ type: "contains", value: "Hello" }],
                  },
                ]
              : [],
        }),
      ),
      http.get("*/api/v1/feedback", () =>
        HttpResponse.json({
          items: [
            {
              messageId: "message",
              conversationId: "conversation",
              comment: "Review this answer",
              rating: "down",
            },
          ],
        }),
      ),
      http.post("*/api/v1/eval-suites/suite/cases:from-conversation", async ({ request }) => {
        writes.push(await request.json());
        return writes.length === 1
          ? HttpResponse.json({ detail: "Origin refused", code: "csrf_failed" }, { status: 403 })
          : HttpResponse.json({
              id: "case",
              suiteId: "suite",
              name: "Copied case",
              input: { messages: ["Hello"] },
              assertions: [{ type: "contains", value: "Hello" }],
            });
      }),
    );
    render(wrap(<EvalsScreen admin />));
    await screen.findByRole("heading", { name: "Release" });
    fireEvent.mouseDown(screen.getByRole("tab", { name: messages.evals.feedback }), {
      button: 0,
      ctrlKey: false,
    });
    fireEvent.click(
      await screen.findByRole("button", { name: "Add feedback message message to a suite" }),
    );
    let dialog = within(screen.getByRole("dialog", { name: messages.evals.addFeedback }));
    expect(
      dialog.getByRole("button", { name: messages.evals.addFeedback }).hasAttribute("disabled"),
    ).toBe(true);
    await waitFor(() =>
      expect(
        dialog.getByRole("button", { name: /^Destination suite:/ }).hasAttribute("disabled"),
      ).toBe(false),
    );
    fireEvent.click(dialog.getByRole("button", { name: /^Destination suite:/ }));
    fireEvent.click(
      await within(
        screen.getByRole("dialog", { name: messages.evals.destinationSuite }),
      ).findByText("Release"),
    );
    dialog = within(screen.getByRole("dialog", { name: messages.evals.addFeedback }));
    fireEvent.click(dialog.getByRole("button", { name: messages.evals.addFeedback }));
    expect(await dialog.findByRole("alert")).toBeTruthy();
    expect(dialog.getByRole("button", { name: /Destination suite: Release/ })).toBeTruthy();
    fireEvent.click(dialog.getByRole("button", { name: messages.evals.copyRefresh }));
    await dialog.findByText(messages.evals.copyChecked);
    fireEvent.click(dialog.getByRole("button", { name: messages.evals.addFeedback }));
    expect(await screen.findByText(messages.evals.added)).toBeTruthy();
    expect(writes).toEqual(Array(2).fill({ conversationId: "conversation", messageId: "message" }));
  });
});
