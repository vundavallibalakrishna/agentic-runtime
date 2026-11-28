import { File as NodeFile } from "node:buffer";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WidgetChat } from "@/components/widget/widget-chat";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const originalParent = Object.getOwnPropertyDescriptor(window, "parent");
const host = { postMessage: vi.fn() };
function view(id = "integration-1") {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <WidgetChat integrationId={id} />
    </NextIntlClientProvider>
  );
}
async function authenticate() {
  await waitFor(() => expect(host.postMessage).toHaveBeenCalled());
  const ready = host.postMessage.mock.calls.at(-1)?.[0];
  const event = new MessageEvent("message", {
    origin: "https://portal.example",
    data: {
      type: "ar-widget:authenticate",
      nonce: ready.nonce,
      integrationId: ready.integrationId,
      token: "unit-test-token",
    },
  });
  Object.defineProperty(event, "source", { value: host });
  fireEvent(window, event);
  await screen.findByLabelText("Message", { selector: "textarea" });
}

beforeEach(() => {
  host.postMessage.mockClear();
  Object.defineProperty(window, "parent", { configurable: true, value: host });
  HTMLElement.prototype.scrollIntoView = vi.fn();
  server.use(
    http.get("*/api/v1/widget/integrations/:id", () =>
      HttpResponse.json({ allowedOrigins: ["https://portal.example"] }),
    ),
    http.post("*/api/v1/widget/sessions", () => new HttpResponse(null, { status: 204 })),
    http.get("*/api/v1/widget/session", () =>
      HttpResponse.json({
        integrationId: "integration-1",
        name: "Workspace chat",
        csrfToken: "unit-csrf",
        conversationId: null,
        agents: [{ id: "agent-1", name: "Support" }],
      }),
    ),
  );
});
afterEach(() => {
  if (originalParent) Object.defineProperty(window, "parent", originalParent);
});

