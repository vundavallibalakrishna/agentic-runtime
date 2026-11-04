import { cleanup, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SchedulesScreen } from "@/components/schedules/schedules-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/schedules",
  useParams: () => ({}),
  useRouter: () => ({ push: () => undefined }),
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("schedules", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows an empty state", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["routines:create", "chat:use"] }),
      ),
      http.get("*/api/v1/routines", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<SchedulesScreen />));
    expect(await screen.findByRole("heading", { name: "Schedules" })).toBeTruthy();
    expect(
      await screen.findByText(
        "No schedules yet. Create one to run an agent on a clock or from a webhook.",
      ),
    ).toBeTruthy();
  });
});
