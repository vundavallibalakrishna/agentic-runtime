import { File as NodeFile } from "node:buffer";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatScreen } from "@/components/chat/chat-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/chat",
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("ChatScreen", () => {
  beforeEach(() => window.history.replaceState(null, "", "/chat"));
  afterEach(() => {
    cleanup();
  });

  it("pages history, searches older titles, and brings a new conversation back into view", async () => {
    let created = false;
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["chat:use"] })),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/files:limits", () => HttpResponse.json({ mimeTypes: [] })),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({
          items: [
            {
              id: "default-agent",
              name: "Assistant",
              slug: "assistant",
              status: "published",
              disabled: false,
            },
          ],
        }),
      ),
      http.get("*/api/v1/model-aliases", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/conversations", ({ request }) => {
        const params = new URL(request.url).searchParams,
          q = params.get("q") || "",
          offset = Number(params.get("cursor") || 0),
          limit = Number(params.get("limit") || 25);
        const all = [
          ...(created ? [{ id: "fresh", title: "Fresh conversation" }] : []),
          ...Array.from({ length: 30 }, (_, id) => ({
            id: `conversation-${id}`,
            title: `Conversation ${id}`,
          })),
        ].filter((row) => row.title.includes(q));
        const more = offset + limit < all.length;
        return HttpResponse.json({
          items: all.slice(offset, offset + limit),
          hasMore: more,
          nextCursor: more ? String(offset + limit) : null,
        });
      }),
      http.post("*/api/v1/conversations", () => {
        created = true;
        return HttpResponse.json({ id: "fresh", title: "Fresh conversation" });
      }),
      http.get("*/api/v1/conversations/fresh", () =>
        HttpResponse.json({ id: "fresh", title: "Fresh conversation", messages: [] }),
      ),
    );
    render(wrap(<ChatScreen />));
    await screen.findByRole("button", { name: "Conversation 0" });
    expect(screen.queryByRole("button", { name: "Conversation 27" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByRole("button", { name: "Conversation 27" })).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: "Find a conversation" }), {
      target: { value: "Conversation 29" },
    });
    expect(await screen.findByRole("button", { name: "Conversation 29" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "New chat" }));
    expect(await screen.findByRole("button", { name: "Fresh conversation" })).toBeTruthy();
    expect(
      (screen.getByRole("searchbox", { name: "Find a conversation" }) as HTMLInputElement).value,
    ).toBe("");
  });

  it("replaces the loading placeholder when chat is rate limited", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["chat:use"],
          user: { displayName: "Ada Lovelace", email: "ada@acme.example" },
          tenant: { name: "Acme" },
        }),
      ),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({
          items: [
            {
              id: "available",
              disabled: false,
              slug: "assistant",
              name: "Assistant",
              publishedVersion: 1,
              status: "published",
            },
          ],
        }),
      ),
      http.get("*/api/v1/model-aliases", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/files:limits", () => HttpResponse.json({ mimeTypes: [] })),
      http.get("*/api/v1/conversations", () =>
        HttpResponse.json({ code: "rate_limited", detail: "rate limit exceeded" }, { status: 429 }),
      ),
    );
    render(wrap(<ChatScreen />));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Too many requests. You are still signed in.",
    );
    expect(screen.queryByText("Loading chat")).toBeNull();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Question" } });
    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" });
    expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe("Question");
    expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
  });
  it("attaches only picked library documents and preserves uploaded files", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["chat:use"] })),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/files:limits", () => HttpResponse.json({ mimeTypes: [] })),
      http.get("*/api/v1/agents", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/model-aliases", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/conversations", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/library-documents", () =>
        HttpResponse.json({
          items: [
            ...Array.from({ length: 30 }, (_, i) => ({
              id: `doc-${i}`,
              title: `Guide ${i}`,
              fileId: `file-${i}`,
              mediaType: "text/plain",
            })),
            { id: "unavailable", title: "Unavailable guide" },
          ],
        }),
      ),
      http.post("*/api/v1/files:upload", () =>
        HttpResponse.json({
          id: "upload",
          name: "Manual.txt",
          mimeType: "text/plain",
          status: "ready",
        }),
      ),
    );
    render(wrap(<ChatScreen />));
    const documents = screen.getByRole("button", { name: "Documents" });
    await waitFor(() => expect(documents.hasAttribute("disabled")).toBe(false));
    fireEvent.change(screen.getByLabelText("Attach file", { selector: "input" }), {
      target: { files: [new NodeFile(["Manual"], "Manual.txt", { type: "text/plain" })] },
    });
    await screen.findByRole("link", { name: "Manual.txt" });
    fireEvent.click(documents);
    let picker = within(screen.getByTestId("document-picker"));
    expect(await picker.findByRole("checkbox", { name: "Guide 0" })).toBeTruthy();
    expect(picker.queryByRole("checkbox", { name: "Unavailable guide" })).toBeNull();
    fireEvent.click(picker.getByRole("button", { name: "Done" }));
    expect(screen.queryByTestId("document-picker")).toBeNull();
    expect(
      within(screen.getByRole("list", { name: "Attached files" })).getAllByRole("link"),
    ).toHaveLength(1);
    fireEvent.click(documents);
    picker = within(screen.getByTestId("document-picker"));
    fireEvent.change(picker.getByRole("searchbox"), { target: { value: "Guide 29" } });
    expect(picker.queryByRole("checkbox", { name: "Guide 0" })).toBeNull();
    fireEvent.click(await picker.findByRole("checkbox", { name: "Guide 29" }));
    fireEvent.click(picker.getByRole("button", { name: "Done" }));
    expect(
      within(screen.getByRole("list", { name: "Attached files" })).getAllByRole("link"),
    ).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Guide 29" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Manual.txt" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Guide 0" })).toBeNull();
    fireEvent.click(documents);
    picker = within(screen.getByTestId("document-picker"));
    fireEvent.change(picker.getByRole("searchbox"), { target: { value: "Guide 29" } });
    const selected = await picker.findByRole("checkbox", { name: "Guide 29" });
    expect((selected as HTMLInputElement).checked).toBe(true);
    fireEvent.click(selected);
    fireEvent.click(picker.getByRole("button", { name: "Done" }));
    expect(screen.queryByRole("link", { name: "Guide 29" })).toBeNull();
    expect(screen.getByRole("link", { name: "Manual.txt" })).toBeTruthy();
  });
});

function chatRegistry({
  count = 2,
  modelAlias = "existing",
}: {
  count?: number;
  modelAlias?: string | null;
} = {}) {
  const state = {
    modelAlias,
    writes: [] as Record<string, unknown>[],
    messages: [] as Record<string, unknown>[],
  };
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["chat:use"] })),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/files:limits", () => HttpResponse.json({ mimeTypes: [] })),
    http.get("*/api/v1/agents", () =>
      HttpResponse.json({
        items: [
          {
            id: "default-agent",
            name: "Assistant",
            slug: "assistant",
            status: "published",
            disabled: false,
          },
          ...Array.from({ length: count }, (_, index) => ({
            id: `agent-${index}`,
            name: `Worker ${index}`,
            slug: `worker-${index}`,
            status: "published",
            disabled: false,
          })),
        ],
      }),
    ),
    http.get("*/api/v1/model-aliases", () =>
      HttpResponse.json({
        items: [
          { alias: "existing", kind: "chat" },
          { alias: "replacement", kind: "chat" },
          ...Array.from({ length: count }, (_, index) => ({
            alias: `choice-${index}`,
            kind: "chat",
          })),
        ],
      }),
    ),
    http.get("*/api/v1/conversations", () =>
      HttpResponse.json({
        items: [
          { id: "first", title: "First chat" },
          { id: "second", title: "Second chat" },
        ],
      }),
    ),
    http.get("*/api/v1/conversations/first", () =>
      HttpResponse.json({ id: "first", modelAlias: state.modelAlias, messages: state.messages }),
    ),
    http.get("*/api/v1/conversations/second", () =>
      HttpResponse.json({ id: "second", modelAlias: null, messages: [] }),
    ),
    http.patch("*/api/v1/conversations/first", async ({ request }) => {
      const body = (await request.json()) as { modelAlias: string };
      state.writes.push(body);
      state.modelAlias = body.modelAlias || null;
      return HttpResponse.json({ id: "first", modelAlias: state.modelAlias });
    }),
  );
  return state;
}
function openOptions() {
  fireEvent.click(screen.getByText(messages.chat.chatOptions));
}
function selectModel(name: string) {
  fireEvent.click(screen.getByRole("button", { name: /^Model:/ }));
  const picker = within(screen.getByRole("dialog", { name: "Model" }));
  fireEvent.change(picker.getByRole("searchbox"), { target: { value: name } });
  fireEvent.click(picker.getByRole("button", { name }));
}

