import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { AppShell } from "@/components/app-shell";
import messages from "@/messages/en.json";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("AppShell", () => {
  it("renders the product name and primary navigation", () => {
    render(wrap(<AppShell>Hello</AppShell>));
    expect(screen.getByText("Agentic Runtime")).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Primary" })).toBeTruthy();
    expect(screen.getByText("Hello")).toBeTruthy();
  });
});
