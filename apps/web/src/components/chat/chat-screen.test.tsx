import { cleanup, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

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
  afterEach(() => {
    cleanup();
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
  });
});