describe("chat choice state", () => {
  beforeEach(() => window.history.replaceState(null, "", "/chat"));

  it("loads the saved model from a direct link and clears it when another chat uses its agent default", async () => {
    chatRegistry();
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    openOptions();
    await screen.findByRole("button", { name: "Model: existing" });
    fireEvent.click(await screen.findByRole("button", { name: "Second chat" }));
    await screen.findByRole("button", { name: `Model: ${messages.chat.modelDefault}` });
    expect(screen.queryByRole("button", { name: "Model: existing" })).toBeNull();
  });

  it("shows confirmed save progress, freezes sending, and adopts the acknowledged value", async () => {
    const state = chatRegistry();
    let finish = () => {};
    const wait = new Promise<void>((resolve) => {
      finish = resolve;
    });
    server.use(
      http.patch("*/api/v1/conversations/first", async ({ request }) => {
        state.writes.push((await request.json()) as Record<string, unknown>);
        await wait;
        return HttpResponse.json({ modelAlias: "replacement" });
      }),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    openOptions();
    await screen.findByRole("button", { name: "Model: existing" });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Next question" } });
    selectModel("replacement");
    await screen.findByText(messages.chat.modelSaving);
    fireEvent.keyDown(screen.getByLabelText("Message"), { key: "Enter" });
    expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe("Next question");
    expect(screen.getByRole("button", { name: "Model: existing" }).matches(":disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
    await waitFor(() => expect(state.writes).toHaveLength(1));
    finish();
    await screen.findByText(messages.chat.modelSaved);
    expect(screen.getByRole("button", { name: "Model: replacement" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(false);
  });

  it("resolves an uncertain save with a read and never repeats the mutation", async () => {
    const state = chatRegistry();
    server.use(
      http.patch("*/api/v1/conversations/first", async ({ request }) => {
        state.writes.push((await request.json()) as Record<string, unknown>);
        state.modelAlias = "replacement";
        return HttpResponse.json({ detail: "Connection lost" }, { status: 503 });
      }),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    openOptions();
    await screen.findByRole("button", { name: "Model: existing" });
    selectModel("replacement");
    await screen.findByText(messages.chat.modelUnconfirmed);
    expect(screen.getByRole("button", { name: "Model: existing" }).matches(":disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: messages.chat.modelRefresh }));
    await screen.findByText(messages.chat.modelLoaded);
    expect(screen.getByRole("button", { name: "Model: replacement" })).toBeTruthy();
    expect(state.writes).toHaveLength(1);
    expect(screen.queryByText(messages.chat.modelUnconfirmed)).toBeNull();
  });

  it("does not apply a late model save to another conversation", async () => {
    chatRegistry();
    let finish = () => {};
    const wait = new Promise<void>((resolve) => {
      finish = resolve;
    });
    let started = false;
    let finished = false;
    server.use(
      http.patch("*/api/v1/conversations/first", async () => {
        started = true;
        await wait;
        finished = true;
        return HttpResponse.json({ modelAlias: "replacement" });
      }),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    openOptions();
    await screen.findByRole("button", { name: "Model: existing" });
    selectModel("replacement");
    await waitFor(() => expect(started).toBe(true));
    fireEvent.click(await screen.findByRole("button", { name: "Second chat" }));
    await screen.findByRole("button", { name: `Model: ${messages.chat.modelDefault}` });
    finish();
    await waitFor(() => expect(finished).toBe(true));
    await waitFor(() => expect(screen.queryByText(messages.chat.modelSaving)).toBeNull());
    expect(
      screen.getByRole("button", { name: `Model: ${messages.chat.modelDefault}` }),
    ).toBeTruthy();
    expect(screen.queryByText(messages.chat.modelSaved)).toBeNull();
  });

  it("bounds 100,000 loaded agent/model choices, preserves Cancel, and restores real default controls", async () => {
    const state = chatRegistry({ count: 100_000 });
    render(wrap(<ChatScreen />));
    openOptions();
    const agent = await screen.findByRole("button", {
      name: `Agent: ${messages.chat.defaultAgent}`,
    });
    await waitFor(() => expect(agent.matches(":disabled")).toBe(false));
    fireEvent.click(agent);
    let picker = within(screen.getByRole("dialog", { name: "Agent" }));
    expect(picker.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.change(picker.getByRole("searchbox"), { target: { value: "worker-99999" } });
    fireEvent.click(picker.getByRole("button", { name: /Worker 99999/ }));
    fireEvent.click(screen.getByRole("button", { name: "Agent: Worker 99999" }));
    picker = within(screen.getByRole("dialog", { name: "Agent" }));
    fireEvent.click(picker.getByRole("button", { name: messages.chat.useDefaultAgent }));
    expect(
      screen.getByRole("button", { name: `Agent: ${messages.chat.defaultAgent}` }),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: `Model: ${messages.chat.modelDefault}` }));
    picker = within(screen.getByRole("dialog", { name: "Model" }));
    expect(picker.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.change(picker.getByRole("searchbox"), { target: { value: "choice-99999" } });
    fireEvent.click(picker.getByRole("button", { name: "Cancel" }));
    expect(
      screen.getByRole("button", { name: `Model: ${messages.chat.modelDefault}` }),
    ).toBeTruthy();
    selectModel("choice-99999");
    expect(screen.getByRole("button", { name: "Model: choice-99999" })).toBeTruthy();
    expect(state.writes).toHaveLength(0);
  });
  it("clears a persisted override through the existing empty modelAlias contract", async () => {
    const state = chatRegistry();
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    openOptions();
    fireEvent.click(await screen.findByRole("button", { name: "Model: existing" }));
    fireEvent.click(
      within(screen.getByRole("dialog", { name: "Model" })).getByRole("button", {
        name: messages.chat.useAgentModel,
      }),
    );
    await screen.findByText(messages.chat.modelSaved);
    expect(state.writes).toEqual([{ modelAlias: "" }]);
    expect(
      screen.getByRole("button", { name: `Model: ${messages.chat.modelDefault}` }),
    ).toBeTruthy();
  });

  it("keeps sending and model changes unavailable after a failed chat read until Retry recovers", async () => {
    chatRegistry();
    let unavailable = true;
    server.use(
      http.get("*/api/v1/conversations/second", () =>
        unavailable
          ? HttpResponse.json({ detail: "Chat unavailable" }, { status: 503 })
          : HttpResponse.json({ modelAlias: null, messages: [] }),
      ),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    openOptions();
    await screen.findByRole("button", { name: "Model: existing" });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Question" } });
    fireEvent.click(await screen.findByRole("button", { name: "Second chat" }));
    await screen.findByText("Chat unavailable");
    expect(screen.getByRole("button", { name: /^Model:/ }).matches(":disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
    unavailable = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("button", { name: `Model: ${messages.chat.modelDefault}` });
    expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(false);
    expect(screen.queryByText("Chat unavailable")).toBeNull();
  });
  it("requires an explicit choice for an unavailable URL agent instead of silently substituting one", async () => {
    chatRegistry();
    server.use(
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({
          items: [
            {
              id: "retired-id",
              slug: "retired",
              name: "Retired",
              status: "archived",
              disabled: false,
            },
            { id: "draft-id", slug: "draft", name: "Draft", status: "draft", disabled: false },
            {
              id: "disabled-id",
              slug: "disabled",
              name: "Disabled",
              status: "published",
              disabled: true,
            },
            {
              id: "available-id",
              slug: "available",
              name: "Available",
              status: "published",
              disabled: false,
            },
          ],
        }),
      ),
    );
    window.history.replaceState(null, "", "/chat?agent=retired");
    render(wrap(<ChatScreen />));
    openOptions();
    await screen.findByText(messages.agentAvailability.requestedUnavailable);
    expect(screen.getByRole("button", { name: "New chat" }).matches(":disabled")).toBe(true);
    fireEvent.click(
      screen.getByRole("button", { name: `Agent: ${messages.agentAvailability.choose}` }),
    );
    const picker = within(screen.getByRole("dialog", { name: "Agent" }));
    expect(picker.getAllByRole("listitem")).toHaveLength(1);
    fireEvent.click(picker.getByRole("button", { name: /Available/ }));
    expect(screen.queryByText(messages.agentAvailability.requestedUnavailable)).toBeNull();
    expect(window.location.search).not.toContain("agent=");
    expect(screen.getByRole("button", { name: "New chat" }).matches(":disabled")).toBe(false);
  });

  it("offers a confirmed default explicitly after an invalid request and keeps archived speaker names", async () => {
    chatRegistry();
    server.use(
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({
          items: [
            {
              id: "default-agent",
              name: "Assistant",
              slug: "assistant",
              status: "published",
              disabled: false,
            },
            {
              id: "archived-agent",
              slug: "retired",
              name: "Past specialist",
              status: "archived",
              disabled: false,
            },
          ],
        }),
      ),
      http.get("*/api/v1/conversations/first", () =>
        HttpResponse.json({
          id: "first",
          modelAlias: null,
          agentId: "archived-agent",
          messages: [
            {
              id: "saved-reply",
              role: "assistant",
              text: "Saved reply",
              status: "completed",
            },
          ],
        }),
      ),
    );
    window.history.replaceState(null, "", "/chat?agent=retired");
    render(wrap(<ChatScreen />));
    await screen.findByText(messages.agentAvailability.requestedUnavailable);
    fireEvent.click(screen.getByRole("button", { name: messages.chat.useDefaultAgent }));
    expect(screen.queryByText(messages.agentAvailability.requestedUnavailable)).toBeNull();
    expect(screen.getByRole("button", { name: "New chat" }).matches(":disabled")).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "First chat" }));
    expect(await screen.findByText("Past specialist")).toBeTruthy();
  });
});

function actionChat() {
  const state = chatRegistry();
  state.messages.push(
    {
      id: "user-message",
      role: "user",
      text: "Original question",
      status: "completed",
      isActiveBranch: true,
      runId: "old-run",
    },
    {
      id: "assistant-message",
      role: "assistant",
      text: "",
      status: "failed",
      isActiveBranch: true,
      runId: "old-run",
      error: { message: "Previous attempt failed" },
    },
  );
  server.use(
    http.get("*/api/v1/runs/:id", ({ params }) =>
      HttpResponse.json({ id: params.id, status: "failed" }),
    ),
  );
  window.history.replaceState(null, "", "/chat?conversation=first");
  render(wrap(<ChatScreen />));
  return state;
}
async function editQuestion(value = "Edited question") {
  fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
  const field = screen.getByRole("textbox", { name: messages.chat.editMessage });
  fireEvent.change(field, { target: { value } });
  return field;
}
const eventResponse = (type: string, data: Record<string, unknown>, seq = 1) =>
  new HttpResponse(`data: ${JSON.stringify({ type, seq, data })}\n\n`, {
    headers: { "content-type": "text/event-stream" },
  });

describe("chat run actions", () => {
  it("preserves an edit and guards duplicate submits until a read-only recovery confirms current data", async () => {
    let finish = () => {};
    const waiting = new Promise<void>((resolve) => {
      finish = resolve;
    });
    const writes: unknown[] = [];
    server.use(
      http.post("*/api/v1/conversations/first/messages/user-message:edit", async ({ request }) => {
        writes.push(await request.json());
        await waiting;
        return HttpResponse.json({ detail: "Edit unavailable" }, { status: 503 });
      }),
    );
    const state = actionChat();
    const field = await editQuestion();
    const form = screen.getByRole("form", { name: messages.chat.editMessage });
    fireEvent.submit(form);
    fireEvent.submit(form);
    await screen.findByText(messages.chat.actions.edit);
    expect(field.matches(":disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "New chat" }).matches(":disabled")).toBe(true);
    await waitFor(() => expect(writes).toHaveLength(1));
    finish();
    await screen.findByText(messages.chat.actionUnconfirmed);
    expect((field as HTMLTextAreaElement).value).toBe("Edited question");
    expect(screen.getByRole("button", { name: "Save and branch" }).matches(":disabled")).toBe(true);
    server.use(
      http.get("*/api/v1/conversations/first", () =>
        HttpResponse.json({ detail: "Refresh unavailable" }, { status: 503 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: messages.chat.refreshChat }));
    await screen.findByText("Refresh unavailable");
    expect(writes).toEqual([{ text: "Edited question" }]);
    server.use(
      http.get("*/api/v1/conversations/first", () =>
        HttpResponse.json({ messages: state.messages, modelAlias: state.modelAlias }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: messages.chat.refreshChat }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save and branch" }).matches(":disabled")).toBe(
        false,
      ),
    );
    expect(screen.queryByText(messages.chat.actionUnconfirmed)).toBeNull();
    expect(
      (screen.getByRole("textbox", { name: messages.chat.editMessage }) as HTMLTextAreaElement)
        .value,
    ).toBe("Edited question");
    expect(writes).toHaveLength(1);
  });

  it.each([
    { label: "Resume", path: "/api/v1/runs/old-run:resume" },
    {
      label: "Try again",
      path: "/api/v1/conversations/first/messages/assistant-message:regenerate",
    },
  ])(
    "shows a $label refusal without replaying it or leaving controls stuck",
    async ({ label, path }) => {
      let writes = 0;
      server.use(
        http.post(`*${path}`, () => {
          writes += 1;
          return HttpResponse.json({ detail: "Action denied" }, { status: 403 });
        }),
      );
      actionChat();
      fireEvent.click(await screen.findByRole("button", { name: label }));
      await screen.findByText("Action denied");
      expect(screen.getByRole("button", { name: label }).matches(":disabled")).toBe(true);
      fireEvent.click(screen.getByRole("button", { name: messages.chat.refreshChat }));
      await screen.findByText(messages.chat.actionUpdated);
      expect(writes).toBe(1);
      expect(screen.getByRole("button", { name: label }).matches(":disabled")).toBe(false);
    },
  );

  it("loads the saved edit branch before observing the actual returned run", async () => {
    const state = actionChat();
    const writes: unknown[] = [];
    server.use(
      http.post("*/api/v1/conversations/first/messages/user-message:edit", async ({ request }) => {
        writes.push(await request.json());
        state.messages.forEach((message) => {
          message.isActiveBranch = false;
        });
        state.messages.push(
          {
            id: "edited-user",
            role: "user",
            text: "Edited question",
            isActiveBranch: true,
            status: "completed",
            runId: "new-run",
          },
          {
            id: "edited-answer",
            role: "assistant",
            text: "",
            isActiveBranch: true,
            status: "streaming",
            runId: "new-run",
          },
        );
        return HttpResponse.json({ run: { id: "new-run" } });
      }),
      http.get("*/api/v1/runs/new-run/events", () => {
        Object.assign(state.messages.at(-1) ?? {}, { text: "Updated reply", status: "completed" });
        return eventResponse("message.completed", { text: "Updated reply" });
      }),
      http.get("*/api/v1/runs/new-run", () =>
        HttpResponse.json({ id: "new-run", status: "completed" }),
      ),
    );
    await editQuestion();
    fireEvent.click(screen.getByRole("button", { name: "Save and branch" }));
    await screen.findByText(messages.chat.actionUpdated);
    expect(screen.getByText("Updated reply")).toBeTruthy();
    expect(screen.getByText("Edited question")).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: messages.chat.editMessage })).toBeNull();
    expect(screen.queryByText("Original question")).toBeNull();
    expect(writes).toEqual([{ text: "Edited question" }]);
  });

  it.each([
    {
      initialStatus: "waiting_approval",
      event: "tool_call.approval_required",
      guidance: messages.chat.actionWaitingApproval,
    },
    {
      initialStatus: "waiting_input",
      event: "input.required",
      guidance: messages.chat.actionWaitingInput,
    },
  ])(
    "holds $initialStatus and reconnects with reads after a decision without another resume",
    async ({ initialStatus, event, guidance }) => {
      const state = actionChat();
      let status = initialStatus;
      let writes = 0;
      server.use(
        http.post("*/api/v1/runs/old-run:resume", () => {
          writes += 1;
          return HttpResponse.json({ id: "old-run" });
        }),
        http.get("*/api/v1/runs/old-run", () => HttpResponse.json({ id: "old-run", status })),
        http.get("*/api/v1/runs/old-run/events", () => {
          if (status === initialStatus) {
            Object.assign(state.messages.at(-1) ?? {}, {
              text: "Waiting for a decision",
              status: "streaming",
            });
            return eventResponse(event, {
              qualifiedName: "connector.action",
            });
          }
          status = "completed";
          Object.assign(state.messages.at(-1) ?? {}, {
            text: "Resumed result",
            status: "completed",
          });
          return eventResponse("message.completed", { text: "Resumed result" }, 2);
        }),
      );
      fireEvent.click(await screen.findByRole("button", { name: "Resume" }));
      await screen.findByText(guidance);
      expect(screen.getByRole("link", { name: messages.chat.openInbox }).getAttribute("href")).toBe(
        "/inbox",
      );
      fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Another question" } });
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
      const refresh = screen.getByRole("button", { name: messages.chat.refreshChat });
      await waitFor(() => expect(refresh.matches(":disabled")).toBe(false));
      status = "running";
      fireEvent.click(refresh);
      await screen.findByText(messages.chat.actionUpdated);
      expect(screen.getByText("Resumed result")).toBeTruthy();
      expect(writes).toBe(1);
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(false);
    },
  );

  it("ignores an edit response after switching to a different chat", async () => {
    actionChat();
    let finish = () => {};
    const waiting = new Promise<void>((resolve) => {
      finish = resolve;
    });
    let started = false;
    let finished = false;
    server.use(
      http.post("*/api/v1/conversations/first/messages/user-message:edit", async () => {
        started = true;
        await waiting;
        finished = true;
        return HttpResponse.json({ run: { id: "late-run" } });
      }),
    );
    openOptions();
    await screen.findByRole("button", { name: "Model: existing" });
    await editQuestion();
    fireEvent.click(screen.getByRole("button", { name: "Save and branch" }));
    await waitFor(() => expect(started).toBe(true));
    fireEvent.click(await screen.findByRole("button", { name: "Second chat" }));
    await screen.findByRole("button", { name: `Model: ${messages.chat.modelDefault}` });
    finish();
    await waitFor(() => expect(finished).toBe(true));
    expect(screen.queryByRole("textbox", { name: messages.chat.editMessage })).toBeNull();
    expect(screen.queryByText(messages.chat.actions.edit)).toBeNull();
    expect(screen.queryByText(messages.chat.actionUpdated)).toBeNull();
    expect(screen.queryByText(messages.chat.actionUnconfirmed)).toBeNull();
  });
  it("keeps an acknowledged edit distinct from a failed reload and recovers without posting it again", async () => {
    const state = actionChat();
    let failRead = false;
    let writes = 0;
    server.use(
      http.get("*/api/v1/conversations/first", () =>
        failRead
          ? HttpResponse.json({ detail: "Saved branch unavailable" }, { status: 503 })
          : HttpResponse.json({ modelAlias: state.modelAlias, messages: state.messages }),
      ),
      http.post("*/api/v1/conversations/first/messages/user-message:edit", () => {
        writes += 1;
        state.messages.forEach((message) => {
          message.isActiveBranch = false;
        });
        state.messages.push(
          {
            id: "saved-user",
            role: "user",
            text: "Edited question",
            isActiveBranch: true,
            runId: "saved-run",
            status: "completed",
          },
          {
            id: "saved-answer",
            role: "assistant",
            text: "Saved response",
            isActiveBranch: true,
            runId: "saved-run",
            status: "completed",
          },
        );
        failRead = true;
        return HttpResponse.json({ run: { id: "saved-run" } });
      }),
      http.get("*/api/v1/runs/saved-run", () =>
        HttpResponse.json({ status: "completed", id: "saved-run" }),
      ),
    );
    await editQuestion();
    fireEvent.click(screen.getByRole("button", { name: "Save and branch" }));
    await screen.findByText(messages.chat.actionAcceptedRecovery);
    expect(screen.queryByRole("textbox", { name: messages.chat.editMessage })).toBeNull();
    failRead = false;
    fireEvent.click(screen.getByRole("button", { name: messages.chat.refreshChat }));
    await screen.findByText(messages.chat.actionUpdated);
    expect(screen.getByText("Saved response")).toBeTruthy();
    expect(writes).toBe(1);
  });
});

function savedActiveRun() {
  const catalogue = chatRegistry();
  const state = {
    status: "running",
    streams: 0,
    reads: 0,
    writes: 0,
    failRead: false,
    cancelRequested: false,
    catalogue,
  };
  catalogue.messages.push({
    id: "saved-assistant",
    role: "assistant",
    text: "Saved partial reply",
    status: "streaming",
    runId: "saved-run",
  });
  server.use(
    http.get("*/api/v1/conversations/first", () =>
      HttpResponse.json({
        id: "first",
        modelAlias: catalogue.modelAlias,
        messages: catalogue.messages,
        activeRunId: ["running", "queued", "waiting_approval", "waiting_input"].includes(
          state.status,
        )
          ? "saved-run"
          : null,
      }),
    ),
    http.get("*/api/v1/runs/saved-run", () => {
      state.reads += 1;
      return state.failRead
        ? HttpResponse.json({ detail: "Run metadata unavailable" }, { status: 503 })
        : HttpResponse.json({
            id: "saved-run",
            status: state.status,
            cancelRequested: state.cancelRequested,
          });
    }),
    http.get("*/api/v1/runs/saved-run/events", () => {
      state.streams += 1;
      state.status = "completed";
      Object.assign(catalogue.messages[0] ?? {}, {
        text: "Saved final reply",
        status: "completed",
      });
      return eventResponse("message.completed", { text: "Saved final reply" });
    }),
    http.post("*", () => {
      state.writes += 1;
      return HttpResponse.json({ detail: "Unexpected mutation" }, { status: 500 });
    }),
  );
  return state;
}

describe("opening saved active runs", () => {
  it.each(["URL", "history"])(
    "reconnects an existing working run from %s without starting work",
    async (source) => {
      const state = savedActiveRun();
      let finish = () => {};
      const waiting = new Promise<void>((resolve) => {
        finish = resolve;
      });
      server.use(
        http.get("*/api/v1/runs/saved-run", async () => {
          state.reads += 1;
          await waiting;
          return HttpResponse.json({ id: "saved-run", status: state.status });
        }),
      );
      window.history.replaceState(
        null,
        "",
        source === "URL" ? "/chat?conversation=first" : "/chat",
      );
      render(wrap(<ChatScreen />));
      if (source === "history")
        fireEvent.click(await screen.findByRole("button", { name: "First chat" }));
      await screen.findByText(messages.chat.actions.refresh);
      fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Keep this draft" } });
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
      finish();
      await screen.findByText(messages.chat.actionUpdated);
      expect(screen.getByText("Saved final reply")).toBeTruthy();
      expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe(
        "Keep this draft",
      );
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(false);
      expect(state.streams).toBe(1);
      expect(state.reads).toBe(2);
      expect(state.writes).toBe(0);
    },
  );

  it.each([
    { status: "waiting_approval", guidance: messages.chat.actionWaitingApproval },
    { status: "waiting_input", guidance: messages.chat.actionWaitingInput },
  ])(
    "holds a saved $status run until a read-only refresh confirms progress",
    async ({ status, guidance }) => {
      const state = savedActiveRun();
      state.status = status;
      window.history.replaceState(null, "", "/chat?conversation=first");
      render(wrap(<ChatScreen />));
      await screen.findByText(guidance);
      expect(state.streams).toBe(0);
      expect(screen.getByRole("link", { name: messages.chat.openInbox }).getAttribute("href")).toBe(
        "/inbox",
      );
      fireEvent.change(screen.getByLabelText("Message"), {
        target: { value: "Wait for current work" },
      });
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
      state.status = "running";
      fireEvent.click(screen.getByRole("button", { name: messages.chat.refreshChat }));
      await screen.findByText(messages.chat.actionUpdated);
      expect(screen.getByText("Saved final reply")).toBeTruthy();
      expect(state.streams).toBe(1);
      expect(state.writes).toBe(0);
    },
  );

  it("keeps failed run reads actionable and retries reads without resuming the run", async () => {
    const state = savedActiveRun();
    state.failRead = true;
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    await screen.findByText("Run metadata unavailable");
    expect(screen.getByText(messages.chat.actionAcceptedRecovery)).toBeTruthy();
    expect(screen.queryByText(messages.chat.actionUnconfirmed)).toBeNull();
    expect(state.streams).toBe(0);
    state.failRead = false;
    fireEvent.click(screen.getByRole("button", { name: messages.chat.refreshChat }));
    await screen.findByText(messages.chat.actionUpdated);
    expect(state.streams).toBe(1);
    expect(state.writes).toBe(0);
  });

  it("ignores late run metadata after opening another saved conversation", async () => {
    const state = savedActiveRun();
    let finish = () => {};
    let finished = false;
    const waiting = new Promise<void>((resolve) => {
      finish = resolve;
    });
    server.use(
      http.get("*/api/v1/runs/saved-run", async () => {
        await waiting;
        finished = true;
        return HttpResponse.json({ id: "saved-run", status: "waiting_approval" });
      }),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    await screen.findByText(messages.chat.actions.refresh);
    openOptions();
    fireEvent.click(await screen.findByRole("button", { name: "Second chat" }));
    await screen.findByRole("button", { name: `Model: ${messages.chat.modelDefault}` });
    finish();
    await waitFor(() => expect(finished).toBe(true));
    expect(screen.queryByText(messages.chat.actionWaitingApproval)).toBeNull();
    expect(screen.queryByText("Saved partial reply")).toBeNull();
    expect(screen.queryByText(messages.chat.actions.refresh)).toBeNull();
    expect(state.streams).toBe(0);
    expect(state.writes).toBe(0);
  });
});

async function submitChatMessage(text: string) {
  fireEvent.change(screen.getByLabelText("Message"), { target: { value: text } });
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(false),
  );
  fireEvent.submit(screen.getByRole("form", { name: messages.chat.composeMessage }));
}

async function attachChatFile(name: string) {
  await waitFor(() =>
    expect(screen.getByLabelText(messages.chat.attach).matches(":disabled")).toBe(false),
  );
  fireEvent.change(screen.getByLabelText(messages.chat.attach), {
    target: { files: [new NodeFile(["File contents"], name, { type: "text/plain" })] },
  });
  await screen.findByRole("link", { name });
}
function uploadChatFiles(...names: string[]) {
  let index = 0;
  server.use(
    http.post("*/api/v1/files:upload", () => {
      const name = names[index++];
      return name
        ? HttpResponse.json({ id: name, name, mimeType: "text/plain", status: "ready" })
        : HttpResponse.json({ detail: "Unexpected upload" }, { status: 500 });
    }),
  );
}

function postedRows(state: ReturnType<typeof chatRegistry>, text: string) {
  state.messages.push(
    {
      id: "posted-user",
      role: "user",
      text,
      status: "completed",
      isActiveBranch: true,
      runId: "posted-run",
    },
    {
      id: "posted-answer",
      role: "assistant",
      text: "",
      status: "streaming",
      isActiveBranch: true,
      runId: "posted-run",
    },
  );
}

describe("normal message submission", () => {
  it("shows a refused send with the server's words and keeps the draft", async () => {
    chatRegistry();
    server.use(
      http.post("*/api/v1/conversations/first/messages", () =>
        HttpResponse.json(
          { code: "quota_exceeded", detail: "Quota reached: the monthly run limit is 0" },
          { status: 429 },
        ),
      ),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    await screen.findByRole("button", { name: "First chat" });
    await submitChatMessage("Show the weekly numbers");
    // A definite answer from the server is not an unconfirmed send, nor a rate limit.
    expect(await screen.findByText(/Quota reached: the monthly run limit is 0/)).toBeTruthy();
    expect(screen.queryByText(messages.chat.messageUnconfirmed)).toBeNull();
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe(
      "Show the weekly numbers",
    );
  });
  it("guards duplicate sends and retains the exact draft/files until a failed send is read back", async () => {
    chatRegistry();
    uploadChatFiles("source.txt");
    let finish = () => {};
    const waiting = new Promise<void>((resolve) => {
      finish = resolve;
    });
    const writes: { body: unknown; key: string | null }[] = [];
    server.use(
      http.post("*/api/v1/conversations/first/messages", async ({ request }) => {
        writes.push({ body: await request.json(), key: request.headers.get("Idempotency-Key") });
        await waiting;
        return HttpResponse.json({ detail: "Message service unavailable" }, { status: 503 });
      }),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    await screen.findByRole("button", { name: "First chat" });
    await attachChatFile("source.txt");
    await submitChatMessage("  Preserve my question  ");
    fireEvent.submit(screen.getByRole("form", { name: messages.chat.composeMessage }));
    await screen.findByText(messages.chat.actions.send);
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]?.key).toMatch(/^[0-9a-f-]{36}$/);
    expect(screen.getByRole("button", { name: "Remove source.txt" }).matches(":disabled")).toBe(
      true,
    );
    expect(screen.getByRole("button", { name: "Documents" }).matches(":disabled")).toBe(true);
    expect(writes[0]?.body).toMatchObject({
      text: "Preserve my question",
      attachmentIds: ["source.txt"],
      fileIds: [],
    });
    expect(screen.queryAllByRole("article")).toHaveLength(0);
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe(
      "  Preserve my question  ",
    );
    finish();
    await screen.findByText(messages.chat.messageUnconfirmed);
    expect(screen.getByRole("region", { name: messages.chat.welcomeTitle }).tabIndex).toBe(0);
    expect(
      screen.queryByRole("button", { name: new RegExp(messages.chat.starterLabel1) }),
    ).toBeNull();
    expect(screen.getByText("Message service unavailable")).toBeTruthy();
    expect(screen.getByRole("link", { name: "source.txt" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: messages.chat.refreshChat }));
    await screen.findByText(messages.chat.actionUpdated);
    expect(writes).toHaveLength(1);
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe(
      "  Preserve my question  ",
    );
    expect(screen.getByRole("link", { name: "source.txt" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(false);
  });

  it("clears only acknowledged text/files while preserving a newer draft and newly attached files", async () => {
    const state = chatRegistry();
    uploadChatFiles("sent.txt", "next.txt");
    let finish = () => {};
    const waiting = new Promise<void>((resolve) => {
      finish = resolve;
    });
    let writes = 0;
    let finishStream = () => {};
    const streamWaiting = new Promise<void>((resolve) => {
      finishStream = resolve;
    });
    server.use(
      http.post("*/api/v1/conversations/first/messages", async () => {
        writes += 1;
        await waiting;
        postedRows(state, "Sent question");
        return HttpResponse.json({ run: { id: "posted-run" } });
      }),
      http.get("*/api/v1/runs/posted-run", () => HttpResponse.json({ status: "completed" })),
      http.get("*/api/v1/runs/posted-run/events", async () => {
        await streamWaiting;
        Object.assign(state.messages.at(-1) ?? {}, { text: "Saved answer", status: "completed" });
        return eventResponse("message.completed", { text: "Saved answer" });
      }),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    await screen.findByRole("button", { name: "First chat" });
    await attachChatFile("sent.txt");
    await submitChatMessage("Sent question");
    await screen.findByText(messages.chat.actions.send);
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "My next question" } });
    finish();
    await screen.findByText(messages.chat.actions.generate);
    await attachChatFile("next.txt");
    expect(screen.getByRole("button", { name: "Remove next.txt" }).matches(":disabled")).toBe(
      false,
    );
    finishStream();
    await screen.findByText(messages.chat.actionUpdated);
    expect(screen.getByTestId("message-posted-user")).toBeTruthy();
    expect(screen.getByText("Saved answer")).toBeTruthy();
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe(
      "My next question",
    );
    expect(screen.queryByRole("link", { name: "sent.txt" })).toBeNull();
    expect(screen.getByRole("link", { name: "next.txt" })).toBeTruthy();
    expect(writes).toBe(1);
  });

  it.each([
    {
      status: "waiting_approval",
      event: "tool_call.approval_required",
      guidance: messages.chat.actionWaitingApproval,
    },
    {
      status: "waiting_input",
      event: "input.required",
      guidance: messages.chat.actionWaitingInput,
    },
  ])(
    "keeps normal sends held after $status EOF and reconnects without another message",
    async ({ status: initialStatus, event, guidance }) => {
      const state = chatRegistry();
      let status = initialStatus;
      let writes = 0;
      server.use(
        http.post("*/api/v1/conversations", () =>
          HttpResponse.json({ detail: "Chat creation unavailable" }, { status: 503 }),
        ),
        http.post("*/api/v1/conversations/first/messages", () => {
          writes += 1;
          postedRows(state, "Please do the work");
          return HttpResponse.json({ run: { id: "posted-run" } });
        }),
        http.get("*/api/v1/runs/posted-run", () => HttpResponse.json({ status })),
        http.get("*/api/v1/runs/posted-run/events", () => {
          if (status === initialStatus)
            return eventResponse(event, { qualifiedName: "connector.action" });
          status = "completed";
          Object.assign(state.messages.at(-1) ?? {}, {
            text: "Work finished",
            status: "completed",
          });
          return eventResponse("message.completed", { text: "Work finished" });
        }),
      );
      window.history.replaceState(null, "", "/chat?conversation=first");
      render(wrap(<ChatScreen />));
      await submitChatMessage("Please do the work");
      await screen.findByText(guidance);
      expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe("");
      fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Next question" } });
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
      expect(screen.getByRole("link", { name: messages.chat.openInbox })).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: "New chat" }));
      await screen.findByText("Chat creation unavailable");
      expect(screen.getByText(guidance)).toBeTruthy();
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
      status = "running";
      fireEvent.click(screen.getByRole("button", { name: messages.chat.refreshChat }));
      await screen.findByText(messages.chat.actionUpdated);
      expect(screen.getByText("Work finished")).toBeTruthy();
      expect(writes).toBe(1);
      expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe("Next question");
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(false);
    },
  );

  it("keeps an acknowledged send distinct from a failed transcript read without posting again", async () => {
    const state = chatRegistry();
    let failRead = false;
    let writes = 0;
    server.use(
      http.get("*/api/v1/conversations/first", () =>
        failRead
          ? HttpResponse.json({ detail: "Transcript unavailable" }, { status: 503 })
          : HttpResponse.json({ id: "first", messages: state.messages }),
      ),
      http.post("*/api/v1/conversations/first/messages", () => {
        writes += 1;
        postedRows(state, "Saved question");
        failRead = true;
        return HttpResponse.json({ run: { id: "posted-run" } });
      }),
      http.get("*/api/v1/runs/posted-run", () => HttpResponse.json({ status: "completed" })),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    await submitChatMessage("Saved question");
    await screen.findByText(messages.chat.actionAcceptedRecovery);
    expect(screen.queryByText(messages.chat.messageUnconfirmed)).toBeNull();
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe("");
    failRead = false;
    fireEvent.click(screen.getByRole("button", { name: messages.chat.refreshChat }));
    await screen.findByText(messages.chat.actionUpdated);
    expect(screen.getByTestId("message-posted-user")).toBeTruthy();
    expect(writes).toBe(1);
  });

  it("creates a chat and submits its first message through one continuing request", async () => {
    const state = chatRegistry();
    const writes: { path: string; key: string | null }[] = [];
    server.use(
      http.post("*/api/v1/conversations", ({ request }) => {
        writes.push({ path: "create", key: request.headers.get("Idempotency-Key") });
        return HttpResponse.json({
          id: "created-chat",
          title: "Created chat",
          agentId: "default-agent",
        });
      }),
      http.post("*/api/v1/conversations/created-chat/messages", ({ request }) => {
        writes.push({ path: "message", key: request.headers.get("Idempotency-Key") });
        postedRows(state, "First question");
        return HttpResponse.json({ run: { id: "posted-run" } });
      }),
      http.get("*/api/v1/conversations/created-chat", () =>
        HttpResponse.json({
          id: "created-chat",
          agentId: "default-agent",
          messages: state.messages,
        }),
      ),
      http.get("*/api/v1/runs/posted-run", () => HttpResponse.json({ status: "completed" })),
      http.get("*/api/v1/runs/posted-run/events", () => {
        Object.assign(state.messages.at(-1) ?? {}, { text: "First answer", status: "completed" });
        return eventResponse("message.completed", { text: "First answer" });
      }),
    );
    window.history.replaceState(null, "", "/chat");
    render(wrap(<ChatScreen />));
    await submitChatMessage("First question");
    await screen.findByText(messages.chat.actionUpdated);
    expect(screen.getByText("First answer")).toBeTruthy();
    expect(writes.map((item) => item.path)).toEqual(["create", "message"]);
    expect(new Set(writes.map((item) => item.key)).size).toBe(2);
    expect(writes.every((item) => /^[0-9a-f-]{36}$/.test(item.key ?? ""))).toBe(true);
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe("");
    expect(new URL(window.location.href).searchParams.get("conversation")).toBe("created-chat");
  });

  it.each([
    {
      label: "refused",
      status: 503,
      body: { detail: "Chat creation unavailable" },
      detail: "Chat creation unavailable",
    },
    {
      label: "verification refused",
      status: 403,
      body: { detail: "Origin rejected", code: "csrf_failed" },
      detail: messages.apiErrors.csrf,
    },
    { label: "unconfirmed", status: 201, body: {}, detail: messages.chat.creationUnconfirmed },
  ])(
    "preserves the draft/files after $label creation before any message is attempted",
    async ({ status, body, detail }) => {
      chatRegistry();
      uploadChatFiles("draft.txt");
      let messageWrites = 0;
      server.use(
        http.post("*/api/v1/conversations", () => HttpResponse.json(body, { status })),
        http.post("*/api/v1/conversations/:id/messages", () => {
          messageWrites += 1;
          return HttpResponse.json({});
        }),
      );
      window.history.replaceState(null, "", "/chat");
      render(wrap(<ChatScreen />));
      await screen.findByRole("button", { name: "First chat" });
      await attachChatFile("draft.txt");
      await submitChatMessage("Keep this first question");
      await screen.findByText(messages.chat.messageNotSent);
      await screen.findByText(detail);
      expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe(
        "Keep this first question",
      );
      expect(screen.getByRole("link", { name: "draft.txt" })).toBeTruthy();
      expect(messageWrites).toBe(0);
      expect(screen.queryAllByRole("article")).toHaveLength(0);
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(false);
    },
  );

  it("holds an unconfirmed message response with a missing run reference and never replays it on Refresh", async () => {
    chatRegistry();
    let writes = 0;
    server.use(
      http.post("*/api/v1/conversations/first/messages", () => {
        writes += 1;
        return HttpResponse.json({}, { status: 202 });
      }),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    await submitChatMessage("Question with an uncertain response");
    await screen.findByText(messages.chat.messageUnconfirmed);
    expect(screen.getByText(messages.chat.runReferenceMissing)).toBeTruthy();
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe(
      "Question with an uncertain response",
    );
    fireEvent.click(screen.getByRole("button", { name: messages.chat.refreshChat }));
    await screen.findByText(messages.chat.actionUpdated);
    expect(writes).toBe(1);
  });

  it("ignores an acknowledgement after switching chats and keeps the unfinished draft", async () => {
    chatRegistry();
    let finish = () => {};
    let finished = false;
    let streams = 0;
    const waiting = new Promise<void>((resolve) => {
      finish = resolve;
    });
    server.use(
      http.post("*/api/v1/conversations/first/messages", async () => {
        await waiting;
        finished = true;
        return HttpResponse.json({ run: { id: "late-run" } });
      }),
      http.get("*/api/v1/runs/late-run/events", () => {
        streams += 1;
        return eventResponse("message.completed", { text: "Late reply" });
      }),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    await submitChatMessage("Unfinished draft");
    await screen.findByText(messages.chat.actions.send);
    openOptions();
    fireEvent.click(await screen.findByRole("button", { name: "Second chat" }));
    await screen.findByRole("button", { name: `Model: ${messages.chat.modelDefault}` });
    finish();
    await waitFor(() => expect(finished).toBe(true));
    expect(screen.queryByText("Late reply")).toBeNull();
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe(
      "Unfinished draft",
    );
    expect(streams).toBe(0);
  });

  it("guards repeated New chat creation and releases progress after loading the saved snapshot", async () => {
    chatRegistry();
    let finish = () => {};
    let writes = 0;
    const waiting = new Promise<void>((resolve) => {
      finish = resolve;
    });
    server.use(
      http.post("*/api/v1/conversations", async () => {
        writes += 1;
        await waiting;
        return HttpResponse.json({ id: "new-empty", title: "Empty chat" });
      }),
      http.get("*/api/v1/conversations/new-empty", () =>
        HttpResponse.json({ id: "new-empty", messages: [] }),
      ),
    );
    window.history.replaceState(null, "", "/chat");
    render(wrap(<ChatScreen />));
    const trigger = await screen.findByRole("button", { name: "New chat" });
    await waitFor(() => expect(trigger.matches(":disabled")).toBe(false));
    fireEvent.click(trigger);
    fireEvent.click(trigger);
    await screen.findByText(messages.chat.actions.create);
    await waitFor(() => expect(writes).toBe(1));
    finish();
    await screen.findByRole("button", { name: "Empty chat" });
    await waitFor(() => expect(screen.queryByText(messages.chat.actions.create)).toBeNull());
    expect(trigger.matches(":disabled")).toBe(false);
    expect(writes).toBe(1);
    expect(new URL(window.location.href).searchParams.get("conversation")).toBe("new-empty");
  });
});

async function chooseChatFiles(...names: string[]) {
  const input = screen.getByLabelText(messages.chat.attach);
  await waitFor(() => expect(input.matches(":disabled")).toBe(false));
  fireEvent.change(input, {
    target: {
      files: names.map((name) => new NodeFile(["Selected contents"], name, { type: "text/plain" })),
    },
  });
}
const readyUpload = (name: string) =>
  HttpResponse.json({ id: name, name, mimeType: "text/plain", status: "ready" });

describe("chat upload progress and context", () => {
  it("blocks sends and duplicate uploads synchronously, then stops only the pending selection", async () => {
    chatRegistry();
    let finish = () => {};
    let finished = false;
    const waiting = new Promise<void>((resolve) => {
      finish = resolve;
    });
    let uploads = 0;
    let messagesPosted = 0;
    server.use(
      http.post("*/api/v1/files:upload", async ({ request }) => {
        await request.arrayBuffer();
        uploads += 1;
        if (uploads === 1) return readyUpload("ready.txt");
        await waiting;
        finished = true;
        return readyUpload("pending.txt");
      }),
      http.post("*/api/v1/conversations/first/messages", () => {
        messagesPosted += 1;
        return HttpResponse.json({});
      }),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    const input = screen.getByLabelText(messages.chat.attach);
    await waitFor(() => expect(input.matches(":disabled")).toBe(false));
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Keep my draft" } });
    act(() => {
      fireEvent.change(input, {
        target: {
          files: ["ready.txt", "pending.txt", "not-started.txt"].map(
            (name) => new NodeFile(["Contents"], name, { type: "text/plain" }),
          ),
        },
      });
      fireEvent.submit(screen.getByRole("form", { name: messages.chat.composeMessage }));
      fireEvent.change(input, { target: { files: [new NodeFile(["Other"], "duplicate.txt")] } });
    });
    await screen.findByText("Uploading 2 of 3…");
    await waitFor(() => expect(uploads).toBe(2));
    expect(screen.getByRole("link", { name: "ready.txt" })).toBeTruthy();
    expect(input.matches(":disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Remove ready.txt" }).matches(":disabled")).toBe(
      true,
    );
    expect(screen.getByRole("button", { name: "Documents" }).matches(":disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
    expect(messagesPosted).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: messages.chat.stopUpload }));
    await screen.findByText(messages.chat.uploadStopped);
    expect(document.activeElement).toBe(screen.getByLabelText("Message"));
    expect(screen.getByRole("link", { name: "ready.txt" })).toBeTruthy();
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe("Keep my draft");
    expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(false);
    finish();
    await waitFor(() => expect(finished).toBe(true));
    expect(screen.queryByRole("link", { name: "pending.txt" })).toBeNull();
    expect(screen.queryByRole("link", { name: "not-started.txt" })).toBeNull();
    expect(uploads).toBe(2);
  });

  it("keeps confirmed files after a batch refusal and requires an explicit decision before sending", async () => {
    chatRegistry();
    let uploads = 0;
    server.use(
      http.post("*/api/v1/files:upload", () => {
        uploads += 1;
        return uploads === 1
          ? readyUpload("confirmed.txt")
          : HttpResponse.json({ detail: "Upload refused" }, { status: 503 });
      }),
    );
    window.history.replaceState(null, "", "/chat?conversation=first");
    render(wrap(<ChatScreen />));
    await chooseChatFiles("confirmed.txt", "refused.txt", "unattempted.txt");
    await screen.findByText("Upload refused");
    expect(screen.getByText(messages.chat.uploadError)).toBeTruthy();
    expect(screen.getByText("refused.txt")).toBeTruthy();
    expect(screen.getByRole("link", { name: "confirmed.txt" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "refused.txt" })).toBeNull();
    expect(screen.queryByRole("link", { name: "unattempted.txt" })).toBeNull();
    expect(uploads).toBe(2);
    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "Draft after refusal" },
    });
    expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: messages.chat.keepAttachedFiles }));
    expect(document.activeElement).toBe(screen.getByLabelText("Message"));
    expect(screen.queryByText("Upload refused")).toBeNull();
    expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(false);
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe(
      "Draft after refusal",
    );
    expect(uploads).toBe(2);
  });

  it.each([
    {
      label: "missing metadata",
      body: { status: "ready" },
      detail: messages.chat.uploadUnconfirmed,
      retry: false,
    },
    {
      label: "not ready",
      body: { id: "pending", name: "pending.txt", mimeType: "text/plain", status: "processing" },
      detail: messages.chat.uploadNotReady,
      retry: true,
    },
  ])(
    "does not attach $label and recovers only through a deliberate choice",
    async ({ body, detail, retry }) => {
      chatRegistry();
      let uploads = 0;
      server.use(
        http.post("*/api/v1/files:upload", () => {
          uploads += 1;
          return uploads === 1 ? HttpResponse.json(body) : readyUpload("retry.txt");
        }),
      );
      window.history.replaceState(null, "", "/chat");
      render(wrap(<ChatScreen />));
      await chooseChatFiles("chosen.txt");
      await screen.findByText(detail);
      expect(screen.queryByRole("list", { name: messages.chat.attachedFiles })).toBeNull();
      expect(screen.queryByText(messages.chat.uploadComplete)).toBeNull();
      fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Still here" } });
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
      if (retry) {
        await chooseChatFiles("retry.txt");
        await screen.findByText(messages.chat.uploadComplete);
        expect(screen.getByRole("link", { name: "retry.txt" })).toBeTruthy();
        expect(uploads).toBe(2);
      } else {
        fireEvent.click(screen.getByRole("button", { name: messages.chat.continueWithoutFiles }));
        expect(uploads).toBe(1);
      }
      expect(screen.queryByText(detail)).toBeNull();
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(false);
    },
  );

  it("ignores an old upload result without clearing another chat's new upload progress", async () => {
    chatRegistry();
    const oldResponse = pendingJsonResponse({
      id: "old-chat.txt",
      name: "old-chat.txt",
      mimeType: "text/plain",
      status: "ready",
    });
    const newResponse = pendingJsonResponse({
      id: "new-chat.txt",
      name: "new-chat.txt",
      mimeType: "text/plain",
      status: "ready",
    });
    let uploads = 0;
    // Keep these two deliberately late response bodies independent of native HTTP socket reuse.
    // All unrelated reads still use the existing MSW registry.
    const originalFetch = globalThis.fetch;
    const transport = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      if (String(input) === "/api/v1/files:upload") {
        uploads += 1;
        return Promise.resolve(uploads === 1 ? oldResponse.response : newResponse.response);
      }
      return originalFetch(input, init);
    });
    try {
      window.history.replaceState(null, "", "/chat?conversation=first");
      render(wrap(<ChatScreen />));
      await chooseChatFiles("old-chat.txt");
      await waitFor(() => expect(uploads).toBe(1));
      fireEvent.click(await screen.findByRole("button", { name: "Second chat" }));
      await chooseChatFiles("new-chat.txt");
      await waitFor(() => expect(uploads).toBe(2));
      act(() => oldResponse.finish());
      await waitFor(() => expect(oldResponse.released()).toBe(true));
      expect(screen.queryByRole("alert")).toBeNull();
      expect(screen.getByRole("button", { name: messages.chat.stopUpload })).toBeTruthy();
      expect(screen.getByText("new-chat.txt")).toBeTruthy();
      expect(screen.queryByRole("link", { name: "old-chat.txt" })).toBeNull();
      act(() => newResponse.finish());
      await screen.findByText(messages.chat.uploadComplete);
      expect(screen.getByRole("link", { name: "new-chat.txt" })).toBeTruthy();
      expect(screen.queryByRole("link", { name: "old-chat.txt" })).toBeNull();
      expect(uploads).toBe(2);
    } finally {
      transport.mockRestore();
    }
  });

  it("cancels an upload when resetting an already-empty new-chat context", async () => {
    chatRegistry();
    let finish = () => {};
    let finished = false;
    let started = false;
    const waiting = new Promise<void>((resolve) => {
      finish = resolve;
    });
    server.use(
      http.post("*/api/v1/files:upload", async ({ request }) => {
        await request.arrayBuffer();
        started = true;
        await waiting;
        finished = true;
        return readyUpload("old-draft.txt");
      }),
    );
    window.history.replaceState(null, "", "/chat");
    render(wrap(<ChatScreen />));
    await chooseChatFiles("old-draft.txt");
    await screen.findByText("old-draft.txt");
    await waitFor(() => expect(started).toBe(true));
    fireEvent(window, new Event("ar-new-chat"));
    expect(screen.queryByRole("button", { name: messages.chat.stopUpload })).toBeNull();
    finish();
    await waitFor(() => expect(finished).toBe(true));
    expect(screen.queryByRole("link", { name: "old-draft.txt" })).toBeNull();
    expect(screen.queryByText(messages.chat.uploadComplete)).toBeNull();
    expect(screen.getByLabelText(messages.chat.attach).matches(":disabled")).toBe(false);
  });

  it.each(["/chat", "/chat?conversation=first"])(
    "clears picked library documents and closes the picker on a new-chat action from %s",
    async (url) => {
      chatRegistry();
      server.use(
        http.get("*/api/v1/library-documents", () =>
          HttpResponse.json({
            items: [{ id: "document", fileId: "library-file", title: "Library document" }],
          }),
        ),
      );
      window.history.replaceState(null, "", url);
      render(wrap(<ChatScreen />));
      await waitFor(() =>
        expect(screen.getByRole("button", { name: "Documents" }).matches(":disabled")).toBe(false),
      );
      fireEvent.click(screen.getByRole("button", { name: "Documents" }));
      let picker = within(screen.getByTestId("document-picker"));
      const choice = await picker.findByRole("checkbox", { name: "Library document" });
      fireEvent.click(choice);
      expect((choice as HTMLInputElement).checked).toBe(true);
      fireEvent(window, new Event("ar-new-chat"));
      await waitFor(() => expect(screen.queryByTestId("document-picker")).toBeNull());
      fireEvent.click(screen.getByRole("button", { name: "Documents" }));
      picker = within(screen.getByTestId("document-picker"));
      expect(
        ((await picker.findByRole("checkbox", { name: "Library document" })) as HTMLInputElement)
          .checked,
      ).toBe(false);
      expect(screen.queryByRole("list", { name: messages.chat.attachedFiles })).toBeNull();
    },
  );
});

