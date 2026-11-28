import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SettingsScreen } from "@/components/settings-screen";
import messages from "@/messages/en.json";

vi.mock("@/components/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => children,
  useShellNav: () => ({
    items: [
      { href: "/tools", labelKey: "navTools", section: "build", icon: () => null },
      { href: "/admin/models", labelKey: "navModels", section: "admin", icon: () => null },
    ],
    packLinks: [{ href: "/pack", label: "Evidence vault" }],
    ready: true,
  }),
}));

describe("SettingsScreen", () => {
  afterEach(cleanup);

  it("finds settings by their descriptions and filters pack links", () => {
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <SettingsScreen />
      </NextIntlClientProvider>,
    );

    const finder = screen.getByRole("searchbox", { name: "Find a setting or task" });
    fireEvent.change(finder, { target: { value: "model" } });

    expect(screen.getByRole("link", { name: /Models/ })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Tools/ })).toBeNull();
    expect(screen.queryByRole("link", { name: /Evidence vault/ })).toBeNull();

    fireEvent.change(finder, { target: { value: "vault" } });
    expect(screen.getByRole("link", { name: /Evidence vault/ })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Models/ })).toBeNull();
  });
});
