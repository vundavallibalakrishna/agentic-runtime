import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChannelsScreen } from "@/components/channels/channels-screen";
import { ProfileScreen } from "@/components/channels/profile-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/chat",
  useRouter: () => ({ push: () => undefined }),
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("channel screens", () => {
  afterEach(() => {
    cleanup();
  });

  it("lists a slack workspace and a recent post", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["channels:manage"], user: { displayName: "Admin" } }),
      ),
      http.get("*/api/v1/channel-integrations", () =>
        HttpResponse.json({
          items: [
            {
              id: "slack-1",
              kind: "slack",
              name: "Workspace Slack",
              status: "active",
              identitiesCount: 1,
            },
          ],
        }),
      ),
      http.get("*/api/v1/channel-integrations/slack-1", () =>
        HttpResponse.json({
          id: "slack-1",
          name: "Workspace Slack",
          recentPosts: [{ id: "p1", body: "The weekly digest is ready for #platform." }],
        }),
      ),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({ items: [{ id: "a1", name: "Assistant" }] }),
      ),
    );
    render(wrap(<ChannelsScreen />));
    expect(await screen.findByRole("heading", { name: "Workspace Slack" })).toBeTruthy();
    expect(screen.getByText("The weekly digest is ready for #platform.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Advanced" })).toBeTruthy();
  });

  it("saves a widget open to anyone with the limits set for visitors", async () => {
    let sent: Record<string, unknown> = {};
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["channels:manage"],
          features: { widget: true },
          user: { displayName: "Admin" },
        }),
      ),
      http.get("*/api/v1/channel-integrations", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({ items: [{ id: "a1", name: "Assistant" }] }),
      ),
      http.post("*/api/v1/channel-integrations", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "w1", kind: "widget", name: "Website" });
      }),
    );
    render(wrap(<ChannelsScreen />));
    fireEvent.change(await screen.findByLabelText("Name"), { target: { value: "Website" } });
    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "widget" } });
    fireEvent.change(screen.getByLabelText("Who can chat"), { target: { value: "public" } });
    // A widget open to anyone has no host secret to ask for.
    expect(screen.queryByLabelText("Host signing secret")).toBeNull();
    fireEvent.change(screen.getByLabelText("Account visitors act as"), {
      target: { value: "visitor@acme.example" },
    });
    fireEvent.change(screen.getByLabelText("Allowed portal origins"), {
      target: { value: "https://www.acme.example" },
    });
    fireEvent.change(screen.getByLabelText("Characters in one message"), {
      target: { value: "500" },
    });
    fireEvent.change(screen.getByLabelText("Minutes a chat stays open"), {
      target: { value: "10" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save channel" }));
    await waitFor(() => expect(sent.kind).toBe("widget"));
    expect(sent.credentials).toEqual({});
    expect(sent.config).toEqual({
      allowedOrigins: ["https://www.acme.example"],
      showSources: true,
      access: "public",
      visitorEmail: "visitor@acme.example",
      notice: "",
      maxMessages: 30,
      maxMessageChars: 500,
      sessionsPerMinute: 60,
      sessionsPerClientPerMinute: 10,
      sessionSeconds: 600,
    });
  });

  it("turns website chat on for the workspace before a widget can be saved", async () => {
    let patched: Record<string, unknown> = {};
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["channels:manage", "tenant:manage"],
          features: { widget: false },
          user: { displayName: "Admin" },
        }),
      ),
      http.get("*/api/v1/channel-integrations", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({ items: [{ id: "a1", name: "Assistant" }] }),
      ),
      http.patch("*/api/v1/tenant", async ({ request }) => {
        patched = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ settings: { features: { widget: true } } });
      }),
    );
    render(wrap(<ChannelsScreen />));
    fireEvent.change(await screen.findByLabelText("Name"), { target: { value: "Website" } });
    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "widget" } });
    expect(screen.getByRole("alert").textContent).toContain("Turn it on above");
    const save = screen.getByRole("button", { name: "Save channel" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Turn on" }));
    await waitFor(() => expect(patched).toEqual({ settings: { features: { widget: true } } }));
    expect(await screen.findByText("Website and portal chat is on.")).toBeTruthy();
    expect(save.disabled).toBe(false);
  });

  it("someone who cannot change the workspace is told whom to ask", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["channels:manage"], features: { widget: false } }),
      ),
      http.get("*/api/v1/channel-integrations", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<ChannelsScreen />));
    expect(await screen.findByText("Ask a workspace administrator to change this.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Turn on" })).toBeNull();
  });

  it("edits a saved widget and keeps its secret when none is typed", async () => {
    let patched: Record<string, unknown> = {};
    const widget = {
      id: "w1",
      kind: "widget",
      name: "Portal",
      status: "active",
      defaultAgent: { id: "a2", name: "Helper" },
      config: { allowedOrigins: ["https://portal.example"], showSources: false },
    };
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["channels:manage"], features: { widget: true } }),
      ),
      http.get("*/api/v1/channel-integrations", () => HttpResponse.json({ items: [widget] })),
      http.get("*/api/v1/channel-integrations/w1", () => HttpResponse.json(widget)),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({
          items: [
            { id: "a1", name: "Helper", slug: "helper", visibility: "tenant", publishedVersion: 3 },
            { id: "a2", name: "Helper", slug: "helper-2", visibility: "private" },
          ],
        }),
      ),
      http.patch("*/api/v1/channel-integrations/w1", async ({ request }) => {
        patched = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(widget);
      }),
    );
    render(wrap(<ChannelsScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Edit Portal" }));
    expect(await screen.findByRole("heading", { name: "Edit Portal" })).toBeTruthy();
    expect((screen.getByLabelText("Kind") as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByLabelText("Allowed portal origins") as HTMLTextAreaElement).value).toBe(
      "https://portal.example",
    );
    const sources = screen.getByRole("checkbox", { name: /see the sources/ }) as HTMLInputElement;
    expect(sources.checked).toBe(false);
    // Two agents of one name are told apart, and the private one says why it may fail.
    const agent = screen.getByLabelText("Agent") as HTMLSelectElement;
    expect([...agent.options].map((option) => option.text)).toEqual([
      "Helper (helper)",
      "Helper (helper-2)",
    ]);
    expect(agent.value).toBe("a2");
    expect(screen.getByText(/Only some people can use this agent/)).toBeTruthy();
    fireEvent.change(agent, { target: { value: "a1" } });
    fireEvent.click(sources);
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(patched).toEqual({
        name: "Portal",
        defaultAgentId: "a1",
        config: { allowedOrigins: ["https://portal.example"], showSources: true },
      }),
    );
  });

  it("turns off and deletes a channel after asking", async () => {
    const calls: string[] = [];
    const slack = { id: "s1", kind: "slack", name: "Team Slack", status: "active" };
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["channels:manage"], features: {} }),
      ),
      http.get("*/api/v1/channel-integrations", () => HttpResponse.json({ items: [slack] })),
      http.get("*/api/v1/channel-integrations/s1", () => HttpResponse.json(slack)),
      http.get("*/api/v1/agents", () => HttpResponse.json({ items: [] })),
      http.patch("*/api/v1/channel-integrations/s1", async ({ request }) => {
        calls.push(`patch ${JSON.stringify(await request.json())}`);
        return HttpResponse.json(slack);
      }),
      http.delete("*/api/v1/channel-integrations/s1", () => {
        calls.push("delete");
        return new HttpResponse(null, { status: 204 });
      }),
    );
    render(wrap(<ChannelsScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Turn off Team Slack" }));
    await waitFor(() => expect(calls).toEqual(['patch {"status":"disabled"}']));
    fireEvent.click(await screen.findByRole("button", { name: "Delete Team Slack" }));
    expect(await screen.findByText(/This cannot be undone/)).toBeTruthy();
    expect(calls).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(calls).toContain("delete"));
  });

  it("saves the Slack secrets typed in and offers no archived agent", async () => {
    let sent: Record<string, unknown> = {};
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["channels:manage"], features: {} }),
      ),
      http.get("*/api/v1/channel-integrations", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({
          items: [
            { id: "old", name: "Helper", slug: "helper-old", status: "archived" },
            { id: "a1", name: "Helper", slug: "helper", status: "published" },
          ],
        }),
      ),
      http.post("*/api/v1/channel-integrations", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "s1", kind: "slack", name: "Team" });
      }),
    );
    render(wrap(<ChannelsScreen />));
    fireEvent.change(await screen.findByLabelText("Name"), { target: { value: "Team" } });
    fireEvent.change(screen.getByLabelText("Bot token"), { target: { value: "xoxb-1" } });
    fireEvent.change(screen.getByLabelText("Signing secret"), { target: { value: "sign-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Advanced" }));
    const agent = (await screen.findByLabelText("Agent")) as HTMLSelectElement;
    expect([...agent.options].map((option) => option.value)).toEqual(["a1"]);
    fireEvent.click(screen.getByRole("button", { name: "Save channel" }));
    await waitFor(() => expect(sent.kind).toBe("slack"));
    expect(sent.credentials).toEqual({ botToken: "xoxb-1", signingSecret: "sign-1" });
    expect(sent.defaultAgentId).toBe("a1");
  });

  it("shows the channel error state", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({})),
      http.get("*/api/v1/channel-integrations", () => new HttpResponse(null, { status: 500 })),
      http.get("*/api/v1/agents", () => new HttpResponse(null, { status: 500 })),
    );
    render(wrap(<ChannelsScreen />));
    expect(await screen.findByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("links and lists a profile identity", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({})),
      http.get("*/api/v1/me/channel-identities", () =>
        HttpResponse.json({
          items: [{ id: "id-1", externalUserId: "U-ADMIN", matchMethod: "manual_link" }],
        }),
      ),
      http.get("*/api/v1/me/usage", () =>
        HttpResponse.json({
          currency: "INR",
          totals: { quantity: 1200, costMicros: 40 },
          quotas: [{ metric: "model_tokens", period: "day", limit: 100000, used: 1200 }],
        }),
      ),
    );
    render(wrap(<ProfileScreen />));
    expect(await screen.findByRole("heading", { name: "U-ADMIN" })).toBeTruthy();
    expect(screen.getByLabelText("Connect code")).toBeTruthy();
  });
});
