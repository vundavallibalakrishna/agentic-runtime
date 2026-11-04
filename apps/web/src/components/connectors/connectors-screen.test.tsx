import { cleanup, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConnectorsScreen } from "@/components/connectors/connectors-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/connectors",
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

describe("connector catalog", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows a not-live-tested badge and an empty search", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["tools:read", "connections:manage_own"] }),
      ),
      http.get("*/api/v1/connectors", () =>
        HttpResponse.json({
          items: [
            {
              slug: "notion",
              name: "Notion",
              category: "Work",
              summary: "Search pages",
              verification: "not_live",
              verificationNote: "No workspace was connected.",
              installed: false,
            },
          ],
        }),
      ),
    );
    render(wrap(<ConnectorsScreen />));
    expect(await screen.findByText("Not live-tested")).toBeTruthy();
    expect(screen.getByText("No workspace was connected.")).toBeTruthy();
  });
});