it("keeps confirmed files and the pending upload when reloading the same saved chat", async () => {
  chatRegistry();
  uploadChatFiles("kept.txt");
  window.history.replaceState(null, "", "/chat?conversation=first");
  render(wrap(<ChatScreen />));
  await attachChatFile("kept.txt");
  let finish = () => {};
  let started = false;
  const waiting = new Promise<void>((resolve) => {
    finish = resolve;
  });
  server.use(
    http.post("*/api/v1/files:upload", async ({ request }) => {
      await request.arrayBuffer();
      started = true;
      await waiting;
      return readyUpload("also-kept.txt");
    }),
  );
  await chooseChatFiles("also-kept.txt");
  await waitFor(() => expect(started).toBe(true));
  openOptions();
  fireEvent.click(screen.getByRole("button", { name: "First chat" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Model: existing" }).matches(":disabled")).toBe(
      false,
    ),
  );
  expect(screen.getByRole("link", { name: "kept.txt" })).toBeTruthy();
  expect(screen.getByRole("button", { name: messages.chat.stopUpload })).toBeTruthy();
  finish();
  await screen.findByText(messages.chat.uploadComplete);
  expect(screen.getByRole("link", { name: "kept.txt" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "also-kept.txt" })).toBeTruthy();
});

function pendingJsonResponse(value: Record<string, unknown>) {
  let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
  let closed = false;
  let released = false;
  const body = new ReadableStream<Uint8Array>({
    start(value) {
      controller = value;
    },
    cancel() {
      closed = true;
    },
  });
  return {
    response: new HttpResponse(body, {
      headers: { "content-type": "application/json" },
    }),
    released: () => released,
    finish() {
      released = true;
      if (closed || !controller) return;
      controller.enqueue(new TextEncoder().encode(JSON.stringify(value)));
      controller.close();
      closed = true;
    },
  };
}

function streamingSavedRun() {
  const state = savedActiveRun();
  let started = false;
  let body: ReadableStreamDefaultController<Uint8Array> | null = null;
  let closed = false;
  // A test-local stream allows deterministic EOF/abort ordering without a shared native socket.
  // Metadata, cancellation receipts and saved transcript reads remain the existing MSW handlers.
  const originalFetch = globalThis.fetch;
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    if (!started && String(input) === "/api/v1/runs/saved-run/events") {
      started = true;
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          body = controller;
          controller.enqueue(
            new TextEncoder().encode(
              `data: ${JSON.stringify({ type: "message.delta", seq: 1, data: { text: "Saved partial reply" } })}\n\n`,
            ),
          );
          init?.signal?.addEventListener(
            "abort",
            () => {
              if (!closed) {
                closed = true;
                controller.close();
              }
            },
            { once: true },
          );
        },
        cancel() {
          closed = true;
        },
      });
      return Promise.resolve(
        new HttpResponse(stream, { headers: { "content-type": "text/event-stream" } }),
      );
    }
    return originalFetch(input, init);
  });

  return {
    state,
    started: () => started,
    finish(status = "completed") {
      if (closed || !body) return;
      state.status = status;
      const text = status === "cancelled" ? "Saved partial reply" : "Saved final result";
      Object.assign(state.catalogue.messages[0] ?? {}, { text, status });
      body.enqueue(
        new TextEncoder().encode(
          `data: ${JSON.stringify({ type: status === "cancelled" ? "run.cancelled" : "message.completed", seq: 2, data: status === "cancelled" ? { by: "user" } : { text } })}\n\n`,
        ),
      );
      body.close();
      closed = true;
    },
    open: async () => {
      window.history.replaceState(null, "", "/chat?conversation=first");
      render(wrap(<ChatScreen />));
      await waitFor(() => expect(started).toBe(true));
    },
  };
}