describe("embedded chat UI", () => {
  it("shows unavailable integration guidance and retries the real reader", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/widget/integrations/:id", () => {
        reads += 1;
        return HttpResponse.json({ detail: "Not found" }, { status: 404 });
      }),
    );
    render(view());
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(messages.widget.unavailable)).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(reads).toBe(2));
    expect(await screen.findByText(messages.widget.unavailable)).toBeTruthy();
  });

  it("keeps uploads unavailable when the portal has no permitted agent", async () => {
    server.use(
      http.get("*/api/v1/widget/session", () =>
        HttpResponse.json({
          integrationId: "integration-1",
          name: "Workspace chat",
          csrfToken: "unit-csrf",
          conversationId: null,
          agents: [],
        }),
      ),
    );
    render(view());
    await authenticate();
    expect(screen.getByText(messages.widget.noAgents)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Attach file" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Send message" }).hasAttribute("disabled")).toBe(
      true,
    );
  });

  it("blocks sending until the selected file is saved and shows upload progress", async () => {
    let finish: (() => void) | undefined;
    server.use(
      http.post("*/api/v1/widget/files", async () => {
        await new Promise<void>((resolve) => {
          finish = resolve;
        });
        return HttpResponse.json({
          id: "file-1",
          name: "notes.txt",
          mimeType: "text/plain",
          status: "ready",
        });
      }),
    );
    render(view());
    await authenticate();
    fireEvent.change(screen.getByLabelText("Message", { selector: "textarea" }), {
      target: { value: "Read these notes" },
    });
    fireEvent.change(screen.getByLabelText("Attach file", { selector: "input" }), {
      target: { files: [new NodeFile(["notes"], "notes.txt", { type: "text/plain" })] },
    });
    expect(await screen.findByText(messages.widget.uploading)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send message" }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(screen.getByRole("button", { name: "Start a new chat" }).hasAttribute("disabled")).toBe(
      true,
    );
    await waitFor(() => expect(finish).toBeTruthy());
    finish?.();
    expect(await screen.findByText("notes.txt")).toBeTruthy();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Send message" }).hasAttribute("disabled")).toBe(
        false,
      ),
    );
    expect(screen.queryByText(messages.widget.uploading)).toBeNull();
  });

  it("does not silently attach a non-ready file", async () => {
    server.use(
      http.post("*/api/v1/widget/files", () =>
        HttpResponse.json({ id: "file-1", status: "quarantined" }),
      ),
    );
    render(view());
    await authenticate();
    fireEvent.change(screen.getByLabelText("Attach file", { selector: "input" }), {
      target: { files: [new NodeFile(["notes"], "notes.txt")] },
    });
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(/notes.txt is not ready to attach/)).toBeTruthy();
    expect(screen.queryByRole("link", { name: "notes.txt" })).toBeNull();
  });

  it("keeps the reconnect action visible after an expired upload session", async () => {
    server.use(
      http.post("*/api/v1/widget/files", () =>
        HttpResponse.json({ detail: "Expired" }, { status: 401 }),
      ),
    );
    render(view());
    await authenticate();
    fireEvent.change(screen.getByLabelText("Message", { selector: "textarea" }), {
      target: { value: "My unsent question" },
    });
    fireEvent.change(screen.getByLabelText("Attach file", { selector: "input" }), {
      target: { files: [new NodeFile(["notes"], "notes.txt")] },
    });
    expect(await screen.findByText(messages.widget.expired)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Start a new chat" }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(screen.getByRole("button", { name: "Send message" }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(screen.getByRole("button", { name: "Reconnect" }).hasAttribute("disabled")).toBe(false);
    expect(
      (screen.getByLabelText("Message", { selector: "textarea" }) as HTMLTextAreaElement).value,
    ).toBe("My unsent question");
  });

  it("removes the previous integration's session and draft during navigation", async () => {
    const { rerender } = render(view());
    await authenticate();
    fireEvent.change(screen.getByLabelText("Message", { selector: "textarea" }), {
      target: { value: "Private unsent draft" },
    });
    server.use(
      http.get("*/api/v1/widget/integrations/:id", () =>
        HttpResponse.json({ detail: "Not found" }, { status: 404 }),
      ),
    );
    rerender(view("integration-2"));
    expect(await screen.findByText(messages.widget.unavailable)).toBeTruthy();
    expect(screen.queryByText("Workspace chat")).toBeNull();
    expect(screen.queryByDisplayValue("Private unsent draft")).toBeNull();
  });

  it("does not offer a working stop action before a run has been accepted", async () => {
    let finish: (() => void) | undefined;
    server.use(
      http.post("*/api/v1/widget/conversations", () => HttpResponse.json({ id: "conversation-1" })),
      http.post("*/api/v1/widget/conversations/conversation-1/messages", async () => {
        await new Promise<void>((resolve) => {
          finish = resolve;
        });
        return HttpResponse.json({ detail: "The message was not accepted" }, { status: 503 });
      }),
    );
    render(view());
    await authenticate();
    fireEvent.change(screen.getByLabelText("Message", { selector: "textarea" }), {
      target: { value: "Keep this question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText(messages.widget.sending)).toBeTruthy();
    expect(
      screen.getByRole("button", { name: messages.widget.sending }).hasAttribute("disabled"),
    ).toBe(true);
    expect(screen.queryByRole("button", { name: "Stop response" })).toBeNull();
    await waitFor(() => expect(finish).toBeTruthy());
    finish?.();
    expect(await screen.findByText("The message was not accepted")).toBeTruthy();
    expect(
      (screen.getByLabelText("Message", { selector: "textarea" }) as HTMLTextAreaElement).value,
    ).toBe("Keep this question");
  });

  it("bounds 100,000 saved messages and keeps each history page chronological", async () => {
    const saved = Array.from({ length: 100_000 }, (_, index) => ({
      id: `message-${index}`,
      role: "user",
      text: `Saved message ${index}`,
    }));
    server.use(
      http.post("*/api/v1/widget/conversations", () => HttpResponse.json({ id: "conversation-1" })),
      http.post("*/api/v1/widget/conversations/conversation-1/messages", () =>
        HttpResponse.json({
          message: { id: "sent", role: "user", text: "Current question" },
          run: { id: "run-1" },
        }),
      ),
      http.get(
        "*/api/v1/widget/runs/run-1/events",
        () =>
          new HttpResponse(
            'event: message.completed\ndata: {"type":"message.completed","seq":1}\n\n',
            {
              headers: { "content-type": "text/event-stream" },
            },
          ),
      ),
      http.get("*/api/v1/widget/conversations/conversation-1", () =>
        HttpResponse.json({ messages: saved, activeRunId: null }),
      ),
    );
    const { container } = render(view());
    await authenticate();
    fireEvent.change(screen.getByLabelText("Message", { selector: "textarea" }), {
      target: { value: "Current question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("Saved message 99999")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(container.querySelectorAll("article").length).toBe(25);
    expect(container.querySelector("article")?.textContent).toContain("Saved message 99975");
    // Settle the latest page's effects before measuring older-page navigation.
    await act(async () => {
      await Promise.resolve();
    });
    vi.mocked(HTMLElement.prototype.scrollIntoView).mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Older messages" }));
    expect(await screen.findByText("Saved message 99950")).toBeTruthy();
    expect(container.querySelectorAll("article").length).toBe(25);
    expect(screen.queryByText("Saved message 99999")).toBeNull();
    expect(HTMLElement.prototype.scrollIntoView).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Back to latest messages" }));
    expect(await screen.findByText("Saved message 99999")).toBeTruthy();
  });
  it("bounds the authorized agent catalogue without workspace metadata reads and sends the selected id", async () => {
    let workspaceReads = 0;
    const writes: Record<string, unknown>[] = [];
    server.use(
      http.get("*/api/v1/agents", () => {
        workspaceReads += 1;
        return HttpResponse.json({ items: [] });
      }),
      http.get("*/api/v1/widget/session", () =>
        HttpResponse.json({
          integrationId: "integration-1",
          name: "Workspace chat",
          csrfToken: "unit-csrf",
          conversationId: null,
          agents: Array.from({ length: 100_000 }, (_, index) => ({
            id: `agent-${index}`,
            name: `Worker ${index}`,
          })),
        }),
      ),
      http.post("*/api/v1/widget/conversations", async ({ request }) => {
        writes.push((await request.json()) as Record<string, unknown>);
        return HttpResponse.json({ id: "created" });
      }),
      http.post("*/api/v1/widget/conversations/created/messages", () =>
        HttpResponse.json({ detail: "Not accepted" }, { status: 503 }),
      ),
    );
    render(view());
    await authenticate();
    const trigger = screen.getByRole("button", { name: "Agent: Worker 0" });
    fireEvent.click(trigger);
    let picker = within(screen.getByRole("dialog", { name: "Agent" }));
    expect(picker.getAllByRole("listitem")).toHaveLength(25);
    fireEvent.change(picker.getByRole("searchbox"), { target: { value: "Worker 99999" } });
    fireEvent.click(picker.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Agent: Worker 0" })).toBeTruthy();
    fireEvent.click(trigger);
    picker = within(screen.getByRole("dialog", { name: "Agent" }));
    fireEvent.change(picker.getByRole("searchbox"), { target: { value: "agent-99999" } });
    fireEvent.click(picker.getByRole("button", { name: /Worker 99999/ }));
    expect(screen.getByRole("button", { name: "Agent: Worker 99999" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Message", { selector: "textarea" }), {
      target: { value: "Question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() => expect(writes).toEqual([{ agentId: "agent-99999" }]));
    await screen.findByRole("alert");
    expect(screen.getByRole("button", { name: "Agent: Worker 99999" }).matches(":disabled")).toBe(
      true,
    );
    expect(workspaceReads).toBe(0);
  });
});
