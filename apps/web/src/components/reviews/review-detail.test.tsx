import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";

import { ReviewDetail } from "@/components/reviews/review-detail";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/reviews",
  useRouter: () => ({ push: () => undefined, replace: () => undefined }),
}));

describe("review detail", () => {
  it("shows the query a saved-query item asks the signer to approve", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ user: { id: "user-1" }, permissions: ["reviews:decide"] }),
      ),
      http.get("*/api/v1/review-items/item-1", () =>
        HttpResponse.json({
          id: "item-1",
          subjectType: "saved_query",
          status: "pending",
          statementText: "I reviewed saved query Open items version 2.",
          contentHash: "abc",
          statementHash: "def",
          subjectRef: {
            name: "Open items",
            version: 2,
            description: "Items still open at the period end",
            sql: "SELECT * FROM items WHERE status = 'open'",
          },
        }),
      ),
    );
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <ReviewDetail reviewId="item-1" />
      </NextIntlClientProvider>,
    );
    expect(await screen.findByText("SELECT * FROM items WHERE status = 'open'")).toBeTruthy();
    expect(screen.getByText("Open items, version 2")).toBeTruthy();
    expect(screen.getByText("Items still open at the period end")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sign" })).toBeTruthy();
  });
});