describe("chat cancellation feedback", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });
  it("guards duplicate stops and waits for actual run cancellation after acknowledgement", async () => {
    const run = streamingSavedRun();
    const acknowledgement = pendingJsonResponse({
      id: "saved-run",
      status: "running",
      cancelRequested: true,
    });
    const writes: { key: string | null; body: unknown }[] = [];
    server.use(
      http.post("*/api/v1/runs/saved-run:cancel", async ({ request }) => {
        writes.push({ key: request.headers.get("Idempotency-Key"), body: await request.json() });
        return acknowledgement.response;
      }),
    );
    await run.open();
    const stop = screen.getByRole("button", { name: "Stop" });
    act(() => {
      fireEvent.click(stop);
      fireEvent.click(stop);
    });
    await screen.findByText(messages.chat.stopPending);
    expect(screen.getByRole("button", { name: messages.chat.stopping }).matches(":disabled")).toBe(
      true,
    );
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]?.key).toMatch(/^[0-9a-f-]{36}$/);
    expect(writes[0]?.body).toEqual({});
    run.state.cancelRequested = true;
    act(() => acknowledgement.finish());
    await screen.findByText(messages.chat.stopRequested);
    expect(screen.queryByText(messages.chat.actionCancelled)).toBeNull();
    expect(screen.getByRole("button", { name: messages.chat.stopping }).matches(":disabled")).toBe(
      true,
    );
    run.finish("cancelled");
    await screen.findByText(messages.chat.actionCancelled);
    expect(screen.getByText("Saved partial reply")).toBeTruthy();
    expect(screen.queryByText("Saved final result")).toBeNull();
    expect(screen.queryByText(messages.chat.stopRequested)).toBeNull();
    expect(writes).toHaveLength(1);
  });

  it.each([
    {
      label: "refused",
      body: { detail: "Stop refused" },
      status: 403,
      failRead: false,
      detail: "Stop refused",
    },
    {
      label: "unconfirmed",
      body: {},
      status: 200,
      failRead: false,
      detail: messages.chat.runReferenceMissing,
    },
    {
      label: "unavailable with failed status read",
      body: { detail: "Stop unavailable" },
      status: 503,
      failRead: true,
      detail: "Stop unavailable",
    },
  ])(
    "keeps $label cancellation actionable and the existing stream attached",
    async ({ body, status, failRead, detail }) => {
      const run = streamingSavedRun();
      let writes = 0;
      server.use(
        http.post("*/api/v1/runs/saved-run:cancel", () => {
          writes += 1;
          run.state.failRead = failRead;
          return HttpResponse.json(body, { status });
        }),
      );
      await run.open();
      fireEvent.click(screen.getByRole("button", { name: "Stop" }));
      await screen.findByText(messages.chat.stopUnconfirmed);
      expect(screen.getByText(detail)).toBeTruthy();
      expect(screen.getByRole("button", { name: "Stop" }).matches(":disabled")).toBe(false);
      expect(writes).toBe(1);
      run.state.failRead = false;
      run.finish();
      await screen.findByText(messages.chat.actionUpdated);
      expect(screen.queryByText(messages.chat.stopUnconfirmed)).toBeNull();
      expect(screen.getByText("Saved final result")).toBeTruthy();
    },
  );

  it.each(["completed", "failed", "interrupted"])(
    "loads a %s race through read-only Refresh without inventing completion",
    async (status) => {
      const run = streamingSavedRun();
      let writes = 0;
      server.use(
        http.post("*/api/v1/runs/saved-run:cancel", () => {
          writes += 1;
          run.state.status = status;
          Object.assign(run.state.catalogue.messages[0] ?? {}, {
            text: "Actual saved result",
            status,
          });
          return HttpResponse.json({ detail: "Run is not active" }, { status: 409 });
        }),
      );
      await run.open();
      fireEvent.click(screen.getByRole("button", { name: "Stop" }));
      await screen.findByText(messages.chat.stopEndedRefresh);
      expect(screen.queryByText(messages.chat.stopUnconfirmed)).toBeNull();
      fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Next draft" } });
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(true);
      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: messages.chat.refreshChat }).matches(":disabled"),
        ).toBe(false),
      );
      const refresh = screen.getByRole("button", { name: messages.chat.refreshChat });
      refresh.focus();
      fireEvent.click(refresh);
      const otherControl = screen.getByRole("button", { name: /Search anything/ });
      if (status === "failed") otherControl.focus();
      else refresh.blur();
      await waitFor(() => {
        const states = [...screen.queryAllByRole("status"), ...screen.queryAllByRole("alert")].map(
          (node) => node.textContent,
        );
        expect(
          states,
          JSON.stringify({ states, reads: run.state.reads, runStatus: run.state.status }),
        ).toContain(messages.chat.actionUpdated);
      });
      expect(screen.getByTestId("message-saved-assistant").textContent).toContain(
        "Actual saved result",
      );
      expect(screen.getByRole("button", { name: "Send" }).matches(":disabled")).toBe(false);
      expect(document.activeElement).toBe(
        status === "failed" ? otherControl : screen.getByLabelText("Message"),
      );
      expect(writes).toBe(1);
      run.finish(status);
    },
  );

  it("ignores a pending stop reply after changing to another chat", async () => {
    const run = streamingSavedRun();
    let finish = () => {};
    let finished = false;
    let started = false;
    const waiting = new Promise<void>((resolve) => {
      finish = resolve;
    });
    server.use(
      http.post("*/api/v1/runs/saved-run:cancel", async () => {
        started = true;
        await waiting;
        finished = true;
        return HttpResponse.json({ detail: "Late stop refused" }, { status: 503 });
      }),
    );
    await run.open();
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    await screen.findByText(messages.chat.stopPending);
    await waitFor(() => expect(started).toBe(true));
    openOptions();
    fireEvent.click(await screen.findByRole("button", { name: "Second chat" }));
    await screen.findByRole("button", { name: `Model: ${messages.chat.modelDefault}` });
    finish();
    await waitFor(() => expect(finished).toBe(true));
    expect(screen.queryByText("Late stop refused")).toBeNull();
    expect(screen.queryByText(messages.chat.stopRequested)).toBeNull();
    expect(screen.queryByText(messages.chat.stopUnconfirmed)).toBeNull();
    run.finish();
  });

  it("restores the server's pending cancellation flag without posting another stop", async () => {
    const run = streamingSavedRun();
    run.state.cancelRequested = true;
    await run.open();
    await screen.findByText(messages.chat.stopRequested);
    expect(screen.getByRole("button", { name: messages.chat.stopping }).matches(":disabled")).toBe(
      true,
    );
    expect(run.state.writes).toBe(0);
    run.finish("cancelled");
    await screen.findByText(messages.chat.actionCancelled);
  });
});

