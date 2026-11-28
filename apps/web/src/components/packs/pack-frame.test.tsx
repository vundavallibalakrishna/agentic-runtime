import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";

import { PackFrame } from "@/components/packs/pack-frame";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));

function view(packId = "selected-pack") {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      <PackFrame packId={packId} />
    </NextIntlClientProvider>
  );
}

describe("pack details", () => {
  it("shows confirmed identity and enablement without asserting tool access", async () => {
    server.use(
      http.get("*/api/v1/tenant/packs", () =>
        HttpResponse.json({
          items: [
            {
              packId: "selected-pack",
              enabled: true,
              version: "2.4.1",
              nav: [{ label: "Operations" }],
            },
          ],
        }),
      ),
    );
    render(view());
    expect(await screen.findByRole("heading", { name: "Operations" })).toBeTruthy();
    expect(screen.getByText("2.4.1")).toBeTruthy();
    expect(screen.getByText("Enabled")).toBeTruthy();
    expect(screen.getByText(messages.packs.accessHelp)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to chat" }).getAttribute("href")).toBe("/chat");
    expect(screen.queryByText(/tools are available/)).toBeNull();
  });

  it("distinguishes a missing pack from a disabled installed pack", async () => {
    server.use(http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })));
    const { rerender } = render(view());
    expect(await screen.findByText(messages.packs.missing)).toBeTruthy();
    expect(screen.queryByText("Disabled")).toBeNull();
    server.use(
      http.get("*/api/v1/tenant/packs", () =>
        HttpResponse.json({ items: [{ packId: "other-pack", enabled: false }] }),
      ),
    );
    rerender(view("other-pack"));
    expect(await screen.findByText("Disabled")).toBeTruthy();
    expect(screen.getByText(messages.packs.disabledHelp)).toBeTruthy();
    expect(screen.queryByText(messages.packs.missing)).toBeNull();
  });

  it("allows retry after failure without showing disabled or stale pack details", async () => {
    server.use(
      http.get("*/api/v1/tenant/packs", () =>
        HttpResponse.json({ detail: "Service unavailable" }, { status: 503 }),
      ),
    );
    render(view());
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText("Disabled")).toBeNull();
    server.use(http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })));
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(messages.packs.missing)).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("does not retain a previous pack while the new identity loads", async () => {
    let finish: (() => void) | undefined;
    server.use(
      http.get("*/api/v1/tenant/packs", async () => {
        await new Promise<void>((resolve) => {
          finish = resolve;
        });
        return HttpResponse.json({
          items: [{ packId: "selected-pack", enabled: true, nav: [{ label: "Previous pack" }] }],
        });
      }),
    );
    const { rerender } = render(view());
    await waitFor(() => expect(finish).toBeTruthy());
    const finishOld = finish;
    server.use(http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })));
    rerender(view("next-pack"));
    expect(await screen.findByText(messages.packs.missing)).toBeTruthy();
    finishOld?.();
    await waitFor(() => expect(screen.queryByText("Previous pack")).toBeNull());
  });
});
