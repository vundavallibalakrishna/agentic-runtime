import { cleanup, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EvalsScreen } from "@/components/evals/evals-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/evals",
  useRouter: () => ({ push: () => undefined }),
  useParams: () => ({ id: "agent" }),
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("evaluation screen", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows an empty library and the feedback inbox", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["evals:manage"], user: { displayName: "Admin" } }),
      ),
      http.get("*/api/v1/eval-suites", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/feedback", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<EvalsScreen admin />));
    expect(await screen.findByRole("heading", { name: "Evaluation library" })).toBeTruthy();
    expect(await screen.findByText("No suites yet. Create one to start.")).toBeTruthy();
    expect(await screen.findByText("No feedback yet.")).toBeTruthy();
  });
});