describe("reply acceptance read-only chat recovery", () => {
  afterEach(() => cleanup());
  it.each([false, true])(
    "preserves the composer and never replays acceptance after refresh failure=%s",
    async (failRefresh) => {
      window.history.replaceState(null, "", "/chat?conversation=first");
      const state = chatRegistry();
      state.messages = [
        {
          id: "reply",
          role: "assistant",
          content: "Saved reply",
          review: { canAccept: true, status: "unreviewed", contentHash: "hash" },
        },
      ];
      let acceptanceCalls = 0;
      let failRead = false;
      server.use(
        http.post("*/api/v1/auth/step-up", () => HttpResponse.json({ steppedUp: "true" })),
        http.post("*/api/v1/messages/reply:accept", () => {
          acceptanceCalls++;
          failRead = failRefresh;
          return HttpResponse.json({ detail: "acceptance unavailable" }, { status: 503 });
        }),
        http.get("*/api/v1/conversations/first", () =>
          failRead
            ? HttpResponse.json({ detail: "snapshot unavailable" }, { status: 503 })
            : HttpResponse.json({
                id: "first",
                messages: state.messages,
                modelAlias: state.modelAlias,
              }),
        ),
      );
      render(wrap(<ChatScreen />));
      const accept = await screen.findByRole("button", { name: "Accept" });
      const draft = screen.getByPlaceholderText(messages.chat.placeholder);
      fireEvent.change(draft, { target: { value: "Keep this draft" } });
      fireEvent.click(accept);
      await screen.findByText("acceptance unavailable");
      fireEvent.click(screen.getByRole("button", { name: "Refresh chat" }));
      if (failRefresh) {
        await screen.findByText("snapshot unavailable");
        failRead = false;
        fireEvent.click(screen.getByRole("button", { name: messages.chat.retry }));
      }
      await screen.findByRole("button", { name: "Accept" });
      expect(
        (screen.getByPlaceholderText(messages.chat.placeholder) as HTMLTextAreaElement).value,
      ).toBe("Keep this draft");
      expect(acceptanceCalls).toBe(1);
      expect(state.writes).toEqual([]);
    },
  );
});
