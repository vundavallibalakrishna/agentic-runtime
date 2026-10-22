import { cleanup, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChannelsScreen } from "@/components/channels/channels-screen";
import { ProfileScreen } from "@/components/channels/profile-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
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
