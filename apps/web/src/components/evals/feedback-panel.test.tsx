import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EvalFeedbackPanel } from "@/components/evals/feedback-panel";
import { formatDateTime } from "@/lib/format";
import { clearCachedSession } from "@/lib/session";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const t = messages.evals;
const session = {
  permissions: ["evals:manage", "chat:use"],
  user: { id: "person" },
  tenant: { id: "workspace" },
};
const feedback = {
  messageId: "message",
  conversationId: "conversation",
  rating: "down",
  agent: { name: "Support" },
  comment: "Needs more context",
  createdAt: "2026-11-10T12:00:00Z",
};
const source = { id: "conversation", userId: "person", messages: [{ id: "message" }] };
const saved = {
  id: "case",
  suiteId: "suite",
  name: "From conversation",
  input: { messages: ["Hello"] },
  assertions: [{ type: "lexical_overlap", rubric: "<script>saved text</script>", threshold: 0.5 }],
};
function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <EvalFeedbackPanel />
    </NextIntlClientProvider>,
  );
}
async function open() {
  fireEvent.click(
    await screen.findByRole("button", { name: "Add feedback message message to a suite" }),
  );
  const modal = within(await screen.findByRole("dialog", { name: t.addFeedback }));
  await waitFor(() =>
    expect(
      modal.getByRole("button", { name: /^Destination suite:/ }).hasAttribute("disabled"),
    ).toBe(false),
  );
  return modal;
}
async function choose(modal: ReturnType<typeof within>, name = "Release") {
  fireEvent.click(modal.getByRole("button", { name: /^Destination suite:/ }));
  const picker = within(await screen.findByRole("dialog", { name: t.destinationSuite }));
  fireEvent.click(await picker.findByText(name));
  await waitFor(() =>
    expect(screen.queryByRole("dialog", { name: t.destinationSuite })).toBeNull(),
  );
  await waitFor(() =>
    expect(document.activeElement).toBe(modal.getByRole("button", { name: /^Destination suite:/ })),
  );
}
beforeEach(() => {
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json(session)),
    http.get("*/api/v1/feedback", () => HttpResponse.json({ items: [feedback] })),
    http.get("*/api/v1/conversations/conversation", () => HttpResponse.json(source)),
    http.get("*/api/v1/eval-suites", () =>
      HttpResponse.json({
        items: [
          { id: "suite", name: "Release" },
          { id: "second", name: "Other suite" },
        ],
      }),
    ),
    http.get("*/api/v1/eval-suites/suite/cases", () => HttpResponse.json({ items: [saved] })),
    http.post("*/api/v1/eval-suites/suite/cases:from-conversation", () =>
      HttpResponse.json(saved, { status: 201 }),
    ),
  );
});
afterEach(() => vi.restoreAllMocks());
describe("evaluation feedback inbox", () => {
  it("shows saved rating, comment, scoped chat link and a zone-labelled instant", async () => {
    show();
    await screen.findByText(feedback.comment);
    expect(
      screen.getByText(formatDateTime(feedback.createdAt, "en")).getAttribute("datetime"),
    ).toBe(feedback.createdAt);
    expect(screen.getByRole("region", { name: t.feedbackComment })).toBeTruthy();
    expect(screen.getByRole("link", { name: t.openConversation }).getAttribute("href")).toBe(
      "/chat?conversation=conversation",
    );
  });
  it("does not load private feedback for a run-only role", async () => {
    const read = vi.fn(() => HttpResponse.json({ items: [feedback] }));
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["evals:run"] })),
      http.get("*/api/v1/feedback", read),
    );
    show();
    await screen.findByText(t.denied);
    expect(read).not.toHaveBeenCalled();
    expect(screen.queryByText(t.noFeedback)).toBeNull();
  });
  it.each([
    {},
    { items: [{ ...feedback, rating: null }] },
    { items: [{ ...feedback, comment: { text: "bad" } }] },
    { items: [{ ...feedback, createdAt: "2026-11-10T12:00:00" }] },
  ])("does not label malformed metadata as an empty inbox %j", async (value) => {
    server.use(http.get("*/api/v1/feedback", () => HttpResponse.json(value)));
    show();
    await screen.findByText(t.feedbackMetadata);
    expect(screen.queryByText(t.noFeedback)).toBeNull();
  });
  it("retains actual metadata and combined filters after a failed refresh", async () => {
    show();
    await screen.findByText(feedback.comment);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "context" } });
    fireEvent.change(screen.getByRole("combobox", { name: t.rating }), {
      target: { value: "down" },
    });
    server.use(
      http.get("*/api/v1/feedback", () =>
        HttpResponse.json({ detail: "Feedback unavailable" }, { status: 503 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await screen.findByText("Feedback unavailable");
    expect(screen.getByText(t.feedbackRetained)).toBeTruthy();
    expect(screen.getByText(feedback.comment)).toBeTruthy();
    server.use(http.get("*/api/v1/feedback", () => HttpResponse.json({ items: [] })));
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await screen.findByText(t.noFeedback);
    expect((screen.getByRole("combobox", { name: t.rating }) as HTMLSelectElement).value).toBe(
      "down",
    );
  });
  it("clears protected rows after explicit read access loss", async () => {
    show();
    await screen.findByText(feedback.comment);
    server.use(
      http.get("*/api/v1/feedback", () =>
        HttpResponse.json({ detail: "Access removed" }, { status: 403 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await screen.findByRole("alert");
    expect(screen.queryByText(feedback.comment)).toBeNull();
    expect(screen.queryByText(t.noFeedback)).toBeNull();
  });
  it("requires chat access and a current user identity before source selection", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["evals:manage"], user: { id: "person" } }),
      ),
    );
    show();
    await screen.findByText(feedback.comment);
    expect(
      screen
        .getByRole("button", { name: "Add feedback message message to a suite" })
        .hasAttribute("disabled"),
    ).toBe(true);
    expect(screen.getByText(t.feedbackSourceAccess)).toBeTruthy();
  });
  it("shows metadata-only feedback but withholds controls for a deleted source", async () => {
    server.use(
      http.get("*/api/v1/feedback", () =>
        HttpResponse.json({ items: [{ ...feedback, conversationId: null }] }),
      ),
    );
    show();
    await screen.findByText(feedback.comment);
    expect(
      screen
        .getByRole("button", { name: "Add feedback message message to a suite" })
        .hasAttribute("disabled"),
    ).toBe(true);
    expect(screen.queryByRole("link", { name: t.openConversation })).toBeNull();
  });
  it("bounds 100,000 loaded rows and searches the full set with combined rating, reset and page sizes", async () => {
    server.use(
      http.get("*/api/v1/feedback", () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, i) => ({
            ...feedback,
            messageId: `message-${i}`,
            rating: i === 99999 ? "up" : "down",
          })),
        }),
      ),
    );
    show();
    await screen.findByRole("button", { name: "Add feedback message message-0 to a suite" });
    expect(screen.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(
      screen.getByRole("button", { name: "Add feedback message message-25 to a suite" }),
    ).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: t.rating }), { target: { value: "up" } });
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "99999" } });
    expect(
      screen.getByRole("button", { name: "Add feedback message message-99999 to a suite" }),
    ).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "no match" } });
    expect(screen.getByText(t.noFeedbackMatches)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: t.clearFilters }));
    expect(document.activeElement).toBe(screen.getByRole("searchbox"));
    expect(
      screen.getByRole("button", { name: "Add feedback message message-0 to a suite" }),
    ).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: "Rows per page" }), {
      target: { value: "100" },
    });
    expect(screen.getAllByRole("listitem")).toHaveLength(100);
  }, 15000);
  it("requires an explicit suite and confirms a saved case before reporting success", async () => {
    const writes: unknown[] = [];
    server.use(
      http.post("*/api/v1/eval-suites/suite/cases:from-conversation", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json(saved, { status: 201 });
      }),
    );
    show();
    const modal = await open();
    expect(modal.getByRole("button", { name: t.addFeedback }).hasAttribute("disabled")).toBe(true);
    await choose(modal);
    fireEvent.click(modal.getByRole("button", { name: t.addFeedback }));
    await modal.findByText(t.added);
    expect(modal.getByText(t.copyConfirmed)).toBeTruthy();
    expect(modal.getByText(t.copiedCaseNotJudged)).toBeTruthy();
    expect(modal.getByRole("button", { name: t.addFeedback }).hasAttribute("disabled")).toBe(true);
    expect(writes).toEqual([{ conversationId: "conversation", messageId: "message" }]);
    expect(modal.queryByText(/saved text/)).toBeNull();
    fireEvent.click(modal.getByText(t.copiedCaseDetails));
    await modal.findByText(/saved text/);
    expect(document.querySelector("script")).toBeNull();
    fireEvent.click(modal.getByRole("button", { name: t.close }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Add feedback message message to a suite" }),
    );
  });
  it("treats reordered JSON keys as the same saved contents", async () => {
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () =>
        HttpResponse.json({
          items: [
            {
              ...saved,
              assertions: [
                { threshold: 0.5, rubric: "<script>saved text</script>", type: "lexical_overlap" },
              ],
            },
          ],
        }),
      ),
    );
    show();
    const modal = await open();
    await choose(modal);
    fireEvent.click(modal.getByRole("button", { name: t.addFeedback }));
    await modal.findByText(t.added);
  });
  it("preserves an acknowledgement after a failed read and recovers without another copy", async () => {
    let writes = 0;
    server.use(
      http.post("*/api/v1/eval-suites/suite/cases:from-conversation", () => {
        writes++;
        return HttpResponse.json(saved, { status: 201 });
      }),
      http.get("*/api/v1/eval-suites/suite/cases", () =>
        HttpResponse.json({ detail: "Saved list unavailable" }, { status: 503 }),
      ),
    );
    show();
    const modal = await open();
    await choose(modal);
    fireEvent.click(modal.getByRole("button", { name: t.addFeedback }));
    await modal.findByText("Saved list unavailable");
    expect(modal.getByText(t.copyAcknowledged)).toBeTruthy();
    expect(modal.getByText("Case reference · case")).toBeTruthy();
    expect(modal.queryByText(t.added)).toBeNull();
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () => HttpResponse.json({ items: [saved] })),
    );
    fireEvent.click(modal.getByRole("button", { name: t.copyRefresh }));
    await modal.findByText(t.added);
    expect(writes).toBe(1);
  });
  it.each([{ id: "case" }, { ...saved, suiteId: "other" }])(
    "holds an unmatched receipt %j without success or replay",
    async (receipt) => {
      let writes = 0;
      server.use(
        http.post("*/api/v1/eval-suites/suite/cases:from-conversation", () => {
          writes++;
          return HttpResponse.json(receipt, { status: 201 });
        }),
      );
      show();
      const modal = await open();
      await choose(modal);
      fireEvent.click(modal.getByRole("button", { name: t.addFeedback }));
      await modal.findByText(t.copyCaseMetadata);
      expect(modal.getByText(t.copyUnconfirmed)).toBeTruthy();
      await waitFor(() => expect(document.activeElement).toBe(modal.getByRole("alert")));
      fireEvent.click(modal.getByRole("button", { name: t.copyRefresh }));
      await modal.findByText(t.copyCasesChecked.replace("{count}", "1"));
      expect(modal.getByRole("button", { name: t.addFeedback }).hasAttribute("disabled")).toBe(
        true,
      );
      expect(writes).toBe(1);
      expect(modal.queryByText(t.added)).toBeNull();
    },
  );
  it("does not discard a known receipt when saved case contents differ", async () => {
    server.use(
      http.get("*/api/v1/eval-suites/suite/cases", () =>
        HttpResponse.json({ items: [{ ...saved, name: "Changed case" }] }),
      ),
    );
    show();
    const modal = await open();
    await choose(modal);
    fireEvent.click(modal.getByRole("button", { name: t.addFeedback }));
    await modal.findByText(t.copyNotVerified);
    expect(modal.getByText(t.copyAcknowledged)).toBeTruthy();
    expect(modal.getByText(saved.name)).toBeTruthy();
    expect(modal.queryByText(t.added)).toBeNull();
  });
  it("retains a true refusal and allows explicit submission only after read-only recovery", async () => {
    let writes = 0;
    server.use(
      http.post("*/api/v1/eval-suites/suite/cases:from-conversation", () => {
        writes++;
        return HttpResponse.json(
          { code: "csrf_failed", detail: "Origin refused" },
          { status: 403 },
        );
      }),
    );
    show();
    const modal = await open();
    await choose(modal);
    fireEvent.click(modal.getByRole("button", { name: t.addFeedback }));
    await modal.findByText(messages.apiErrors.csrf);
    expect(modal.getByText(t.copyRefused)).toBeTruthy();
    expect(modal.getByRole("button", { name: t.addFeedback }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(modal.getByRole("button", { name: t.copyRefresh }));
    await modal.findByText(t.copyChecked);
    expect(writes).toBe(1);
    expect(modal.getByRole("button", { name: t.addFeedback }).hasAttribute("disabled")).toBe(false);
  });
  it("does not retry an ambiguous create failure or forget it when changing destinations", async () => {
    let writes = 0;
    server.use(
      http.post("*/api/v1/eval-suites/suite/cases:from-conversation", () => {
        writes++;
        return HttpResponse.json({ detail: "Copy unavailable" }, { status: 503 });
      }),
    );
    show();
    const modal = await open();
    await choose(modal);
    fireEvent.click(modal.getByRole("button", { name: t.addFeedback }));
    await modal.findByText("Copy unavailable");
    expect(modal.getByText(t.copyUnconfirmed)).toBeTruthy();
    await choose(modal, "Other suite");
    expect(modal.getByRole("button", { name: t.addFeedback }).hasAttribute("disabled")).toBe(false);
    await choose(modal, "Release");
    expect(modal.getByRole("button", { name: t.addFeedback }).hasAttribute("disabled")).toBe(true);
    expect(writes).toBe(1);
  });
  it.each([
    { ...source, id: "other" },
    { ...source, messages: [{ id: "other" }] },
    { ...source, userId: "someone-else" },
  ])("withholds copy when source access/identity is not confirmed %j", async (value) => {
    const write = vi.fn(() => HttpResponse.json(saved));
    server.use(
      http.get("*/api/v1/conversations/conversation", () => HttpResponse.json(value)),
      http.post("*/api/v1/eval-suites/suite/cases:from-conversation", write),
    );
    show();
    fireEvent.click(
      await screen.findByRole("button", { name: "Add feedback message message to a suite" }),
    );
    const modal = within(screen.getByRole("dialog", { name: t.addFeedback }));
    await modal.findByRole("alert");
    expect(modal.getByRole("button", { name: t.addFeedback }).hasAttribute("disabled")).toBe(true);
    expect(write).not.toHaveBeenCalled();
  });
  it("lets a denied source read recover without sending a copy", async () => {
    server.use(
      http.get("*/api/v1/conversations/conversation", () =>
        HttpResponse.json({ detail: "Source not available" }, { status: 404 }),
      ),
    );
    show();
    fireEvent.click(
      await screen.findByRole("button", { name: "Add feedback message message to a suite" }),
    );
    const modal = within(screen.getByRole("dialog", { name: t.addFeedback }));
    await modal.findByText("Source not available");
    server.use(http.get("*/api/v1/conversations/conversation", () => HttpResponse.json(source)));
    fireEvent.click(modal.getByRole("button", { name: t.copyRefresh }));
    await waitFor(() =>
      expect(
        modal.getByRole("button", { name: /^Destination suite:/ }).hasAttribute("disabled"),
      ).toBe(false),
    );
    expect(modal.queryByRole("alert")).toBeNull();
  });
  it("rechecks source access before copying, and never posts after that access is lost", async () => {
    const write = vi.fn(() => HttpResponse.json(saved));
    server.use(http.post("*/api/v1/eval-suites/suite/cases:from-conversation", write));
    show();
    const modal = await open();
    await choose(modal);
    server.use(
      http.get("*/api/v1/conversations/conversation", () =>
        HttpResponse.json({ detail: "Source no longer readable" }, { status: 404 }),
      ),
    );
    fireEvent.click(modal.getByRole("button", { name: t.addFeedback }));
    await modal.findByText("Source no longer readable");
    expect(write).not.toHaveBeenCalled();
  });
  it("clears the old account's inbox when a refreshed session changes", async () => {
    show();
    await screen.findByText(feedback.comment);
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ ...session, user: { id: "different" } }),
      ),
      http.get("*/api/v1/feedback", () =>
        HttpResponse.json({ detail: "New account unavailable" }, { status: 503 }),
      ),
    );
    clearCachedSession();
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await screen.findByText("New account unavailable");
    expect(screen.queryByText(feedback.comment)).toBeNull();
  });
  it("aborts a pending copy on Cancel, holds that target and ignores its late acknowledgement", async () => {
    const nativeFetch = globalThis.fetch;
    let resolve!: (value: Response) => void;
    let signal: AbortSignal | null | undefined;
    let writes = 0;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input).endsWith("/cases:from-conversation")) {
        writes++;
        signal = init?.signal;
        return new Promise((done) => {
          resolve = done;
        });
      }
      return nativeFetch(input, init);
    });
    show();
    const modal = await open();
    await choose(modal);
    const button = modal.getByRole("button", { name: t.addFeedback });
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(writes).toBe(1));
    expect(modal.getByText(t.copyCancelHelp)).toBeTruthy();
    fireEvent.click(modal.getByRole("button", { name: t.cancel }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(signal?.aborted).toBe(true);
    await act(async () => {
      resolve(Response.json(saved));
    });
    const reopened = await open();
    await choose(reopened);
    expect(reopened.getByText(t.copyUnconfirmed)).toBeTruthy();
    expect(reopened.getByRole("button", { name: t.addFeedback }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(writes).toBe(1);
  });
  it("allows Cancel during a pending source read and ignores the late result", async () => {
    const nativeFetch = globalThis.fetch;
    let resolve!: (value: Response) => void;
    let signal: AbortSignal | null | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input) === "/api/v1/conversations/conversation") {
        signal = init?.signal;
        return new Promise((done) => {
          resolve = done;
        });
      }
      return nativeFetch(input, init);
    });
    show();
    fireEvent.click(
      await screen.findByRole("button", { name: "Add feedback message message to a suite" }),
    );
    await waitFor(() => expect(signal).toBeTruthy());
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: t.cancel }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(signal?.aborted).toBe(true);
    await act(async () => {
      resolve(Response.json(source));
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  it("confirms the current account afresh before a write instead of trusting a cached session", async () => {
    const write = vi.fn(() => HttpResponse.json(saved));
    server.use(http.post("*/api/v1/eval-suites/suite/cases:from-conversation", write));
    show();
    const modal = await open();
    await choose(modal);
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ ...session, user: { id: "new-person" } }),
      ),
    );
    fireEvent.click(modal.getByRole("button", { name: t.addFeedback }));
    await screen.findByText(t.sessionChanged);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.queryByText(feedback.comment)).toBeNull();
    expect(write).not.toHaveBeenCalled();
  });
  it("uses the existing broad evaluation-reader permission only after a readable source is confirmed", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          ...session,
          permissions: [...session.permissions, "agents:manage_all"],
        }),
      ),
      http.get("*/api/v1/conversations/conversation", () =>
        HttpResponse.json({ ...source, userId: "another-person" }),
      ),
    );
    show();
    const modal = await open();
    await choose(modal);
    fireEvent.click(modal.getByRole("button", { name: t.addFeedback }));
    await modal.findByText(t.added);
  });
  it("guards repeated inbox refreshes and aborts a late read on unmount", async () => {
    const nativeFetch = globalThis.fetch;
    const signals: (AbortSignal | null | undefined)[] = [];
    const resolvers: ((value: Response) => void)[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input) === "/api/v1/feedback") {
        signals.push(init?.signal);
        return new Promise((done) => resolvers.push(done));
      }
      return nativeFetch(input, init);
    });
    const view = show();
    await waitFor(() => expect(signals).toHaveLength(1));
    resolvers[0]?.(Response.json({ items: [feedback] }));
    await screen.findByText(feedback.comment);
    const refresh = screen.getByRole("button", { name: t.refresh });
    fireEvent.click(refresh);
    fireEvent.click(refresh);
    await waitFor(() => expect(signals).toHaveLength(2));
    expect(screen.getByText(feedback.comment)).toBeTruthy();
    view.unmount();
    expect(signals[1]?.aborted).toBe(true);
    await act(async () => {
      resolvers[1]?.(Response.json({ items: [] }));
    });
  });
  it("explains where feedback comes from and offers the existing chat route only with access", async () => {
    server.use(http.get("*/api/v1/feedback", () => HttpResponse.json({ items: [] })));
    show();
    await screen.findByText(t.noFeedback);
    expect(screen.getByText(t.feedbackEmptyHelp)).toBeTruthy();
    expect(screen.getByRole("link", { name: t.openChat }).getAttribute("href")).toBe("/chat");
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ ...session, permissions: ["evals:manage"] }),
      ),
    );
    clearCachedSession();
    fireEvent.click(screen.getByRole("button", { name: t.refresh }));
    await waitFor(() => expect(screen.queryByRole("link", { name: t.openChat })).toBeNull());
  });
});
