import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

const assistant = {
  id: "a1",
  name: "Assistant",
  status: "published",
  disabled: false,
  visibility: "tenant",
  publishedVersion: 1,
};

async function pickAgent(name: string) {
  fireEvent.click(screen.getByRole("button", { name: /^Default agent:/ }));
  const dialog = within(screen.getByRole("dialog"));
  fireEvent.click(await dialog.findByText(name));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
}

describe("channel screens", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
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
        HttpResponse.json({
          items: [{ id: "a1", name: "Assistant", status: "published", disabled: false }],
        }),
      ),
    );
    render(wrap(<ChannelsScreen />));
    expect(await screen.findByRole("heading", { name: "Workspace Slack" })).toBeTruthy();
    expect(await screen.findByText("The weekly digest is ready for #platform.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Advanced" })).toBeTruthy();
  });

  it("saves a widget open to anyone with the limits set for visitors", async () => {
    let sent: Record<string, unknown> = {};
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["channels:manage", "agents:read"],
          features: { widget: true },
          user: { displayName: "Admin" },
        }),
      ),
      http.get("*/api/v1/channel-integrations", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () => HttpResponse.json({ items: [{ ...assistant }] })),
      http.get("*/api/v1/agents/a1", () => HttpResponse.json(assistant)),
      http.post("*/api/v1/channel-integrations", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "w1", kind: "widget", name: "Website" });
      }),
    );
    render(wrap(<ChannelsScreen />));
    fireEvent.change(await screen.findByLabelText("Name"), { target: { value: "Website" } });
    await pickAgent("Assistant");
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
    expect(sent.defaultAgentId).toBe("a1");
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
          permissions: ["channels:manage", "tenant:manage", "agents:read"],
          features: { widget: false },
          user: { displayName: "Admin" },
        }),
      ),
      http.get("*/api/v1/channel-integrations", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () => HttpResponse.json({ items: [{ ...assistant }] })),
      http.get("*/api/v1/agents/a1", () => HttpResponse.json(assistant)),
      http.patch("*/api/v1/tenant", async ({ request }) => {
        patched = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ settings: { features: { widget: true } } });
      }),
    );
    render(wrap(<ChannelsScreen />));
    fireEvent.change(await screen.findByLabelText("Name"), { target: { value: "Website" } });
    await pickAgent("Assistant");
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
    const shared = {
      id: "a1",
      name: "Helper",
      slug: "helper",
      status: "published",
      disabled: false,
      visibility: "tenant",
      publishedVersion: 3,
    };
    const privateAgent = {
      id: "a2",
      name: "Helper",
      slug: "helper-2",
      status: "published",
      disabled: false,
      visibility: "private",
      publishedVersion: 1,
    };
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["channels:manage", "agents:read"],
          features: { widget: true },
        }),
      ),
      http.get("*/api/v1/channel-integrations", () => HttpResponse.json({ items: [widget] })),
      http.get("*/api/v1/channel-integrations/w1", () => HttpResponse.json(widget)),
      http.get("*/api/v1/agents", () => HttpResponse.json({ items: [shared, privateAgent] })),
      http.get("*/api/v1/agents/a1", () => HttpResponse.json(shared)),
      http.get("*/api/v1/agents/a2", () => HttpResponse.json(privateAgent)),
      http.patch("*/api/v1/channel-integrations/w1", async ({ request }) => {
        patched = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(widget);
      }),
    );
    render(wrap(<ChannelsScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Edit Portal" }));
    expect(await screen.findByRole("heading", { name: "Edit Portal" })).toBeTruthy();
    expect((form().getByLabelText("Kind") as HTMLSelectElement).disabled).toBe(true);
    await waitFor(() =>
      expect((screen.getByLabelText("Allowed portal origins") as HTMLTextAreaElement).value).toBe(
        "https://portal.example",
      ),
    );
    const sources = screen.getByRole("checkbox", { name: /see the sources/ }) as HTMLInputElement;
    expect(sources.checked).toBe(false);
    // No secret is asked for unless the saved one is replaced.
    expect(screen.queryByLabelText("Host signing secret")).toBeNull();
    // The private agent says why it may fail for others.
    expect(await screen.findByText(/Only some people can use this agent/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /^Default agent:/ }));
    const dialog = within(screen.getByRole("dialog"));
    // Two agents of one name are told apart by their slug.
    expect(await dialog.findByText(/^helper · a1/)).toBeTruthy();
    expect(dialog.getByText(/^helper-2 · a2/)).toBeTruthy();
    fireEvent.click(dialog.getByText(/^helper · a1/));
    await waitFor(() =>
      expect(screen.queryByText(/Only some people can use this agent/)).toBeNull(),
    );
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
        HttpResponse.json({ permissions: ["channels:manage", "agents:read"], features: {} }),
      ),
      http.get("*/api/v1/channel-integrations", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({
          items: [
            { id: "old", name: "Old helper", slug: "helper-old", status: "archived" },
            { ...assistant },
          ],
        }),
      ),
      http.get("*/api/v1/agents/a1", () => HttpResponse.json(assistant)),
      http.post("*/api/v1/channel-integrations", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "s1", kind: "slack", name: "Team" });
      }),
    );
    render(wrap(<ChannelsScreen />));
    fireEvent.change(await screen.findByLabelText("Name"), { target: { value: "Team" } });
    fireEvent.change(screen.getByLabelText("Bot token"), { target: { value: "xoxb-1" } });
    fireEvent.change(screen.getByLabelText("Signing secret"), { target: { value: "sign-1" } });
    fireEvent.click(screen.getByRole("button", { name: /^Default agent:/ }));
    const dialog = within(screen.getByRole("dialog"));
    await dialog.findByText("Assistant");
    expect(dialog.queryByText("Old helper")).toBeNull();
    fireEvent.click(dialog.getByText("Assistant"));
    fireEvent.click(screen.getByRole("button", { name: "Save channel" }));
    await waitFor(() => expect(sent.kind).toBe("slack"));
    expect(sent.credentials).toEqual({ botToken: "xoxb-1", signingSecret: "sign-1" });
    expect(sent.defaultAgentId).toBe("a1");
  });

  it("shows the channel error state", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["channels:manage"] }),
      ),
      http.get("*/api/v1/channel-integrations", () => new HttpResponse(null, { status: 500 })),
      http.get("*/api/v1/agents", () => new HttpResponse(null, { status: 500 })),
    );
    render(wrap(<ChannelsScreen />));
    expect(await screen.findByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("lists a profile identity alongside personal usage", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["chat:use"], user: { id: "owner" } }),
      ),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/me/channel-identities", () =>
        HttpResponse.json({
          items: [
            {
              id: "id-1",
              integrationId: "service-1",
              userId: "owner",
              externalUserId: "U-ADMIN",
              matchMethod: "manual_link",
            },
          ],
        }),
      ),
      http.get("*/api/v1/me/usage", () =>
        HttpResponse.json({
          currency: "INR",
          totals: { quantity: 1200, costMicros: 40 },
          quotas: [
            { id: "quota-1", metric: "model_tokens", period: "day", limit: 100000, used: 1200 },
          ],
        }),
      ),
    );
    render(wrap(<ProfileScreen />));
    const links = within(await screen.findByRole("region", { name: messages.profile.linksTitle }));
    expect(await links.findByText("U-ADMIN")).toBeTruthy();
    expect(screen.getByLabelText("Connect code")).toBeTruthy();
    expect(
      await screen.findByRole("progressbar", { name: "Model tokens (Day): 1,200 used of 100,000" }),
    ).toBeTruthy();
  });
  const agentId = "00000000-0000-4000-8000-000000000001";
  function setup(items: object[] = []) {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({
          permissions: ["channels:manage", "agents:read"],
          features: { widget: true },
        }),
      ),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/channel-integrations", () => HttpResponse.json({ items })),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({
          items: [
            { id: "archived", name: "Archived agent", status: "archived", disabled: false },
            { id: "draft", name: "Draft agent", status: "draft", disabled: false },
            { id: "disabled", name: "Disabled agent", status: "published", disabled: true },
            { id: agentId, name: "Workspace assistant", status: "published", disabled: false },
          ],
        }),
      ),
      http.get("*/api/v1/channel-integrations/:id", ({ params }) =>
        HttpResponse.json({ id: params.id, kind: "slack", name: "Saved setup", recentPosts: [] }),
      ),
    );
  }
  const form = () => within(within(screen.getByRole("main")).getByRole("complementary"));
  async function chooseAgent() {
    fireEvent.click(form().getByRole("button", { name: "Default agent: Choose existing" }));
    await within(screen.getByRole("dialog")).findByText("Workspace assistant");
    expect(within(screen.getByRole("dialog")).getAllByRole("listitem")).toHaveLength(1);
    fireEvent.click(within(screen.getByRole("dialog")).getByText("Workspace assistant"));
  }
  it("requires real setup fields and never inserts placeholder identities or secrets", async () => {
    setup();
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/v1/channel-integrations", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(
          { id: "created", kind: "slack", name: "Saved setup" },
          { status: 201 },
        );
      }),
    );
    render(wrap(<ChannelsScreen />));
    await screen.findByText(messages.channels.empty);
    expect(
      (form().getByRole("button", { name: "Save channel" }) as HTMLButtonElement).disabled,
    ).toBe(true);
    await chooseAgent();
    fireEvent.change(form().getByLabelText("Name"), { target: { value: "  Work chat  " } });
    fireEvent.change(form().getByLabelText("Bot token"), {
      target: { value: "user-entered-bot-token" },
    });
    fireEvent.click(form().getByRole("button", { name: "Save channel" }));
    expect(bodies).toHaveLength(0);
    fireEvent.change(form().getByLabelText("Signing secret"), {
      target: { value: "user-entered-signing-secret" },
    });
    fireEvent.click(form().getByRole("button", { name: "Save channel" }));
    await waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toEqual({
      name: "Work chat",
      kind: "slack",
      defaultAgentId: agentId,
      credentials: {
        botToken: "user-entered-bot-token",
        signingSecret: "user-entered-signing-secret",
      },
      config: {},
    });
    expect(screen.queryByRole("button", { name: "Test connection" })).toBeNull();
    expect(screen.queryByLabelText("Routing")).toBeNull();
    expect(screen.getByText(messages.channels.verificationHelp)).toBeTruthy();
  });
  it("clears credentials on a kind change and keeps a failed setup editable", async () => {
    setup();
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/v1/channel-integrations", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ detail: "Save unavailable" }, { status: 503 });
      }),
    );
    render(wrap(<ChannelsScreen />));
    await screen.findByText(messages.channels.empty);
    await chooseAgent();
    fireEvent.change(form().getByLabelText("Name"), { target: { value: "Workspace channel" } });
    fireEvent.change(form().getByLabelText("Bot token"), { target: { value: "old-slack-secret" } });
    fireEvent.change(form().getByRole("combobox", { name: "Kind" }), {
      target: { value: "teams" },
    });
    fireEvent.change(form().getByLabelText("Application ID"), {
      target: { value: "customer-application-id" },
    });
    fireEvent.change(form().getByLabelText("Application secret"), {
      target: { value: "customer-application-secret" },
    });
    fireEvent.click(form().getByRole("button", { name: "Save channel" }));
    await form().findByText("Save unavailable");
    expect(bodies).toEqual([
      {
        name: "Workspace channel",
        kind: "teams",
        defaultAgentId: agentId,
        credentials: {
          appId: "customer-application-id",
          appPassword: "customer-application-secret",
        },
        config: {},
      },
    ]);
    expect((form().getByLabelText("Application secret") as HTMLInputElement).value).toBe(
      "customer-application-secret",
    );
    fireEvent.change(form().getByRole("combobox", { name: "Kind" }), {
      target: { value: "slack" },
    });
    expect((form().getByLabelText("Bot token") as HTMLInputElement).value).toBe("");
    expect((form().getByLabelText("Signing secret") as HTMLInputElement).value).toBe("");
  });
  it("captures mailbox server fields as entered and validates integer ports", async () => {
    setup();
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/v1/channel-integrations", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ detail: "Save unavailable" }, { status: 503 });
      }),
    );
    render(wrap(<ChannelsScreen />));
    await screen.findByText(messages.channels.empty);
    await chooseAgent();
    fireEvent.change(form().getByLabelText("Name"), { target: { value: "Mailbox" } });
    fireEvent.change(form().getByRole("combobox", { name: "Kind" }), {
      target: { value: "email" },
    });
    for (const [label, value] of [
      ["Mailbox email address", "agent@workspace.invalid"],
      ["Mailbox username", "mail-user"],
      ["Mailbox password", "mail-password"],
      ["IMAP server", "imap.workspace.invalid"],
      ["IMAP port", "993.5"],
      ["SMTP server", "smtp.workspace.invalid"],
      ["SMTP port", "465"],
    ])
      fireEvent.change(form().getByLabelText(label as string), { target: { value } });
    expect((form().getByLabelText("IMAP port") as HTMLInputElement).checkValidity()).toBe(false);
    const input = form().getByLabelText("Name") as HTMLInputElement;
    const element = input.closest("form");
    if (!element) throw new Error("Missing channel form");
    fireEvent.submit(element);
    expect(bodies).toHaveLength(0);
    fireEvent.change(form().getByLabelText("IMAP port"), { target: { value: "993" } });
    fireEvent.click(form().getByRole("button", { name: "Save channel" }));
    await form().findByText("Save unavailable");
    expect(bodies[0]).toMatchObject({
      credentials: {
        address: "agent@workspace.invalid",
        username: "mail-user",
        password: "mail-password",
        imapHost: "imap.workspace.invalid",
        imapPort: 993,
        smtpHost: "smtp.workspace.invalid",
        smtpPort: 465,
      },
    });
  });
  it("validates exact widget origins without reusing credentials from another kind", async () => {
    setup();
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/v1/channel-integrations", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ detail: "Save unavailable" }, { status: 503 });
      }),
    );
    render(wrap(<ChannelsScreen />));
    await screen.findByText(messages.channels.empty);
    await chooseAgent();
    fireEvent.change(form().getByLabelText("Name"), { target: { value: "Embedded chat" } });
    fireEvent.change(form().getByRole("combobox", { name: "Kind" }), {
      target: { value: "widget" },
    });
    fireEvent.change(form().getByLabelText("Host signing secret"), {
      target: { value: "host-signing-value" },
    });
    fireEvent.change(form().getByLabelText("Allowed portal origins"), {
      target: { value: "https://workspace.invalid/path" },
    });
    fireEvent.click(form().getByRole("button", { name: "Save channel" }));
    expect(form().getByText(messages.channels.invalidOrigins)).toBeTruthy();
    expect(bodies).toHaveLength(0);
    fireEvent.change(form().getByLabelText("Allowed portal origins"), {
      target: { value: "https://workspace.invalid https://workspace.invalid" },
    });
    fireEvent.click(form().getByRole("button", { name: "Save channel" }));
    await form().findByText("Save unavailable");
    expect(bodies[0]).toMatchObject({
      credentials: { widgetSecret: "host-signing-value" },
      config: { allowedOrigins: ["https://workspace.invalid"] },
    });
  });
  it("bounds the catalogue and filters before paging without a full-list post selector", async () => {
    setup(
      Array.from({ length: 30 }, (_, i) => ({
        id: `channel-${i}`,
        kind: i % 2 ? "email" : "slack",
        name: `Setup ${i}`,
        status: i % 3 ? "active" : "disabled",
      })),
    );
    render(wrap(<ChannelsScreen />));
    await screen.findByRole("heading", { name: "Setup 0" });
    expect(within(screen.getByRole("main")).getAllByRole("listitem")).toHaveLength(25);
    expect(screen.queryByRole("heading", { name: "Setup 29" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "Setup 29" })).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.channels.search }), {
      target: { value: "channel-29" },
    });
    expect(screen.getByText("1–1 of 1")).toBeTruthy();
    const filters = within(screen.getByRole("group", { name: "Channel filters" }));
    fireEvent.change(filters.getByRole("combobox", { name: "Kind" }), {
      target: { value: "slack" },
    });
    expect(screen.getByText(messages.channels.noMatches)).toBeTruthy();
    expect(screen.queryByLabelText("Show posts from")).toBeNull();
  });
  it("isolates detail errors from the list and retries the selected setup", async () => {
    setup([{ id: "one", kind: "slack", name: "Saved channel" }]);
    let reads = 0;
    server.use(
      http.get("*/api/v1/channel-integrations/one", () =>
        ++reads === 1
          ? HttpResponse.json({ detail: "Details unavailable" }, { status: 503 })
          : HttpResponse.json({ id: "one", kind: "slack", name: "Saved channel", recentPosts: [] }),
      ),
    );
    render(wrap(<ChannelsScreen />));
    await screen.findByText("Details unavailable");
    expect(screen.getByRole("heading", { name: "Saved channel" })).toBeTruthy();
    expect(screen.queryByText(messages.channels.noPosts)).toBeNull();
    const details = within(screen.getByRole("region", { name: "Channel setup details" }));
    fireEvent.click(details.getByRole("button", { name: "Try again" }));
    await details.findByText(messages.channels.noPosts);
  });
  it("edits only name and agent, preserves existing secrets/configuration and restores focus", async () => {
    setup([
      {
        id: "one",
        kind: "slack",
        name: "Saved channel",
        defaultAgent: {
          id: agentId,
          name: "Workspace assistant",
          status: "published",
          disabled: false,
        },
      },
    ]);
    const bodies: unknown[] = [];
    server.use(
      http.patch("*/api/v1/channel-integrations/one", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ detail: "Update unavailable" }, { status: 503 });
      }),
    );
    render(wrap(<ChannelsScreen />));
    const button = await screen.findByRole("button", { name: "Edit Saved channel" });
    fireEvent.click(button);
    expect(document.activeElement).toBe(form().getByLabelText("Name"));
    expect(form().queryByLabelText("Bot token")).toBeNull();
    fireEvent.click(form().getByRole("button", { name: "Cancel" }));
    expect(document.activeElement).toBe(button);
    fireEvent.click(button);
    fireEvent.change(form().getByLabelText("Name"), { target: { value: "Renamed channel" } });
    fireEvent.click(form().getByRole("button", { name: "Save changes" }));
    await form().findByText("Update unavailable");
    expect(bodies).toEqual([{ name: "Renamed channel", defaultAgentId: agentId }]);
    expect(screen.getByRole("heading", { name: "Saved channel" })).toBeTruthy();
  });
  it("does not request integrations or offer credentials without permission", async () => {
    let reads = 0;
    server.use(
      http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["chat:use"] })),
      http.get("*/api/v1/channel-integrations", () => {
        reads++;
        return HttpResponse.json({ items: [] });
      }),
    );
    render(wrap(<ChannelsScreen />));
    await screen.findByText(messages.channels.denied);
    expect(reads).toBe(0);
    expect(screen.queryByLabelText("Bot token")).toBeNull();
  });
  it("replaces credentials only with an explicit complete set", async () => {
    setup([
      {
        id: "one",
        kind: "slack",
        name: "Saved channel",
        defaultAgent: {
          id: agentId,
          name: "Workspace assistant",
          status: "published",
          disabled: false,
        },
      },
    ]);
    const bodies: unknown[] = [];
    server.use(
      http.patch("*/api/v1/channel-integrations/one", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ detail: "Update unavailable" }, { status: 503 });
      }),
    );
    render(wrap(<ChannelsScreen />));
    fireEvent.click(await screen.findByRole("button", { name: "Edit Saved channel" }));
    fireEvent.click(form().getByRole("checkbox", { name: "Replace saved credentials" }));
    fireEvent.change(form().getByLabelText("Bot token"), {
      target: { value: "replacement-bot-token" },
    });
    fireEvent.click(form().getByRole("button", { name: "Save changes" }));
    expect(bodies).toHaveLength(0);
    fireEvent.change(form().getByLabelText("Signing secret"), {
      target: { value: "replacement-signing-secret" },
    });
    fireEvent.change(form().getByLabelText("App-level token · Optional"), {
      target: { value: "replacement-app-token" },
    });
    fireEvent.click(form().getByRole("button", { name: "Save changes" }));
    await form().findByText("Update unavailable");
    expect(bodies[0]).toEqual({
      name: "Saved channel",
      defaultAgentId: agentId,
      credentials: {
        botToken: "replacement-bot-token",
        signingSecret: "replacement-signing-secret",
        appToken: "replacement-app-token",
      },
    });
  });
  it("does not show an earlier setup's posts after a late detail response", async () => {
    setup([
      { id: "one", kind: "slack", name: "First setup" },
      { id: "two", kind: "email", name: "Second setup" },
    ]);
    let release: () => void = () => undefined;
    let started: () => void = () => undefined;
    const waiting = new Promise<void>((resolve) => {
      release = resolve;
    });
    const requested = new Promise<void>((resolve) => {
      started = resolve;
    });
    server.use(
      http.get("*/api/v1/channel-integrations/one", async () => {
        started();
        await waiting;
        return HttpResponse.json({
          id: "one",
          kind: "slack",
          name: "First setup",
          recentPosts: [{ id: "old", body: "Earlier setup post" }],
        });
      }),
      http.get("*/api/v1/channel-integrations/two", () =>
        HttpResponse.json({
          id: "two",
          kind: "email",
          name: "Second setup",
          recentPosts: [{ id: "new", body: "Current setup post" }],
        }),
      ),
    );
    render(wrap(<ChannelsScreen />));
    await requested;
    const row = screen.getByRole("heading", { name: "Second setup" }).closest("li");
    if (!row) throw new Error("Missing channel row");
    const viewButton = within(row).getByRole("button", { name: "View activity and setup" });
    fireEvent.click(viewButton);
    await screen.findByText("Current setup post");
    release();
    await waitFor(() => expect(screen.queryByText("Earlier setup post")).toBeNull());
    expect(document.activeElement).toBe(
      screen.getByRole("heading", { name: "Setup · Second setup" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Back to channel list" }));
    expect(document.activeElement).toBe(viewButton);
  });
  it("opens a newly saved widget's real metadata and installation output", async () => {
    setup();
    const saved = {
      id: "widget-id",
      kind: "widget",
      name: "Portal chat",
      config: { allowedOrigins: ["https://workspace.invalid"] },
      recentPosts: [],
    };
    let created = false;
    server.use(
      http.post("*/api/v1/channel-integrations", () => {
        created = true;
        return HttpResponse.json(saved, { status: 201 });
      }),
      http.get("*/api/v1/channel-integrations", () =>
        HttpResponse.json({ items: created ? [saved] : [] }),
      ),
      http.get("*/api/v1/channel-integrations/widget-id", () => HttpResponse.json(saved)),
    );
    render(wrap(<ChannelsScreen />));
    await screen.findByText(messages.channels.empty);
    await chooseAgent();
    fireEvent.change(form().getByLabelText("Name"), { target: { value: "Portal chat" } });
    fireEvent.change(form().getByRole("combobox", { name: "Kind" }), {
      target: { value: "widget" },
    });
    fireEvent.change(form().getByLabelText("Host signing secret"), {
      target: { value: "host-signing-value" },
    });
    fireEvent.change(form().getByLabelText("Allowed portal origins"), {
      target: { value: "https://workspace.invalid" },
    });
    fireEvent.click(form().getByRole("button", { name: "Save channel" }));
    expect(await screen.findByRole("heading", { name: "Setup · Portal chat" })).toBeTruthy();
    expect(await screen.findByText(/data-integration="widget-id"/)).toBeTruthy();
    expect((screen.getByLabelText("Saved portal origins") as HTMLTextAreaElement).value).toBe(
      "https://workspace.invalid",
    );
    expect((form().getByLabelText("Bot token") as HTMLInputElement).value).toBe("");
  });
});
