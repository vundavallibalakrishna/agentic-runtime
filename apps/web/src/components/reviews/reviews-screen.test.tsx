import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ReviewsScreen } from "@/components/reviews/reviews-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/reviews",
  useParams: () => ({}),
  useRouter: () => ({ push: () => undefined }),
}));
function show() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ReviewsScreen />
    </NextIntlClientProvider>,
  );
}
beforeEach(() => {
  server.use(
    http.get("*/api/v1/auth/session", () => HttpResponse.json({ permissions: ["reviews:read"] })),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
  );
});

describe("review list", () => {
  it("identifies rows and searches before paging, with server-backed scope views", async () => {
    const scopes: string[] = [];
    server.use(
      http.get("*/api/v1/review-items", ({ request }) => {
        const scope = new URL(request.url).searchParams.get("scope") ?? "";
        scopes.push(scope);
        return HttpResponse.json({
          items:
            scope === "all"
              ? [{ id: "historic-12345678", subjectType: "file", status: "signed" }]
              : Array.from({ length: 30 }, (_, i) => ({
                  id: `review-${i.toString().padStart(8, "0")}`,
                  subjectId: `subject-${i}`,
                  subjectType: "saved_query",
                  status: i === 29 ? "in_review" : "pending",
                  createdAt: "2026-11-21T09:00:00Z",
                })),
        });
      }),
    );
    show();
    await screen.findByRole("link", { name: "saved query · Reference 00000000" });
    expect(screen.queryByRole("link", { name: "saved query · Reference 00000029" })).toBeNull();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.reviews.search }), {
      target: { value: "subject-29" },
    });
    expect(
      screen.getByRole("link", { name: "saved query · Reference 00000029" }).getAttribute("href"),
    ).toBe("/reviews/review-00000029");
    fireEvent.change(screen.getByRole("searchbox", { name: messages.reviews.search }), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "in_review" } });
    expect(screen.getByRole("link", { name: "saved query · Reference 00000029" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "saved query · Reference 00000000" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Show reviews"), { target: { value: "all" } });
    expect(await screen.findByRole("link", { name: "file · Reference 12345678" })).toBeTruthy();
    expect(scopes).toEqual(["to_decide", "all"]);
  });

  it("retries failed loads and distinguishes a filtered empty view", async () => {
    let attempts = 0;
    server.use(
      http.get("*/api/v1/review-items", () =>
        ++attempts === 1
          ? HttpResponse.json({ detail: "Service unavailable" }, { status: 503 })
          : HttpResponse.json({ items: [] }),
      ),
    );
    show();
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText(messages.reviews.empty)).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: messages.reviews.search }), {
      target: { value: "missing" },
    });
    expect(screen.getByText(messages.reviews.noMatches)).toBeTruthy();
    await waitFor(() => expect(attempts).toBe(2));
  });
});
