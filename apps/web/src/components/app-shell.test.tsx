import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/app-shell";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const navigation = vi.hoisted(() => ({
  replace: vi.fn(),
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/chat",
  useRouter: () => navigation,
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

const signedIn = () =>
  HttpResponse.json({
    permissions: ["chat:use"],
    user: { displayName: "Ada Lovelace", email: "ada@acme.example" },
    tenant: { name: "Acme" },
  });

describe("AppShell", () => {
  afterEach(() => {
    cleanup();
    navigation.replace.mockClear();
  });

  it("renders the product name, the navigation and the page for a signed-in person", async () => {
    server.use(
      http.get("*/api/v1/auth/session", signedIn),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<AppShell>Hello</AppShell>));
    expect(screen.getByText("Agentic Runtime")).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeTruthy();
    expect(screen.getByText("Hello")).toBeTruthy();
    expect(await screen.findByText("Acme")).toBeTruthy();
    expect(screen.getByText("Hello")).toBeTruthy();
  });

  it("sends a visitor who is not signed in to the sign-in page", async () => {
    server.use(http.get("*/api/v1/auth/session", () => HttpResponse.json({}, { status: 401 })));
    render(wrap(<AppShell>Hello</AppShell>));
    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("replaces the page with an error and a retry when the session check fails", async () => {
    let answers = 0;
    server.use(
      http.get("*/api/v1/auth/session", () => {
        answers += 1;
        return answers === 1 ? HttpResponse.json({}, { status: 500 }) : signedIn();
      }),
      http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<AppShell>Hello</AppShell>));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "We could not check your sign-in",
    );
    expect(screen.getByRole("heading", { name: "We could not check your sign-in" })).toBeTruthy();
    // A failed check is not a sign-in: the page is gone, and nobody is sent anywhere.
    expect(screen.queryByText("Hello")).toBeNull();
    expect(navigation.replace).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Sign in again" }).getAttribute("href")).toBe("/login");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Hello")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
