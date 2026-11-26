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
        HttpResponse.json({ permissions: ["channels:manage"], user: { displayName: "Admin" } }),
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
